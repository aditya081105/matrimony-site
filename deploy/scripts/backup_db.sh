#!/bin/bash
# ==============================================================================
# Poorvanchal Matrimony - Automated PostgreSQL Nightly Backup Script
# ==============================================================================
set -euo pipefail

BACKUP_DIR="/var/backups/poorvanchal/db"
LOG_FILE="/var/log/poorvanchal/backup.log"
DB_NAME="poorvanchal_db"
RETENTION_DAYS=14
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

mkdir -p "${BACKUP_DIR}"
mkdir -p "$(dirname "${LOG_FILE}")"

log "Starting database backup for ${DB_NAME}..."

# Execute pg_dump as postgres user and compress with gzip
if sudo -u postgres pg_dump "${DB_NAME}" | gzip > "${BACKUP_FILE}"; then
    FILESIZE=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}" 2>/dev/null || echo 0)
    if [ "${FILESIZE}" -gt 1000 ]; then
        log "SUCCESS: Backup created at ${BACKUP_FILE} (Size: ${FILESIZE} bytes)."
    else
        log "ERROR: Backup file is suspiciously small (${FILESIZE} bytes)."
        exit 1
    fi
else
    log "ERROR: pg_dump command failed!"
    exit 1
fi

# Rotate backups older than RETENTION_DAYS
log "Pruning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -type f -name "${DB_NAME}_*.sql.gz" -mtime +"${RETENTION_DAYS}" -exec rm -f {} \;
log "Backup process completed successfully."
