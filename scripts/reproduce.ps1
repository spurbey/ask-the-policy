# OP-05 Reproduction and Service Runner (PowerShell)
param(
    [string]$Mode = "serve"
)

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $RepoRoot

if (-not $env:PORT) { $env:PORT = "8000" }
if (-not $env:CORPUS_DIR) { $env:CORPUS_DIR = Join-Path (Split-Path -Parent $RepoRoot) "Deployment.inc-Hiring-Problems\references\OP-05\corpus" }

Write-Host "========================================================="
Write-Host "OP-05 Policy Book Assistant Runner"
Write-Host "Mode:       $Mode"
Write-Host "Corpus:     $env:CORPUS_DIR"
Write-Host "Port:       $env:PORT"
Write-Host "========================================================="

switch ($Mode) {
    "serve" {
        uvicorn src.server:app --host 0.0.0.0 --port $env:PORT
    }
    "eval" {
        python (Join-Path $PSScriptRoot "run_eval.py")
    }
    "test" {
        python (Join-Path $RepoRoot "tests\test_indexer.py")
        python (Join-Path $RepoRoot "tests\test_retriever.py")
        python (Join-Path $RepoRoot "tests\test_temporal.py")
        python (Join-Path $RepoRoot "tests\test_span_extractor.py")
        python (Join-Path $RepoRoot "tests\test_server.py")
        Write-Host "All reproduction tests passed!" -ForegroundColor Green
    }
    Default {
        Write-Host "Usage: .\reproduce.ps1 -Mode {serve|eval|test}"
    }
}
