from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def _zip_path(mode: str, backup_root: Path) -> Path:
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    if mode == "hourly":
        folder = backup_root / "hourly"
        name = f"lifeos_{now}_incremental.zip"
    else:
        folder = backup_root / "daily"
        name = f"lifeos_{now}_full.zip"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name


def _add_tree(zf: ZipFile, src: Path, arc_prefix: str) -> int:
    count = 0
    if not src.exists():
        return 0
    for path in src.rglob("*"):
        if path.is_file():
            zf.write(path, arcname=f"{arc_prefix}/{path.relative_to(src).as_posix()}")
            count += 1
    return count


def run(mode: str, vault: Path, db: Path, backup_root: Path) -> Path:
    out = _zip_path(mode, backup_root)
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as zf:
        _add_tree(zf, vault, "Vault")
        if mode == "daily" and db.exists():
            zf.write(db, arcname=f"data/{db.name}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Create local LifeOS backup zip.")
    parser.add_argument("--mode", choices=["hourly", "daily"], default="daily")
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--backup-root", default=Path("backups"), type=Path)
    args = parser.parse_args()
    out = run(args.mode, args.vault, args.db, args.backup_root)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
