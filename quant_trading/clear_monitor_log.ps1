
$LogFile    = Join-Path $PSScriptRoot "monitor.log"
$BackupFile = Join-Path $PSScriptRoot "monitor.log.bak"

if (-not (Test-Path $LogFile)) {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]  monitor.log 不存在，略過清理。"
    exit 0
}

if (Test-Path $BackupFile) {
    Remove-Item $BackupFile -Force
}
Copy-Item $LogFile $BackupFile

Clear-Content $LogFile

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]  monitor.log 已清空，上週備份 → monitor.log.bak"
