#!/usr/bin/env bash
set -euo pipefail

docker compose build fastapi
docker compose run --no-deps --rm fastapi pytest -q
