#!/usr/bin/bash
# Parallel batch processing script
# Processes multiple books simultaneously
# Usage: ./batch_parallel.sh

CONFIG="config/batch_full.yaml"
SOURCE_DIR="data/sources"
LOG_DIR="logs/batch_parallel"
EXCLUDE="Ядро 2025-08-29.pdf"
PARALLEL_JOBS=3  # Number of books to process simultaneously

mkdir -p "$LOG_DIR"

# Counter files
mkdir -p /tmp/batch_counters
echo "0" > /tmp/batch_counters/success
echo "0" > /tmp/batch_counters/failed
echo "0" > /tmp/batch_counters/total

start_time=$(date +%s)

echo "================================================================"
echo "  PARALLEL BATCH PROCESSING WITH LM EXTRACTION"
echo "  Started: $(date)"
echo "  Config: $CONFIG"
echo "  Parallel jobs: $PARALLEL_JOBS"
echo "  LM Model: qwen2.5:7b (via Ollama)"
echo "================================================================"
echo ""

# Validate sources
echo "Validating source files..."
python tools/validate_sources.py -d "$SOURCE_DIR" --non-interactive
if [ $? -ne 0 ]; then
    echo "[ERROR] Source validation failed. Run: python tools/validate_sources.py --auto-rename"
    exit 1
fi
echo ""

# Process function
process_book() {
    local pdf="$1"
    local idx="$2"
    local filename=$(basename "$pdf")
    local log_file="$LOG_DIR/${filename%.pdf}.log"

    echo "[$idx] Processing: $filename (PID: $$)"

    if python run_mvp.py -i "$pdf" -c "$CONFIG" --start structural > "$log_file" 2>&1; then
        echo "[$idx] ✓ SUCCESS: $filename"
        echo $(($(cat /tmp/batch_counters/success) + 1)) > /tmp/batch_counters/success
    else
        echo "[$idx] ✗ FAILED: $filename"
        echo $(($(cat /tmp/batch_counters/failed) + 1)) > /tmp/batch_counters/failed
    fi
}

export -f process_book
export CONFIG LOG_DIR

# Get list of PDFs
idx=0
for pdf in "$SOURCE_DIR"/*.pdf; do
    filename=$(basename "$pdf")

    # Skip excluded
    if [ "$filename" == "$EXCLUDE" ]; then
        continue
    fi

    idx=$((idx + 1))
    echo "$pdf" >> /tmp/batch_list.txt
done

total_books=$(wc -l < /tmp/batch_list.txt)
echo "Total books to process: $total_books"
echo ""

# Process in parallel using xargs
cat /tmp/batch_list.txt | \
    nl -w1 -s' ' | \
    xargs -n2 -P$PARALLEL_JOBS bash -c 'process_book "$1" "$0"'

# Final stats
end_time=$(date +%s)
total_time=$((end_time - start_time))
total_min=$((total_time / 60))

success=$(cat /tmp/batch_counters/success)
failed=$(cat /tmp/batch_counters/failed)

echo ""
echo "================================================================"
echo "  PARALLEL BATCH PROCESSING COMPLETE"
echo "================================================================"
echo "Total processed: $total_books"
echo "Successful: $success"
echo "Failed: $failed"
echo "Total time: ${total_min} minutes (parallel with $PARALLEL_JOBS jobs)"
echo "Completion time: $(date)"
echo "================================================================"

# Cleanup
rm -f /tmp/batch_list.txt
rm -rf /tmp/batch_counters

exit 0
