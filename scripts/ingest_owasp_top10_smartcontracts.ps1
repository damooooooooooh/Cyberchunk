# Ingest OWASP Smart Contract Top 10 – 2025
# Run from project root: .\scripts\ingest_owasp_top10_smartcontracts.ps1

$ErrorActionPreference = "Continue"

$sources = @(
    @{id="SC01:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC01-access-control.md"},            # Access Control:contentReference[oaicite:2]{index=2}
    @{id="SC02:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC02-price-oracle-manipulation.md"},  # Price Oracle Manipulation:contentReference[oaicite:3]{index=3}
    @{id="SC03:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC03-logic-errors.md"},               # Logic Errors:contentReference[oaicite:4]{index=4}
    @{id="SC04:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC04-lack-of-input-validation.md"},    # Lack of Input Validation:contentReference[oaicite:5]{index=5}
    @{id="SC05:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC05-reentrancy-attacks.md"},          # Reentrancy Attacks:contentReference[oaicite:6]{index=6}
    @{id="SC06:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC06-unchecked-external-calls.md"},    # Unchecked External Calls:contentReference[oaicite:7]{index=7}
    @{id="SC07:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC07-flash-loan-attacks.md"},          # Flash Loan Attacks:contentReference[oaicite:8]{index=8}
    @{id="SC08:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC08-integer-overflow-underflow.md"},  # Integer Overflow/Underflow:contentReference[oaicite:9]{index=9}
    @{id="SC09:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC09-insecure-randomness.md"},         # Insecure Randomness:contentReference[oaicite:10]{index=10}
    @{id="SC10:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-smart-contract-top-10/main/2025/en/src/SC10-denial-of-service.md"}            # Denial of Service:contentReference[oaicite:11]{index=11}
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Smart Contract Top 10 2025($($sources.Count) items)" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$success = 0
$failed  = 0

foreach ($source in $sources) {
    Write-Host "`n--- Processing $($source.id) ---" -ForegroundColor Yellow

    # Build args as an array (no escaping hell, no Invoke-Expression)
    $args = @(
        "-m", "rag_builder.cli", "ingest",
        "--publisher", "OWASP",
        "--collection", "OWASP Top 10",
        "--document-name", "Smart Contract Top 10",
        "--edition", "2025",
        "--dataset-id", "owasp_top10_smartcontracts",
        "--version", "2025",
        "--use-llm",
        "--enrich-tags",
        "--use-postgres",
        "--preserve-source",
        "--source", $source.url,
        "--item-id", $source.id
    )

    Write-Host ("Running: python " + ($args -join " ")) -ForegroundColor Gray

    try {
        & python @args
        $exit = $LASTEXITCODE

        if ($exit -eq 0) {
            $success++
            Write-Host "`n✓ Success: $($source.id)" -ForegroundColor Green
        }
        else {
            $failed++
            Write-Host "`n✗ Failed: $($source.id) (exit code: $exit)" -ForegroundColor Red
        }
    }
    catch {
        $failed++
        Write-Host "`n✗ Error: $($source.id) - $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingestion Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✓ Successful: $success" -ForegroundColor Green
Write-Host "✗ Failed: $failed" -ForegroundColor Red
Write-Host "`nNext step: python -m rag_builder.cli embed --provider ollama --batch-size 50`n" -ForegroundColor Yellow
