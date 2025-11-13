#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download embedding model for sentence-transformers

This script downloads BAAI/bge-m3 model to HuggingFace cache
so it can be used offline later.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("BGE-M3 Model Download for sentence-transformers")
print("=" * 60)
print()

try:
    from sentence_transformers import SentenceTransformer
    print("[OK] sentence-transformers is installed")
except ImportError:
    print("[ERROR] sentence-transformers not installed")
    print("Install: pip install sentence-transformers")
    sys.exit(1)

MODEL_NAME = "BAAI/bge-m3"
print(f"Downloading model: {MODEL_NAME}")
print(f"Size: ~1.5 GB (1024-dimensional embeddings)")
print()
print("This may take 5-15 minutes depending on your connection...")
print()

try:
    # Download and cache the model
    print("Starting download...")
    model = SentenceTransformer(MODEL_NAME)

    print()
    print("[OK] Model downloaded successfully!")
    print(f"Embedding dimension: {model.get_sentence_embedding_dimension()}")
    print()

    # Test the model
    print("Testing model with sample text...")
    test_text = "This is a test sentence for embeddings."
    embedding = model.encode(test_text)

    print(f"[OK] Test embedding shape: {embedding.shape}")
    print()
    print("=" * 60)
    print("SUCCESS! Model is ready to use offline.")
    print("=" * 60)
    print()
    print("To use sentence-transformers in config/mvp_fast.yaml:")
    print('  provider: "sentence-transformers"')
    print('  model: "BAAI/bge-m3"')
    print()

except Exception as e:
    print()
    print(f"[ERROR] Failed to download model: {e}")
    print()
    print("Possible issues:")
    print("- No internet connection")
    print("- HuggingFace Hub is down")
    print("- Not enough disk space (~1.5 GB needed)")
    print("- Network timeout")
    sys.exit(1)
