#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Ollama embedding integration

Quick test to verify Ollama embeddings work.
"""

import sys
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("Ollama Embedding Integration Test")
print("=" * 60)
print()

try:
    import requests
    print("[OK] requests library available")
except ImportError:
    print("[ERROR] requests not installed")
    print("Install: pip install requests")
    sys.exit(1)

# Test Ollama connectivity
print("Testing Ollama server...")
try:
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    if response.status_code == 200:
        print("[OK] Ollama server is running")
        models = response.json().get('models', [])
        print(f"Available models: {len(models)}")
        for model in models:
            print(f"  - {model.get('name')}")
    else:
        print(f"[ERROR] Ollama returned status {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] Cannot connect to Ollama: {e}")
    print("Make sure Ollama is running: ollama serve")
    sys.exit(1)

print()
print("Testing embedding generation...")

# Test single embedding
test_text = "This is a test sentence for embeddings."
payload = {
    "model": "bge-m3",
    "prompt": test_text
}

try:
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json=payload,
        timeout=60
    )
    response.raise_for_status()

    result = response.json()
    embedding = result.get('embedding')

    if embedding:
        print(f"[OK] Got embedding from Ollama")
        print(f"Dimension: {len(embedding)}")
        print(f"Sample values: {embedding[:5]}")
    else:
        print("[ERROR] No embedding in response")
        sys.exit(1)

except Exception as e:
    print(f"[ERROR] Failed to get embedding: {e}")
    sys.exit(1)

print()
print("Testing EmbeddingEngine with Ollama provider...")

try:
    from am_embed import EmbeddingEngine
    print("[OK] Imported EmbeddingEngine")
except ImportError as e:
    print(f"[ERROR] Cannot import EmbeddingEngine: {e}")
    sys.exit(1)

# Create config
config = {
    'provider': 'ollama',
    'model': 'bge-m3',
    'batch_size': 4,
    'normalize': True,
    'ollama': {
        'base_url': 'http://localhost:11434',
        'timeout': 60,
        'max_retries': 3,
        'retry_delay': 1.0
    }
}

try:
    engine = EmbeddingEngine(config)
    print(f"[OK] EmbeddingEngine initialized")
    print(f"Provider: {engine.provider}")
    print(f"Model: {engine.model_name}")
    print(f"Embedding dim: {engine.embedding_dim}")
except Exception as e:
    print(f"[ERROR] Failed to initialize engine: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("Testing batch encoding...")

test_texts = [
    "First test sentence.",
    "Second test sentence.",
    "Third test sentence.",
    "Fourth test sentence."
]

try:
    embeddings = engine.encode_batch(test_texts)
    print(f"[OK] Batch encoding successful")
    print(f"Shape: {embeddings.shape}")
    print(f"Dtype: {embeddings.dtype}")
    print(f"Sample: {embeddings[0, :5]}")
except Exception as e:
    print(f"[ERROR] Batch encoding failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("SUCCESS! Ollama embedding integration works!")
print("=" * 60)
print()
print("You can now use Ollama for embeddings in the pipeline.")
print("Config is already set to provider='ollama' in mvp_fast.yaml")
print()
