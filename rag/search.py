#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search.py - RAG Search Engine (MVP v2.0)
========================================
Semantic search with filtering and ranking

Features:
- Semantic search via FAISS
- Keyword search (BM25)
- Hybrid search (semantic + keyword)
- Comprehensive filtering (chapters, topics, tools, etc)
- Query expansion
- Result reranking
- Context expansion

Version: 2.0.0
Dependencies: sentence-transformers, faiss-cpu, rank-bm25
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import re

import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("[ERROR] faiss not available")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("[ERROR] sentence-transformers not available")

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("[WARN] rank-bm25 not available, keyword search disabled")

from am_common import ConfigLoader

logger = logging.getLogger('search')

VERSION = "2.0.0"


class QueryExpander:
    """Expand query with synonyms and related terms."""
    
    # Common synonyms for technical terms
    SYNONYMS = {
        'deploy': ['deployment', 'release', 'rollout'],
        'monitor': ['monitoring', 'observability', 'telemetry'],
        'ci': ['continuous integration', 'build automation'],
        'cd': ['continuous delivery', 'continuous deployment'],
        'devops': ['site reliability', 'sre', 'platform engineering'],
        'architecture': ['design', 'system design', 'infrastructure'],
        'microservice': ['microservices', 'service-oriented'],
        'container': ['docker', 'kubernetes', 'containerization'],
        'test': ['testing', 'qa', 'quality assurance'],
        'agile': ['scrum', 'kanban', 'sprint'],
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get('enabled', True)
        self.max_expansions = config.get('max_expansions', 3)
    
    def expand(self, query: str) -> List[str]:
        """
        Expand query with synonyms.
        
        Returns:
            List of expanded queries (including original)
        """
        if not self.enabled:
            return [query]
        
        queries = [query]
        query_lower = query.lower()
        
        # Find matching terms
        for term, synonyms in self.SYNONYMS.items():
            if term in query_lower:
                # Add queries with synonyms
                for syn in synonyms[:self.max_expansions]:
                    expanded = query_lower.replace(term, syn)
                    if expanded != query_lower:
                        queries.append(expanded)
        
        return queries[:5]  # Limit total queries


class KeywordSearcher:
    """BM25-based keyword search."""
    
    def __init__(self):
        self.available = BM25_AVAILABLE
        self.corpus = []
        self.bm25 = None
        self.metadata = []
    
    def index(self, texts: List[str], metadata: List[Dict[str, Any]]) -> None:
        """Index documents for keyword search."""
        if not self.available:
            return
        
        self.metadata = metadata
        
        # Tokenize corpus
        tokenized_corpus = [self._tokenize(text) for text in texts]
        self.corpus = tokenized_corpus
        
        # Build BM25 index
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        logger.info(f"BM25 index built: {len(texts)} documents")
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Search using BM25.
        
        Returns:
            List of (index, score) tuples
        """
        if not self.available or not self.bm25:
            return []
        
        # Tokenize query
        tokenized_query = self._tokenize(query)
        
        # Get scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]
        
        return results
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r'\w+', text.lower())
        # Remove very short tokens
        return [t for t in tokens if len(t) > 2]


class SemanticSearcher:
    """FAISS-based semantic search."""
    
    def __init__(self, config: Dict[str, Any]):
        if not FAISS_AVAILABLE or not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError("FAISS and sentence-transformers required")
        
        self.config = config
        self.model_name = config.get('model', 'BAAI/bge-m3')
        
        # Load model
        logger.info(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        # Index and metadata
        self.index = None
        self.metadata = []
    
    def load_index(self, index_path: Path, metadata: List[Dict[str, Any]]) -> None:
        """Load FAISS index and metadata."""
        logger.info(f"Loading index: {index_path.name}")
        
        self.index = faiss.read_index(str(index_path))
        self.metadata = metadata
        
        logger.info(f"Index loaded: {self.index.ntotal} vectors, dim={self.index.d}")
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Semantic search using FAISS.
        
        Returns:
            List of (index, score) tuples
        """
        if not self.index:
            raise RuntimeError("Index not loaded")
        
        # Encode query
        query_embedding = self.model.encode([query], normalize_embeddings=True)
        query_vector = query_embedding.astype('float32')
        
        # Search
        scores, indices = self.index.search(query_vector, top_k)
        
        # Format results
        results = [
            (int(indices[0][i]), float(scores[0][i]))
            for i in range(len(indices[0]))
            if indices[0][i] != -1  # Valid result
        ]
        
        return results


class ResultFilter:
    """Filter search results by metadata."""
    
    @staticmethod
    def apply(results: List[Dict[str, Any]], 
             metadata: List[Dict[str, Any]],
             filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Apply filters to search results.
        
        Filters:
            - chapter: str or list
            - section: str or list
            - page_range: (min, max)
            - has_table: bool
            - has_code: bool
            - has_formulas: bool
            - has_diagram: bool
            - content_type: str (theory, practice, case_study, etc)
            - domain: str (devops, architecture, etc)
            - complexity: str (beginner, intermediate, advanced)
            - topics: list (filter by topic presence)
            - technologies: list
            - tools: list
            - companies: list
            - min_score: float
        """
        if not filters:
            return results
        
        filtered = []
        
        for result in results:
            idx = result['index']
            meta = metadata[idx].get('metadata', {})
            
            # Check each filter
            if not ResultFilter._check_filters(result, meta, filters):
                continue
            
            filtered.append(result)
        
        return filtered
    
    @staticmethod
    def _check_filters(result: Dict[str, Any], meta: Dict[str, Any],
                      filters: Dict[str, Any]) -> bool:
        """Check if result passes all filters."""
        
        # Score threshold
        if 'min_score' in filters:
            if result['score'] < filters['min_score']:
                return False
        
        # Chapter filter
        if 'chapter' in filters:
            chapter_filter = filters['chapter']
            result_chapter = meta.get('chapter_title', '')
            
            if isinstance(chapter_filter, list):
                if result_chapter not in chapter_filter:
                    return False
            else:
                if result_chapter != chapter_filter:
                    return False
        
        # Section filter
        if 'section' in filters:
            section_filter = filters['section']
            result_section = meta.get('section_title', '')
            
            if isinstance(section_filter, list):
                if result_section not in section_filter:
                    return False
            else:
                if result_section != section_filter:
                    return False
        
        # Page range
        if 'page_range' in filters:
            min_page, max_page = filters['page_range']
            result_page = meta.get('page_num', 0)
            
            if not (min_page <= result_page <= max_page):
                return False
        
        # Boolean flags
        bool_filters = ['has_table', 'has_code', 'has_formulas', 'has_diagram',
                       'has_best_practices', 'has_antipatterns', 'has_metrics',
                       'has_case_study']
        
        for bool_filter in bool_filters:
            if bool_filter in filters:
                if meta.get(bool_filter, False) != filters[bool_filter]:
                    return False
        
        # Extended fields filters
        extended = meta.get('extended_fields', {})
        
        # Content type
        if 'content_type' in filters:
            if extended.get('content_type') != filters['content_type']:
                return False
        
        # Domain
        if 'domain' in filters:
            if extended.get('domain') != filters['domain']:
                return False
        
        # Complexity
        if 'complexity' in filters:
            if extended.get('complexity') != filters['complexity']:
                return False
        
        # Topics (any match)
        if 'topics' in filters:
            filter_topics = set(filters['topics'])
            result_topics = set(extended.get('topics', []))
            
            if not (filter_topics & result_topics):  # No intersection
                return False
        
        # Technologies (any match)
        if 'technologies' in filters:
            filter_tech = set(filters['technologies'])
            result_tech = set(extended.get('technologies', []))
            
            if not (filter_tech & result_tech):
                return False
        
        # Tools (any match)
        if 'tools' in filters:
            filter_tools = set(filters['tools'])
            result_tools = set(extended.get('tools_mentioned', []))
            
            if not (filter_tools & result_tools):
                return False
        
        # Companies (any match)
        if 'companies' in filters:
            filter_companies = set(filters['companies'])
            result_companies = set(extended.get('companies', []))
            
            if not (filter_companies & result_companies):
                return False
        
        return True


class HybridSearcher:
    """Combine semantic and keyword search."""
    
    def __init__(self, semantic_weight: float = 0.7):
        self.semantic_weight = semantic_weight
        self.keyword_weight = 1.0 - semantic_weight
    
    def combine(self, semantic_results: List[Tuple[int, float]],
               keyword_results: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
        """
        Combine semantic and keyword results.
        
        Returns:
            Sorted list of (index, combined_score)
        """
        # Normalize scores
        semantic_dict = self._normalize_scores(semantic_results)
        keyword_dict = self._normalize_scores(keyword_results)
        
        # Combine scores
        all_indices = set(semantic_dict.keys()) | set(keyword_dict.keys())
        
        combined = []
        for idx in all_indices:
            sem_score = semantic_dict.get(idx, 0.0)
            kw_score = keyword_dict.get(idx, 0.0)
            
            combined_score = (
                self.semantic_weight * sem_score +
                self.keyword_weight * kw_score
            )
            
            combined.append((idx, combined_score))
        
        # Sort by score
        combined.sort(key=lambda x: x[1], reverse=True)
        
        return combined
    
    def _normalize_scores(self, results: List[Tuple[int, float]]) -> Dict[int, float]:
        """Normalize scores to [0, 1]."""
        if not results:
            return {}
        
        scores = [score for _, score in results]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return {idx: 1.0 for idx, _ in results}
        
        normalized = {}
        for idx, score in results:
            norm_score = (score - min_score) / (max_score - min_score)
            normalized[idx] = norm_score
        
        return normalized


class SearchEngine:
    """Main search engine with semantic + keyword + filtering."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.search_config = self.config_loader.get_stage_config('search')
        
        # Components
        self.semantic_searcher = SemanticSearcher(self.search_config.get('semantic', {}))
        self.keyword_searcher = KeywordSearcher()
        self.query_expander = QueryExpander(self.search_config.get('query_expansion', {}))
        self.hybrid_searcher = HybridSearcher(
            semantic_weight=self.search_config.get('hybrid_weight', 0.7)
        )
        
        # Settings
        self.use_hybrid = self.search_config.get('use_hybrid', False)
        self.use_query_expansion = self.search_config.get('use_query_expansion', False)
        
        # Loaded index info
        self.index_name = None
        self.metadata = []
    
    def load_index(self, index_name: str, index_dir: Path, metadata_dir: Path) -> None:
        """Load FAISS index and metadata."""
        logger.info(f"Loading index: {index_name}")
        
        # Load FAISS index
        index_path = index_dir / f"{index_name}.faiss"
        
        # Load metadata
        import pickle
        metadata_path = metadata_dir / f"{index_name}.pkl"
        
        with open(metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
        
        # Load into semantic searcher
        self.semantic_searcher.load_index(index_path, self.metadata)
        
        # Build keyword index if hybrid enabled
        if self.use_hybrid and self.keyword_searcher.available:
            texts = [m.get('text', '') for m in self.metadata]
            self.keyword_searcher.index(texts, self.metadata)
        
        self.index_name = index_name
        logger.info(f"Index loaded: {len(self.metadata)} chunks")
    
    def search(self, query: str, top_k: int = 5, 
              filters: Optional[Dict[str, Any]] = None,
              expand_context: int = 0) -> Dict[str, Any]:
        """
        Search for query.
        
        Args:
            query: search query
            top_k: number of results to return
            filters: metadata filters
            expand_context: number of chunks to include before/after (0 = disabled)
            
        Returns:
            Search results with metadata
        """
        if not self.index_name:
            raise RuntimeError("No index loaded")
        
        logger.info(f"Search: '{query}' (top_k={top_k})")
        
        # Query expansion
        queries = [query]
        if self.use_query_expansion:
            queries = self.query_expander.expand(query)
            if len(queries) > 1:
                logger.info(f"Expanded to {len(queries)} queries")
        
        # Search with each query
        all_results = []
        
        for q in queries:
            if self.use_hybrid and self.keyword_searcher.available:
                # Hybrid search
                semantic_results = self.semantic_searcher.search(q, top_k=top_k*2)
                keyword_results = self.keyword_searcher.search(q, top_k=top_k*2)
                
                combined = self.hybrid_searcher.combine(semantic_results, keyword_results)
                all_results.extend(combined)
            else:
                # Semantic only
                semantic_results = self.semantic_searcher.search(q, top_k=top_k*2)
                all_results.extend(semantic_results)
        
        # Deduplicate and sort
        seen = set()
        unique_results = []
        for idx, score in all_results:
            if idx not in seen:
                unique_results.append({'index': idx, 'score': score})
                seen.add(idx)
        
        # Sort by score
        unique_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Apply filters
        if filters:
            unique_results = ResultFilter.apply(unique_results, self.metadata, filters)
        
        # Limit to top_k
        unique_results = unique_results[:top_k]
        
        # Build response
        results = []
        for item in unique_results:
            idx = item['index']
            meta = self.metadata[idx]
            
            result = {
                'chunk_id': meta.get('chunk_id'),
                'score': round(item['score'], 4),
                'text': meta.get('text', ''),
                'metadata': meta.get('metadata', {}),
                'context': meta.get('context', {}),
            }
            
            # Add context expansion
            if expand_context > 0:
                result['expanded_context'] = self._get_expanded_context(idx, expand_context)
            
            results.append(result)
        
        return {
            'query': query,
            'expanded_queries': queries if len(queries) > 1 else None,
            'total_results': len(results),
            'results': results,
            'search_method': 'hybrid' if self.use_hybrid else 'semantic',
            'filters_applied': filters is not None,
        }
    
    def _get_expanded_context(self, idx: int, context_size: int) -> Dict[str, Any]:
        """Get surrounding chunks for context."""
        expanded = {
            'before': [],
            'after': [],
        }
        
        # Get chunks before
        for i in range(max(0, idx - context_size), idx):
            if i < len(self.metadata):
                chunk = self.metadata[i]
                expanded['before'].append({
                    'chunk_id': chunk.get('chunk_id'),
                    'text': chunk.get('text', ''),
                })
        
        # Get chunks after
        for i in range(idx + 1, min(len(self.metadata), idx + context_size + 1)):
            chunk = self.metadata[i]
            expanded['after'].append({
                'chunk_id': chunk.get('chunk_id'),
                'text': chunk.get('text', ''),
            })
        
        return expanded


def main():
    """CLI interface."""
    import argparse
    import sys
    from am_common import PathManager
    
    parser = argparse.ArgumentParser(description='RAG Search (MVP v2.0)')
    parser.add_argument('-i', '--index', required=True,
                       help='Index name (without extension)')
    parser.add_argument('-q', '--query', required=True,
                       help='Search query')
    parser.add_argument('-k', '--top-k', type=int, default=5,
                       help='Number of results (default: 5)')
    parser.add_argument('-c', '--config',
                       help='Config file path')
    parser.add_argument('--hybrid', action='store_true',
                       help='Use hybrid search (semantic + keyword)')
    parser.add_argument('--expand-context', type=int, default=0,
                       help='Include N chunks before/after')
    
    # Filter arguments
    parser.add_argument('--chapter', help='Filter by chapter')
    parser.add_argument('--section', help='Filter by section')
    parser.add_argument('--has-table', action='store_true', help='Only chunks with tables')
    parser.add_argument('--has-code', action='store_true', help='Only chunks with code')
    parser.add_argument('--content-type', help='Filter by content type')
    parser.add_argument('--domain', help='Filter by domain')
    parser.add_argument('--complexity', help='Filter by complexity')
    parser.add_argument('--topic', action='append', help='Filter by topic (can specify multiple)')
    
    args = parser.parse_args()
    
    # Initialize search engine
    config_path = Path(args.config) if args.config else None
    engine = SearchEngine(config_path)
    
    # Override hybrid if specified
    if args.hybrid:
        engine.use_hybrid = True
    
    # Load index
    path_manager = PathManager()
    try:
        engine.load_index(
            args.index,
            path_manager.index_faiss,
            path_manager.index_metadata
        )
    except Exception as e:
        logger.error(f"Failed to load index: {e}")
        sys.exit(1)
    
    # Build filters
    filters = {}
    
    if args.chapter:
        filters['chapter'] = args.chapter
    if args.section:
        filters['section'] = args.section
    if args.has_table:
        filters['has_table'] = True
    if args.has_code:
        filters['has_code'] = True
    if args.content_type:
        filters['content_type'] = args.content_type
    if args.domain:
        filters['domain'] = args.domain
    if args.complexity:
        filters['complexity'] = args.complexity
    if args.topic:
        filters['topics'] = args.topic
    
    # Search
    try:
        results = engine.search(
            query=args.query,
            top_k=args.top_k,
            filters=filters if filters else None,
            expand_context=args.expand_context
        )
        
        # Print results
        print(f"\nQuery: {results['query']}")
        print(f"Found: {results['total_results']} results")
        print(f"Method: {results['search_method']}\n")
        
        for i, result in enumerate(results['results'], 1):
            print(f"--- Result {i} (score: {result['score']}) ---")
            print(f"Chunk: {result['chunk_id']}")
            
            meta = result['metadata']
            if meta.get('chapter_title'):
                print(f"Chapter: {meta['chapter_title']}")
            if meta.get('page_num'):
                print(f"Page: {meta['page_num']}")
            
            print(f"\nText: {result['text'][:200]}...")
            
            if result.get('expanded_context'):
                ctx = result['expanded_context']
                if ctx['before']:
                    print(f"\n[Context before: {len(ctx['before'])} chunks]")
                if ctx['after']:
                    print(f"[Context after: {len(ctx['after'])} chunks]")
            
            print()
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()