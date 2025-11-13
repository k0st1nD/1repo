#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_extended.py - Extended Processing (MVP v2.0)
===============================================
Stage 4: Enrichment + deduplication + continuity validation + extended fields extraction

Features:
- Page deduplication (near-duplicate detection)
- Continuity audit (text overlap between pages)
- Navigation links (prev_page, next_page)
- Extended fields extraction via LM (Ollama)
- Quality metrics tracking

Version: 2.0.0
Dependencies: am_common, requests (for Ollama API)
"""

import logging
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[WARNING] requests not available. Install: pip install requests")

from am_common import (
    DatasetIO, ConfigLoader, PathManager, TextNormalizer,
    utc_now_iso
)

logger = logging.getLogger('am_extended')

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"

# Regex patterns
WORD_RE = re.compile(r'[A-Za-zА-Яа-я0-9]{2,}')
STOP_WORDS = set("""
a an the and or for to of in on at by as is are was were be been being
this that those these with from into over under about across between
among through during before after above below not no nor so such it
its their our your my we you they he she his her them us
и в во не на но а к ко от до по за из у о об при над под для без
между как так же уже ещё еще или либо это эти эта этот кто что где
когда чем чтобы который которая которые бы то все всё
""".split())


class TextAnalyzer:
    """Text analysis utilities."""
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text, remove stop words."""
        tokens = WORD_RE.findall(text.lower())
        return [w for w in tokens if w not in STOP_WORDS]
    
    @staticmethod
    def jaccard_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
        """Calculate Jaccard similarity between token sets."""
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def text_hash(text: str) -> str:
        """Simple text hash for deduplication."""
        import hashlib
        # Normalize: lowercase, remove extra spaces
        normalized = ' '.join(text.lower().split())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()


