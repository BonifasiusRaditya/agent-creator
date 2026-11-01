param([int]$Port)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.cache\uv'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv from https://docs.astral.sh/uv/ and run this script again.'
}
uv sync --extra video --group dev
if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed.' }
if ($PSBoundParameters.ContainsKey('Port')) {
    uv run --extra video trendforge --port $Port
} else {
    uv run --extra video trendforge
}

