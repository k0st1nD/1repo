#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quality_tracker.py - Quality Metrics Tracker (MVP v2.0 Enhanced)
================================================================
Track and report quality metrics across pipeline stages with logging integration

Features:
- Stage-wise metrics collection
- JSON reports with timestamps
- Threshold checking with alerts
- Statistics aggregation
- Trend analysis
- Integration with am_logging v2.0
- Performance tracking
- Error aggregation

Version: 2.0.0 Enhanced
Dependencies: am_common, am_logging
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from am_common import PathManager, utc_now_iso
from am_logging import (
    get_logger, log_section, log_metrics,
    log_operation, get_error_aggregator,
    get_performance_tracker
)

logger = get_logger(__name__)

VERSION = "2.0.0"


class QualityThresholds:
    """Quality thresholds for different stages."""
    
    # Structural stage
    STRUCTURAL = {
        'min_success_ratio': 0.95,      # 95% pages extracted successfully
        'max_empty_ratio': 0.10,        # Max 10% empty pages
        'min_avg_page_length': 500,     # Min 500 chars per page average
        'max_error_ratio': 0.05,        # Max 5% error pages
        'max_ocr_ratio': 0.20,          # Max 20% OCR pages (prefer native extraction)
    }
    
    # Structure detection
    STRUCTURE_DETECT = {
        'min_chapters_detected': 1,     # At least 1 chapter
        'min_toc_coverage': 0.80,       # 80% pages in TOC
        'max_orphan_pages': 0.15,       # Max 15% pages without chapter
    }
    
    # Summarization
    SUMMARIZE = {
        'min_summary_ratio': 0.90,      # 90% pages have summaries
        'min_summary_length': 100,      # Min 100 chars per summary
        'max_summary_length': 400,      # Max 400 chars (should be concise)
    }
    
    # Extended stage
    EXTENDED = {
        'max_duplicates_ratio': 0.05,   # Max 5% duplicates
        'min_extended_fields_ratio': 0.70,  # 70% pages have extended fields
        'min_topics_per_page': 1,       # At least 1 topic per page
        'min_lm_extraction_ratio': 0.80,  # 80% using LM (not just heuristics)
        'max_continuity_gaps': 0.10,    # Max 10% pages with continuity gaps
    }
    
    # Finalization
    FINALIZE = {
        'min_validation_pass_rate': 0.99,  # 99% cards should validate
        'max_policy_violations': 0.01,     # Max 1% policy violations
    }
    
    # Chunking
    CHUNK = {
        'min_chunks_per_page': 1,       # At least 1 chunk per page
        'max_chunks_per_page': 20,      # Max 20 chunks per page
        'min_chunk_length': 100,        # Min 100 chars per chunk
        'max_chunk_length': 2000,       # Max 2000 chars per chunk
        'min_avg_tokens': 50,           # Min 50 tokens per chunk
        'max_avg_tokens': 600,          # Max 600 tokens per chunk
    }
    
    # Embedding
    EMBED = {
        'min_embedding_success': 0.99,  # 99% chunks embedded successfully
        'max_embedding_time_per_chunk': 0.5,  # Max 0.5s per chunk
    }


