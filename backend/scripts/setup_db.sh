#!/bin/bash

set -e

echo "Setting up database..."

if [ -z "$DATABASE_URL" ]; then
    echo "Warning: DATABASE_URL not set, using default"
    export DATABASE_URL="postgresql://user:password@localhost/lexitau"
fi

echo "Initializing Alembic..."
alembic init alembic

echo "Creating initial migration..."
alembic revision --autogenerate -m "Initial migration"

echo "Running migrations..."
python scripts/migrate.py

echo "Database setup complete!"