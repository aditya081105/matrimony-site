# Backup script: Downloads latest database dump, user media, and config from VPS to local laptop
$ErrorActionPreference = "Stop"

$KeyPath = "C:\Users\adity\Downloads\instance\ssh-key-2026-08-28.key"
$VpsHost = "opc@140.238.167.173"
$BackupDir = Join-Path $PSScriptRoot "backups"

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
}

Write-Host "Creating backup bundle on VPS..."
$RemoteCmd = "sudo -u postgres pg_dump -d poorvanchal_db -F c -b -f /tmp/poorvanchal_db.dump && sudo tar -czf /tmp/media_backup.tar.gz -C /var/www/poorvanchalmatrimony media && sudo cp /var/www/poorvanchalmatrimony/.env /tmp/production.env && sudo chown opc:opc /tmp/poorvanchal_db.dump /tmp/media_backup.tar.gz /tmp/production.env"
ssh -i $KeyPath -o StrictHostKeyChecking=no $VpsHost $RemoteCmd

Write-Host "Downloading database dump and media to laptop..."
scp -i $KeyPath -o StrictHostKeyChecking=no "${VpsHost}:/tmp/poorvanchal_db.dump" (Join-Path $BackupDir "poorvanchal_db.dump")
scp -i $KeyPath -o StrictHostKeyChecking=no "${VpsHost}:/tmp/media_backup.tar.gz" (Join-Path $BackupDir "media_backup.tar.gz")
scp -i $KeyPath -o StrictHostKeyChecking=no "${VpsHost}:/tmp/production.env" (Join-Path $BackupDir "production.env")

Write-Host "Cleaning up temporary files on VPS..."
ssh -i $KeyPath -o StrictHostKeyChecking=no $VpsHost "rm -f /tmp/poorvanchal_db.dump /tmp/media_backup.tar.gz /tmp/production.env"

Write-Host "VPS backup completed successfully! Files stored in $BackupDir"
