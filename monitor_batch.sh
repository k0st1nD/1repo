#!/usr/bin/bash
# Monitor batch processing progress
# Usage: ./monitor_batch.sh

LOG_FILE="logs/batch_lm_v3.log"

while true; do
    clear
    echo "================================================================"
    echo "  BATCH PROCESSING MONITOR - $(date +%H:%M:%S)"
    echo "================================================================"
    echo ""

    # Show current processing status
    tail -5 "$LOG_FILE" 2>/dev/null || echo "Waiting for log file..."

    echo ""
    echo "----------------------------------------------------------------"

    # Count processed books
    success=$(grep -c "\[OK\]" "$LOG_FILE" 2>/dev/null || echo "0")
    failed=$(grep -c "\[FAIL\]" "$LOG_FILE" 2>/dev/null || echo "0")
    total=$((success + failed))

    echo "Progress: $success OK / $failed FAIL / $total of 20"

    # Current stage (if processing)
    current_stage=$(tail -50 logs/batch_lm_v3/*.log 2>/dev/null | grep "Stage:" | tail -1)
    if [ -n "$current_stage" ]; then
        echo "Current: $current_stage"
    fi

    echo ""
    echo "Press Ctrl+C to exit monitor"
    echo "================================================================"

    sleep 10
done
