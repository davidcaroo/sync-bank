param(
    [string]$ProjectRoot = (Resolve-Path ".").Path,
    [string]$BackupRoot = "backups",
    [switch]$SkipImageExport
)

$ErrorActionPreference = "Stop"

Set-Location $ProjectRoot

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $ProjectRoot (Join-Path $BackupRoot $timestamp)
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Write-Host "[backup] Backup directory: $backupDir"

# 1) Source + git metadata
$commit = git rev-parse HEAD
$commit | Out-File (Join-Path $backupDir "git-commit.txt") -Encoding utf8

git status | Out-File (Join-Path $backupDir "git-status.txt") -Encoding utf8

git diff | Out-File (Join-Path $backupDir "git-diff.patch") -Encoding utf8

git archive --format=zip -o (Join-Path $backupDir "source-tracked.zip") HEAD

if (Test-Path ".env") {
    Copy-Item ".env" (Join-Path $backupDir ".env.backup") -Force
}
if (Test-Path "docker-compose.yml") {
    Copy-Item "docker-compose.yml" (Join-Path $backupDir "docker-compose.yml.backup") -Force
}

# 2) Docker images + compose config
if (-not $SkipImageExport) {
    $images = docker compose images --quiet | Sort-Object -Unique | Where-Object { $_ }
    if ($images) {
        $normalizedImages = @()
        foreach ($img in $images) {
            $trimmed = $img.Trim()
            if ($trimmed -match '^[0-9a-f]{64}$') {
                $normalizedImages += "sha256:$trimmed"
            } else {
                $normalizedImages += $trimmed
            }
        }

        try {
            docker image save $normalizedImages -o (Join-Path $backupDir "compose-images.tar")
        } catch {
            Write-Warning "[backup] No se pudieron exportar imagenes compose: $($_.Exception.Message)"
        }
    }
} else {
    Write-Host "[backup] SkipImageExport habilitado"
}
docker compose config > (Join-Path $backupDir "compose-resolved.yml")

# 3) Container runtime data (if running)
$redisId = docker compose ps -q redis
if ($redisId) {
    docker cp "${redisId}:/data" (Join-Path $backupDir "redis-data")
}

$ollamaId = docker compose ps -q ollama
if ($ollamaId) {
    docker cp "${ollamaId}:/root/.ollama" (Join-Path $backupDir "ollama-data")
}

$backupDir | Out-File (Join-Path $backupDir "backup-path.txt") -Encoding utf8
Write-Host "[backup] Done: $backupDir"
