#!/usr/bin/env python3
"""
Script to refresh the project: delete database, cache, and uploads, then optionally rebuild

Usage:
  python refresh_project.py          # Clean and rebuild DB with migrations & seeding
  python refresh_project.py --delete # Clean only, don't rebuild DB
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def clear_pycache():
    """Remove all __pycache__ directories and .pyc files"""
    print("\n1. Removing __pycache__ directories...")
    current_dir = Path.cwd()
    pycache_count = 0

    for pycache_dir in current_dir.rglob('__pycache__'):
        try:
            shutil.rmtree(pycache_dir)
            pycache_count += 1
        except Exception as e:
            print(f"   ✗ Failed to remove {pycache_dir}: {e}")

    print(f"   ✓ Removed {pycache_count} __pycache__ directories")

    print("\n2. Removing .pyc files...")
    pyc_count = 0
    for pyc_file in current_dir.rglob('*.pyc'):
        try:
            pyc_file.unlink()
            pyc_count += 1
        except Exception as e:
            print(f"   ✗ Failed to remove {pyc_file}: {e}")

    print(f"   ✓ Removed {pyc_count} .pyc files")


def clear_database():
    """Remove database files"""
    print("\n3. Removing database files...")
    current_dir = Path.cwd()
    db_patterns = ['*.db', '*.sqlite', '*.sqlite3']
    db_count = 0

    for pattern in db_patterns:
        for db_file in current_dir.rglob(pattern):
            try:
                db_file.unlink()
                print(f"   ✓ Removed: {db_file.name}")
                db_count += 1
            except Exception as e:
                print(f"   ✗ Failed to remove {db_file}: {e}")

    print(f"   Total database files removed: {db_count}")


def clear_media():
    """Remove all uploaded files from app/media"""
    print("\n4. Removing uploaded media files...")
    media_dir = Path('app/media')
    media_count = 0

    if media_dir.exists():
        try:
            for item in media_dir.rglob('*'):
                if item.is_file():
                    media_count += 1

            # Remove all contents but keep the directory
            for item in list(media_dir.rglob('*')):
                if item.is_file():
                    item.unlink()
                elif item.is_dir() and not any(item.iterdir()):
                    item.rmdir()

            print(f"   ✓ Cleared {media_count} media files from {media_dir}")
        except Exception as e:
            print(f"   ✗ Failed to clear media: {e}")
    else:
        print(f"   ℹ Directory {media_dir} doesn't exist")


def clear_migrations():
    """Clear all migration files except __init__.py"""
    print("\n5. Clearing migration files...")
    app_dir = Path('app')
    migration_count = 0

    for migrations_dir in app_dir.rglob('migrations'):
        if migrations_dir.is_dir():
            for migration_file in migrations_dir.glob('*.py'):
                if migration_file.name != '__init__.py':
                    try:
                        migration_file.unlink()
                        migration_count += 1
                    except Exception as e:
                        print(f"   ✗ Failed to remove {migration_file}: {e}")

    print(f"   ✓ Removed {migration_count} migration files")


def rebuild_database():
    """Regenerate migrations, apply them, and seed data"""
    print("\n6. Regenerating migrations...")
    result = subprocess.run(
        [sys.executable, 'manage.py', 'makemigrations'],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"   ✗ makemigrations failed: {result.stderr}")
        return False
    print("   ✓ Migrations generated")

    print("\n7. Applying migrations...")
    result = subprocess.run(
        [sys.executable, 'manage.py', 'migrate'],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"   ✗ migrate failed: {result.stderr}")
        return False
    print("   ✓ Migrations applied")

    return True


def seed_database():
    """Load dev fixtures and run seed commands (default post-step after every rebuild).

    Returns False on any fixture/seed-command failure (other than a missing
    fixture, which is OK) so the caller can abort instead of leaving the
    project silently half-seeded.
    """
    print("\n8. Loading fixtures...")
    fixtures = [
        'dev_auth_groups',
        'dev_users',
        'dev_ownership',
        'dev_user_scope',
        'dev_roles',
        'dev_assets_base',
        'dev_assets_instances',
        'dev_extensions_enablement',
    ]
    for fixture in fixtures:
        result = subprocess.run(
            [sys.executable, 'manage.py', 'loaddata', fixture],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"   ✓ {fixture} loaded")
        else:
            if "No fixture named" in result.stderr:
                print(f"   ℹ {fixture} not found (OK)")
            else:
                print(f"   ✗ {fixture} failed: {result.stderr[:500]}")
                return False

    print("\n9. Running seed commands...")
    seed_commands = [
        'seed_parts_dev',
        'seed_procurement_dev',
        'seed_inventory_dev',
        'seed_maintenance_dev',
        'seed_dispatching_dev',
    ]
    for seed_cmd in seed_commands:
        result = subprocess.run(
            [sys.executable, 'manage.py', seed_cmd],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"   ✓ {seed_cmd} seeded")
        else:
            print(f"   ✗ {seed_cmd} failed: {result.stderr}")
            return False

    print("   ✓ Seeding complete")
    return True


def stop_server():
    """Stop the dev server if it's running via ./run"""
    print("\n0. Stopping dev server...")
    stop_script = Path('stop.sh')
    if stop_script.exists():
        result = subprocess.run(['bash', 'stop.sh'], capture_output=True, text=True)
        if result.returncode == 0:
            print("   ✓ Server stopped")
        else:
            if "No PID file" in result.stdout or "not running" in result.stdout:
                print("   ℹ Server not running (OK)")
            else:
                print(f"   ⚠ {result.stdout.strip()}")
    else:
        print("   ℹ stop.sh not found, skipping")


def start_server():
    """Start the dev server via ./run.sh, mirroring stop_server()."""
    print("\n10. Starting dev server...")
    run_script = Path('run.sh')
    if run_script.exists():
        result = subprocess.run(['bash', 'run.sh'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✓ {result.stdout.strip()}")
        else:
            print(f"   ⚠ Failed to start server: {result.stderr.strip()}")
    else:
        print("   ℹ run.sh not found, skipping")


def main():
    delete_only = '--delete' in sys.argv

    print("=" * 60)
    print("🔄 PROJECT REFRESH")
    print("=" * 60)

    if delete_only:
        print("Mode: DELETE ONLY (no rebuild)")
    else:
        print("Mode: CLEAN & REBUILD")

    print("⚠️  WARNING: All database data and uploaded files will be deleted!\n")

    # Stop server first
    stop_server()

    # Clear everything
    clear_pycache()
    clear_database()
    clear_media()
    clear_migrations()

    # Optionally rebuild
    if not delete_only:
        success = rebuild_database()
        if not success:
            print("\n✗ Rebuild failed!")
            return 1
        if not seed_database():
            print("\n✗ Seeding failed!")
            return 1

    # Restart the server we stopped at the start, so the refresh is a
    # single stop → clear → reseed → restart pass with no manual follow-up.
    start_server()

    print("\n" + "=" * 60)
    if delete_only:
        print("✅ Cleanup complete!")
    else:
        print("✅ Project refreshed successfully!")
    print("=" * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
