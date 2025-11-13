#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_embed.py - Embeddings Generation (MVP v2.0)
==============================================
Stage 7: Generate embeddings and create FAISS index

Features:
- Embeddings via sentence-transformers (local)
- FAISS index creation
- Metadata storage
- Batch processing
- Quality metrics tracking

Version: 2.0.0
Dependencies: am_common, sentence-transformers, faiss-cpu, numpy
"""

import logging
import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import time

# Embeddings model (sentence-transformers)
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("[WARN] sentence-transformers not available. Install: pip install sentence-transformers")

# Ollama API client
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[WARN] requests not available. Install: pip install requests")

# FAISS
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("[ERROR] faiss not available. Install: pip install faiss-cpu")

from am_common import (
    ConfigLoader, PathManager, format_size,
    utc_now_iso
)

logger = logging.getLogger('am_embed')

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"


class EmbeddingEngine:
    """Generate embeddings using sentence-transformers or Ollama."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Provider selection: "sentence-transformers" or "ollama"
        self.provider = config.get('provider', 'sentence-transformers')

        if self.provider == 'sentence-transformers':
            self._init_sentence_transformers()
        elif self.provider == 'ollama':
            self._init_ollama()
        else:
            raise ValueError(f"Unknown embedding provider: {self.provider}")

    def _init_sentence_transformers(self):
        """Initialize sentence-transformers provider."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError("sentence-transformers is required. Install: pip install sentence-transformers")

        self.model_name = self.config.get('model', 'all-MiniLM-L6-v2')
        self.batch_size = self.config.get('batch_size', 32)
        self.normalize = self.config.get('normalize', True)

        logger.info(f"[sentence-transformers] Loading model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"[sentence-transformers] Embedding dimension: {self.embedding_dim}")

    def _init_ollama(self):
        """Initialize Ollama provider."""
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library required for Ollama. Install: pip install requests")

        # Get Ollama config (nested or at root level for backward compatibility)
        ollama_config = self.config.get('ollama', {})
        self.ollama_base_url = ollama_config.get('base_url', 'http://localhost:11434')
        self.model_name = self.config.get('model', 'bge-m3')
        self.batch_size = self.config.get('batch_size', 16)  # Smaller for network calls
        self.timeout = ollama_config.get('timeout', 60)
        self.max_retries = ollama_config.get('max_retries', 3)
        self.retry_delay = ollama_config.get('retry_delay', 1.0)
        self.normalize = self.config.get('normalize', True)

        logger.info(f"[Ollama] Using model: {self.model_name}")
        logger.info(f"[Ollama] API endpoint: {self.ollama_base_url}")

        # Check Ollama availability
        if not self._check_ollama():
            raise RuntimeError(
                f"Ollama not available at {self.ollama_base_url}. "
                f"Make sure Ollama is running: ollama serve"
            )

        # Get embedding dimension from test embedding
        logger.info(f"[Ollama] Getting embedding dimension...")
        test_embedding = self._get_ollama_embedding("test", retry=False)
        self.embedding_dim = len(test_embedding)
        logger.info(f"[Ollama] Embedding dimension: {self.embedding_dim}")

    def _check_ollama(self) -> bool:
        """Check if Ollama server is available."""
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"[Ollama] Health check failed: {e}")
            return False

    def _get_ollama_embedding(self, text: str, retry: bool = True) -> List[float]:
        """
        Get embedding from Ollama API.

        Args:
            text: text to embed
            retry: whether to retry on failure

        Returns:
            embedding as list of floats
        """
        url = f"{self.ollama_base_url}/api/embeddings"
        payload = {
            "model": self.model_name,
            "prompt": text
        }

        last_error = None
        max_attempts = self.max_retries if retry else 1

        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

                result = response.json()
                embedding = result.get('embedding')

                if not embedding:
                    raise ValueError("No embedding in response")

                return embedding

            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    logger.warning(f"[Ollama] Attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"[Ollama] All {max_attempts} attempts failed")

        raise RuntimeError(f"Failed to get embedding from Ollama: {last_error}")

    def _encode_batch_ollama(self, texts: List[str]) -> np.ndarray:
        """
        Encode batch using Ollama API.

        Args:
            texts: list of texts

        Returns:
            numpy array of embeddings
        """
        embeddings = []

        for text in texts:
            embedding = self._get_ollama_embedding(text, retry=True)
            embeddings.append(embedding)

        embeddings_array = np.array(embeddings, dtype=np.float32)

        # Normalize if requested
        if self.normalize:
            norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
            embeddings_array = embeddings_array / np.maximum(norms, 1e-12)

        return embeddings_array

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """
        Encode batch of texts to embeddings.

        Args:
            texts: list of texts

        Returns:
            numpy array of embeddings (n_texts, embedding_dim)
        """
        if self.provider == 'ollama':
            return self._encode_batch_ollama(texts)
        else:  # sentence-transformers
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                normalize_embeddings=self.normalize,
            )
            return embeddings
    
    def encode_chunks(self, chunks: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[int]]:
        """
        Encode all chunks.
        
        Args:
            chunks: list of chunk dictionaries
            
        Returns:
            (embeddings array, list of failed indices)
        """
        texts = [c.get('full_text', c.get('text', '')) for c in chunks]
        
        # Encode in batches
        all_embeddings = []
        failed_indices = []
        
        total_batches = (len(texts) + self.batch_size - 1) // self.batch_size
        logger.info(f"Encoding {len(texts)} chunks in {total_batches} batches")
        
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            
            try:
                batch_embeddings = self.encode_batch(batch_texts)
                all_embeddings.append(batch_embeddings)
                
                if batch_num % 10 == 0:
                    logger.info(f"Processed batch {batch_num}/{total_batches}")
                    
            except Exception as e:
                logger.error(f"Failed to encode batch {batch_num}: {e}")
                # Add indices to failed list
                batch_indices = list(range(i, min(i + self.batch_size, len(texts))))
                failed_indices.extend(batch_indices)
                # Add zero embeddings for failed batch
                zero_embeddings = np.zeros((len(batch_texts), self.embedding_dim))
                all_embeddings.append(zero_embeddings)
        
        # Concatenate all embeddings
        embeddings = np.vstack(all_embeddings)
        
        logger.info(f"Encoded {len(embeddings)} embeddings, {len(failed_indices)} failures")
        return embeddings, failed_indices


class FAISSIndexBuilder:
    """Build FAISS index from embeddings."""
    
    def __init__(self, config: Dict[str, Any]):
        if not FAISS_AVAILABLE:
            raise RuntimeError("faiss is required for indexing")
        
        self.config = config
        self.index_type = config.get('index_type', 'flat')  # flat or ivf
        self.metric = config.get('metric', 'cosine')  # cosine or l2
    
    def build_index(self, embeddings: np.ndarray) -> faiss.Index:
        """
        Build FAISS index from embeddings.
        
        Args:
            embeddings: numpy array (n_vectors, dimension)
            
        Returns:
            FAISS index
        """
        dimension = embeddings.shape[1]
        n_vectors = embeddings.shape[0]
        
        logger.info(f"Building FAISS index: {self.index_type}, metric={self.metric}")
        logger.info(f"Vectors: {n_vectors}, Dimension: {dimension}")
        
        # Create index based on type and metric
        if self.metric == 'cosine':
            # For cosine similarity, normalize vectors and use inner product
            faiss.normalize_L2(embeddings)
            
            if self.index_type == 'flat':
                index = faiss.IndexFlatIP(dimension)
            else:  # ivf
                nlist = min(100, n_vectors // 10)
                quantizer = faiss.IndexFlatIP(dimension)
                index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
                index.train(embeddings)
        else:  # l2
            if self.index_type == 'flat':
                index = faiss.IndexFlatL2(dimension)
            else:  # ivf
                nlist = min(100, n_vectors // 10)
                quantizer = faiss.IndexFlatL2(dimension)
                index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
                index.train(embeddings)
        
        # Add vectors to index
        index.add(embeddings)
        
        logger.info(f"FAISS index built: {index.ntotal} vectors")
        return index
    
    def save_index(self, index: faiss.Index, path: Path) -> None:
        """Save FAISS index to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(path))
        
        index_size = path.stat().st_size
        logger.info(f"Saved FAISS index: {path.name} ({format_size(index_size)})")


