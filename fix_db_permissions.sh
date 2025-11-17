#!/usr/bin/env bash
set -euo pipefail

DB_FILE="${1:-/opt/sharenest/sharenest.db}"
DB_DIR="$(dirname "$DB_FILE")"

sudo chown ubuntu:www-data "$DB_FILE" || true
sudo chmod 660 "$DB_FILE" || true
sudo chown -R ubuntu:www-data "$DB_DIR"
sudo find "$DB_DIR" -type d -exec chmod 775 {} \;
echo "Permissions updated on $DB_FILE"
