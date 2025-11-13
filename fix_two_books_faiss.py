#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_two_books_faiss.py - Fix FAISS indexes for SAFe and Kagan books
====================================================================
After renaming chunks files, need to:
1. Update book_name field inside chunks
2. Create FAISS indexes

Version: 1.0.0
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from am_logging import setup_logging
from am_embed import AmEmbed

# Setup logging
logger = setup_logging("fix_two_books_faiss", level="INFO")


def update_book_name_in_chunks(chunks_path: Path, new_book_name: str):
    """Update book_name field in all chunks."""
    logger.info(f"Updating book_name in {chunks_path.name} to '{new_book_name}'")

    # Read all chunks
    chunks = []
    with open(chunks_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i == 0:  # Skip header
                chunks.append(line.strip())
                continue

            chunk = json.loads(line)
            chunk['book_name'] = new_book_name
            chunks.append(json.dumps(chunk, ensure_ascii=False))

    # Write back
    with open(chunks_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(chunks))

    logger.info(f"Updated {len(chunks)-1} chunks")


def create_faiss_index(chunks_path: Path, config: dict):
    """Create FAISS index from chunks."""
    logger.info(f"Creating FAISS index for {chunks_path.name}")

    embedder = AmEmbed(config=config)
    result = embedder.process(chunks_path)

    if result['status'] == 'success':
        logger.info(f"[OK] FAISS index created: {result['index_path']}")
        logger.info(f"  Vectors: {result['total_chunks']}")
        return True
    else:
        logger.error(f"[FAIL] Failed to create FAISS index: {result.get('error')}")
        return False


def main():
    """Main entry point."""
    print("=" * 70)
    print("  FIXING FAISS INDEXES FOR 2 BOOKS")
    print("=" * 70)
    print("")

    # Books to fix
    books = [
        {
            'old_name': 'baza-znanij-safe®-russia',
            'new_name': 'baza_znanij_safe_russia',
            'chunks_path': Path('data/datasets/chunks/baza_znanij_safe_russia.dataset.chunks.jsonl')
        },
        {
            'old_name': 'каган_марти_-_вдохновленные_-_2020',
            'new_name': 'kagan_marti_vdohnovlennye_2020',
            'chunks_path': Path('data/datasets/chunks/kagan_marti_vdohnovlennye_2020.dataset.chunks.jsonl')
        }
    ]

    # Config for embedding
    config = {
        'embedding': {
            'provider': 'ollama',
            'model': 'bge-m3',
            'dimensions': 384
        },
        'paths': {
            'indexes': 'data/indexes/faiss'
        }
    }

    success_count = 0

    for book in books:
        print(f"\n[{book['new_name']}]")
        print(f"  Old name: {book['old_name']}")
        print(f"  Chunks: {book['chunks_path']}")

        if not book['chunks_path'].exists():
            print(f"  [SKIP] Chunks file not found")
            continue

        # Update book_name
        update_book_name_in_chunks(book['chunks_path'], book['new_name'])

        # Create FAISS index
        if create_faiss_index(book['chunks_path'], config):
            success_count += 1
            print(f"  [OK] Successfully fixed")
        else:
            print(f"  [FAIL] Failed to create FAISS index")

    print("")
    print("=" * 70)
    print(f"  RESULTS: {success_count}/{len(books)} books fixed")
    print("=" * 70)

    return 0 if success_count == len(books) else 1


if __name__ == '__main__':
    sys.exit(main())
