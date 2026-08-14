#!/usr/bin/env python
"""Wipe project migrations + database, then rebuild schema from current models.

Aligns with `.cursor/rules/migration-strategy.mdc`. Stop the dev server before running.

Usage (from repository root):
  python dev_tools/delete_database_rebuild_models.py
  python dev_tools/delete_database_rebuild_models.py --seed
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Parent of ``dev_tools/`` when this file lives under ``dev_tools/``."""
    here = Path(__file__).resolve().parent
    return here.parent if here.name == "dev_tools" else here


def _bootstrap_django() -> None:
    root = _repo_root()
    sys.path.insert(0, str(root / "app"))
    sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def _remove_project_migrations(root: Path) -> list[Path]:
    """Clear ``app/<application>/migrations/`` for each application package.

    Deletes every file in each migrations directory except ``__init__.py`` (required
    for the package). Removes ``__pycache__`` if present.
    """
    removed: list[Path] = []
    app_pkg = root / "app"
    if not app_pkg.is_dir():
        return removed

    for application_dir in sorted(app_pkg.iterdir()):
        if not application_dir.is_dir():
            continue
        migrations_dir = application_dir / "migrations"
        if not migrations_dir.is_dir():
            continue

        for path in sorted(migrations_dir.iterdir()):
            if path.is_dir():
                if path.name == "__pycache__":
                    shutil.rmtree(path)
                continue
            if not path.is_file():
                continue
            if path.name == "__init__.py":
                continue
            path.unlink()
            removed.append(path)
    return removed


def _clear_database() -> None:
    from django.conf import settings
    from django.db import connections

    db = settings.DATABASES["default"]
    engine = db["ENGINE"]

    connections.close_all()

    if "sqlite" in engine:
        name = Path(db["NAME"])
        if name.exists():
            name.unlink()
        return

    if engine == "django.db.backends.postgresql":
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cursor.execute("CREATE SCHEMA public")
        return

    raise SystemExit(
        f"Unsupported database engine {engine!r}. "
        "Use SQLite or PostgreSQL, or empty the database manually and re-run.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete project migrations and database, then makemigrations + migrate.",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Load dev fixtures via `manage.py loaddata` after migrate.",
    )
    args = parser.parse_args()

    root = _repo_root()

    _bootstrap_django()

    from django.core.management import call_command

    removed = _remove_project_migrations(root)
    print(f"Removed {len(removed)} migration file(s).", flush=True)

    _clear_database()
    print("Database cleared.", flush=True)

    call_command("makemigrations", verbosity=1)
    call_command("migrate", verbosity=1)

    if args.seed:
        for label in (
            "dev_auth_groups",
            "dev_users",
            "dev_ownership",
            "dev_user_scope",
            "dev_roles",
            "dev_assets_base",
            "dev_assets_instances",
            "dev_extensions_enablement",
        ):
            call_command("loaddata", label, verbosity=1)

        call_command("seed_parts_dev", verbosity=1)
        call_command("seed_procurement_dev", verbosity=1)

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
