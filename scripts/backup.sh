#!/usr/bin/env bash
# Backs up journal data to the private mirror-backup repo.
# The archive/ directory is its own git repo (nested, gitignored by this repo):
#   - markdown exports written by the n8n workflow
#   - db-backups/ pg_dump snapshots created here
set -euo pipefail

cd "$(dirname "$0")/.."

STAMP=$(date +%Y-%m-%d)
mkdir -p archive/db-backups
docker exec mirror-postgres pg_dump -U mirror -d mirror > "archive/db-backups/snapshot-${STAMP}.sql"

git -C archive add -A
if ! git -C archive diff --cached --quiet; then
  git -C archive commit -m "backup: ${STAMP}"
fi
git -C archive push origin main
echo "Backup complete: ${STAMP}"
