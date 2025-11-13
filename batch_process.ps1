# Batch processing script for Windows
# Usage: .\batch_process.ps1

$CONFIG = "config/batch_full.yaml"
$SOURCE_DIR = "data/sources"
$LOG_DIR = "logs/batch_final"
$EXCLUDE = "Yadro 2025-08-29.pdf"

# Create log directory
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

# Counters
$total = 0
$success = 0
$failed = 0
$startTime = Get-Date

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  BATCH PROCESSING WITH LM EXTRACTION" -ForegroundColor Yellow
Write-Host "  Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Validate sources
Write-Host "[1/2] Validating source files..." -ForegroundColor Cyan
python tools/validate_sources.py -d $SOURCE_DIR --non-interactive

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[WARNING] Source validation found issues!" -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y") {
        exit 1
    }
}

Write-Host ""
Write-Host "[2/2] Processing books..." -ForegroundColor Cyan
Write-Host "----------------------------------------"
Write-Host ""

# Get all PDFs
$pdfs = Get-ChildItem "$SOURCE_DIR\*.pdf" | Where-Object { $_.Name -ne $EXCLUDE }
$totalBooks = $pdfs.Count

Write-Host "Found $totalBooks books to process" -ForegroundColor Gray
Write-Host ""

foreach ($pdf in $pdfs) {
    $total++
    $filename = $pdf.Name
    $logFile = Join-Path $LOG_DIR "$($pdf.BaseName).log"

    Write-Host "[$total/$totalBooks] $filename" -ForegroundColor White

    try {
        $proc = Start-Process python -ArgumentList "run_mvp.py", "-i", "`"$($pdf.FullName)`"", "-c", $CONFIG, "--start", "structural" `
                                      -RedirectStandardOutput $logFile `
                                      -RedirectStandardError "$logFile.err" `
                                      -NoNewWindow -Wait -PassThru

        if ($proc.ExitCode -eq 0) {
            Write-Host "  [OK] Success" -ForegroundColor Green
            $success++
        } else {
            Write-Host "  [FAIL] Exit code: $($proc.ExitCode)" -ForegroundColor Red
            $failed++
        }
    } catch {
        Write-Host "  [ERROR] $_" -ForegroundColor Red
        $failed++
    }

    # Progress
    $elapsed = (Get-Date) - $startTime
    if ($total -gt 0) {
        $avgTime = $elapsed.TotalSeconds / $total
        $remaining = ($totalBooks - $total) * $avgTime
        $eta = [TimeSpan]::FromSeconds($remaining)
        Write-Host "  Progress: $success OK / $failed FAIL | ETA: $($eta.ToString('hh\:mm\:ss'))" -ForegroundColor Cyan
    }
    Write-Host ""
}

# Final report
$endTime = Get-Date
$totalTime = $endTime - $startTime

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  PROCESSING COMPLETED" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Total:   $total books" -ForegroundColor White
Write-Host "Success: $success" -ForegroundColor Green
Write-Host "Failed:  $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host "Time:    $($totalTime.ToString('hh\:mm\:ss'))" -ForegroundColor White
Write-Host ""
Write-Host "Logs: $LOG_DIR" -ForegroundColor Gray
Write-Host ""
