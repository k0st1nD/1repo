#!/usr/bin/bash
# Simple batch processing script for all PDFs
# Usage: ./batch_simple.sh

# Configuration
CONFIG="config/batch_full.yaml"
SOURCE_DIR="data/sources"
LOG_DIR="logs/batch_v2"
EXCLUDE="Ядро 2025-08-29.pdf"

# Create log directory
mkdir -p "$LOG_DIR"

# Counter
total=0
success=0
failed=0

# Get list of PDFs (excluding Ядро)
echo "================================================================"
echo "  BATCH PROCESSING START - $(date)"
echo "  Config: $CONFIG"
echo "================================================================"
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

    # Run pipeline
    log_file="$LOG_DIR/${filename%.pdf}.log"

    if python run_mvp.py -i "$pdf" -c "$CONFIG" --start structural > "$log_file" 2>&1; then
        success=$((success + 1))
        echo "[OK] ✓ Success"
    else
        failed=$((failed + 1))
        echo "[FAIL] ✗ Failed (see $log_file)"
    fi

    # Progress
    echo "Stats: $success OK / $failed FAIL / $total total"
done

echo ""
echo "================================================================"
echo "  BATCH PROCESSING COMPLETE"
echo "================================================================"
echo "Total processed: $total"
echo "Successful: $success"
echo "Failed: $failed"
echo "Completion time: $(date)"
echo "================================================================"

exit 0
