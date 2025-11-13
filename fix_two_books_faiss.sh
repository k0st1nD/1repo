#!/usr/bin/bash
# Fix FAISS indexes for 2 books that failed due to filename issues
# After renaming, we need to create FAISS indexes from existing chunks

CONFIG="config/batch_full.yaml"
LOG_DIR="logs/fix_faiss"

mkdir -p "$LOG_DIR"

echo "================================================================"
echo "  FIXING FAISS INDEXES FOR 2 BOOKS"
echo "================================================================"
echo ""

# Book 1: SAFe (previously had ® symbol)
echo "[1] Processing: baza_znanij_safe_russia"
python run_mvp.py \
    -i "data/datasets/chunks/baza_znanij_safe_russia.dataset.chunks.jsonl" \
    -c "$CONFIG" \
    --start embed \
    > "$LOG_DIR/safe.log" 2>&1

if [ $? -eq 0 ]; then
    echo "    [OK] FAISS index created"
else
    echo "    [FAIL] See logs/fix_faiss/safe.log"
fi

# Book 2: Kagan (previously had Cyrillic)
echo "[2] Processing: kagan_marti_vdohnovlennye_2020"
python run_mvp.py \
    -i "data/datasets/chunks/kagan_marti_vdohnovlennye_2020.dataset.chunks.jsonl" \
    -c "$CONFIG" \
    --start embed \
    > "$LOG_DIR/kagan.log" 2>&1

if [ $? -eq 0 ]; then
    echo "    [OK] FAISS index created"
else
    echo "    [FAIL] See logs/fix_faiss/kagan.log"
fi

echo ""
echo "================================================================"
echo "  DONE - Check data/indexes/faiss/ for new files"
echo "================================================================"
