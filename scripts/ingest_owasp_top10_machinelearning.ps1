# Ingest OWASP Machine Learning Security Top 10 - 2023
# Run from project root: .\scripts\ingest_owasp_top10_machinelearning.ps1

$ErrorActionPreference = "Continue"

$sources = @(
    @{id="ML01:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML01_2023-Input_Manipulation_Attack.md"},     # Input Manipulation Attack:contentReference[oaicite:2]{index=2}
    @{id="ML02:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML02_2023-Data_Poisoning_Attack.md"},         # Data Poisoning Attack:contentReference[oaicite:3]{index=3}
    @{id="ML03:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML03_2023-Model_Inversion_Attack.md"},         # Model Inversion Attack:contentReference[oaicite:4]{index=4}
    @{id="ML04:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML04_2023-Membership_Inference_Attack.md"},     # Membership Inference Attack:contentReference[oaicite:5]{index=5}
    @{id="ML05:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML05_2023-Model_Theft.md"},                     # Model Theft:contentReference[oaicite:6]{index=6}
    @{id="ML06:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML06_2023-AI_Supply_Chain_Attacks.md"},        # AI Supply Chain Attacks:contentReference[oaicite:7]{index=7}
    @{id="ML07:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML07_2023-Transfer_Learning_Attack.md"},       # Transfer Learning Attack:contentReference[oaicite:8]{index=8}
    @{id="ML08:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML08_2023-Model_Skewing.md"},                # Model Skewing:contentReference[oaicite:9]{index=9}
    @{id="ML09:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML09_2023-Output_Integrity_Attack.md"},        # Output Integrity Attack:contentReference[oaicite:10]{index=10}
    @{id="ML10:2023"; url="https://raw.githubusercontent.com/OWASP/www-project-machine-learning-security-top-10/master/docs/ML10_2023-Model_Poisoning.md"}                # Model Poisoning:contentReference[oaicite:11]{index=11}
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Machine Learning Security Top 10 2023($($sources.Count) items)" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$success = 0
$failed  = 0

foreach ($source in $sources) {
    Write-Host "`n--- Processing $($source.id) ---" -ForegroundColor Yellow

    # Build args as an array (no escaping hell, no Invoke-Expression)
    $args = @(
        "-m", "rag_builder.cli", "ingest",
        "--publisher", "OWASP",
        "--collection", "OWASP Machine Learning Security Top 10",
        "--document-name", "Machine Learning Security Top 10",
        "--edition", "2023",
        "--dataset-id", "owasp_top10_machinelearning",
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