class ExtendedFieldsExtractor:
    """Extract extended metadata fields using LM (Ollama) and heuristics."""
    
    # Extraction prompt template
    EXTRACTION_PROMPT = """Analyze this page from a technical/business book and extract structured metadata.

Page text:
{text}

Extract the following information and return ONLY valid JSON (no explanations):

{{
  "content_type": "theory|practice|case_study|reference|tutorial|review",
  "domain": "devops|architecture|management|security|data_science|programming|other",
  "complexity": "beginner|intermediate|advanced|expert",
  "entities": {{
    "companies": ["list of company names mentioned"],
    "people": ["list of people/authors mentioned"],
    "products": ["list of product names"],
    "technologies": ["list of technologies, languages, platforms"],
    "frameworks": ["list of frameworks mentioned"],
    "methodologies": ["list of methodologies like Agile, DevOps, Scrum"]
  }},
  "technical_content": {{
    "has_code": true|false,
    "programming_languages": ["list if has_code"],
    "has_formulas": true|false,
    "has_diagram": true|false
  }},
  "actionable_content": {{
    "has_best_practices": true|false,
    "has_antipatterns": true|false,
    "has_instructions": true|false
  }},
  "business_content": {{
    "has_metrics": true|false,
    "metrics": ["list of KPIs/metrics mentioned"],
    "has_case_study": true|false,
    "case_study_company": "company name or null"
  }},
  "tools_mentioned": ["list of tools, software, platforms"],
  "topics": ["3-5 main topics"],
  "key_concepts": ["key ideas or concepts"],
  "problem_statement": "what problem is discussed (or null)",
  "solution_approach": "how it's solved (or null)"
}}

Return ONLY the JSON object, nothing else."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_lm = config.get('use_lm', True)
        self.ollama_base_url = config.get('ollama_base_url', 'http://localhost:11434')
        # FIX: использовать правильный ключ конфига 'lm_model' вместо 'model'
        self.model = config.get('lm_model', config.get('model', 'qwen2.5:7b'))
        self.timeout = config.get('timeout', 30)
        self.max_text_length = config.get('max_text_length', 4000)

        # Check Ollama availability
        self.ollama_available = False
        if self.use_lm and REQUESTS_AVAILABLE:
            self.ollama_available = self._check_ollama()
            if self.ollama_available:
                logger.info(f"[LM EXTRACTION] Ollama available, using model: {self.model}")
            else:
                logger.warning("[LM EXTRACTION] Ollama not available, using heuristic extraction only")
        else:
            logger.info("[LM EXTRACTION] LM extraction disabled, using heuristics only")
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            # Проверка что Ollama запущен
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                logger.warning(f"[LM EXTRACTION] Ollama API not responding (status: {response.status_code})")
                return False

            # Проверка что нужная модель установлена
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]

            if self.model not in model_names:
                logger.warning(f"[LM EXTRACTION] Model '{self.model}' not found. Available: {', '.join(model_names)}")
                return False

            logger.info(f"[LM EXTRACTION] Model '{self.model}' confirmed available")
            return True
        except Exception as e:
            logger.debug(f"[LM EXTRACTION] Ollama check failed: {e}")
            return False
    
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract extended fields from text.
        
        Returns:
            Dictionary with extended metadata
        """
        # Always do heuristic extraction as baseline
        fields = self._heuristic_extraction(text)
        
        # Try LM extraction if available
        if self.use_lm and self.ollama_available:
            try:
                lm_fields = self._lm_extraction(text)
                if lm_fields:
                    # Merge LM fields with heuristic (LM takes precedence)
                    fields.update(lm_fields)
                    fields['extraction_method'] = 'lm'
            except Exception as e:
                logger.warning(f"LM extraction failed: {e}, using heuristics")
                fields['extraction_method'] = 'heuristic'
        else:
            fields['extraction_method'] = 'heuristic'
        
        return fields
    
    def _heuristic_extraction(self, text: str) -> Dict[str, Any]:
        """Extract fields using simple heuristics (fallback)."""
        fields = {}
        
        # Technical content detection
        fields['has_code'] = self._detect_code(text)
        fields['has_formulas'] = self._detect_formulas(text)
        fields['has_diagram'] = self._detect_diagram(text)
        fields['has_list'] = self._detect_list(text)
        fields['has_citations'] = self._detect_citations(text)
        
        # Simple key terms extraction
        fields['key_terms'] = self._extract_key_terms(text)
        
        return fields
    
    def _lm_extraction(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract fields using Ollama LM."""
        # Truncate text if too long
        if len(text) > self.max_text_length:
            text = text[:self.max_text_length] + "..."
        
        # Build prompt
        prompt = self.EXTRACTION_PROMPT.format(text=text)
        
        # Call Ollama API
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent extraction
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama API error: {response.status_code}")
                return None
            
            result = response.json()
            response_text = result.get('response', '')
            
            # Parse JSON from response
            extracted = self._parse_json_response(response_text)
            
            if extracted:
                # Flatten structure for easier use
                flattened = self._flatten_lm_response(extracted)
                return flattened
            else:
                logger.warning("Failed to parse LM response")
                return None
                
        except Exception as e:
            logger.error(f"LM extraction error: {e}")
            return None
    
    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LM response (may contain extra text)."""
        # Try to find JSON in response
        # Look for {...} pattern
        import re
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # Try parsing entire response
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    
    def _flatten_lm_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested LM response structure."""
        flattened = {}
        
        # Top-level fields
        flattened['content_type'] = data.get('content_type')
        flattened['domain'] = data.get('domain')
        flattened['complexity'] = data.get('complexity')
        
        # Entities
        entities = data.get('entities', {})
        flattened['companies'] = entities.get('companies', [])
        flattened['people'] = entities.get('people', [])
        flattened['products'] = entities.get('products', [])
        flattened['technologies'] = entities.get('technologies', [])
        flattened['frameworks'] = entities.get('frameworks', [])
        flattened['methodologies'] = entities.get('methodologies', [])
        
        # Technical content
        technical = data.get('technical_content', {})
        flattened['has_code'] = technical.get('has_code', False)
        flattened['programming_languages'] = technical.get('programming_languages', [])
        flattened['has_formulas'] = technical.get('has_formulas', False)
        flattened['has_diagram'] = technical.get('has_diagram', False)
        
        # Actionable content
        actionable = data.get('actionable_content', {})
        flattened['has_best_practices'] = actionable.get('has_best_practices', False)
        flattened['has_antipatterns'] = actionable.get('has_antipatterns', False)
        flattened['has_instructions'] = actionable.get('has_instructions', False)
        
        # Business content
        business = data.get('business_content', {})
        flattened['has_metrics'] = business.get('has_metrics', False)
        flattened['metrics'] = business.get('metrics', [])
        flattened['has_case_study'] = business.get('has_case_study', False)
        flattened['case_study_company'] = business.get('case_study_company')
        
        # Other fields
        flattened['tools_mentioned'] = data.get('tools_mentioned', [])
        flattened['topics'] = data.get('topics', [])
        flattened['key_concepts'] = data.get('key_concepts', [])
        flattened['problem_statement'] = data.get('problem_statement')
        flattened['solution_approach'] = data.get('solution_approach')
        
        return flattened
    
    def _detect_code(self, text: str) -> bool:
        """Detect code blocks."""
        code_indicators = [
            '```', 'def ', 'class ', 'function ', 'import ',
            'const ', 'var ', 'let ', '=>', 'public class', 'private '
        ]
        return any(indicator in text for indicator in code_indicators)
    
    def _detect_formulas(self, text: str) -> bool:
        """Detect mathematical formulas."""
        math_symbols = ['=', '∑', '∫', '√', '±', '×', '÷', '∂', '∆', '≈', '≤', '≥']
        formula_pattern = re.compile(r'[a-zA-Z]\s*[=+\-*/]\s*[a-zA-Z0-9]|[a-zA-Z][²³⁴]')
        return any(sym in text for sym in math_symbols) or bool(formula_pattern.search(text))
    
    def _detect_diagram(self, text: str) -> bool:
        """Detect diagram references."""
        diagram_keywords = ['Figure', 'Fig.', 'Diagram', 'Chart', 'Graph', 'Illustration']
        return any(keyword in text for keyword in diagram_keywords)
    
    def _detect_list(self, text: str) -> bool:
        """Detect lists (bullets or numbered)."""
        # Bullet points
        bullets = text.count('•') + text.count('*') + text.count('–')
        # Numbered lists
        numbered = len(re.findall(r'^\s*\d+\.', text, re.MULTILINE))
        return bullets > 2 or numbered > 2
    
    def _detect_citations(self, text: str) -> bool:
        """Detect citations."""
        # [1], (Smith 2020), [Smith2020]
        citation_patterns = [
            r'\[\d+\]',
            r'\([A-Z][a-z]+\s+\d{4}\)',
            r'\[[A-Z][a-z]+\d{4}\]',
        ]
        return any(re.search(pattern, text) for pattern in citation_patterns)
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms using TF approach."""
        tokens = TextAnalyzer.tokenize(text)
        
        # Count frequencies
        freq = {}
        for token in tokens:
            if len(token) > 3:  # Only longer words
                freq[token] = freq.get(token, 0) + 1
        
        # Get top terms
        sorted_terms = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        top_terms = [term for term, count in sorted_terms[:10] if count > 1]
        
        return top_terms


class DuplicateDetector:
    """Detect near-duplicate pages."""
    
    def __init__(self, config: Dict[str, Any]):
        self.similarity_threshold = config.get('similarity_threshold', 0.95)
        self.min_tokens = config.get('min_tokens', 10)
    
    def detect_duplicates(self, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect duplicate pages.
        
        Returns:
            List of duplicate groups: [{'pages': [1, 2, 3], 'similarity': 0.98}]
        """
        duplicates = []
        seen_hashes: Dict[str, List[int]] = {}
        analyzer = TextAnalyzer()
        
        # First pass: exact duplicates by hash
        for card in cards:
            text = card.get('segment', '')
            if len(text.strip()) < 50:  # Skip very short pages
                continue
            
            text_hash = analyzer.text_hash(text)
            page_num = card.get('page_num', 0)
            
            if text_hash in seen_hashes:
                seen_hashes[text_hash].append(page_num)
            else:
                seen_hashes[text_hash] = [page_num]
        
        # Collect exact duplicates
        for text_hash, pages in seen_hashes.items():
            if len(pages) > 1:
                duplicates.append({
                    'pages': sorted(pages),
                    'similarity': 1.0,
                    'type': 'exact'
                })
        
        return duplicates
    
    def mark_duplicates(self, cards: List[Dict[str, Any]], 
                       duplicates: List[Dict[str, Any]]) -> int:
        """
        Mark duplicate pages in cards.
        
        Returns:
            Number of pages marked as duplicates
        """
        marked_count = 0
        duplicate_pages: Set[int] = set()
        
        for dup_group in duplicates:
            pages = dup_group['pages']
            # Keep first page, mark others as duplicates
            for page_num in pages[1:]:
                duplicate_pages.add(page_num)
        
        # Mark cards
        for card in cards:
            page_num = card.get('page_num', 0)
            if page_num in duplicate_pages:
                card['is_duplicate'] = True
                # Find which group this belongs to
                for dup_group in duplicates:
                    if page_num in dup_group['pages']:
                        card['duplicate_of'] = dup_group['pages'][0]
                        break
                marked_count += 1
        
        return marked_count


class ContinuityAuditor:
    """Audit text continuity between pages."""
    
    def __init__(self, config: Dict[str, Any]):
        self.overlap_threshold = config.get('overlap_threshold', 0.1)
        self.analyzer = TextAnalyzer()
    
    def audit_continuity(self, cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Audit continuity between consecutive pages.
        
        Returns:
            Audit report with gaps and statistics
        """
        gaps = []
        overlaps = []
        
        for i in range(1, len(cards)):
            prev_card = cards[i - 1]
            curr_card = cards[i]
            
            # Skip duplicates
            if curr_card.get('is_duplicate', False):
                continue
            
            prev_text = prev_card.get('segment', '')
            curr_text = curr_card.get('segment', '')
            
            # Tokenize
            prev_tokens = self.analyzer.tokenize(prev_text)
            curr_tokens = self.analyzer.tokenize(curr_text)
            
            # Calculate overlap
            if prev_tokens and curr_tokens:
                similarity = self.analyzer.jaccard_similarity(prev_tokens, curr_tokens)
                overlaps.append(similarity)
                
                # Check for gaps
                if similarity < self.overlap_threshold:
                    gap_info = {
                        'from_page': prev_card.get('page_num'),
                        'to_page': curr_card.get('page_num'),
                        'overlap': round(similarity, 3)
                    }
                    gaps.append(gap_info)
                    
                    # Mark in card
                    curr_card.setdefault('flags', {})['continuity_gap'] = True
        
        # Statistics
        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.0
        
        return {
            'gaps': gaps,
            'gap_count': len(gaps),
            'gap_ratio': len(gaps) / max(1, len(cards) - 1),
            'avg_overlap': round(avg_overlap, 3),
            'threshold': self.overlap_threshold,
        }


class ExtendedProcessor:
    """Main processor for extended stage."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.stage_config = self.config_loader.get_stage_config('extended')
        
        # Components
        self.path_manager = PathManager()
        self.normalizer = TextNormalizer()
        self.duplicate_detector = DuplicateDetector(self.stage_config.get('deduplication', {}))
        self.continuity_auditor = ContinuityAuditor(self.stage_config.get('continuity', {}))
        self.fields_extractor = ExtendedFieldsExtractor(self.stage_config.get('extended_fields', {}))
        
        # Quality tracking
        self.quality_tracker = None
    
    def process_dataset(self, input_path: Path, 
                       output_dir: Optional[Path] = None) -> Path:
        """
        Process dataset through extended stage.
        
        Args:
            input_path: path to input dataset (from summarize or structured)
            output_dir: output directory (default: auto from PathManager)
            
        Returns:
            path to output dataset
        """
        logger.info(f"Processing: {input_path.name}")
        
        if output_dir is None:
            output_dir = self.path_manager.dataset_extended
        
        # Load dataset
        header, cards, audit, footer = DatasetIO.load(input_path)
        
        # Add navigation links
        self._add_navigation_links(cards)
        
        # Detect duplicates
        duplicates = []
        if self.stage_config.get('deduplication', {}).get('enabled', True):
            duplicates = self.duplicate_detector.detect_duplicates(cards)
            marked_count = self.duplicate_detector.mark_duplicates(cards, duplicates)
            logger.info(f"Marked {marked_count} duplicate pages")
        
        # Audit continuity
        continuity_report = {}
        if self.stage_config.get('continuity', {}).get('enabled', True):
            continuity_report = self.continuity_auditor.audit_continuity(cards)
            logger.info(f"Found {continuity_report['gap_count']} continuity gaps")
        
        # Extract extended fields
        extracted_count = 0
        if self.stage_config.get('extended_fields', {}).get('enabled', True):
            logger.info("Extracting extended fields (this may take a while)...")
            for i, card in enumerate(cards):
                if card.get('is_duplicate', False):
                    continue
                
                text = card.get('segment', '')
                if len(text.strip()) < 100:  # Skip very short pages
                    continue
                
                try:
                    extended_fields = self.fields_extractor.extract(text)
                    if extended_fields:
                        card['extended_fields'] = extended_fields
                        extracted_count += 1
                        
                        if (i + 1) % 10 == 0:
                            logger.info(f"  Processed {i + 1}/{len(cards)} pages")
                except Exception as e:
                    logger.warning(f"Failed to extract fields for page {card.get('page_num')}: {e}")
            
            logger.info(f"Extracted extended fields for {extracted_count} pages")
        
        # Update header
        header['stage'] = 'extended'
        header['extended_at'] = utc_now_iso()
        
        # Update audit
        audit = self._build_audit(
            cards=cards,
            duplicates=duplicates,
            continuity=continuity_report,
            extracted_count=extracted_count,
        )
        
        # Save dataset
        output_path = output_dir / input_path.name
        DatasetIO.save(output_path, header, cards, audit, footer)
        
        # Quality tracking
        if self.quality_tracker:
            metrics = self._calculate_metrics(cards, duplicates, continuity_report, extracted_count)
            self.quality_tracker.track('extended', input_path.name, metrics)
        
        logger.info(f"Saved: {output_path.name}")
        return output_path
    
    def _add_navigation_links(self, cards: List[Dict[str, Any]]) -> None:
        """Add prev_page and next_page links."""
        for i, card in enumerate(cards):
            # Previous page
            if i > 0:
                prev_card = cards[i - 1]
                card['prev_page'] = {
                    'page_num': prev_card.get('page_num'),
                    'segment_id': prev_card.get('segment_id'),
                }
            
            # Next page
            if i < len(cards) - 1:
                next_card = cards[i + 1]
                card['next_page'] = {
                    'page_num': next_card.get('page_num'),
                    'segment_id': next_card.get('segment_id'),
                }
    
    def _build_audit(self, cards: List[Dict[str, Any]], 
                    duplicates: List[Dict[str, Any]],
                    continuity: Dict[str, Any],
                    extracted_count: int) -> Dict[str, Any]:
        """Build audit section."""
        return {
            'total_cards': len(cards),
            'duplicate_groups': len(duplicates),
            'duplicate_pages': sum(len(d['pages']) - 1 for d in duplicates),
            'continuity': continuity,
            'extended_fields_extracted': extracted_count,
            'extraction_coverage': extracted_count / len(cards) if cards else 0,
            'stage': 'extended',
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
    
    def _calculate_metrics(self, cards: List[Dict[str, Any]],
                          duplicates: List[Dict[str, Any]],
                          continuity: Dict[str, Any],
                          extracted_count: int) -> Dict[str, Any]:
        """Calculate quality metrics."""
        total = len(cards)
        duplicate_count = sum(len(d['pages']) - 1 for d in duplicates)
        
        # Count LM vs heuristic extraction
        lm_count = sum(
            1 for c in cards 
            if c.get('extended_fields', {}).get('extraction_method') == 'lm'
        )
        
        return {
            'total_cards': total,
            'duplicates_found': duplicate_count,
            'duplicate_ratio': duplicate_count / total if total > 0 else 0,
            'continuity_gaps': continuity.get('gap_count', 0),
            'continuity_gap_ratio': continuity.get('gap_ratio', 0),
            'avg_overlap': continuity.get('avg_overlap', 0),
            'extended_fields_extracted': extracted_count,
            'extraction_coverage': extracted_count / total if total > 0 else 0,
            'lm_extraction_count': lm_count,
            'lm_extraction_ratio': lm_count / extracted_count if extracted_count > 0 else 0,
        }


def main():
    """CLI interface."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Extended processing (MVP v2.0)')
    parser.add_argument('-i', '--input', required=True, 
                       help='Input dataset or directory')
    parser.add_argument('-o', '--output', 
                       help='Output directory')
    parser.add_argument('-c', '--config', 
                       help='Config file path')
    parser.add_argument('--pattern', default='*.dataset.jsonl',
                       help='File pattern for directory input')
    parser.add_argument('--no-lm', action='store_true',
                       help='Disable LM extraction (use heuristics only)')
    
    args = parser.parse_args()
    
    # Initialize processor
    config_path = Path(args.config) if args.config else None
    processor = ExtendedProcessor(config_path)
    
    # Override LM setting if specified
    if args.no_lm:
        processor.fields_extractor.use_lm = False
    
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