#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_chunk.py - Text Chunking (MVP v2.0)
======================================
Stage 6: Split documents into chunks for embedding

Features:
- Sliding window chunking with overlap
- Context-aware chunks (chapter/section metadata)
- Token counting
- Metadata preservation
- Quality metrics tracking

Version: 2.0.0
Dependencies: am_common, tiktoken
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

# Token counter
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("[WARN] tiktoken not available. Using approximate token counting.")

from am_common import (
    DatasetIO, ConfigLoader, PathManager,
    utc_now_iso
)

logger = logging.getLogger('am_chunk')

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"


class TokenCounter:
    """Token counting utilities."""
    
    def __init__(self, model: str = "cl100k_base"):
        self.model = model
        
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.get_encoding(model)
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoding: {e}")
                self.encoding = None
        else:
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Approximate: 1 token ~= 4 chars
            return len(text) // 4
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to max tokens."""
        if self.encoding:
            tokens = self.encoding.encode(text)
            if len(tokens) > max_tokens:
                tokens = tokens[:max_tokens]
                return self.encoding.decode(tokens)
            return text
        else:
            # Approximate
            max_chars = max_tokens * 4
            return text[:max_chars]


class ChunkingEngine:
    """Text chunking engine with sliding window."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Chunking parameters
        self.chunk_size = config.get('chunk_size', 512)  # tokens
        self.chunk_overlap = config.get('chunk_overlap', 128)  # tokens
        self.min_chunk_size = config.get('min_chunk_size', 100)  # tokens
        
        # Token counter
        token_model = config.get('token_model', 'cl100k_base')
        self.token_counter = TokenCounter(token_model)
        
        # Context settings
        self.include_context = config.get('include_context', True)
        self.context_max_tokens = config.get('context_max_tokens', 200)
    
    def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split text into chunks.
        
        Args:
            text: input text
            metadata: metadata to attach to chunks (page_num, chapter, etc)
            
        Returns:
            List of chunks with metadata
        """
        if not text or len(text.strip()) < 10:
            return []
        
        # Split into sentences (rough)
        sentences = self._split_sentences(text)
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.token_counter.count_tokens(sentence)
            
            # Check if adding sentence exceeds chunk size
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk:
                # Create chunk
                chunk_text = ' '.join(current_chunk)
                if self.token_counter.count_tokens(chunk_text) >= self.min_chunk_size:
                    chunks.append(self._create_chunk(chunk_text, metadata))
                
                # Start new chunk with overlap
                overlap_size = 0
                overlap_sentences = []
                
                # Add sentences for overlap (from end of current chunk)
                for sent in reversed(current_chunk):
                    sent_tokens = self.token_counter.count_tokens(sent)
                    if overlap_size + sent_tokens <= self.chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_size += sent_tokens
                    else:
                        break
                
                current_chunk = overlap_sentences
                current_tokens = overlap_size
            
            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if self.token_counter.count_tokens(chunk_text) >= self.min_chunk_size:
                chunks.append(self._create_chunk(chunk_text, metadata))
        
        return chunks
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences (simple)."""
        import re
        
        # Split on period, exclamation, question mark followed by space
        pattern = r'(?<=[.!?])\s+'
        sentences = re.split(pattern, text)
        
        # Filter empty
        return [s.strip() for s in sentences if s.strip()]
    
    def _create_chunk(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create chunk with metadata."""
        # Count tokens
        tokens = self.token_counter.count_tokens(text)
        
        # Build context string
        context = self._build_context(metadata) if self.include_context else ""
        
        # Combine text with context
        full_text = f"{context}\n\n{text}" if context else text
        
        return {
            'text': text,
            'full_text': full_text,
            'tokens': tokens,
            'metadata': metadata.copy(),
            'context': context,
        }
    
    def _build_context(self, metadata: Dict[str, Any]) -> str:
        """Build context string from metadata."""
        parts = []
        
        # Source info
        if metadata.get('source_file'):
            parts.append(f"Source: {metadata['source_file']}")
        
        # Chapter info
        if metadata.get('chapter_title'):
            chapter_str = f"Chapter {metadata.get('chapter_num', '')}: {metadata['chapter_title']}"
            parts.append(chapter_str.strip())
        
        # Section info
        if metadata.get('section_title'):
            section_str = f"Section {metadata.get('section_num', '')}: {metadata['section_title']}"
            parts.append(section_str.strip())
        
        context = ' | '.join(parts)
        
        # Truncate if too long
        if context:
            context = self.token_counter.truncate_to_tokens(context, self.context_max_tokens)
        
        return context


class ChunkProcessor:
    """Main processor for chunking stage."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.stage_config = self.config_loader.get_stage_config('chunk')
        
        # Components
        self.path_manager = PathManager()
        self.engine = ChunkingEngine(self.stage_config)
        
        # Quality tracking
        self.quality_tracker = None
    
    def process_dataset(self, input_path: Path,
                       output_dir: Optional[Path] = None) -> Path:
        """
        Process dataset to create chunks.
        
        Args:
            input_path: path to input dataset (from final)
            output_dir: output directory (default: auto from PathManager)
            
        Returns:
            path to output chunks file
        """
        logger.info(f"Processing: {input_path.name}")
        
        if output_dir is None:
            output_dir = self.path_manager.dataset_chunks
        
        # Load dataset
        header, cards, audit, footer = DatasetIO.load(input_path)
        
        # Generate chunks from all cards
        all_chunks = []
        chunk_id = 0
        
        for card in cards:
            # Build metadata
            metadata = {
                'source_file': card.get('source_file'),
                'page_num': card.get('page_num'),
                'segment_id': card.get('segment_id'),
                'chapter_num': card.get('chapter_num'),
                'chapter_title': card.get('chapter_title'),
                'section_num': card.get('section_num'),
                'section_title': card.get('section_title'),
                'has_table': card.get('has_table', False),
            }
            
            # Get text (prefer segment for chunking, as it has full content)
            # Fall back to l1_summary only if segment is empty
            segment = card.get('segment', '')
            l1_summary = card.get('l1_summary', '')
            text = segment if segment else l1_summary
            
            # Create chunks
            chunks = self.engine.chunk_text(text, metadata)
            
            # Assign chunk IDs
            for chunk in chunks:
                chunk['chunk_id'] = f"{chunk_id:08d}"
                chunk_id += 1
            
            all_chunks.extend(chunks)
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(cards)} pages")
        
        # Build chunks header
        chunks_header = {
            'source_dataset': input_path.name,
            'source_file': header.get('source_file'),
            'book': header.get('book'),
            'title': header.get('title'),
            'total_chunks': len(all_chunks),
            'chunk_size': self.engine.chunk_size,
            'chunk_overlap': self.engine.chunk_overlap,
            'stage': 'chunks',
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
        
        # Build audit
        chunks_audit = self._build_audit(all_chunks, len(cards))
        
        # Save chunks
        output_path = output_dir / f"{input_path.stem}.chunks.jsonl"
        self._save_chunks(output_path, chunks_header, all_chunks, chunks_audit)
        
        # Quality tracking
        if self.quality_tracker:
            metrics = self._calculate_metrics(all_chunks, len(cards))
            self.quality_tracker.track('chunk', input_path.name, metrics)
        
        logger.info(f"Saved: {output_path.name}")
        return output_path
    
    def _save_chunks(self, path: Path, header: Dict[str, Any],
                    chunks: List[Dict[str, Any]], audit: Dict[str, Any]) -> None:
        """Save chunks to JSONL file."""
        import json
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            # Header
            f.write(json.dumps({'type': 'header', **header}, ensure_ascii=False) + '\n')
            
            # Chunks
            for chunk in chunks:
                f.write(json.dumps({'type': 'chunk', **chunk}, ensure_ascii=False) + '\n')
            
            # Audit
            f.write(json.dumps({'type': 'audit', **audit}, ensure_ascii=False) + '\n')
    
    def _build_audit(self, chunks: List[Dict[str, Any]], source_pages: int) -> Dict[str, Any]:
        """Build audit section."""
        # Token statistics
        token_counts = [c['tokens'] for c in chunks]
        avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0
        min_tokens = min(token_counts) if token_counts else 0
        max_tokens = max(token_counts) if token_counts else 0
        
        # Context statistics
        chunks_with_context = sum(1 for c in chunks if c.get('context'))
        
        return {
            'total_chunks': len(chunks),
            'source_pages': source_pages,
            'chunks_per_page': len(chunks) / source_pages if source_pages > 0 else 0,
            'avg_tokens': round(avg_tokens, 1),
            'min_tokens': min_tokens,
            'max_tokens': max_tokens,
            'chunks_with_context': chunks_with_context,
            'context_coverage': chunks_with_context / len(chunks) if chunks else 0,
            'stage': 'chunk',
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
    
    def _calculate_metrics(self, chunks: List[Dict[str, Any]], source_pages: int) -> Dict[str, Any]:
        """Calculate quality metrics."""
        token_counts = [c['tokens'] for c in chunks]
        
        # Token distribution
        token_ranges = {
            '0-100': 0,
            '100-300': 0,
            '300-512': 0,
            '512+': 0,
        }
        
        for tokens in token_counts:
            if tokens < 100:
                token_ranges['0-100'] += 1
            elif tokens < 300:
                token_ranges['100-300'] += 1
            elif tokens <= 512:
                token_ranges['300-512'] += 1
            else:
                token_ranges['512+'] += 1
        
        # Context completeness
        chunks_with_context = sum(1 for c in chunks if c.get('context'))
        
        return {
            'total_chunks': len(chunks),
            'chunks_per_page': len(chunks) / source_pages if source_pages > 0 else 0,
            'avg_chunk_tokens': sum(token_counts) / len(token_counts) if token_counts else 0,
            'min_chunk_tokens': min(token_counts) if token_counts else 0,
            'max_chunk_tokens': max(token_counts) if token_counts else 0,
            'token_distribution': token_ranges,
            'context_completeness': chunks_with_context / len(chunks) if chunks else 0,
        }


def main():
    """CLI interface."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Text chunking (MVP v2.0)')
    parser.add_argument('-i', '--input', required=True,
                       help='Input dataset or directory')
    parser.add_argument('-o', '--output',
                       help='Output directory')
    parser.add_argument('-c', '--config',
                       help='Config file path')
    parser.add_argument('--pattern', default='*.dataset.jsonl',
                       help='File pattern for directory input')
    parser.add_argument('--chunk-size', type=int,
                       help='Chunk size in tokens (override config)')
    parser.add_argument('--overlap', type=int,
                       help='Chunk overlap in tokens (override config)')
    
    args = parser.parse_args()
    
    # Initialize processor
    config_path = Path(args.config) if args.config else None
    processor = ChunkProcessor(config_path)
    
    # Override settings if specified
    if args.chunk_size:
        processor.engine.chunk_size = args.chunk_size
    if args.overlap:
        processor.engine.chunk_overlap = args.overlap
    
    # Process
    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else None
    
    if input_path.is_file():
        # Single file
        processor.process_dataset(input_path, output_dir)
    elif input_path.is_dir():
        # Directory
        dataset_files = sorted(input_path.glob(args.pattern))
        logger.info(f"Found {len(dataset_files)} datasets")
        
        for dataset_path in dataset_files:
            try:
                processor.process_dataset(dataset_path, output_dir)
            except Exception as e:
                logger.error(f"Failed to process {dataset_path.name}: {e}")
    else:
        logger.error(f"Invalid input path: {input_path}")
        sys.exit(1)
    
    logger.info("Done!")


if __name__ == '__main__':
    main()