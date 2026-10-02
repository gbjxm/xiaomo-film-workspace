from __future__ import annotations

import argparse
from pathlib import Path

from common import load_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, action="append", required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    hashes = {item["file_id"]: item["sha256"] for item in registry["files"]}
    updated = 0
    for path in args.artifact:
        data = load_json(path)
        for collection_key in ("books", "results", "rows", "targets"):
            for item in data.get(collection_key, []):
                file_id = item.get("file_id")
                if file_id in hashes:
                    item["source_sha256"] = hashes[file_id]
                    updated += 1
        write_json(path, data)
    print(f"Attached source hashes to {updated} artifact records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
