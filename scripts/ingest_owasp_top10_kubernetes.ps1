# Ingest OWASP Kubernetes Top 10 – 2023
# Run from project root: .\scripts\ingest_owasp_top10_kubernetes.ps1

$ErrorActionPreference = "Continue"

$sources = @(
    @{id = "K01:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K01-insecure-workload-configurations.md"},
    @{id = "K02:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K02-supply-chain-vulnerabilities.md"},
    @{id = "K03:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K03-overly-permissive-rbac.md"},
    @{id = "K04:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K04-policy-enforcement.md"},
    @{id = "K05:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K05-inadequate-logging.md"},
    @{id = "K06:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K06-broken-authentication.md"},
    @{id = "K07:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K07-network-segmentation.md"},
    @{id = "K08:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K08-secrets-management.md"},
    @{id = "K09:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K09-misconfigured-cluster-components.md"},
    @{id = "K10:2022"; url = "https://raw.githubusercontent.com/OWASP/www-project-kubernetes-top-ten/main/2022/en/src/K10-vulnerable-components.md"}
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Kubernetes Top 10 2022 ($($sources.Count) items)" -ForegroundColor Cyan
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
        "--document-name", "Top 10 for Kubernetes 2022",
        "--edition", "2022",
        "--dataset-id", "owasp_top10_kubernetes",
        "--version", "2022",
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
