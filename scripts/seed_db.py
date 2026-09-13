#!/usr/bin/env python3
"""Popula o banco SQLite com os perfis de segurados.

Uso:
    python scripts/seed_db.py                  # usa CSV padrao + DB padrao
    python scripts/seed_db.py --reset          # apaga DB e recria do zero
    python scripts/seed_db.py --csv FILE.csv   # usa CSV customizado
    python scripts/seed_db.py --db  path.db    # usa DB customizado
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "insured_profiles.csv"
DEFAULT_DB = ROOT / "data" / "seguramente.db"

sys.path.insert(0, str(ROOT))

from seguramente.database import Database, InsuredProfileRow


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "sim", "yes", "ativo"}


def seed(csv_path: Path, db_path: Path, reset: bool = False) -> int:
    """Le o CSV e popula o SQLite. Retorna numero de registros inseridos."""
    if reset and db_path.exists():
        db_path.unlink()
        print(f"Banco antigo removido: {db_path}")

    if not csv_path.exists():
        print(f"CSV nao encontrado: {csv_path}")
        return 0

    db = Database(db_path)

    with db._session() as session:
        count = 0
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                exists = (
                    session.query(InsuredProfileRow)
                    .filter_by(profile_id=row["profile_id"])
                    .first()
                )
                if not exists:
                    session.add(
                        InsuredProfileRow(
                            profile_id=row["profile_id"],
                            name=row["name"],
                            city=row["city"],
                            state=row["state"],
                            product=row["product"].strip().lower(),
                            channel=row["channel"].strip().lower(),
                            consent=_as_bool(row["consent"]),
                            contact=row["contact"],
                        )
                    )
                    count += 1
        session.commit()

    total = len(db.load_profiles())
    print(f"Inseridos {count} novos registros. Total no banco: {total}")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Caminho do CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Caminho do SQLite (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove o banco existente antes de popular",
    )
    args = parser.parse_args()
    seed(args.csv, args.db, args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
