#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch Processing Script for Archivist Magika
Processes entire library with full pipeline and creates unified index.

Usage:
    python batch_process_library.py
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import traceback

# Fix Windows encoding issues (must be after imports, before any print)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add repo root to path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from run_mvp import main as run_mvp_main
from am_common import ConfigLoader, PathManager


class BatchProcessor:
    """Orchestrates batch processing of multiple books."""

    def __init__(self, config_path: str = "config/batch_full.yaml"):
        self.config_path = Path(config_path)
        config_loader = ConfigLoader(self.config_path)
        self.config = config_loader.load()

        # Paths
        self.source_dir = Path(self.config["paths"]["source_pdfs"])
        self.checkpoint_file = Path(self.config["batch"]["checkpoint_file"])

        # Settings
        self.continue_on_error = self.config["batch"]["continue_on_error"]
        self.save_partial = self.config["batch"]["save_partial_results"]
        self.max_retries = self.config["batch"]["max_retries"]

        # Exclusions
        self.exclude_files = set(self.config["batch"].get("exclude_files", []))

        # State
        self.checkpoint = self._load_checkpoint()
        self.results = []
        self.start_time = None

    def _load_checkpoint(self) -> Dict:
        """Load checkpoint from previous run."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "processed_books": [],
            "failed_books": [],
            "last_book": None,
            "timestamp": None
        }

    def _save_checkpoint(self):
        """Save current progress."""
        self.checkpoint["timestamp"] = datetime.now().isoformat()
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(self.checkpoint, indent=2, fp=f)

    def get_pdf_files(self) -> List[Path]:
        """Get all PDF files to process (excluding exceptions)."""
        all_pdfs = sorted(self.source_dir.glob("*.pdf"))

        # Filter out exclusions and already processed
        pdfs = []
        for pdf in all_pdfs:
            if pdf.name in self.exclude_files:
                print(f"⏭️  Excluding: {pdf.name}")
                continue
            if pdf.name in self.checkpoint["processed_books"]:
                print(f"✅ Already processed: {pdf.name}")
                continue
            pdfs.append(pdf)

        return pdfs

    def process_single_book(self, pdf_path: Path) -> Dict:
        """
        Process a single book through the full pipeline.

        Returns:
            Dict with result info (success, error, timing, etc.)
        """
        book_name = pdf_path.name
        result = {
            "book": book_name,
            "path": str(pdf_path),
            "success": False,
            "error": None,
            "stages_completed": [],
            "stages_failed": [],
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "duration_seconds": None
        }

        print(f"\n{'='*80}")
        print(f"📚 PROCESSING: {book_name}")
        print(f"{'='*80}\n")

        start = time.time()

        try:
            # Build command-line args for run_mvp.py
            args = [
                "--input", str(pdf_path),
                "--config", self.config_path,
                "--start", "structural",  # Full pipeline
                "--verbose"
            ]

            # Backup sys.argv
            original_argv = sys.argv

            # Override sys.argv for run_mvp
            sys.argv = ["run_mvp.py"] + args

            # Run the pipeline
            print(f"🚀 Running pipeline with config: {self.config_path}")
            run_mvp_main()

            # Restore sys.argv
            sys.argv = original_argv

            # Success!
            result["success"] = True
            result["stages_completed"] = [
                "structural", "structure_detect", "summarize",
                "extended", "finalize", "chunk", "embed"
            ]

            print(f"\n✅ SUCCESS: {book_name}")

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["error_traceback"] = traceback.format_exc()

            print(f"\n❌ FAILED: {book_name}")
            print(f"Error: {e}")

            if not self.continue_on_error:
                raise  # Re-raise to stop batch

        finally:
            end = time.time()
            result["end_time"] = datetime.now().isoformat()
            result["duration_seconds"] = round(end - start, 2)

        return result

    def process_batch(self):
        """Process all books in the batch."""
        self.start_time = time.time()

        # Get PDFs to process
        pdfs = self.get_pdf_files()
        total = len(pdfs)

        if total == 0:
            print("✅ No books to process (all already done or excluded)")
            return

        print(f"\n🔥 BATCH PROCESSING: {total} books")
        print(f"Config: {self.config_path}")
        print(f"Continue on error: {self.continue_on_error}")
        print(f"Save partial results: {self.save_partial}")
        print(f"Exclusions: {', '.join(self.exclude_files)}\n")

        # Process each book
        for idx, pdf_path in enumerate(pdfs, 1):
            print(f"\n📊 Progress: {idx}/{total}")

            # Process with retries
            result = None
            for attempt in range(1, self.max_retries + 1):
                if attempt > 1:
                    print(f"🔄 Retry {attempt}/{self.max_retries} for {pdf_path.name}")

                result = self.process_single_book(pdf_path)

                if result["success"]:
                    # Success - mark as processed
                    self.checkpoint["processed_books"].append(pdf_path.name)
                    self.checkpoint["last_book"] = pdf_path.name
                    break
                else:
                    # Failed
                    if attempt == self.max_retries:
                        # Final attempt failed
                        self.checkpoint["failed_books"].append({
                            "book": pdf_path.name,
                            "error": result["error"],
                            "attempts": self.max_retries
                        })
                        print(f"❌ Gave up after {self.max_retries} attempts")

            # Save result
            self.results.append(result)

            # Save checkpoint
            self._save_checkpoint()

            # Print interim stats
            success_count = len([r for r in self.results if r["success"]])
            fail_count = len(self.results) - success_count
            print(f"\n📈 Current stats: {success_count} ✅ / {fail_count} ❌")

        # Final summary
        self._print_summary()
        self._save_final_report()

    def _print_summary(self):
        """Print final batch summary."""
        total_time = time.time() - self.start_time

        success = [r for r in self.results if r["success"]]
        failed = [r for r in self.results if not r["success"]]

        print(f"\n{'='*80}")
        print(f"📊 BATCH PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"Total books: {len(self.results)}")
        print(f"✅ Success: {len(success)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"⏱️  Total time: {total_time/60:.1f} minutes")
        print(f"⏱️  Avg time per book: {total_time/len(self.results):.1f} seconds")
        print(f"{'='*80}\n")

        if failed:
            print("❌ FAILED BOOKS:")
            for r in failed:
                print(f"  - {r['book']}: {r['error'][:100]}")
            print()

    def _save_final_report(self):
        """Save comprehensive final report."""
        report_path = Path("logs/batch_processing_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "config": self.config_path,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": round(time.time() - self.start_time, 2),
            "total_books": len(self.results),
            "successful": len([r for r in self.results if r["success"]]),
            "failed": len([r for r in self.results if not r["success"]]),
            "excluded_books": list(self.exclude_files),
            "results": self.results
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, indent=2, fp=f)

        print(f"📄 Full report saved: {report_path}")


def main():
    """Main entry point."""
    print("""
    ================================================================
         ARCHIVIST MAGIKA - BATCH PROCESSING PIPELINE
                    Maximum Quality Mode
    ================================================================
    """)

    # Create processor
    processor = BatchProcessor(config_path="config/batch_full.yaml")

    # Run batch
    try:
        processor.process_batch()
        print("\n🎉 BATCH PROCESSING COMPLETE!")
        return 0

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user. Progress saved to checkpoint.")
        processor._save_checkpoint()
        return 130

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
        processor._save_checkpoint()
        return 1


if __name__ == "__main__":
    sys.exit(main())
