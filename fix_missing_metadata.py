#!/usr/bin/env python3
"""
Fix missing metadata files by recreating them from chunk files.
"""

import json
import pickle
from pathlib import Path
from datetime import datetime

def create_metadata_from_chunks(chunk_file: Path, output_pkl: Path):
    """Create .pkl metadata from .chunks.jsonl file."""
    print(f"Processing: {chunk_file.name}")

    # Load chunks
    chunks = []
    with open(chunk_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    # Create metadata structure
    metadata = {
        "chunks": chunks,
        "book_name": chunk_file.stem.replace('.chunks', ''),
        "total_chunks": len(chunks),
        "created_at": datetime.now().isoformat(),
        "source": "reconstructed_from_chunks"
    }

    # Save as pickle
    with open(output_pkl, 'wb') as f:
        pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"  Created: {output_pkl.name} ({len(chunks)} chunks)")

def main():
    chunks_dir = Path("data/datasets/chunks")
    metadata_dir = Path("data/indexes/metadata")

    # Find all chunk files
    chunk_files = list(chunks_dir.glob("*.chunks.jsonl"))
    print(f"Found {len(chunk_files)} chunk files\n")

    # Check which need metadata
    for chunk_file in chunk_files:
        # Determine expected metadata filename
        book_name = chunk_file.stem.replace('.chunks', '')
        metadata_file = metadata_dir / f"{book_name}.dataset.pkl"

        if not metadata_file.exists():
            print(f"Missing metadata for: {book_name}")
            create_metadata_from_chunks(chunk_file, metadata_file)
            print()

    print("Done!")

if __name__ == "__main__":
    main()
