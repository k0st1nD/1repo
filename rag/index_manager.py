#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
index_manager.py - FAISS Index Management (MVP v2.0)
====================================================
Manage FAISS indexes and metadata for RAG search

Features:
- Load/unload indexes
- List available indexes
- Get index information
- Validate index integrity
- Cache management

Version: 2.0.0
Dependencies: am_common, faiss-cpu, pickle
"""

import logging
import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("[ERROR] faiss not available. Install: pip install faiss-cpu")

from am_common import PathManager, format_size

logger = logging.getLogger('index_manager')

VERSION = "2.0.0"


@dataclass
class IndexInfo:
    """Index metadata information."""
    name: str
    index_path: Path
    metadata_path: Path
    info_path: Optional[Path]
    
    # Index stats
    total_vectors: int
    dimension: int
    index_type: str
    metric: str
    
    # File info
    index_size: int
    metadata_size: int
    
    # Creation info
    model: Optional[str]
    created_at: Optional[str]
    version: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'index_path': str(self.index_path),
            'metadata_path': str(self.metadata_path),
            'total_vectors': self.total_vectors,
            'dimension': self.dimension,
            'index_type': self.index_type,
            'metric': self.metric,
            'index_size': self.index_size,
            'index_size_human': format_size(self.index_size),
            'metadata_size': self.metadata_size,
            'metadata_size_human': format_size(self.metadata_size),
            'model': self.model,
            'created_at': self.created_at,
            'version': self.version,
        }


class IndexManager:
    """Manage FAISS indexes for RAG search."""
    
    def __init__(self, index_dir: Optional[Path] = None, 
                 metadata_dir: Optional[Path] = None):
        """
        Initialize IndexManager.
        
        Args:
            index_dir: Directory containing FAISS indexes (default: from PathManager)
            metadata_dir: Directory containing metadata files (default: from PathManager)
        """
        if not FAISS_AVAILABLE:
            raise RuntimeError("faiss is required for index management")
        
        self.path_manager = PathManager()
        
        self.index_dir = index_dir or self.path_manager.index_faiss
        self.metadata_dir = metadata_dir or self.path_manager.index_metadata
        
        # Ensure directories exist
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for loaded indexes
        self._cache: Dict[str, Tuple[faiss.Index, List[Dict[str, Any]]]] = {}
        
        logger.info(f"IndexManager initialized")
        logger.info(f"  Index dir: {self.index_dir}")
        logger.info(f"  Metadata dir: {self.metadata_dir}")
    
    def list_indexes(self) -> List[str]:
        """
        List all available index names.
        
        Returns:
            List of index names (without extensions)
        """
        index_files = list(self.index_dir.glob("*.faiss"))
        names = [f.stem for f in index_files]
        
        # Verify metadata exists
        valid_names = []
        for name in names:
            metadata_path = self.metadata_dir / f"{name}.pkl"
            if metadata_path.exists():
                valid_names.append(name)
            else:
                logger.warning(f"Index {name} has no metadata file, skipping")
        
        return sorted(valid_names)
    
    def get_index_info(self, name: str) -> Optional[IndexInfo]:
        """
        Get information about an index.
        
        Args:
            name: Index name (without extension)
            
        Returns:
            IndexInfo object or None if not found
        """
        index_path = self.index_dir / f"{name}.faiss"
        metadata_path = self.metadata_dir / f"{name}.pkl"
        info_path = self.metadata_dir / f"{name}.info.json"
        
        if not index_path.exists() or not metadata_path.exists():
            logger.error(f"Index {name} not found")
            return None
        
        # Load index to get stats
        try:
            index = faiss.read_index(str(index_path))
            total_vectors = index.ntotal
            dimension = index.d
            
            # Determine index type
            index_type = self._get_index_type(index)
            
            # Determine metric
            metric = self._get_index_metric(index)
            
        except Exception as e:
            logger.error(f"Failed to load index {name}: {e}")
            return None
        
        # Get file sizes
        index_size = index_path.stat().st_size
        metadata_size = metadata_path.stat().st_size
        
        # Load info.json if exists
        model = None
        created_at = None
        version_info = None
        
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info_data = json.load(f)
                    model = info_data.get('model')
                    created_at = info_data.get('created_at')
                    version_info = info_data.get('version')
            except Exception as e:
                logger.warning(f"Failed to load info.json for {name}: {e}")
        
        return IndexInfo(
            name=name,
            index_path=index_path,
            metadata_path=metadata_path,
            info_path=info_path if info_path.exists() else None,
            total_vectors=total_vectors,
            dimension=dimension,
            index_type=index_type,
            metric=metric,
            index_size=index_size,
            metadata_size=metadata_size,
            model=model,
            created_at=created_at,
            version=version_info,
        )
    
    def load_index(self, name: str, use_cache: bool = True) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
        """
        Load FAISS index and metadata.
        
        Args:
            name: Index name (without extension)
            use_cache: Use cached index if available
            
        Returns:
            (faiss_index, metadata_list)
        """
        # Check cache
        if use_cache and name in self._cache:
            logger.debug(f"Using cached index: {name}")
            return self._cache[name]
        
        index_path = self.index_dir / f"{name}.faiss"
        metadata_path = self.metadata_dir / f"{name}.pkl"
        
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found: {index_path}")
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        
        logger.info(f"Loading index: {name}")
        
        # Load FAISS index
        try:
            index = faiss.read_index(str(index_path))
            logger.info(f"  Loaded FAISS index: {index.ntotal} vectors, dim={index.d}")
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            raise
        
        # Load metadata
        try:
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
            logger.info(f"  Loaded metadata: {len(metadata)} items")
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            raise
        
        # Validate consistency
        if index.ntotal != len(metadata):
            logger.warning(
                f"Index/metadata size mismatch: "
                f"index={index.ntotal}, metadata={len(metadata)}"
            )
        
        # Cache
        if use_cache:
            self._cache[name] = (index, metadata)
        
        return index, metadata
    
    def unload_index(self, name: str) -> bool:
        """
        Unload index from cache.
        
        Args:
            name: Index name
            
        Returns:
            True if unloaded, False if not in cache
        """
        if name in self._cache:
            del self._cache[name]
            logger.info(f"Unloaded index from cache: {name}")
            return True
        return False
    
    def clear_cache(self) -> int:
        """
        Clear all cached indexes.
        
        Returns:
            Number of indexes cleared
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared cache: {count} indexes")
        return count
    
    def validate_index(self, name: str) -> Dict[str, Any]:
        """
        Validate index integrity.
        
        Args:
            name: Index name
            
        Returns:
            Validation report
        """
        report = {
            'index_name': name,
            'valid': False,
            'errors': [],
            'warnings': [],
        }
        
        # Check files exist
        index_path = self.index_dir / f"{name}.faiss"
        metadata_path = self.metadata_dir / f"{name}.pkl"
        
        if not index_path.exists():
            report['errors'].append(f"Index file not found: {index_path}")
            return report
        
        if not metadata_path.exists():
            report['errors'].append(f"Metadata file not found: {metadata_path}")
            return report
        
        # Load and validate
        try:
            index, metadata = self.load_index(name, use_cache=False)
            
            # Check sizes match
            if index.ntotal != len(metadata):
                report['warnings'].append(
                    f"Size mismatch: index={index.ntotal}, metadata={len(metadata)}"
                )
            
            # Check metadata structure
            if metadata:
                sample = metadata[0]
                required_fields = ['chunk_id', 'text']
                missing_fields = [f for f in required_fields if f not in sample]
                if missing_fields:
                    report['warnings'].append(f"Missing fields in metadata: {missing_fields}")
            
            # Check index dimension
            if index.d <= 0:
                report['errors'].append(f"Invalid index dimension: {index.d}")
            
            # All checks passed
            if not report['errors']:
                report['valid'] = True
                report['total_vectors'] = index.ntotal
                report['dimension'] = index.d
                report['metadata_count'] = len(metadata)
        
        except Exception as e:
            report['errors'].append(f"Validation error: {str(e)}")
        
        return report
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for all indexes.
        
        Returns:
            Statistics dictionary
        """
        indexes = self.list_indexes()
        
        total_vectors = 0
        total_index_size = 0
        total_metadata_size = 0
        
        index_details = []
        
        for name in indexes:
            info = self.get_index_info(name)
            if info:
                total_vectors += info.total_vectors
                total_index_size += info.index_size
                total_metadata_size += info.metadata_size
                
                index_details.append({
                    'name': name,
                    'vectors': info.total_vectors,
                    'dimension': info.dimension,
                    'size': format_size(info.index_size + info.metadata_size),
                })
        
        return {
            'total_indexes': len(indexes),
            'total_vectors': total_vectors,
            'total_index_size': total_index_size,
            'total_index_size_human': format_size(total_index_size),
            'total_metadata_size': total_metadata_size,
            'total_metadata_size_human': format_size(total_metadata_size),
            'cached_indexes': len(self._cache),
            'indexes': index_details,
        }
    
    def _get_index_type(self, index: faiss.Index) -> str:
        """Determine index type from FAISS index."""
        index_class = index.__class__.__name__
        
        if 'Flat' in index_class:
            return 'flat'
        elif 'IVF' in index_class:
            return 'ivf'
        elif 'HNSW' in index_class:
            return 'hnsw'
        else:
            return index_class.lower()
    
    def _get_index_metric(self, index: faiss.Index) -> str:
        """Determine metric from FAISS index."""
        index_class = index.__class__.__name__
        
        if 'IP' in index_class:
            return 'cosine'  # Inner Product (used with normalized vectors)
        elif 'L2' in index_class:
            return 'l2'
        else:
            return 'unknown'


def main():
    """CLI interface for index management."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='FAISS Index Management (MVP v2.0)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # List command
    subparsers.add_parser('list', help='List all indexes')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Get index information')
    info_parser.add_argument('name', help='Index name')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate index')
    validate_parser.add_argument('name', help='Index name')
    
    # Stats command
    subparsers.add_parser('stats', help='Get statistics for all indexes')
    
    # Clear cache command
    subparsers.add_parser('clear-cache', help='Clear index cache')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize manager
    manager = IndexManager()
    
    # Execute command
    if args.command == 'list':
        indexes = manager.list_indexes()
        if indexes:
            print(f"Found {len(indexes)} indexes:")
            for name in indexes:
                print(f"  - {name}")
        else:
            print("No indexes found")
    
    elif args.command == 'info':
        info = manager.get_index_info(args.name)
        if info:
            print(json.dumps(info.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"Index not found: {args.name}")
            sys.exit(1)
    
    elif args.command == 'validate':
        report = manager.validate_index(args.name)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not report['valid']:
            sys.exit(1)
    
    elif args.command == 'stats':
        stats = manager.get_statistics()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif args.command == 'clear-cache':
        count = manager.clear_cache()
        print(f"Cleared {count} cached indexes")


if __name__ == '__main__':
    main()