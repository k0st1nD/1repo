#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_summarize.py - Extractive Summarization (MVP v2.0)
=====================================================
Stage 3: Generate extractive summaries (L1, L2)

Features:
- Extractive summarization (sentence scoring)
- Two-level summaries (L1: brief, L2: detailed)
- Text normalization
- Quality metrics tracking

Version: 2.0.0
Dependencies: am_common
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from am_common import (
    DatasetIO, ConfigLoader, PathManager, TextNormalizer,
    utc_now_iso
)

logger = logging.getLogger('am_summarize')

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"

# Text processing patterns
SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+|\n{2,}')
WORD_RE = re.compile(r'[A-Za-zА-Яа-я0-9]{3,}')

# Stop words (common words to ignore in scoring)
STOP_WORDS = set("""
a an the and or for to of in on at by as is are was were be been being
this that those these with from into over under about across between
among through during before after above below not no nor so such it
its their our your my we you they he she his her them us
и в во не на но а к ко от до по за из у о об при над под для без
между как так же уже ещё еще или либо это эти эта этот кто что где
когда чем чтобы который которая которые бы то все всё
""".split())


class ExtractiveEngine:
    """Extractive summarization engine using sentence scoring."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.normalizer = TextNormalizer()
        
        # L1 settings (brief summary)
        self.l1_max_sentences = config.get('l1_max_sentences', 3)
        self.l1_max_chars = config.get('l1_max_chars', 300)
        
        # L2 settings (detailed summary)
        self.l2_max_sentences = config.get('l2_max_sentences', 6)
        self.l2_max_chars = config.get('l2_max_chars', 900)
        
        # Scoring weights
        self.position_weight = config.get('position_weight', 0.1)
        self.length_weight = config.get('length_weight', 0.1)
        self.numeric_bonus = config.get('numeric_bonus', 0.05)
        self.colon_bonus = config.get('colon_bonus', 0.03)
    
    def summarize(self, text: str, level: str = 'l1') -> str:
        """
        Generate extractive summary.
        
        Args:
            text: input text
            level: 'l1' (brief) or 'l2' (detailed)
            
        Returns:
            summary text
        """
        if not text or len(text.strip()) < 50:
            return ""
        
        # Normalize text
        normalized = self.normalizer.normalize(text)
        
        # Split into sentences
        sentences = self._split_sentences(normalized)
        if not sentences:
            return normalized[:self.l1_max_chars]
        
        # Calculate word frequencies
        word_freq = self._calculate_word_frequencies(normalized)
        
        # Score sentences
        scored_sentences = self._score_sentences(sentences, word_freq)
        
        # Select top sentences
        max_sentences = self.l1_max_sentences if level == 'l1' else self.l2_max_sentences
        max_chars = self.l1_max_chars if level == 'l1' else self.l2_max_chars
        
        summary = self._select_sentences(scored_sentences, max_sentences, max_chars)
        
        return summary
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text)]
        # Filter out very short sentences
        return [s for s in sentences if len(s) > 20]
    
    def _calculate_word_frequencies(self, text: str) -> Dict[str, float]:
        """Calculate normalized word frequencies."""
        words = [w.lower() for w in WORD_RE.findall(text)]
        words = [w for w in words if w not in STOP_WORDS]
        
        if not words:
            return {}
        
        # Count frequencies
        word_count = {}
        for word in words:
            word_count[word] = word_count.get(word, 0) + 1
        
        # Normalize
        max_freq = max(word_count.values())
        return {w: c / max_freq for w, c in word_count.items()}
    
    def _score_sentences(self, sentences: List[str], 
                        word_freq: Dict[str, float]) -> List[Tuple[int, float, str]]:
        """
        Score sentences based on word frequencies and features.
        
        Returns:
            List of (index, score, sentence)
        """
        scored = []
        total_sentences = len(sentences)
        
        for idx, sentence in enumerate(sentences):
            # Base score: average word frequency
            words = [w.lower() for w in WORD_RE.findall(sentence)]
            words = [w for w in words if w not in STOP_WORDS]
            
            if not words:
                continue
            
            # Word frequency score
            word_score = sum(word_freq.get(w, 0) for w in words) / len(words)
            
            # Position bonus (earlier sentences are more important)
            position_score = (total_sentences - idx) / total_sentences * self.position_weight
            
            # Length penalty (very long sentences are less preferred)
            length_penalty = min(1.0, 100 / (len(sentence) + 1)) * self.length_weight
            
            # Feature bonuses
            numeric_score = self.numeric_bonus if any(c.isdigit() for c in sentence) else 0
            colon_score = self.colon_bonus if ':' in sentence else 0
            
            # Total score
            total_score = word_score + position_score + length_penalty + numeric_score + colon_score
            
            scored.append((idx, total_score, sentence))
        
        # Sort by score (descending)
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored
    
    def _select_sentences(self, scored_sentences: List[Tuple[int, float, str]],
                         max_sentences: int, max_chars: int) -> str:
        """
        Select top sentences respecting limits.
        
        Returns:
            summary text
        """
        # Select top sentences
        selected = scored_sentences[:max_sentences]
        
        # Sort by original order
        selected = sorted(selected, key=lambda x: x[0])
        
        # Join sentences
        summary = ' '.join(s for _, _, s in selected)
        
        # Truncate if needed
        if len(summary) > max_chars:
            summary = summary[:max_chars].rsplit(' ', 1)[0]
            summary = summary.rstrip('.,;:-') + '...'
        
        return summary


class SummaryProcessor:
    """Main processor for summarization stage."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.stage_config = self.config_loader.get_stage_config('summarize')
        
        # Components
        self.path_manager = PathManager()
        self.engine = ExtractiveEngine(self.stage_config.get('extractive', {}))
        
        # Settings
        self.generate_l2 = self.stage_config.get('generate_l2', True)
        self.min_text_length = self.stage_config.get('min_text_length', 50)
        
        # Quality tracking
        self.quality_tracker = None
    
    def process_dataset(self, input_path: Path,
                       output_dir: Optional[Path] = None) -> Path:
        """
        Process dataset to add summaries.
        
        Args:
            input_path: path to input dataset (from structured or structural)
            output_dir: output directory (default: auto from PathManager)
            
        Returns:
            path to output dataset
        """
        logger.info(f"Processing: {input_path.name}")
        
        if output_dir is None:
            output_dir = self.path_manager.dataset_summarized
        
        # Load dataset
        header, cards, audit, footer = DatasetIO.load(input_path)
        
        # Generate summaries
        summarized_count = 0
        skipped_count = 0
        
        for card in cards:
            text = card.get('segment', '')
            
            # Skip if text too short
            if len(text.strip()) < self.min_text_length:
                skipped_count += 1
                continue
            
            # Generate L1 summary
            l1_summary = self.engine.summarize(text, level='l1')
            card['l1_summary'] = l1_summary
            
            # Generate L2 summary (optional)
            if self.generate_l2:
                l2_summary = self.engine.summarize(text, level='l2')
                card['l2_summary'] = l2_summary
            
            summarized_count += 1
        
        logger.info(f"Summarized {summarized_count} pages, skipped {skipped_count}")
        
        # Update header
        header['stage'] = 'summarized'
        header['summarized_at'] = utc_now_iso()
        header['summary_engine'] = 'extractive-v2'
        header['generate_l2'] = self.generate_l2
        
        # Update audit
        audit = self._build_audit(
            cards=cards,
            summarized_count=summarized_count,
            skipped_count=skipped_count,
        )
        
        # Save dataset
        output_path = output_dir / input_path.name
        DatasetIO.save(output_path, header, cards, audit, footer)
        
        # Quality tracking
        if self.quality_tracker:
            metrics = self._calculate_metrics(cards, summarized_count, skipped_count)
            self.quality_tracker.track('summarize', input_path.name, metrics)
        
        logger.info(f"Saved: {output_path.name}")
        return output_path
    
    def _build_audit(self, cards: List[Dict[str, Any]],
                    summarized_count: int, skipped_count: int) -> Dict[str, Any]:
        """Build audit section."""
        # Calculate average summary lengths
        l1_lengths = [len(c.get('l1_summary', '')) for c in cards if c.get('l1_summary')]
        l2_lengths = [len(c.get('l2_summary', '')) for c in cards if c.get('l2_summary')]
        
        avg_l1 = sum(l1_lengths) / len(l1_lengths) if l1_lengths else 0
        avg_l2 = sum(l2_lengths) / len(l2_lengths) if l2_lengths else 0
        
        return {
            'total_cards': len(cards),
            'summarized_count': summarized_count,
            'skipped_count': skipped_count,
            'summary_coverage': summarized_count / len(cards) if cards else 0,
            'avg_l1_length': round(avg_l1, 1),
            'avg_l2_length': round(avg_l2, 1),
            'stage': 'summarize',
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
    
    def _calculate_metrics(self, cards: List[Dict[str, Any]],
                          summarized_count: int, skipped_count: int) -> Dict[str, Any]:
        """Calculate quality metrics."""
        total = len(cards)
        
        # Calculate average lengths
        l1_lengths = [len(c.get('l1_summary', '')) for c in cards if c.get('l1_summary')]
        l2_lengths = [len(c.get('l2_summary', '')) for c in cards if c.get('l2_summary')]
        
        # Calculate compression ratios
        compression_ratios = []
        for card in cards:
            if card.get('l1_summary'):
                original_len = len(card.get('segment', ''))
                summary_len = len(card.get('l1_summary', ''))
                if original_len > 0:
                    compression_ratios.append(original_len / summary_len)
        
        avg_compression = sum(compression_ratios) / len(compression_ratios) if compression_ratios else 0
        
        return {
            'total_pages': total,
            'summarized_pages': summarized_count,
            'skipped_pages': skipped_count,
            'summary_coverage': summarized_count / total if total > 0 else 0,
            'avg_l1_length': sum(l1_lengths) / len(l1_lengths) if l1_lengths else 0,
            'avg_l2_length': sum(l2_lengths) / len(l2_lengths) if l2_lengths else 0,
            'avg_compression_ratio': round(avg_compression, 2),
        }


def main():
    """CLI interface."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Extractive summarization (MVP v2.0)')
    parser.add_argument('-i', '--input', required=True,
                       help='Input dataset or directory')
    parser.add_argument('-o', '--output',
                       help='Output directory')
    parser.add_argument('-c', '--config',
                       help='Config file path')
    parser.add_argument('--pattern', default='*.dataset.jsonl',
                       help='File pattern for directory input')
    parser.add_argument('--no-l2', action='store_true',
                       help='Skip L2 summaries (only generate L1)')
    
    args = parser.parse_args()
    
    # Initialize processor
    config_path = Path(args.config) if args.config else None
    processor = SummaryProcessor(config_path)
    
    # Override L2 generation if specified
    if args.no_l2:
        processor.generate_l2 = False
    
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