# Ingest OWASP Top 10 API Security Risks – 2023
# Run from project root: .\scripts\ingest_owasp_top10_API.ps1

$ErrorActionPreference = "Continue"

$sources = @(
    @{id="API1:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa1-broken-object-level-authorization.md"},
    @{id="API2:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa2-broken-authentication.md"},
    @{id="API3:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa3-broken-object-property-level-authorization.md"},
    @{id="API4:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa4-unrestricted-resource-consumption.md"},
    @{id="API5:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa5-broken-function-level-authorization.md"},
    @{id="API6:2023"; url="hhttps://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa6-unrestricted-access-to-sensitive-business-flows.md"},
    @{id="API7:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa7-server-side-request-forgery.md"},
    @{id="API8:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa8-security-misconfiguration.md"},
    @{id="API9:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xa9-improper-inventory-management.md"},
    @{id="API10:2023"; url="https://raw.githubusercontent.com/OWASP/API-Security/refs/heads/master/editions/2023/en/0xaa-unsafe-consumption-of-apis.md"}
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Top 10 API Security Risks 2023 ($($sources.Count) items)" -ForegroundColor Cyan
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
        "--document-name", "Top 10 API Security Risks 2023",
        "--edition", "2023",
        "--dataset-id", "owasp_top10_API",
        "--version", "2023",
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
