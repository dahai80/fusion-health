#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("ingest_data")

DATA_DIR = Path(__file__).resolve().parent.parent / "fusion_health" / "data"

DATASETS = {
    "icd10_cn": {
        "file": "icd10_cn/icd10_cn.tsv",
        "required_cols": ["code", "description", "category"],
        "key": "code",
    },
    "icd9cm3_cn": {
        "file": "icd9cm3_cn/icd9cm3_cn.tsv",
        "required_cols": ["code", "description", "category"],
        "key": "code",
    },
    "drg": {
        "file": "drg/drg_cn.tsv",
        "required_cols": ["drg_code", "drg_name", "mdc", "category"],
        "key": "drg_code",
    },
    "insurance_catalog": {
        "file": "insurance_catalog.tsv",
        "required_cols": ["code", "name", "category", "level"],
        "key": "code",
    },
}


def validate_tsv(path: Path, required_cols: list[str], key: str) -> tuple[bool, int, list[str]]:
    if not path.exists():
        logger.error("source file missing: %s", path)
        return False, 0, []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        header = reader.fieldnames or []
        missing = [c for c in required_cols if c not in header]
        if missing:
            logger.error("%s missing columns: %s (have %s)", path.name, missing, header)
            return False, 0, []
        rows = list(reader)
        keys = [r.get(key, "").strip() for r in rows if r.get(key, "").strip()]
        dupes = [k for k in set(keys) if keys.count(k) > 1]
        if dupes:
            logger.warning("%s duplicate %s keys (%d): %s", path.name, key, len(dupes), dupes[:5])
        return True, len(keys), dupes


def ingest(src_dir: Path, dataset: str | None, dry_run: bool) -> int:
    targets = DATASETS if dataset is None else {dataset: DATASETS[dataset]}
    failures = 0
    for name, spec in targets.items():
        src = src_dir / Path(spec["file"]).name
        dst = DATA_DIR / spec["file"]
        ok, count, dupes = validate_tsv(src, spec["required_cols"], spec["key"])
        if not ok:
            failures += 1
            continue
        logger.info("%s: %d rows valid (dupes=%d) src=%s", name, count, len(dupes), src)
        if dry_run:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        backup = dst.with_suffix(dst.suffix + ".bak")
        if dst.exists():
            shutil.copy2(dst, backup)
            logger.info("backed up %s -> %s", dst.name, backup.name)
        shutil.copy2(src, dst)
        logger.info("installed %s -> %s", src.name, dst)
    if failures:
        logger.error("%d dataset(s) failed validation, aborting marker update", failures)
        return 1
    if not dry_run:
        marker = DATA_DIR / ".data_source"
        marker.write_text("full", encoding="utf-8")
        logger.info("data_source marker set to 'full' at %s", marker)
    return 0


def status() -> int:
    marker = DATA_DIR / ".data_source"
    src = "sample"
    if marker.exists():
        src = marker.read_text(encoding="utf-8").strip() or "sample"
    print(f"data_dir: {DATA_DIR}")
    print(f"data_source: {src}")
    for name, spec in DATASETS.items():
        p = DATA_DIR / spec["file"]
        count = 0
        if p.exists():
            with open(p, encoding="utf-8") as f:
                count = sum(1 for _ in csv.DictReader(f, delimiter="\t"))
        print(f"  {name}: {count} rows ({p.name})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest authoritative medical coding datasets")
    parser.add_argument("--src", type=Path, help="source directory holding authoritative TSV files")
    parser.add_argument("--dataset", choices=list(DATASETS), help="ingest single dataset only")
    parser.add_argument("--dry-run", action="store_true", help="validate only, do not write")
    parser.add_argument("--status", action="store_true", help="show current data status")
    args = parser.parse_args(argv)
    if args.status:
        return status()
    if not args.src:
        parser.error("--src required for ingestion (or use --status)")
    src_dir = args.src.resolve()
    if not src_dir.is_dir():
        logger.error("source dir not found: %s", src_dir)
        return 1
    return ingest(src_dir, args.dataset, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
