param(
    [string]$Branch = "codex/production-saas-readiness",
    [string]$RemoteName = "origin",
    [string]$RemoteUrl = "https://github.com/kennechen554-code/AHR999-Optimized-Kenne-Index.git",
    [string]$CommitMessage = "feat(saas): production readiness upgrade"
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Remove-WorkspaceItem {
    param([string]$Path)
    $target = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
    if (-not $target.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside repository: $target"
    }
    if (Test-Path -LiteralPath $target) {
        Get-ChildItem -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
            $_.Attributes = "Normal"
        }
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

Invoke-Git rev-parse --show-toplevel | Out-Null

$existingRemote = (& git remote get-url $RemoteName 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($existingRemote)) {
    Invoke-Git remote add $RemoteName $RemoteUrl
}

Remove-WorkspaceItem "frontend/build"
Remove-WorkspaceItem "frontend/dist"
Remove-WorkspaceItem "reports"
Remove-WorkspaceItem ".npm-cache"
Remove-WorkspaceItem ".pip-audit-cache"
Remove-WorkspaceItem "backend/.mypy_cache"
Remove-WorkspaceItem "backend/.pytest_cache"
Remove-WorkspaceItem "backend/tests/_test_temp.db"
Remove-WorkspaceItem "backend/tests/_ci_temp.db"

$forbiddenPaths = @(
    "backend/.env",
    "backend/dev.db",
    "backend/app/__pycache__",
    "backend/app/api/__pycache__",
    "backend/app/api/v1/__pycache__",
    "backend/app/core/__pycache__",
    "backend/app/engine/__pycache__",
    "backend/app/model/__pycache__",
    "backend/app/schema/__pycache__",
    "backend/app/service/__pycache__"
)

Invoke-Git rm --cached -r --ignore-unmatch @forbiddenPaths
Invoke-Git add -A

$staged = (& git diff --cached --name-only)
if ([string]::IsNullOrWhiteSpace($staged)) {
    throw "No staged changes to commit."
}

Invoke-Git commit -m $CommitMessage
Invoke-Git push -u $RemoteName "HEAD:$Branch"

Write-Host "Release branch pushed: $Branch"
Write-Host "If GitHub CLI is installed, run: gh pr create --base main --head $Branch --draft --title `"$CommitMessage`""
