#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor_realtime.py - Real-time Pipeline Monitor
================================================
Shows live progress of batch processing with detailed statistics.

Features:
- Real-time book processing progress
- Current stage tracking
- LM extraction status
- Time estimates
- Resource usage (optional)

Version: 1.0.0
Usage: python tools/monitor_realtime.py [--log-dir logs/batch_lm_v3]
"""

import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class PipelineMonitor:
    """Real-time pipeline progress monitor."""

    STAGES = [
        'structural', 'structure_detect', 'summarize',
        'extended', 'finalize', 'chunk', 'embed'
    ]

    def __init__(self, log_dir: str = "logs/batch_lm_v3"):
        self.log_dir = Path(log_dir)
        self.refresh_interval = 5  # seconds
        self.books_status = {}
        self.start_time = None

    def clear_screen(self):
        """Clear terminal screen."""
        print('\033[2J\033[H', end='')  # ANSI escape codes

    def parse_log_file(self, log_path: Path) -> Dict:
        """Parse individual log file for progress."""
        status = {
            'current_stage': None,
            'completed_stages': [],
            'status': 'processing',
            'error': None,
            'lm_extraction': False,
            'progress_percent': 0
        }

        if not log_path.exists():
            status['status'] = 'pending'
            return status

        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Check for completion
            if 'Pipeline completed successfully' in content or 'SUCCESS' in content:
                status['status'] = 'completed'
                status['progress_percent'] = 100
                status['completed_stages'] = self.STAGES.copy()
            elif 'ERROR' in content or 'FAIL' in content:
                status['status'] = 'failed'
                # Find last completed stage
                for stage in self.STAGES:
                    if f"Stage: {stage}" in content and "completed" in content:
                        status['completed_stages'].append(stage)

            # Find current/last stage
            for line in content.split('\n')[-50:]:  # Check last 50 lines
                if 'Stage:' in line:
                    for stage in self.STAGES:
                        if stage in line:
                            status['current_stage'] = stage
                            if stage not in status['completed_stages']:
                                status['completed_stages'].append(stage)
                            break

            # Check LM extraction
            if 'LM EXTRACTION' in content or 'qwen2.5:7b' in content:
                status['lm_extraction'] = True

            # Calculate progress
            if status['status'] == 'processing':
                completed = len(status['completed_stages'])
                status['progress_percent'] = int((completed / len(self.STAGES)) * 100)

        except Exception as e:
            status['error'] = str(e)

        return status

    def scan_logs(self) -> Dict[str, Dict]:
        """Scan all log files in directory."""
        if not self.log_dir.exists():
            return {}

        books = {}
        for log_file in self.log_dir.glob('*.log'):
            book_name = log_file.stem
            books[book_name] = self.parse_log_file(log_file)

        return books

    def get_summary_stats(self) -> Dict:
        """Calculate summary statistics."""
        total = len(self.books_status)
        completed = sum(1 for b in self.books_status.values() if b['status'] == 'completed')
        failed = sum(1 for b in self.books_status.values() if b['status'] == 'failed')
        processing = sum(1 for b in self.books_status.values() if b['status'] == 'processing')
        pending = total - completed - failed - processing

        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'processing': processing,
            'pending': pending,
            'success_rate': (completed / total * 100) if total > 0 else 0
        }

    def format_time_elapsed(self, seconds: int) -> str:
        """Format seconds to human-readable time."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}h {mins}m"

    def estimate_eta(self, stats: Dict, elapsed: int) -> Optional[str]:
        """Estimate time to completion."""
        completed = stats['completed']
        processing = stats['processing']
        pending = stats['pending']

        if completed == 0:
            return "Calculating..."

        avg_time_per_book = elapsed / completed
        remaining = processing + pending
        eta_seconds = int(avg_time_per_book * remaining)

        return self.format_time_elapsed(eta_seconds)

    def render_progress_bar(self, percent: int, width: int = 20) -> str:
        """Render ASCII progress bar."""
        filled = int(width * percent / 100)
        bar = '=' * filled + '-' * (width - filled)
        return f"[{bar}] {percent}%"

    def display(self):
        """Display current status."""
        self.clear_screen()

        now = datetime.now()
        stats = self.get_summary_stats()

        # Calculate elapsed time
        if not self.start_time:
            # Try to find oldest log file
            if self.log_dir.exists():
                log_files = list(self.log_dir.glob('*.log'))
                if log_files:
                    oldest = min(log_files, key=lambda p: p.stat().st_mtime)
                    self.start_time = datetime.fromtimestamp(oldest.stat().st_mtime)
                else:
                    self.start_time = now

        elapsed = int((now - self.start_time).total_seconds()) if self.start_time else 0
        eta = self.estimate_eta(stats, elapsed) if elapsed > 0 else "N/A"

        # Header
        print("=" * 80)
        print(f"  ARCHIVIST MAGIKA v2.0 - REAL-TIME PIPELINE MONITOR")
        print(f"  {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()

        # Summary
        print(f"SUMMARY:")
        print(f"  Total books: {stats['total']}")
        print(f"  Completed:   {stats['completed']} ({stats['success_rate']:.1f}%)")
        print(f"  Failed:      {stats['failed']}")
        print(f"  Processing:  {stats['processing']}")
        print(f"  Pending:     {stats['pending']}")
        print()
        print(f"  Elapsed: {self.format_time_elapsed(elapsed)}")
        print(f"  ETA:     {eta}")
        print()

        # Overall progress bar
        overall_progress = int((stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0)
        print(f"  Overall: {self.render_progress_bar(overall_progress, width=50)}")
        print()
        print("-" * 80)

        # Currently processing books
        processing_books = {k: v for k, v in self.books_status.items()
                           if v['status'] == 'processing'}

        if processing_books:
            print()
            print("CURRENTLY PROCESSING:")
            for book_name, status in sorted(processing_books.items())[:5]:  # Show max 5
                stage = status.get('current_stage', 'unknown')
                progress = status.get('progress_percent', 0)
                lm_mark = '[LM]' if status.get('lm_extraction') else '    '

                print(f"  {lm_mark} {book_name[:50]:<50}")
                print(f"       Stage: {stage:<20} {self.render_progress_bar(progress, 30)}")
        else:
            print()
            print("No books currently processing...")

        # Recently completed
        completed_books = [(k, v) for k, v in self.books_status.items()
                          if v['status'] == 'completed']
        if completed_books:
            print()
            print(f"COMPLETED ({len(completed_books)}):")
            for book_name, status in sorted(completed_books, key=lambda x: x[0])[-10:]:  # Last 10
                lm_mark = '[LM]' if status.get('lm_extraction') else '    '
                print(f"  {lm_mark} [OK] {book_name[:60]}")

        # Failed books
        failed_books = {k: v for k, v in self.books_status.items()
                       if v['status'] == 'failed'}
        if failed_books:
            print()
            print(f"FAILED ({len(failed_books)}):")
            for book_name, status in sorted(failed_books.items())[:5]:
                print(f"  [FAIL] {book_name[:60]}")

        # Footer
        print()
        print("=" * 80)
        print(f"  Refreshing every {self.refresh_interval}s... (Press Ctrl+C to exit)")
        print("=" * 80)

    def run(self):
        """Run monitoring loop."""
        print("Starting pipeline monitor...")
        print(f"Watching: {self.log_dir}")
        print()

        try:
            while True:
                self.books_status = self.scan_logs()
                self.display()

                # Check if all done
                stats = self.get_summary_stats()
                if stats['processing'] == 0 and stats['pending'] == 0:
                    print()
                    print("[INFO] All books processed. Monitoring stopped.")
                    break

                time.sleep(self.refresh_interval)

        except KeyboardInterrupt:
            print()
            print()
            print("[INFO] Monitoring stopped by user")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Real-time pipeline monitor")
    parser.add_argument(
        '--log-dir',
        default='logs/batch_lm_v3',
        help='Log directory to monitor (default: logs/batch_lm_v3)'
    )
    parser.add_argument(
        '--refresh',
        type=int,
        default=5,
        help='Refresh interval in seconds (default: 5)'
    )

    args = parser.parse_args()

    monitor = PipelineMonitor(log_dir=args.log_dir)
    monitor.refresh_interval = args.refresh
    monitor.run()


if __name__ == '__main__':
    main()
