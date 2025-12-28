<#
    Ingest OWASP Cornucopia Mobile App cards (version 1.1)

    This script will iterate through all of the "Cornucopia" playing cards for
    mobile applications published by OWASP.  Each card lives in its own
    directory and contains two Markdown files: an `explanation.md` and a
    `technical-note.md`.  The raw Markdown files are ingested separately so
    that both the explanation and the technical note are captured in the
    knowledge base.

    To run this script, execute it from the root of your project:

        .\scripts\ingest_owasp_cornucopia_mobile_cards.ps1

    The script uses the `rag_builder` CLI to ingest each source and stores
    all documents under a single dataset (`owasp_cornucopia_mobileapp_cards`).
    After ingestion you may embed the dataset via the next command printed
    at the end of the run.  Errors are logged but do not halt the script.
    See the README for details on the ingestion parameters.
#>

$ErrorActionPreference = "Continue"

# Define the version of the Cornucopia mobile cards set.  The directory
# structure in the OWASP repository follows this version (e.g. "mobileapp-cards-1.1-en").
$cornucopiaVersion = "1.1"

# The GitHub base URL for raw Markdown files in the OWASP Cornucopia repo
$githubBaseUrl = "https://raw.githubusercontent.com/OWASP/cornucopia/master/cornucopia.owasp.org/data/cards/mobileapp-cards-" + $cornucopiaVersion + "-en"

# Helper function to generate card codes for a given prefix.  The game uses
# numbers 2 through 9 and the letters A, J, K, Q and X (Ace, Jack, King, Queen,
# and Joker) to denote the thirteen ranks in each suit.  For example,
# prefix "AA" yields AA2, AA3, …, AA9, AAA, AAJ, AAK, AAQ and AAX.
function Get-CardCodes {
    param(
        [string] $prefix
    )
    $cards = @()
    # numeric ranks 2–9
    foreach ($n in 2..9) {
        $cards += ($prefix + $n)
    }
    # letter ranks: Ace (A), Jack (J), King (K), Queen (Q), Joker (X)
    foreach ($suff in @('A','J','K','Q','X')) {
        $cards += ($prefix + $suff)
    }
    return $cards
}

# Build a list of all mobile-app card codes grouped by category.  Each
# category corresponds to a suit in the Cornucopia deck.  The wild-card
# category uses special codes that don't follow the same pattern, so they
# are listed explicitly.
$cardCategories = @{
    'authentication-%26-authorization' = Get-CardCodes 'AA'
    'cornucopia'                       = Get-CardCodes 'CM'
    'cryptography'                     = Get-CardCodes 'CRM'
    'network-%26-storage'              = Get-CardCodes 'NS'
    'platform-%26-code'                = Get-CardCodes 'PC'
    'resilience'                       = Get-CardCodes 'RS'
    'wild-card'                        = @('JOAM','JOBM')
}

# Assemble the array of sources to ingest.  Each entry contains a unique
# identifier and the fully-qualified raw GitHub URL to the Markdown file.
# Two entries are produced for every card: one for the explanation and
# another for the technical note.  The identifier reflects both the card
# code and the file type (e.g. "AA2-explanation" or "CRM5-technical-note").
$sources = @()
foreach ($category in $cardCategories.Keys) {
    $cardList = $cardCategories[$category]
    foreach ($card in $cardList) {
        # Explanation file entry
        $explUrl  = "$githubBaseUrl/$category/$card/explanation.md"
        $explId   = "$card-explanation"
        $sources += @{ id = $explId; url = $explUrl }

        # Technical note entry
        $techUrl  = "$githubBaseUrl/$category/$card/technical-note.md"
        $techId   = "$card-technical-note"
        $sources += @{ id = $techId; url = $techUrl }
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Ingesting OWASP Cornucopia Mobile App Cards ($($sources.Count) items)" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$success = 0
$failed  = 0

foreach ($source in $sources) {
    Write-Host "`n--- Processing $($source.id) ---" -ForegroundColor Yellow

    # Build the argument list for the rag_builder CLI.  All cards are stored
    # under a single dataset and share common metadata.  We preserve the
    # source file and request enrichment via the LLM.  Feel free to modify
    # collection, document-name or dataset-id if you need to separate
    # different editions later on.
    $args = @(
        "-m", "rag_builder.cli", "ingest",
        "--publisher", "OWASP",
        "--collection", "Cornucopia Mobile App",
        "--document-name", "Cornucopia Mobile App Card",
        "--edition", $cornucopiaVersion,
        "--dataset-id", "owasp_cornucopia_mobileapp_cards",
        "--version", $cornucopiaVersion,
        "--use-llm",
        "--enrich-tags",
        "--use-postgres",
        "--preserve-source",
        "--source", $source.url,
        "--item-id", $source.id
    )

    Write-Host ("Running: python " + ($args -join " ")) -ForegroundColor Gray
    try {
        # & python @args
        Write-Host @args
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