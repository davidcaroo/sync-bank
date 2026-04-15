param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,
    [string]$ProjectRoot = (Resolve-Path ".").Path,
    [string]$Commit = ""
)

$ErrorActionPreference = "Stop"

Set-Location $ProjectRoot

if (-not (Test-Path $BackupDir)) {
    throw "BackupDir not found: $BackupDir"
}

Write-Host "[restore] Using backup: $BackupDir"

docker compose down

$imagesTar = Join-Path $BackupDir "compose-images.tar"
if (Test-Path $imagesTar) {
    docker image load -i $imagesTar
}

if ($Commit -and $Commit.Trim()) {
    git checkout $Commit
}

docker compose up -d

Write-Host "[restore] Restore completed"
