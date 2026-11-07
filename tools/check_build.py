"""Verify a build from pristine local copies of Devin Desktop and the Microsoft language pack."""

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from devin_zh import Installation, ROOT, atomic, digest
from src.resources import pretty


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--extensions", required=True, type=Path)
    parser.add_argument("--update-hashes", action="store_true", help="Update localized hashes in the repository after editing translations")
    args = parser.parse_args()
    args.user_data = None
    install = Installation(args)
    sources = {}
    for row in install.entries:
        path = install.path(row)
        if digest(path) != row["original"]:
            raise ValueError("需要指定未修改的原版文件：" + row["path"])
        sources[row["path"]] = path if row["original"] else None
    changes = []
    for row, payload in install.generated_files(sources):
        value = hashlib.sha256(payload).hexdigest()
        if value != row["localized"]:
            changes.append(row["path"])
            row["localized"] = value
    if changes and not args.update_hashes:
        raise ValueError("输出与发布清单不同：" + ", ".join(changes))
    if changes:
        atomic(ROOT / "manifest.json", pretty(install.release))
    print(f"已从原版重建并校验 {len(sources)} 个文件。更新了 {len(changes)} 个哈希。")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        sys.exit(str(exc))
