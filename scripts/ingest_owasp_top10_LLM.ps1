# Ingest OWASP Top 10 for LLM Applications 2025
# Run from project root: .\scripts\ingest_owasp_top10_LLM.ps1

$ErrorActionPreference = "Continue"

$sources = @(
    @{id="LLM01:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM01_PromptInjection.md"},
    @{id="LLM02:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM02_SensitiveInformationDisclosure.md"},
    @{id="LLM03:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM03_SupplyChain.md"},
    @{id="LLM04:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM04_DataModelPoisoning.md"},
    @{id="LLM05:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM05_ImproperOutputHandling.md"},
    @{id="LLM06:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM06_ExcessiveAgency.md"},
    @{id="LLM07:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM07_SystemPromptLeakage.md"},
    @{id="LLM08:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM08_VectorAndEmbeddingWeaknesses.md"},
    @{id="LLM09:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM09_Misinformation.md"},
    @{id="LLM10:2025"; url="https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/refs/heads/main/2_0_vulns/LLM10_UnboundedConsumption.md"}
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Top 10 for LLM Applications 2025 ($($sources.Count) items)" -ForegroundColor Cyan
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
        "--document-name", "Top 10 for LLM Application 2025",
        "--edition", "2025",
        "--dataset-id", "owasp_top10_llm",
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
