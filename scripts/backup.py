from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import tarfile
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backup")


def _home_dir() -> Path:
    return Path(os.getenv("FUSION_HEALTH_HOME", str(Path.home() / ".fusion-health")))


def _audit_log() -> Path:
    p = os.getenv("FUSION_HEALTH_AUDIT_LOG", "")
    return Path(p) if p else _home_dir() / "audit.log"


def _conversations_dir() -> Path:
    # matches ConversationMemory.save default: literature_cache_dir.parent / "conversations"
    # literature_cache_dir defaults to ~/.fusion-health/literature/cache
    return _home_dir() / "conversations"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(out_dir: Path, verify: bool = True) -> Path:
    """Create a tar.gz backup of audit log + conversation sessions.

    Verifies audit integrity before backup (fails if tampered, unless --no-verify).
    Returns the archive path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    archive = out_dir / f"fusion-health-backup-{stamp}.tar.gz"
    manifest_entries: list[dict] = []

    audit = _audit_log()
    conv = _conversations_dir()

    if verify and audit.exists():
        from fusion_health.audit import verify_log_file
        ok, tampered = verify_log_file(audit)
        if tampered:
            logger.error("audit verification found %d tampered lines — ABORTING backup", tampered)
            sys.exit(3)

    staged: list[Path] = []
    if audit.exists():
        staged.append(audit)
        manifest_entries.append({"path": str(audit), "sha256": _sha256(audit), "bytes": audit.stat().st_size})
    if conv.exists():
        for p in sorted(conv.glob("*.json")):
            staged.append(p)
            manifest_entries.append({"path": str(p), "sha256": _sha256(p), "bytes": p.stat().st_size})

    if not staged:
        logger.warning("nothing to back up (no audit log, no sessions)")
    else:
        logger.info("backing up %d files (%d audit + sessions)", len(staged), len(staged))

    import json
    manifest = {
        "created": stamp,
        "hostname": os.uname().nodename,
        "files": manifest_entries,
    }
    manifest_path = out_dir / f".manifest-{stamp}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with tarfile.open(archive, "w:gz") as tar:
        for p in staged:
            tar.add(p, arcname=str(p.relative_to(p.anchor)) if p.is_absolute() else str(p))
        tar.add(manifest_path, arcname="manifest.json")

    manifest_path.unlink()
    logger.info("backup complete: %s (%d bytes)", archive, archive.stat().st_size)
    return archive


def restore(archive: Path, dry_run: bool = False) -> int:
    """Verify a backup archive integrity (manifest sha256 match) then list contents.

    Does NOT auto-restore (too dangerous for PHI — operator must copy files manually).
    """
    if not archive.exists():
        logger.error("archive not found: %s", archive)
        return 1
    import json
    with tarfile.open(archive, "r:gz") as tar:
        m_file = tar.extractfile("manifest.json")
        if m_file is None:
            logger.error("no manifest.json in archive")
            return 2
        manifest = json.loads(m_file.read())
    print(f"archive: {archive}")
    print(f"created: {manifest.get('created')}  hostname: {manifest.get('hostname')}")
    print(f"files: {len(manifest.get('files', []))}")
    all_ok = True
    for entry in manifest.get("files", []):
        # re-read archive to hash each member
        with tarfile.open(archive, "r:gz") as tar:
            member = None
            for m in tar.getmembers():
                if m.name.endswith(Path(entry["path"]).name):
                    member = m
                    break
            if member is None:
                print(f"  MISSING  {entry['path']}")
                all_ok = False
                continue
            f = tar.extractfile(member)
            digest = hashlib.sha256(f.read()).hexdigest() if f else ""
            ok = digest == entry["sha256"]
            if not ok:
                all_ok = False
            print(f"  {'OK' if ok else 'MISMATCH'}  {entry['path']}  {entry['bytes']}b")
    if all_ok:
        print("integrity: PASS — all files match manifest")
        return 0
    print("integrity: FAIL — do not restore from this archive")
    return 4


def main():
    p = argparse.ArgumentParser(description="Fusion-Health DR backup/restore")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("create", help="create backup archive")
    b.add_argument("--out", type=Path, default=Path("backups"))
    b.add_argument("--no-verify", action="store_true", help="skip audit integrity check")
    r = sub.add_parser("verify", help="verify a backup archive")
    r.add_argument("archive", type=Path)
    args = p.parse_args()
    if args.cmd == "create":
        backup(args.out, verify=not args.no_verify)
    elif args.cmd == "verify":
        sys.exit(restore(args.archive))


if __name__ == "__main__":
    main()
