#!/usr/bin/env python3
"""Extract Params defaults and bigFeed map overrides from bot sources."""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPE = r"(?:double|float|int|long|bool|size_t)"
DECL = re.compile(r"\b(" + TYPE + r")\s+(.+?);", re.S)
ASSIGN = re.compile(r"\bP\.(\w+)\s*=\s*([^;]+)\s*;")


def uncomment(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def balanced_block(text, start):
    """Return brace-delimited block beginning at start, respecting strings/comments."""
    opening = text.find("{", start)
    if opening < 0:
        raise ValueError("opening brace not found")
    depth, quote, escape = 0, None, False
    for i in range(opening, len(text)):
        c = text[i]
        if quote:
            if escape: escape = False
            elif c == "\\": escape = True
            elif c == quote: quote = None
            continue
        if c in ('"', "'"): quote = c
        elif c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return text[opening + 1:i]
    raise ValueError("unclosed brace block")


def split_declarators(body):
    # Params declarations use scalar literals; split commas outside parentheses/strings.
    chunks, begin, depth, quote, esc = [], 0, 0, None, False
    for i, c in enumerate(body):
        if quote:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == quote: quote = None
        elif c in ('"', "'"): quote = c
        elif c == "(": depth += 1
        elif c == ")": depth -= 1
        elif c == "," and depth == 0:
            chunks.append(body[begin:i]); begin = i + 1
    chunks.append(body[begin:])
    return chunks


def source_files():
    dirs = set()
    for p in ROOT.iterdir():
        if p.is_dir() and (p.name.startswith("cand_") or p.name.startswith("viper")):
            dirs.add(p)
    for parent_name in ("baselines", "opponents"):
        parent = ROOT / parent_name
        if parent.exists():
            dirs.update(p for p in parent.iterdir() if p.is_dir() and (p / "main.cpp").is_file())
    for directory in sorted(dirs, key=lambda p: p.name.lower()):
        main = directory / "main.cpp"
        if main.is_file(): yield directory.name, main


def parse_bot(bot, main):
    defaults, overrides = {}, {"open": {}, "maze": {}}
    sources = [main]
    common = main.parent / "common.hpp"
    if common.is_file(): sources.insert(0, common)
    for path in sources:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            clean = uncomment(raw)
            m = re.search(r"\bstruct\s+Params\b", clean)
            if m:
                block = balanced_block(clean, m.end())
                for declaration in DECL.finditer(block):
                    typ, rest = declaration.groups()
                    for item in split_declarators(rest):
                        pair = re.match(r"\s*(\w+)\s*=\s*(.*?)\s*$", item, re.S)
                        if pair:
                            defaults.setdefault(pair.group(1), pair.group(2).strip())
            # Extract only direct bigFeed branches; unrelated nested blocks cannot
            # accidentally change which map bucket receives an assignment.
            am = re.search(r"\bactivateMap\s*\([^;]*?\)\s*\{", clean, re.S)
            if am:
                body = balanced_block(clean, am.start())
                gate = re.search(r"\bif\s*\(\s*bigFeed\s*\)\s*\{", body)
                if gate:
                    open_start = gate.end() - 1
                    open_body = balanced_block(body, open_start)
                    close = open_start + len(open_body) + 1
                    for name, value in ASSIGN.findall(open_body): overrides["open"][name] = value.strip()
                    tail = body[close + 1:]
                    other = re.match(r"\s*else\s*\{", tail)
                    if other:
                        maze_body = balanced_block(tail, other.end() - 1)
                        for name, value in ASSIGN.findall(maze_body): overrides["maze"][name] = value.strip()
        except Exception as exc:
            print(f"{bot}: could not parse {path.relative_to(ROOT)}: {exc}", file=sys.stderr)
    return defaults, overrides


def main():
    bots = {name: parse_bot(name, path) for name, path in source_files()}
    if "cand_y10" not in bots:
        print("cand_y10 not found; cannot produce comparison", file=sys.stderr)
        return 1
    table = ROOT / "ladder" / "params_table.csv"
    table.parent.mkdir(parents=True, exist_ok=True)
    with table.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bot", "param", "default_value", "override_open", "override_maze"])
        for bot in sorted(bots, key=str.lower):
            defaults, ov = bots[bot]
            for param in sorted(defaults, key=str.lower):
                writer.writerow([bot, param, defaults[param], ov["open"].get(param, ""), ov["maze"].get(param, "")])
    base = bots["cand_y10"][0]
    lines = ["# Parameter differences from cand_y10", "", "Defaults are compared as source expressions (textually)."]
    for bot in sorted(bots, key=str.lower):
        if bot == "cand_y10": continue
        values = bots[bot][0]
        changed = [(k, values[k], base[k]) for k in sorted(values.keys() & base.keys(), key=str.lower) if values[k] != base[k]]
        only = [(k, values[k]) for k in sorted(values.keys() - base.keys(), key=str.lower)]
        lines.extend(["", f"## {bot}"])
        if changed:
            lines.extend(["", "Different defaults:"])
            lines.extend(f"- `{k}`: `{v}` (bot) vs `{b}` (cand_y10)" for k, v, b in changed)
        else: lines.extend(["", "Different defaults: none."])
        if only:
            lines.extend(["", "Only in this bot:"])
            lines.extend(f"- `{k}`: `{v}`" for k, v in only)
        else: lines.extend(["", "Only in this bot: none."])
    (ROOT / "ladder" / "params_diff.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