class QualityTracker:
    """Track quality metrics across pipeline stages."""
    
    def __init__(self, output_dir: Optional[Path] = None, config: Optional[Dict] = None):
        """
        Initialize quality tracker.
        
        Args:
            output_dir: Output directory for reports
            config: Configuration dict
        """
        self.path_manager = PathManager()
        self.output_dir = output_dir or self.path_manager.quality
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or {}
        
        # Metrics storage
        self.metrics = defaultdict(list)  # stage -> [metrics]
        
        # Integration with logging
        self.error_aggregator = get_error_aggregator()
        self.performance_tracker = get_performance_tracker()
        
        logger.info(f"Quality tracker initialized: {self.output_dir}")
    
    def track(self, stage: str, source_name: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Track metrics for a stage.
        
        Args:
            stage: pipeline stage name
            source_name: source file/book name
            metrics: metrics dictionary
            
        Returns:
            Threshold check results
        """
        with log_operation(logger, 'track_quality', stage=stage, source=source_name):
            # Create record
            record = {
                'timestamp': utc_now_iso(),
                'stage': stage,
                'source': source_name,
                'metrics': metrics,
            }
            
            # Check thresholds
            threshold_result = self.check_thresholds(stage, metrics)
            record['threshold_check'] = threshold_result
            
            # Store
            self.metrics[stage].append(record)
            
            # Save individual record
            self._save_record(stage, source_name, record)
            
            # Log metrics
            log_metrics(logger, metrics, f"{stage} metrics")
            
            # Log threshold result
            if not threshold_result['passed']:
                logger.warning(f"⚠ Quality thresholds not met for {stage}")
                for violation in threshold_result['violations']:
                    logger.warning(f"  - {violation}")
                
                # Add to error aggregator
                self.error_aggregator.add_warning(
                    stage,
                    f"Quality thresholds not met: {len(threshold_result['violations'])} violations",
                    source=source_name,
                    violations=threshold_result['violations']
                )
            else:
                logger.info(f"✓ Quality thresholds passed for {stage}")
            
            return threshold_result
    
    def check_thresholds(self, stage: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if metrics meet quality thresholds.
        
        Returns:
            {
                'passed': bool,
                'violations': [str],
                'warnings': [str]
            }
        """
        thresholds = self._get_thresholds(stage)
        if not thresholds:
            return {'passed': True, 'violations': [], 'warnings': []}
        
        violations = []
        warnings = []
        
        for key, threshold in thresholds.items():
            if key not in metrics:
                warnings.append(f"Missing metric: {key}")
                continue
            
            value = metrics[key]
            
            # Check threshold
            if key.startswith('min_'):
                if value < threshold:
                    violations.append(f"{key}: {value:.3f} < {threshold} (expected)")
            elif key.startswith('max_'):
                if value > threshold:
                    violations.append(f"{key}: {value:.3f} > {threshold} (expected)")
        
        result = {
            'passed': len(violations) == 0,
            'violations': violations,
            'warnings': warnings,
        }
        
        return result
    
    def _get_thresholds(self, stage: str) -> Dict[str, Any]:
        """Get thresholds for stage."""
        stage_normalized = stage.upper().replace('-', '_')
        
        threshold_map = {
            'STRUCTURAL': QualityThresholds.STRUCTURAL,
            'STRUCTURE_DETECT': QualityThresholds.STRUCTURE_DETECT,
            'SUMMARIZE': QualityThresholds.SUMMARIZE,
            'EXTENDED': QualityThresholds.EXTENDED,
            'FINALIZE': QualityThresholds.FINALIZE,
            'CHUNK': QualityThresholds.CHUNK,
            'EMBED': QualityThresholds.EMBED,
        }
        
        return threshold_map.get(stage_normalized, {})
    
    def _save_record(self, stage: str, source_name: str, record: Dict[str, Any]) -> None:
        """Save individual record to JSON."""
        # Create stage directory
        stage_dir = self.output_dir / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize source name
        safe_name = source_name.replace('/', '_').replace('\\', '_')
        
        # Filename: source_timestamp.json
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_name}_{timestamp}.json"
        filepath = stage_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved quality record: {filepath}")
    
    def generate_report(self, stage: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive quality report.
        
        Args:
            stage: specific stage (None = all stages)
            
        Returns:
            Report dictionary
        """
        with log_operation(logger, 'generate_quality_report', stage=stage or 'all'):
            if stage:
                stages = [stage]
            else:
                stages = list(self.metrics.keys())
            
            report = {
                'generated_at': utc_now_iso(),
                'version': VERSION,
                'stages': {},
            }
            
            for stage_name in stages:
                if stage_name not in self.metrics:
                    continue
                
                records = self.metrics[stage_name]
                stage_report = self._generate_stage_report(stage_name, records)
                report['stages'][stage_name] = stage_report
            
            # Add performance data if available
            perf_stats = self.performance_tracker.get_all_stats()
            if perf_stats:
                report['performance'] = perf_stats
            
            # Add error summary
            error_summary = self.error_aggregator.get_summary()
            if error_summary:
                report['errors'] = error_summary
            
            # Save report
            report_path = self.output_dir / f'quality_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Quality report saved: {report_path}")
            
            # Also save as latest
            latest_path = self.output_dir / 'quality_report_latest.json'
            with open(latest_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            return report
    
    def _generate_stage_report(self, stage: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate report for a single stage."""
        if not records:
            return {'total_runs': 0}
        
        # Aggregate metrics
        all_metrics = [r['metrics'] for r in records]
        
        # Calculate statistics
        stats = {}
        metric_keys = set()
        for m in all_metrics:
            metric_keys.update(m.keys())
        
        for key in metric_keys:
            values = [m.get(key, 0) for m in all_metrics if key in m]
            
            if not values:
                continue
            
            # Check if numeric
            if all(isinstance(v, (int, float)) for v in values):
                stats[key] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'count': len(values),
                }
        
        # Threshold checks
        threshold_checks = []
        for record in records:
            check = record.get('threshold_check', 
                             self.check_thresholds(stage, record['metrics']))
            threshold_checks.append({
                'source': record['source'],
                'timestamp': record['timestamp'],
                'passed': check['passed'],
                'violations': check['violations'],
            })
        
        passed_count = sum(1 for c in threshold_checks if c['passed'])
        
        # Recent trend (last 5 runs)
        recent_records = records[-5:]
        trend = {
            'recent_sources': [r['source'] for r in recent_records],
            'recent_pass_rate': sum(1 for r in recent_records 
                                   if r.get('threshold_check', {}).get('passed', False)) / len(recent_records),
        }
        
        return {
            'total_runs': len(records),
            'passed_threshold': passed_count,
            'failed_threshold': len(records) - passed_count,
            'pass_rate': passed_count / len(records) if records else 0,
            'statistics': stats,
            'threshold_checks': threshold_checks,
            'thresholds': self._get_thresholds(stage),
            'trend': trend,
        }
    
    def print_report(self, stage: Optional[str] = None, detailed: bool = False) -> None:
        """
        Print quality report to console.
        
        Args:
            stage: specific stage (None = all)
            detailed: show detailed statistics
        """
        report = self.generate_report(stage)
        
        log_section(logger, "QUALITY REPORT", "INFO")
        logger.info(f"Generated: {report['generated_at']}")
        logger.info(f"Version: {report['version']}\n")
        
        for stage_name, stage_data in report['stages'].items():
            log_section(logger, f"Stage: {stage_name.upper()}", "INFO", char="-")
            
            if stage_data['total_runs'] == 0:
                logger.info("  No data recorded")
                continue
            
            # Summary
            summary = {
                'total_runs': stage_data['total_runs'],
                'passed_threshold': stage_data['passed_threshold'],
                'failed_threshold': stage_data['failed_threshold'],
                'pass_rate': f"{stage_data['pass_rate']:.1%}",
            }
            log_metrics(logger, summary, "Summary")
            
            # Statistics (if detailed)
            if detailed and stage_data.get('statistics'):
                logger.info("\nStatistics:")
                for metric, stats in stage_data['statistics'].items():
                    logger.info(f"  {metric}:")
                    logger.info(f"    min={stats['min']:.2f}, max={stats['max']:.2f}, avg={stats['avg']:.2f}")
            
            # Recent trend
            if stage_data.get('trend'):
                trend = stage_data['trend']
                logger.info(f"\nRecent trend (last {len(trend['recent_sources'])} runs):")
                logger.info(f"  Pass rate: {trend['recent_pass_rate']:.1%}")
            
            # Failed checks
            failed_checks = [c for c in stage_data['threshold_checks'] if not c['passed']]
            if failed_checks:
                logger.warning(f"\n⚠ Failed threshold checks: {len(failed_checks)}")
                for check in failed_checks[:5]:  # Show first 5
                    logger.warning(f"  {check['source']}:")
                    for violation in check['violations'][:3]:  # Show first 3 violations
                        logger.warning(f"    - {violation}")
                
                if len(failed_checks) > 5:
                    logger.warning(f"  ... and {len(failed_checks) - 5} more")
            
            logger.info("")
        
        # Performance summary (if available)
        if report.get('performance'):
            log_section(logger, "PERFORMANCE SUMMARY", "INFO", char="-")
            for operation, stats in report['performance'].items():
                logger.info(f"{operation}:")
                logger.info(f"  Count: {stats['count']}, Avg: {stats['avg']:.2f}s")
        
        # Error summary (if available)
        if report.get('errors'):
            errors = report['errors']
            if errors['total_errors'] > 0 or errors['total_warnings'] > 0:
                log_section(logger, "ERROR SUMMARY", "WARNING", char="-")
                logger.warning(f"Total Errors: {errors['total_errors']}")
                logger.warning(f"Total Warnings: {errors['total_warnings']}")
    
    def get_trends(self, stage: str, metric_key: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get trend data for a specific metric.
        
        Args:
            stage: stage name
            metric_key: metric key
            limit: number of recent records
            
        Returns:
            List of {timestamp, source, value}
        """
        if stage not in self.metrics:
            return []
        
        records = self.metrics[stage][-limit:]
        
        trends = []
        for record in records:
            if metric_key in record['metrics']:
                trends.append({
                    'timestamp': record['timestamp'],
                    'source': record['source'],
                    'value': record['metrics'][metric_key],
                })
        
        return trends
    
    def compare_sources(self, stage: str, sources: List[str]) -> Dict[str, Any]:
        """
        Compare metrics across multiple sources.
        
        Args:
            stage: stage name
            sources: list of source names
            
        Returns:
            Comparison report
        """
        if stage not in self.metrics:
            return {}
        
        comparison = {}
        
        for source in sources:
            # Find records for this source
            source_records = [
                r for r in self.metrics[stage]
                if r['source'] == source
            ]
            
            if not source_records:
                comparison[source] = {'error': 'No data'}
                continue
            
            # Get latest record
            latest = source_records[-1]
            
            # Get threshold check
            threshold = latest.get('threshold_check', 
                                  self.check_thresholds(stage, latest['metrics']))
            
            comparison[source] = {
                'timestamp': latest['timestamp'],
                'metrics': latest['metrics'],
                'threshold_passed': threshold['passed'],
                'violations': threshold['violations'],
            }
        
        return comparison
    
    def get_summary(self) -> Dict[str, Any]:
        """Get overall quality summary."""
        total_runs = sum(len(records) for records in self.metrics.values())
        
        if total_runs == 0:
            return {
                'total_runs': 0,
                'stages_tracked': 0,
            }
        
        # Count passed/failed
        passed = 0
        failed = 0
        
        for stage, records in self.metrics.items():
            for record in records:
                check = record.get('threshold_check', {})
                if check.get('passed', False):
                    passed += 1
                else:
                    failed += 1
        
        return {
            'total_runs': total_runs,
            'stages_tracked': len(self.metrics),
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / (passed + failed) if (passed + failed) > 0 else 0,
        }


def main():
    """CLI interface."""
    import argparse
    import sys
    from am_logging import setup_logging
    
    parser = argparse.ArgumentParser(description='Quality metrics tracker v2.0')
    parser.add_argument('command', choices=['report', 'check', 'compare', 'summary'],
                       help='Command to execute')
    parser.add_argument('-s', '--stage',
                       help='Pipeline stage')
    parser.add_argument('-f', '--file',
                       help='Metrics JSON file to check')
    parser.add_argument('--sources', nargs='+',
                       help='Source names for comparison')
    parser.add_argument('--detailed', action='store_true',
                       help='Show detailed statistics')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(level=log_level, console=True, colored=True)
    
    tracker = QualityTracker()
    
    if args.command == 'report':
        # Generate and print report
        tracker.print_report(args.stage, detailed=args.detailed)
    
    elif args.command == 'check':
        # Check metrics against thresholds
        if not args.file or not args.stage:
            logger.error("--file and --stage required for check")
            sys.exit(1)
        
        # Load metrics from file
        with open(args.file, 'r') as f:
            data = json.load(f)
        
        metrics = data.get('metrics', {})
        
        # Check thresholds
        result = tracker.check_thresholds(args.stage, metrics)
        
        log_section(logger, f"Threshold Check: {args.stage}", "INFO")
        logger.info(f"Passed: {result['passed']}")
        
        if result['violations']:
            logger.warning("Violations:")
            for v in result['violations']:
                logger.warning(f"  - {v}")
        
        if result['warnings']:
            logger.info("Warnings:")
            for w in result['warnings']:
                logger.info(f"  - {w}")
        
        sys.exit(0 if result['passed'] else 1)
    
    elif args.command == 'compare':
        # Compare sources
        if not args.stage or not args.sources:
            logger.error("--stage and --sources required for compare")
            sys.exit(1)
        
        comparison = tracker.compare_sources(args.stage, args.sources)
        
        log_section(logger, f"Comparison: {args.stage}", "INFO")
        
        for source, data in comparison.items():
            logger.info(f"\n{source}:")
            
            if 'error' in data:
                logger.warning(f"  {data['error']}")
            else:
                logger.info(f"  Timestamp: {data['timestamp']}")
                logger.info(f"  Threshold: {'✓ PASSED' if data['threshold_passed'] else '✗ FAILED'}")
                
                if data['violations']:
                    logger.warning("  Violations:")
                    for v in data['violations']:
                        logger.warning(f"    - {v}")
    
    elif args.command == 'summary':
        # Overall summary
        summary = tracker.get_summary()
        
        log_section(logger, "QUALITY SUMMARY", "INFO")
        log_metrics(logger, summary, "Overall Quality")


if __name__ == '__main__':
    main()