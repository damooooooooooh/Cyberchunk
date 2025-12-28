# Ingest OWASP Mobie Top 10 – 2023
# Run from project root: .\scripts\ingest_owasp_top10_mobile.ps1

$ErrorActionPreference = "Continue"

$sources = @(
    @{id="M1:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m1-improper-credential-usage.md"},    # Improper Credential Usage:contentReference[oaicite:0]{index=0}
    @{id="M2:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m2-inadequate-supply-chain-security.md"},  # Inadequate Supply Chain Security:contentReference[oaicite:1]{index=1}
    @{id="M3:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m3-insecure-authentication-authorization.md"},  # Insecure Authentication/Authorization:contentReference[oaicite:2]{index=2}
    @{id="M4:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m4-insufficient-input-output-validation.md"},  # Insufficient Input/Output Validation:contentReference[oaicite:3]{index=3}
    @{id="M5:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m5-insecure-communication.md"},  # Insecure Communication:contentReference[oaicite:4]{index=4}
    @{id="M6:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m6-inadequate-privacy-controls.md"},  # Inadequate Privacy Controls:contentReference[oaicite:5]{index=5}
    @{id="M7:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m7-insufficient-binary-protection.md"},  # Insufficient Binary Protection:contentReference[oaicite:6]{index=6}
    @{id="M8:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m8-security-misconfiguration.md"},  # Security Misconfiguration:contentReference[oaicite:7]{index=7}
    @{id="M9:2023";  url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m9-insecure-data-storage.md"},  # Insecure Data Storage:contentReference[oaicite:8]{index=8}
    @{id="M10:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-mobile-top-10/master/2023-risks/m10-insufficient-cryptography.md"}   # Insufficient Cryptography:contentReference[oaicite:9]{index=9}
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Mobile Top 10 2023 ($($sources.Count) items)" -ForegroundColor Cyan
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
        "--document-name", "Top 10 for Mobile 2023",
        "--edition", "2023",
        "--dataset-id", "owasp_top10_mobile",
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
