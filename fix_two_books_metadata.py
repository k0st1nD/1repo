#!/usr/bin/env python3
"""
Create metadata for the two problematic books (SAFe and Kagan).
"""

import json
import pickle
from pathlib import Path
from datetime import datetime

def create_metadata(chunk_file: Path, index_name: str, output_dir: Path):
    """Create metadata PKL file from chunks JSONL."""
    print(f"Processing: {chunk_file.name}")
    print(f"  Target index: {index_name}")

    # Load chunks
    chunks = []
    with open(chunk_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    # Create metadata
    metadata = {
        "chunks": chunks,
        "book_name": index_name.replace('.dataset', ''),
        "total_chunks": len(chunks),
        "created_at": datetime.now().isoformat(),
        "source": "fixed_from_chunks"
    }

    # Save
    output_file = output_dir / f"{index_name}.pkl"
    with open(output_file, 'wb') as f:
        pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"  Created: {output_file.name} ({len(chunks)} chunks)\n")

def main():
    chunks_dir = Path("data/datasets/chunks")
    metadata_dir = Path("data/indexes/metadata")

    # Mapping: chunk_file_pattern -> target_index_name
    mappings = {
        "baza-znanij-safe": "baza-znanij-safe-russia.dataset",
        "каган": "kagan_inspired_2020.dataset"
    }

    for pattern, index_name in mappings.items():
        # Find chunk file
        chunk_files = list(chunks_dir.glob(f"*{pattern}*.chunks.jsonl"))

        if not chunk_files:
            print(f"ERROR: No chunk file found for pattern '{pattern}'")
            continue

        chunk_file = chunk_files[0]
        create_metadata(chunk_file, index_name, metadata_dir)

    print("Done! Both metadata files created.")

if __name__ == "__main__":
    main()
