"""Reconstruct Simplified Chinese resources from the supported, original Devin build."""

import base64
import json
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_bytes())


def pretty(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def js_json(obj):
    return compact(obj).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def set_leaf(obj, parts, value):
    node = obj
    for key in parts[:-1]:
        node = node[key]
    node[parts[-1]] = value


def embedded_catalog(repository, stock_host):
    """Fill the unchanged English cells from the original host's own string data."""
    table = read_json(repository / "locales/agent.zh-CN.json")
    for parts, start, size, encoding in read_json(repository / "locales/inherit.json"):
        text = stock_host[start:start + size]
        if encoding == "json":
            text = json.loads('"' + text + '"')
        set_leaf(table, parts, text)
    return js_json(js_json(table))


def apply_splices(stock, edits, catalog):
    parts = []
    cursor = 0
    for start, removed, added in edits:
        if start < cursor or start + removed > len(stock):
            raise ValueError("Patch offsets fall outside the original file")
        parts.append(stock[cursor:start])
        if isinstance(added, list):
            for piece in added:
                if piece is None:
                    parts.append(catalog)
                elif isinstance(piece, list):
                    pos, length = piece
                    parts.append(stock[pos:pos + length])
                else:
                    parts.append(piece)
        else:
            parts.append(added)
        cursor = start + removed
    parts.append(stock[cursor:])
    return "".join(parts).encode("utf-8")


def build_extension(stock_manifest, fields):
    """Keep English display strings in a fallback catalog and localize presentation keys only."""
    manifest = json.loads(stock_manifest)
    en, zh = {}, {}
    for parts, key, translated in fields:
        source = manifest
        for part in parts:
            source = source[part]
        if not isinstance(source, str):
            raise ValueError("Unexpected extension metadata")
        en[key] = source
        zh[key] = translated
        set_leaf(manifest, parts, "%" + key + "%")
    return {
        "package.json": pretty(manifest),
        "package.nls.json": pretty(en),
        "package.nls.zh-cn.json": pretty(zh),
    }


def build_editor(stock, additions):
    base = json.loads(stock)
    for module, entries in additions.items():
        base["contents"].setdefault(module, {}).update(entries)
    return compact(base).encode("utf-8")


def build_product(stock, localized_hashes):
    text = stock.decode("utf-8")
    for key, previous in json.loads(text)["checksums"].items():
        output = localized_hashes.get("out/" + key)
        if output is None:
            continue
        value = base64.b64encode(bytes.fromhex(output)).decode("ascii").rstrip("=")
        if value != previous:
            if text.count(previous) != 1:
                raise ValueError("无法唯一定位应用完整性校验：" + key)
            text = text.replace(previous, value)
    return text.encode("utf-8")
