# Ingest OWASP Top 10 2025
# Run from project root: .\scripts\ingest_owasp_top10.ps1

$ErrorActionPreference = "Continue"

$sources = @(
    @{id="A01:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/refs/heads/master/2025/docs/en/A01_2025-Broken_Access_Control.md"},
    @{id="A02:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A02_2025-Security_Misconfiguration.md"},
    @{id="A03:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A03_2025-Software_Supply_Chain_Failures.md"},
    @{id="A04:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A04_2025-Cryptographic_Failures.md"},
    @{id="A05:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A05_2025-Injection.md"},
    @{id="A06:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A06_2025-Insecure_Design.md"},
    @{id="A07:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A07_2025-Authentication_Failures.md"},
    @{id="A08:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A08_2025-Software_or_Data_Integrity_Failures.md"},
    @{id="A09:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A09_2025-Security_Logging_and_Alerting_Failures.md"},
    @{id="A10:2025"; url="https://raw.githubusercontent.com/OWASP/Top10/0913e6101a5ed1ea358bf2f74653a1ed30e29226/2025/docs/en/A10_2025-Mishandling_of_Exceptional_Conditions.md"}
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Top 10 2025 ($($sources.Count) items)" -ForegroundColor Cyan
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
        "--document-name", "Top 10 2025",
        "--edition", "2025",
        "--dataset-id", "owasp_top10",
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
