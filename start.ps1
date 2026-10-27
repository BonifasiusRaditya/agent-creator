param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.cache\uv'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv from https://docs.astral.sh/uv/ and run this script again.'
}
uv sync --group dev
if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed.' }
uv run trendforge --port $Port

