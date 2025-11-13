# PowerShell script for full library reprocessing with LM extraction
# Version: 2.0
# Usage: .\reprocess_all_with_lm.ps1 -ParallelJobs 2

param(
    [switch]$DryRun,
    [int]$ParallelJobs = 1
)

$ErrorActionPreference = "Continue"

Write-Host "================================================================================"
Write-Host "  ARCHIVIST MAGIKA v2.0 - FULL REPROCESSING WITH LM" -ForegroundColor Yellow
Write-Host "================================================================================"
Write-Host ""
Write-Host "Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host "Parallel jobs: $ParallelJobs" -ForegroundColor Gray
Write-Host "Dry run: $DryRun" -ForegroundColor Gray
Write-Host ""

# Configuration
$CONFIG = "config/batch_full.yaml"
$SOURCE_DIR = "data/sources"
$LOG_DIR_REGULAR = "logs/batch_lm_final"
$LOG_DIR_YADRO = "logs/yadro_lm_final"

# Create directories
New-Item -ItemType Directory -Force -Path $LOG_DIR_REGULAR | Out-Null
New-Item -ItemType Directory -Force -Path $LOG_DIR_YADRO | Out-Null

# Books without LM metadata (need reprocessing)
$BOOKS_WITHOUT_LM = @(
    "2024_final_dora_report.pdf",
    "Actionable_Agile_Metrics_for_Predictability_An_Introduction_-_Daniel_S_Vacanti.pdf",
    "Agile_Conversations_-_Douglas_SquirrelJeffrey_Fredrick.pdf",
    "Continuous_Discovery_Habits_-_Teresa_Torres.pdf",
    "data-driven-organization.pdf",
    "Data-Science-for-Business.pdf",
    "Escaping_the_build_trap_-_Melissa_Perri.pdf",
    "Forsgren N., Humble J., Kim G.- Accelerate. The Science of DevOps - 2018.pdf",
    "GOOD-STRATEGY-BAD-STRATEGY.pdf",
    "Hooked-How-to-Build-Habit-Forming-Products.pdf",
    "Каган Марти - Вдохновленные - 2020.pdf",
    "Lean_Analytics.pdf",
    "measure-what-matters-by-john-doerr.pdf",
    "naked-statistics-pdf.pdf",
    "Playing_to_Win__How_Strategy_Really_Works_-_AG_Lafley.pdf",
    "Project Management Institute - PMBOK 7.pdf",
    "Team_Topologies_Organizing_Business_and_Technology_Teams_for_Fast_Flow_-_Matthew_Skelton.pdf"
)

$YADRO = "Yadro 2025-08-29.pdf"

# Check Ollama
Write-Host "[1/5] Checking Ollama..." -ForegroundColor Cyan
Write-Host "----------------------------------------"

try {
    $null = ollama list 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Ollama is running" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Ollama not running" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Cannot check Ollama" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Validate files
Write-Host "[2/5] Validating source files..." -ForegroundColor Cyan
Write-Host "----------------------------------------"

python tools/validate_sources.py -d $SOURCE_DIR --non-interactive

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[WARN] Found issues with filenames" -ForegroundColor Yellow
    $continue = Read-Host "Continue? (y/N)"
    if ($continue -ne "y") {
        exit 1
    }
}

Write-Host ""

# Start monitor
Write-Host "[3/5] Starting real-time monitor..." -ForegroundColor Cyan
Write-Host "----------------------------------------"

$monitorScript = "Write-Host 'Monitor started' -ForegroundColor Cyan; python tools/monitor_realtime.py --log-dir '$LOG_DIR_REGULAR' --refresh 5"
$monitorScriptPath = "logs/start_monitor.ps1"
$monitorScript | Out-File -FilePath $monitorScriptPath -Encoding UTF8

Start-Process powershell -ArgumentList "-NoExit", "-File", $monitorScriptPath

Write-Host "[OK] Monitor started in separate window" -ForegroundColor Green
Write-Host ""
Start-Sleep -Seconds 2

# Process Yadro
Write-Host "[4/5] Processing Yadro (background)..." -ForegroundColor Cyan
Write-Host "----------------------------------------"

$yadroPath = Join-Path $SOURCE_DIR $YADRO
$yadroLog = Join-Path $LOG_DIR_YADRO "yadro_processing.log"

