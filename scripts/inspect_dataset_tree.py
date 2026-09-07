#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a dataset tree without assuming its schema")
    parser.add_argument("root", type=Path)
    parser.add_argument("--max-examples", type=int, default=20)
    parser.add_argument("--json", dest="json_out", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"dataset root does not exist: {root}")

    suffix_counts: collections.Counter[str] = collections.Counter()
    name_tokens: collections.Counter[str] = collections.Counter()
    examples: dict[str, list[str]] = collections.defaultdict(list)
    total_files = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        total_files += 1
        suffix = path.suffix.lower() or "<no_suffix>"
        suffix_counts[suffix] += 1
        rel = str(path.relative_to(root))
        if len(examples[suffix]) < args.max_examples:
            examples[suffix].append(rel)
        for token in path.stem.lower().replace("-", "_").split("_"):
            if token:
                name_tokens[token] += 1

    report = {
        "root": str(root),
        "total_files": total_files,
        "suffix_counts": dict(suffix_counts.most_common()),
        "common_name_tokens": dict(name_tokens.most_common(50)),
        "examples_by_suffix": dict(examples),
    }

    print(json.dumps(report, indent=2))
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
