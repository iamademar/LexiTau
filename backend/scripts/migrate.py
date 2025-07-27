#!/usr/bin/env python3
import subprocess
import sys
import os

def run_migrations():
    try:
        print("Running database migrations...")
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        print("Migrations completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Alembic not found. Make sure it's installed.")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()