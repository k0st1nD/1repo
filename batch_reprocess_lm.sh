#!/usr/bin/bash
# Batch reprocessing script with LM extraction
# Reprocesses all 20 books with fixed LM summarization
# Usage: ./batch_reprocess_lm.sh

# Configuration
CONFIG="config/batch_full.yaml"
SOURCE_DIR="data/sources"
LOG_DIR="logs/batch_lm_v3"
EXCLUDE="Ядро 2025-08-29.pdf"

# Create log directory
mkdir -p "$LOG_DIR"

# Counters
total=0
success=0
failed=0
start_time=$(date +%s)

# Validate source files first
echo "================================================================"
echo "  BATCH REPROCESSING WITH LM EXTRACTION"
echo "  Started: $(date)"
echo "  Config: $CONFIG"
echo "  LM Model: qwen2.5:7b (via Ollama)"
echo "================================================================"
echo ""

echo "Step 1: Validating source files..."
echo "----------------------------------------"
python tools/validate_sources.py -d "$SOURCE_DIR" --non-interactive

if [ $? -ne 0 ]; then
    echo ""
    echo "[WARNING] Source validation found issues!"
    echo "Run 'python tools/validate_sources.py --auto-rename' to fix."
    echo ""
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted by user"
        exit 1
    fi
fi

echo ""
echo "Step 2: Processing books..."
echo "----------------------------------------"
echo ""

# Process each PDF
for pdf in "$SOURCE_DIR"/*.pdf; do
    filename=$(basename "$pdf")

    # Skip excluded file
    if [ "$filename" == "$EXCLUDE" ]; then
        echo "[SKIP] $filename (excluded)"
        continue
    fi

    total=$((total + 1))
    echo ""
    echo "[$total] Processing: $filename"
    echo "----------------------------------------"

    # Run pipeline (full pipeline from structural to embed)
    log_file="$LOG_DIR/${filename%.pdf}.log"

    if python run_mvp.py -i "$pdf" -c "$CONFIG" --start structural > "$log_file" 2>&1; then
        success=$((success + 1))
        echo "[OK] ✓ Success"
    else
        failed=$((failed + 1))
        echo "[FAIL] ✗ Failed (see $log_file)"
    fi

    # Progress + time estimate
    elapsed=$(($(date +%s) - start_time))
    avg_time=$((elapsed / total))
    remaining=$((20 - total))
    eta=$((remaining * avg_time))
    eta_min=$((eta / 60))

    echo "Stats: $success OK / $failed FAIL / $total total"
    echo "Time: ${elapsed}s elapsed, ~${eta_min}min remaining"
done

end_time=$(date +%s)
total_time=$((end_time - start_time))
total_min=$((total_time / 60))

echo ""
echo "================================================================"
echo "  BATCH REPROCESSING COMPLETE"
echo "================================================================"
echo "Total processed: $total"
echo "Successful: $success"
echo "Failed: $failed"
echo "Total time: ${total_min} minutes"
echo "Completion time: $(date)"
echo "================================================================"

# Show any errors
if [ $failed -gt 0 ]; then
    echo ""
    echo "Failed files:"
    grep -l "ERROR\|FAIL" "$LOG_DIR"/*.log | xargs -n1 basename
fi

exit 0