if (Test-Path $yadroPath) {
    Write-Host "[START] $YADRO" -ForegroundColor Yellow

    if (-not $DryRun) {
        $yadroJob = Start-Job -ScriptBlock {
            param($pdf, $config, $log)
            python run_mvp.py -i $pdf -c $config --start structural 2>&1 | Tee-Object -FilePath $log
        } -ArgumentList $yadroPath, $CONFIG, $yadroLog

        Write-Host "[OK] Yadro started (Job ID: $($yadroJob.Id))" -ForegroundColor Green
    }
} else {
    Write-Host "[SKIP] Yadro not found" -ForegroundColor Yellow
}

Write-Host ""

# Process library
Write-Host "[5/5] Processing library ($($BOOKS_WITHOUT_LM.Count) books)..." -ForegroundColor Cyan
Write-Host "----------------------------------------"
Write-Host ""

$startTime = Get-Date
$processed = 0
$succeeded = 0
$failed = 0

foreach ($book in $BOOKS_WITHOUT_LM) {
    $processed++
    $pdfPath = Join-Path $SOURCE_DIR $book

    if (-not (Test-Path $pdfPath)) {
        Write-Host "[$processed] SKIP: $book (not found)" -ForegroundColor Yellow
        continue
    }

    $logName = [System.IO.Path]::GetFileNameWithoutExtension($book) + ".log"
    $logPath = Join-Path $LOG_DIR_REGULAR $logName

    Write-Host "[$processed/$($BOOKS_WITHOUT_LM.Count)] $book" -ForegroundColor White

    if ($DryRun) {
        Write-Host "  [DRY RUN] Skipped" -ForegroundColor Gray
        continue
    }

    try {
        $proc = Start-Process python -ArgumentList "run_mvp.py", "-i", "`"$pdfPath`"", "-c", $CONFIG, "--start", "structural" `
                                      -RedirectStandardOutput $logPath `
                                      -RedirectStandardError "$logPath.err" `
                                      -NoNewWindow -Wait -PassThru

        if ($proc.ExitCode -eq 0) {
            Write-Host "  [OK] Success" -ForegroundColor Green
            $succeeded++
        } else {
            Write-Host "  [FAIL] Exit code: $($proc.ExitCode)" -ForegroundColor Red
            $failed++
        }
    } catch {
        Write-Host "  [ERROR] $_" -ForegroundColor Red
        $failed++
    }

    # Show progress
    $elapsed = (Get-Date) - $startTime
    if ($processed -gt 0) {
        $eta = [TimeSpan]::FromSeconds(($BOOKS_WITHOUT_LM.Count - $processed) * ($elapsed.TotalSeconds / $processed))
        Write-Host "  Progress: $processed/$($BOOKS_WITHOUT_LM.Count) | OK: $succeeded | FAIL: $failed | ETA: $($eta.ToString('hh\:mm\:ss'))" -ForegroundColor Cyan
    }
    Write-Host ""
}

# Final report
$endTime = Get-Date
$totalTime = $endTime - $startTime

Write-Host ""
Write-Host "================================================================================"
Write-Host "  PROCESSING COMPLETED" -ForegroundColor Green
Write-Host "================================================================================"
Write-Host ""
Write-Host "Processed: $processed books" -ForegroundColor White
Write-Host "Success:   $succeeded" -ForegroundColor Green
Write-Host "Failed:    $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host "Time:      $($totalTime.ToString('hh\:mm\:ss'))" -ForegroundColor White
Write-Host ""

# Check Yadro status
$yadroJob = Get-Job | Where-Object { $_.State -eq 'Running' } | Select-Object -First 1
if ($yadroJob) {
    Write-Host "Yadro: STILL PROCESSING (Job ID: $($yadroJob.Id))" -ForegroundColor Yellow
    Write-Host "  Check: Get-Job -Id $($yadroJob.Id)" -ForegroundColor Gray
    Write-Host "  Wait: Wait-Job -Id $($yadroJob.Id)" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "================================================================================"
Write-Host "  NEXT STEPS" -ForegroundColor Yellow
Write-Host "================================================================================"
Write-Host ""
Write-Host "1. Check LM metadata:" -ForegroundColor White
Write-Host "   python -c `"exec('from pathlib import Path; import json; [print(f.stem) for f in Path(`\"data/datasets/extended`\").glob(`\"*.jsonl`\")]')`"" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Create unified index:" -ForegroundColor White
Write-Host "   python create_unified_index.py" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Validate chunks:" -ForegroundColor White
Write-Host "   python validate.py -d data/datasets/chunks --stage chunks --pattern '*.chunks.jsonl'" -ForegroundColor Gray
Write-Host ""
