#!/usr/bin/env python3
"""
Create unified multi-book FAISS index from individual book indexes.
Merges all embeddings into single searchable index.
"""

import sys
import json
import pickle
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

try:
    import faiss
except ImportError:
    print("ERROR: faiss not installed. Install with: pip install faiss-cpu")
    sys.exit(1)


class UnifiedIndexBuilder:
    """Builds unified FAISS index from multiple book indexes."""

    def __init__(self, index_dir: str = "data/indexes/faiss",
                 metadata_dir: str = "data/indexes/metadata"):
        self.index_dir = Path(index_dir)
        self.metadata_dir = Path(metadata_dir)

    def find_all_indexes(self, exclude_patterns: List[str] = None) -> List[Path]:
        """Find all .faiss index files."""
        indexes = sorted(self.index_dir.glob("*.faiss"))

        # Exclude problematic files (encoding issues)
        if exclude_patterns:
            filtered = []
            for idx in indexes:
                skip = False
                for pattern in exclude_patterns:
                    if pattern in str(idx):
                        print(f"Excluding: {idx.name} (pattern: {pattern})")
                        skip = True
                        break
                if not skip:
                    filtered.append(idx)
            indexes = filtered

        print(f"Found {len(indexes)} FAISS indexes")
        return indexes

    def load_index_and_metadata(self, index_path: Path) -> tuple:
        """Load FAISS index and its metadata."""
        # Load FAISS index
        index = faiss.read_index(str(index_path))

        # Load metadata (.pkl file) - try both naming patterns
        book_name = index_path.stem  # e.g., "book.dataset"

        # Try .dataset.pkl first, then .dataset.dataset.pkl
        metadata_path = self.metadata_dir / f"{book_name}.pkl"
        if not metadata_path.exists():
            metadata_path = self.metadata_dir / f"{book_name}.dataset.pkl"

        if not metadata_path.exists():
            print(f"WARNING: Metadata not found for {book_name}")
            return index, None

        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)

        return index, metadata

    def create_unified_index(self, output_name: str = "library_unified",
                             exclude_patterns: List[str] = None):
        """Create unified index from all individual indexes."""
        print("\n" + "="*70)
        print("  CREATING UNIFIED MULTI-BOOK INDEX")
        print("="*70 + "\n")

        # Find all indexes
        index_paths = self.find_all_indexes(exclude_patterns=exclude_patterns)

        if not index_paths:
            print("ERROR: No indexes found!")
            return

        # Load first index to get dimension
        first_index, first_metadata = self.load_index_and_metadata(index_paths[0])
        dimension = first_index.d

        print(f"Index dimension: {dimension}")
        print(f"Creating Flat index with cosine similarity...\n")

        # Create unified index (Flat L2 for quality)
        unified_index = faiss.IndexFlatL2(dimension)

        # Unified metadata storage
        unified_metadata = {
            "chunks": [],
            "books": [],
            "total_chunks": 0,
            "dimension": dimension,
            "created_at": datetime.now().isoformat(),
            "index_type": "Flat",
            "num_books": len(index_paths)
        }

        chunk_offset = 0

        # Merge all indexes
        for idx, index_path in enumerate(index_paths, 1):
            book_name = index_path.stem
            print(f"[{idx}/{len(index_paths)}] Merging: {book_name}")

            # Load index and metadata
            book_index, book_metadata = self.load_index_and_metadata(index_path)

            if book_metadata is None:
                print(f"  Skipping {book_name} (no metadata)")
                continue

            # Get vectors from book index
            num_vectors = book_index.ntotal
            vectors = np.zeros((num_vectors, dimension), dtype=np.float32)

            for i in range(num_vectors):
                vectors[i] = book_index.reconstruct(i)

            # Add to unified index
            unified_index.add(vectors)

            # Merge metadata (handle both dict and list formats)
            if isinstance(book_metadata, dict):
                book_chunks = book_metadata.get("chunks", [])
            elif isinstance(book_metadata, list):
                book_chunks = book_metadata
            else:
                print(f"  WARNING: Unknown metadata format, skipping")
                continue

            # Add book info to each chunk
            for i, chunk in enumerate(book_chunks):
                if isinstance(chunk, dict):
                    chunk["book_name"] = book_name
                    chunk["chunk_global_id"] = chunk_offset + i
                    chunk["original_chunk_id"] = chunk.get("chunk_id", i)

            unified_metadata["chunks"].extend(book_chunks)
            unified_metadata["books"].append({
                "name": book_name,
                "num_chunks": len(book_chunks),
                "chunk_offset": chunk_offset,
                "index_range": [chunk_offset, chunk_offset + len(book_chunks)]
            })

            chunk_offset += len(book_chunks)

            print(f"  Added {num_vectors} vectors ({len(book_chunks)} chunks)")

        unified_metadata["total_chunks"] = chunk_offset

        # Save unified index
        output_index_path = self.index_dir / f"{output_name}.faiss"
        output_metadata_path = self.metadata_dir / f"{output_name}.dataset.pkl"
        output_info_path = self.metadata_dir / f"{output_name}.info.json"

        print(f"\nSaving unified index...")
        faiss.write_index(unified_index, str(output_index_path))

        print(f"Saving metadata...")
        with open(output_metadata_path, 'wb') as f:
            pickle.dump(unified_metadata, f, protocol=pickle.HIGHEST_PROTOCOL)

        # Save human-readable info
        info = {
            "name": output_name,
            "created_at": unified_metadata["created_at"],
            "num_books": unified_metadata["num_books"],
            "total_chunks": unified_metadata["total_chunks"],
            "dimension": dimension,
            "index_type": "Flat (L2)",
            "books": [
                {"name": b["name"], "chunks": b["num_chunks"]}
                for b in unified_metadata["books"]
            ]
        }

        with open(output_info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)

        # Print summary
        print("\n" + "="*70)
        print("  UNIFIED INDEX CREATED SUCCESSFULLY")
        print("="*70)
        print(f"Name: {output_name}")
        print(f"Books: {unified_metadata['num_books']}")
        print(f"Total chunks: {unified_metadata['total_chunks']}")
        print(f"Dimension: {dimension}")
        print(f"\nFiles created:")
        print(f"  - {output_index_path}")
        print(f"  - {output_metadata_path}")
        print(f"  - {output_info_path}")
        print("="*70 + "\n")

        return unified_index, unified_metadata


def main():
    """Main entry point."""
    import sys

    # Parse args
    exclude_yadro = "--exclude-yadro" in sys.argv

    print("Starting unified index creation...\n")

    builder = UnifiedIndexBuilder()

    # Exclude Ядро and old unified indexes
    exclude_patterns = ["yadro", "Ядро", "library_unified"] if exclude_yadro else ["library_unified"]

    builder.create_unified_index(
        output_name="library_unified",
        exclude_patterns=exclude_patterns
    )

    print("\nDone! Unified index ready for search.")


if __name__ == "__main__":
    main()
