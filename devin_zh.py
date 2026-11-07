"""Install or restore the optional Simplified Chinese locale for Devin Desktop on Windows."""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from src.resources import apply_splices, build_editor, build_extension, build_product, embedded_catalog, pretty, read_json


ROOT = Path(__file__).resolve().parent


def digest(path):
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def under(root, relative):
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()) or result == root.resolve():
        raise ValueError("资源路径超出指定目录：" + str(relative))
    return result


def atomic(path, value):
    if value is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".devin-zh-", dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
    try:
        if isinstance(value, Path):
            shutil.copyfile(value, tmp)
        else:
            tmp.write_bytes(value)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def lock(directory):
    import msvcrt
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "install.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"1")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("另一个汉化安装或恢复操作正在运行。") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class Installation:
    def __init__(self, args):
        self.release = read_json(ROOT / "manifest.json")
        local = Path(os.environ["LOCALAPPDATA"])
        self.app = (args.app or local / "Programs/Devin/resources/app").resolve()
        self.data = (args.user_data or Path(os.environ["APPDATA"]) / "Devin").resolve()
        self.extensions = (args.extensions or Path.home() / ".devin/extensions").resolve()
        self.product = read_json(self.app / "product.json")
        if self.product.get("commit") != self.release["commit"]:
            raise ValueError("此包适配 Devin Desktop " + self.release["appVersion"] + "，当前构建与发布清单不符。")
        self.entries = self.release["files"]
        self.rows = {row["path"]: row for row in self.entries}
        key = os.path.normcase(str(self.app) + "|" + str(self.extensions))
        scope = hashlib.sha256(key.encode()).hexdigest()[:16]
        self.backups = local / "devin-desktop-zh-cn/backups" / scope / self.release["commit"]
        self.legacy = local / "Devin-zh-CN" / self.release["appVersion"]
        self.legacy_rows = {}
        old_manifest = self.legacy / "manifest.json"
        if old_manifest.is_file():
            old = read_json(old_manifest)
            if old.get("build") == self.release["commit"]:
                self.legacy_rows = {row["rel"]: row for row in old.get("files", [])}
        self.pack = next(row for row in self.entries if row["type"] == "editor")
        self.pack_path = self.path(self.pack)
        self.registry_file = self.data / "languagepacks.json"
        self.cli = self.app.parent.parent / "bin/devin-desktop.cmd"

    def path(self, row):
        return under(self.extensions if row["type"] == "editor" else self.app, row["path"])

    def states(self):
        return {row["path"]: digest(self.path(row)) for row in self.entries}

    def ensure_pack(self, action):
        registry = read_json(self.registry_file) if self.registry_file.is_file() else {}
        existing = registry.get("zh-cn", {})
        registered = existing.get("translations", {}).get("vscode")
        if registered and Path(registered).resolve() != self.pack_path:
            raise ValueError("已启用其他版本的简体中文扩展。请使用匹配的语言包 " + self.release["packVersion"] + "。")
        if not self.pack_path.is_file() and action == "apply":
            if not self.cli.is_file():
                raise FileNotFoundError("未找到 Devin 的扩展安装命令：" + str(self.cli))
            installed_index = self.extensions / "extensions.json"
            if installed_index.is_file():
                for ext in read_json(installed_index):
                    if ext.get("identifier", {}).get("id", "").lower() == self.release["packId"] and ext.get("version") != self.release["packVersion"]:
                        raise ValueError("已安装其他版本的微软简体中文扩展。请检查扩展版本。")
            exact = self.release["packId"] + "@" + self.release["packVersion"]
            print("正在使用 Devin 的扩展安装器安装 " + exact, flush=True)
            subprocess.run([str(self.cli), "--user-data-dir", str(self.data), "--extensions-dir", str(self.extensions),
                            "--install-extension", exact], check=True)
            if not self.pack_path.is_file():
                raise FileNotFoundError("扩展安装后仍未找到 " + str(self.pack_path))
            registry = read_json(self.registry_file) if self.registry_file.is_file() else {}
            existing = registry.get("zh-cn", {})
        return registry, existing

    def make_registration(self, registry, existing):
        if existing:
            if Path(existing["translations"]["vscode"]).resolve() != self.pack_path:
                raise ValueError("当前简体中文扩展的位置与发布清单不符。")
            return None
        pack_root = self.pack_path.parent.parent
        info = read_json(pack_root / "package.json")
        if (info["publisher"] + "." + info["name"]).lower() != self.release["packId"] or info["version"] != self.release["packVersion"]:
            raise ValueError("微软简体中文扩展版本不符。")
        loc = next(x for x in info["contributes"]["localizations"] if x["languageId"].lower() == "zh-cn")
        paths = {x["id"]: str(under(pack_root, x["path"])) for x in loc["translations"]}
        if Path(paths["vscode"]).resolve() != self.pack_path:
            raise ValueError("扩展声明的主词典与发布清单不符。")
        registry["zh-cn"] = {"hash": self.release["packHash"], "translations": paths, "extensions": [{
            "extensionIdentifier": {"id": self.release["packId"], "uuid": self.release["packUUID"]},
            "version": self.release["packVersion"]
        }]}
        return pretty(registry)

    def source(self, row, current):
        signature = row["original"]
        if signature is None:
            return None
        backup = self.backups / "original" / signature
        if backup.exists() and digest(backup) != signature:
            raise ValueError("原版备份校验失败：" + row["path"])
        if not backup.is_file():
            src = self.path(row)
            if current != signature:
                legacy = self.legacy_rows.get(row["path"], {})
                if legacy.get("original") != signature:
                    raise ValueError("缺少可验证的原版备份：" + row["path"])
                src = under(self.legacy / "original", legacy["name"])
            if digest(src) != signature:
                raise ValueError("原版文件校验失败：" + row["path"])
            atomic(backup, src)
            if digest(backup) != signature:
                raise ValueError("创建原版备份失败：" + row["path"])
        return backup

    def generated_files(self, sources):
        host = sources[self.release["host"]].read_bytes().decode("utf-8")
        catalog = embedded_catalog(ROOT, host)
        fields = read_json(ROOT / "locales/extensions.zh-CN.json")
        builtins = {}
        for extension, data in fields.items():
            rel = "extensions/" + extension + "/"
            stock = sources[rel + "package.json"].read_bytes()
            builtins.update({rel + name: contents for name, contents in build_extension(stock, data).items()})
        hashes = {}
        for row in self.entries:
            rel = row["path"]
            if row["type"] == "product":
                continue
            if row["type"] == "extension":
                result = builtins[rel]
            elif row["type"] == "editor":
                result = build_editor(sources[rel].read_bytes(), read_json(ROOT / "locales/editor.zh-CN.json"))
            else:
                edits = read_json(under(ROOT, row["patch"]))
                result = apply_splices(sources[rel].read_bytes().decode("utf-8"), edits, catalog)
            hashes[rel] = hashlib.sha256(result).hexdigest()
            yield row, result
        product = self.rows["product.json"]
        yield product, build_product(sources[product["path"]].read_bytes(), hashes)

    def cache_paths(self, existing):
        # Devin regenerates both files on the next Chinese-language startup.
        hash_id = existing.get("hash", self.release["packHash"])
        nls = self.product.get("nlsMetadataHash", "")
        if not (len(hash_id) == 32 and len(nls) == 64 and all(c in "0123456789abcdef" for c in hash_id+nls)):
            raise ValueError("无法识别当前语言缓存。")
        return [under(self.data, "clp/" + hash_id + ".zh-cn/" + nls + "/nls.messages.json"),
                under(self.data, "CachedProfilesData/__default__profile__/extensions.builtin.zh-cn.cache")]

    def change(self, action):
        # Check app files before invoking an extension install or touching the application.
        states = self.states()
        for row in self.entries:
            current = states[row["path"]]
            if current not in (row["original"], row["localized"]) and not (row["type"] == "editor" and current is None):
                raise ValueError("发现与原版及本发布包都不匹配的文件：" + row["path"])
        registry, existing = self.ensure_pack(action)
        states[self.pack["path"]] = digest(self.pack_path)
        if states[self.pack["path"]] not in (self.pack["original"], self.pack["localized"], None):
            raise ValueError("已安装扩展的词典与发布校验不符。")
        applying = action == "apply"
        update_registry = self.make_registration(registry, existing) if applying else None
        cache_paths = self.cache_paths(existing)
        sources = {}
        for row in self.entries:
            if not applying and row["type"] == "editor" and states[row["path"]] is None:
                continue
            sources[row["path"]] = self.source(row, states[row["path"]])
        with tempfile.TemporaryDirectory(dir=self.backups, prefix="txn-") as temp:
            temp = Path(temp)
            ready = {}
            if applying:
                for row, data in self.generated_files(sources):
                    if hashlib.sha256(data).hexdigest() != row["localized"]:
                        raise ValueError("生成的汉化文件未通过发布校验：" + row["path"])
                    if states[row["path"]] != row["localized"]:
                        stage = temp / ("new-" + row["localized"])
                        stage.write_bytes(data)
                        ready[row["path"]] = stage
            else:
                for row in self.entries:
                    rel = row["path"]
                    if rel in sources and states[rel] != row["original"]:
                        ready[rel] = sources[rel]
            undo = []
            def replace(target, contents):
                saved = None
                if target.exists():
                    saved = temp / ("undo-" + str(len(undo)))
                    shutil.copyfile(target, saved)
                atomic(target, contents)
                undo.append((target, saved))
            try:
                for rel, stage in ready.items():
                    target = self.path(self.rows[rel])
                    if digest(target) != states[rel]:
                        raise RuntimeError("安装期间文件被其他进程修改：" + rel)
                    replace(target, stage)
                    want = self.rows[rel]["localized" if applying else "original"]
                    if digest(target) != want:
                        raise RuntimeError("写入后校验失败：" + rel)
                if update_registry is not None:
                    fresh = read_json(self.registry_file) if self.registry_file.is_file() else {}
                    merged = self.make_registration(fresh, fresh.get("zh-cn", {}))
                    if merged is not None:
                        replace(self.registry_file, merged)
                for cache in cache_paths:
                    if cache.is_file():
                        replace(cache, None)
            except BaseException:
                for target, previous in reversed(undo):
                    atomic(target, previous)
                raise
        print(("已安装简体中文" if applying else "已恢复原版资源") + "。本次更新 " + str(len(ready)) + " 个文件。")

    def status(self):
        states = self.states()
        results = Counter()
        for row in self.entries:
            current = states[row["path"]]
            if current == row["localized"]:
                results["已汉化"] += 1
            elif current == row["original"] or row["type"] == "editor" and current is None:
                results["原版或未安装"] += 1
            else:
                results["外部修改"] += 1
                print("外部修改：" + row["path"])
        print("Devin Desktop " + self.release["appVersion"] + "  " +
              "，".join(f"{key} {value}" for key, value in results.items()))
        return 1 if results["外部修改"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["apply", "status", "restore"])
    parser.add_argument("--app", type=Path, help="Devin resources/app directory")
    parser.add_argument("--user-data", type=Path, help="Devin user data directory")
    parser.add_argument("--extensions", type=Path, help="Devin extensions directory")
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("当前发布包适用于 Windows。")
    installation = Installation(args)
    if args.action == "status":
        return installation.status()
    with lock(installation.backups):
        installation.change(args.action)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print("Devin 汉化：" + str(exc), file=sys.stderr)
        sys.exit(1)
