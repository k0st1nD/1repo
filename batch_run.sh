#!/bin/bash
# Simple batch processing for all PDFs

CONFIG="config/batch_full.yaml"
SOURCE_DIR="data/sources"
LOG_DIR="logs/batch_v2"
EXCLUDE="Ядро 2025-08-29.pdf"

mkdir -p "$LOG_DIR"

total=0
success=0
failed=0

echo "================================================================"
echo "  BATCH PROCESSING START - $(date)"
echo "================================================================"

for pdf in "$SOURCE_DIR"/*.pdf; do
    filename=$(basename "$pdf")
    
    if [ "$filename" == "$EXCLUDE" ]; then
        echo "[SKIP] $filename"
        continue
    fi
    
    total=$((total + 1))
    echo ""
    echo "[$total] $filename"
    
    log_file="$LOG_DIR/${filename%.pdf}.log"
    
    if python run_mvp.py -i "$pdf" -c "$CONFIG" --start structural > "$log_file" 2>&1; then
        success=$((success + 1))
        echo "  [OK] Success"
    else
        failed=$((failed + 1))
        echo "  [FAIL] See $log_file"
    fi
    
    echo "  Progress: $success OK / $failed FAIL / $total total"
done

echo ""
echo "================================================================"
echo "Total: $total | Success: $success | Failed: $failed"
echo "Completed: $(date)"
echo "================================================================"