class MetadataManager:
    """Manage chunk metadata for search."""
    
    @staticmethod
    def save_metadata(chunks: List[Dict[str, Any]], path: Path) -> None:
        """Save chunk metadata to pickle file."""
        # Extract essential metadata (not full_text to save space)
        metadata = []
        for chunk in chunks:
            meta = {
                'chunk_id': chunk.get('chunk_id'),
                'text': chunk.get('text'),
                'tokens': chunk.get('tokens'),
                'metadata': chunk.get('metadata', {}),
                'context': chunk.get('context'),
            }
            metadata.append(meta)
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            pickle.dump(metadata, f)
        
        meta_size = path.stat().st_size
        logger.info(f"Saved metadata: {path.name} ({format_size(meta_size)})")


class EmbedProcessor:
    """Main processor for embeddings stage."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.stage_config = self.config_loader.get_stage_config('embed')
        
        # Components
        self.path_manager = PathManager()
        self.embedding_engine = EmbeddingEngine(self.stage_config)
        self.index_builder = FAISSIndexBuilder(self.stage_config.get('faiss', {}))
        
        # Quality tracking
        self.quality_tracker = None
    
    def process_chunks(self, chunks_path: Path,
                      output_dir: Optional[Path] = None) -> Tuple[Path, Path]:
        """
        Process chunks to create embeddings and index.
        
        Args:
            chunks_path: path to chunks JSONL file
            output_dir: output directory (default: auto from PathManager)
            
        Returns:
            (index_path, metadata_path)
        """
        logger.info(f"Processing: {chunks_path.name}")
        
        if output_dir is None:
            index_dir = self.path_manager.index_faiss
            metadata_dir = self.path_manager.index_metadata
        else:
            index_dir = output_dir / 'faiss'
            metadata_dir = output_dir / 'metadata'
        
        # Load chunks
        chunks = self._load_chunks(chunks_path)
        logger.info(f"Loaded {len(chunks)} chunks")
        
        # Generate embeddings
        embeddings, failed_indices = self.embedding_engine.encode_chunks(chunks)
        
        # Build FAISS index
        index = self.index_builder.build_index(embeddings)
        
        # Save index
        index_name = chunks_path.stem.replace('.chunks', '')
        index_path = index_dir / f"{index_name}.faiss"
        self.index_builder.save_index(index, index_path)
        
        # Save metadata
        metadata_path = metadata_dir / f"{index_name}.pkl"
        MetadataManager.save_metadata(chunks, metadata_path)
        
        # Save embedding info
        info_path = metadata_dir / f"{index_name}.info.json"
        self._save_embedding_info(info_path, chunks, embeddings, failed_indices)
        
        # Quality tracking
        if self.quality_tracker:
            metrics = self._calculate_metrics(embeddings, failed_indices)
            self.quality_tracker.track('embed', chunks_path.name, metrics)
        
        logger.info(f"Saved: {index_path.name}, {metadata_path.name}")
        return index_path, metadata_path
    
    def _load_chunks(self, path: Path) -> List[Dict[str, Any]]:
        """Load chunks from JSONL file."""
        chunks = []
        
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                if obj.get('type') == 'chunk':
                    chunks.append(obj)
        
        return chunks
    
    def _save_embedding_info(self, path: Path, chunks: List[Dict[str, Any]],
                           embeddings: np.ndarray, failed_indices: List[int]) -> None:
        """Save embedding metadata info."""
        info = {
            'provider': self.embedding_engine.provider,
            'model': self.embedding_engine.model_name,
            'embedding_dim': self.embedding_engine.embedding_dim,
            'total_chunks': len(chunks),
            'total_embeddings': len(embeddings),
            'failed_count': len(failed_indices),
            'index_type': self.index_builder.index_type,
            'metric': self.index_builder.metric,
            'created_at': utc_now_iso(),
            'version': VERSION,
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
    
    def _calculate_metrics(self, embeddings: np.ndarray, 
                          failed_indices: List[int]) -> Dict[str, Any]:
        """Calculate quality metrics."""
        total = len(embeddings)
        
        # Calculate embedding statistics
        norms = np.linalg.norm(embeddings, axis=1)
        
        return {
            'total_vectors': total,
            'embedding_dim': embeddings.shape[1],
            'embedding_failures': len(failed_indices),
            'failure_rate': len(failed_indices) / total if total > 0 else 0,
            'avg_norm': float(np.mean(norms)),
            'min_norm': float(np.min(norms)),
            'max_norm': float(np.max(norms)),
        }


def main():
    """CLI interface."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Embeddings generation (MVP v2.0)')
    parser.add_argument('-i', '--input', required=True,
                       help='Input chunks file or directory')
    parser.add_argument('-o', '--output',
                       help='Output directory')
    parser.add_argument('-c', '--config',
                       help='Config file path')
    parser.add_argument('--pattern', default='*.chunks.jsonl',
                       help='File pattern for directory input')
    parser.add_argument('--model',
                       help='Embedding model name (override config)')
    
    args = parser.parse_args()
    
    # Initialize processor
    config_path = Path(args.config) if args.config else None
    processor = EmbedProcessor(config_path)
    
    # Override model if specified
    if args.model:
        processor.embedding_engine.model_name = args.model
        processor.embedding_engine.model = SentenceTransformer(args.model)
    
    # Process
    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else None
    
    if input_path.is_file():
        # Single file
        processor.process_chunks(input_path, output_dir)
    elif input_path.is_dir():
        # Directory
        chunk_files = sorted(input_path.glob(args.pattern))
        logger.info(f"Found {len(chunk_files)} chunk files")
        
        for chunks_path in chunk_files:
            try:
                processor.process_chunks(chunks_path, output_dir)
            except Exception as e:
                logger.error(f"Failed to process {chunks_path.name}: {e}")
    else:
        logger.error(f"Invalid input path: {input_path}")
        sys.exit(1)
    
    logger.info("Done!")


if __name__ == '__main__':
    main()