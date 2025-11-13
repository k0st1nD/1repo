#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_mvp.py - Archivist Magika MVP v2.0 Orchestrator
===================================================
Main entry point for running the complete RAG pipeline with enhanced logging

Version: 2.0.1 - UTF-8 encoding fix + LM extraction fix
"""

import sys
import os

# ============================================
# UTF-8 ENCODING SETUP (Windows compatibility)
# ============================================
if sys.platform == 'win32':
    # Для stdout/stderr
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding='utf-8',
        errors='replace',
        line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer,
        encoding='utf-8',
        errors='replace',
        line_buffering=True
    )

    # Для Windows Console API
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)  # UTF-8
    except Exception:
        pass  # Не критично если не удалось

from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse

# Logging
from am_logging import (
    setup_logging_from_config, get_logger, log_section, log_stage,
    log_performance_summary, log_error_summary, reset_tracking,
    create_progress_bar, log_operation, log_metrics
)

# Import with try/except for compatibility
try:
    from am_structural_robust import RobustStructuralProcessor
except ImportError:
    from am_structural import StructuralProcessor as RobustStructuralProcessor

try:
    from am_structure_detect import StructureProcessor
except ImportError:
    from am_structure_detect import StructureDetectionProcessor as StructureProcessor

try:
    from am_summarize import SummarizationProcessor
except ImportError:
    try:
        from am_summarize import SummaryProcessor as SummarizationProcessor
    except ImportError:
        from am_summarize import Summarizer as SummarizationProcessor

try:
    from am_extended import ExtendedProcessor
except ImportError:
    from am_extended import ExtendedFieldsProcessor as ExtendedProcessor

try:
    from am_finalize import FinalizeProcessor
except ImportError:
    from am_finalize import DatasetFinalizer as FinalizeProcessor

try:
    from am_chunk import ChunkProcessor
except ImportError:
    from am_chunk import Chunker as ChunkProcessor

try:
    from am_embed import EmbedProcessor
except ImportError:
    from am_embed import Embedder as EmbedProcessor

# Tools
from quality_tracker import QualityTracker
from validate import DatasetValidator
from am_common import PathManager, ConfigLoader

logger = get_logger(__name__)

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"


# ============================================
# PIPELINE STAGES
# ============================================

class PipelineStage:
    """Pipeline stage configuration."""
    STRUCTURAL = 'structural'
    STRUCTURE_DETECT = 'structure_detect'
    SUMMARIZE = 'summarize'
    EXTENDED = 'extended'
    FINALIZE = 'finalize'
    CHUNK = 'chunk'
    EMBED = 'embed'
    
    ALL = [
        STRUCTURAL,
        STRUCTURE_DETECT,
        SUMMARIZE,
        EXTENDED,
        FINALIZE,
        CHUNK,
        EMBED,
    ]


# ============================================
# PIPELINE ORCHESTRATOR
# ============================================

class PipelineOrchestrator:
    """Orchestrate the complete RAG pipeline with enhanced features."""
    
    def __init__(self, config_path: Optional[Path] = None,
                 quality_check: bool = True,
                 validate_stages: bool = True,
                 dry_run: bool = False):
        """
        Initialize orchestrator.
        
        Args:
            config_path: Path to config file
            quality_check: Enable quality checking
            validate_stages: Validate output after each stage
            dry_run: Dry run mode (plan only, no execution)
        """
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.path_manager = PathManager()
        
        self.quality_check = quality_check
        self.validate_stages = validate_stages
        self.dry_run = dry_run
        
        # Initialize tools
        self.quality_tracker = QualityTracker() if quality_check else None
        self.validator = DatasetValidator() if validate_stages else None
        
        # Initialize processors (lazy loading)
        self.processors = {}
        
        # Setup logging from config
        setup_logging_from_config(self.config)
        
        log_section(logger, f"🚀 {PRODUCT_NAME} {VERSION}", "INFO")
        logger.info(f"Quality check: {'enabled' if quality_check else 'disabled'}")
        logger.info(f"Validation: {'enabled' if validate_stages else 'disabled'}")
        logger.info(f"Dry run: {'yes' if dry_run else 'no'}")
    
    def _get_processor(self, stage: str) -> Any:
        """Get or create processor for stage."""
        if stage in self.processors:
            return self.processors[stage]
        
        processor_map = {
            PipelineStage.STRUCTURAL: RobustStructuralProcessor,
            PipelineStage.STRUCTURE_DETECT: StructureProcessor,
            PipelineStage.SUMMARIZE: SummarizationProcessor,
            PipelineStage.EXTENDED: ExtendedProcessor,
            PipelineStage.FINALIZE: FinalizeProcessor,
            PipelineStage.CHUNK: ChunkProcessor,
            PipelineStage.EMBED: EmbedProcessor,
        }
        
        processor_class = processor_map.get(stage)
        if not processor_class:
            raise ValueError(f"Unknown stage: {stage}")
        
        # Create processor with config_path
        try:
            processor = processor_class(self.config_loader.config_path)
        except TypeError:
            # Fallback: try without config
            processor = processor_class()
        
        # Inject quality tracker if available
        if self.quality_tracker and hasattr(processor, 'quality_tracker'):
            processor.quality_tracker = self.quality_tracker
        
        self.processors[stage] = processor
        logger.debug(f"Initialized processor: {stage}")
        
        return processor
    
    def run_single(self, input_path: Path,
                  start_stage: str = PipelineStage.STRUCTURAL,
                  end_stage: str = PipelineStage.EMBED) -> Dict[str, Any]:
        """
        Run pipeline for single file.
        
        Args:
            input_path: Path to input file (PDF or dataset)
            start_stage: Stage to start from
            end_stage: Stage to end at
            
        Returns:
            Pipeline results
        """
        with log_operation(logger, "run_single_pipeline",
                          input=str(input_path),
                          start=start_stage,
                          end=end_stage):
            
            logger.info(f"Processing: {input_path.name}")
            logger.info(f"Pipeline: {start_stage} → {end_stage}")
            
            if self.dry_run:
                logger.info("[DRY RUN] Simulating execution")
                stages = self._get_stage_sequence(start_stage, end_stage)
                return {
                    'status': 'dry_run',
                    'input': str(input_path),
                    'stages_planned': stages
                }
            
            # Get stage sequence
            stages = self._get_stage_sequence(start_stage, end_stage)
            logger.info(f"Stages: {' → '.join(stages)}")
            
            results = {
                'input': str(input_path),
                'stages': {},
                'errors': [],
                'warnings': [],
            }
            
            current_input = input_path
            
            # Execute stages
            for stage in stages:
                log_stage(logger, stage, "Starting")
                
                try:
                    # Run stage
                    stage_result = self._run_stage(stage, current_input)
                    
                    # Validate output
                    if self.validate_stages and stage != PipelineStage.EMBED:
                        try:
                            validation_result = self._validate_output(stage, stage_result)
                            
                            if not validation_result['valid']:
                                logger.warning(
                                    f"Validation issues: {validation_result.get('error_count', 0)} errors"
                                )
                                results['warnings'].append({
                                    'stage': stage,
                                    'validation_errors': validation_result.get('error_count', 0),
                                })
                        except Exception as e:
                            logger.warning(f"Validation failed: {e}")
                    
                    # Store result
                    results['stages'][stage] = {
                        'status': 'success',
                        'output': str(stage_result),
                    }
                    
                    # Update input for next stage
                    current_input = stage_result
                    
                    log_stage(logger, stage, "Completed")
                    
                except Exception as e:
                    logger.error(f"Stage failed: {e}")
                    logger.exception("Error details:")
                    
                    results['stages'][stage] = {
                        'status': 'failed',
                        'error': str(e),
                    }
                    results['errors'].append({
                        'stage': stage,
                        'error': str(e),
                    })
                    
                    # Decide whether to continue
                    if self._is_critical_stage(stage):
                        logger.error("Critical stage failed, stopping pipeline")
                        break
                    else:
                        logger.warning("Non-critical stage failed, attempting to continue")
            
            # Determine final status
            if not results['errors']:
                results['status'] = 'completed'
            elif len(results['errors']) < len(stages):
                results['status'] = 'partial'
            else:
                results['status'] = 'failed'
            
            logger.info(f"Pipeline status: {results['status']}")
            
            return results
    
    def run_batch(self, input_dir: Path,
                 pattern: str = '*.pdf',
                 start_stage: str = PipelineStage.STRUCTURAL,
                 end_stage: str = PipelineStage.EMBED,
                 continue_on_error: bool = True) -> Dict[str, Any]:
        """
        Run pipeline for multiple files.
        
        Args:
            input_dir: Directory containing input files
            pattern: File pattern
            start_stage: Stage to start from
            end_stage: Stage to end at
            continue_on_error: Continue processing other files on error
            
        Returns:
            Batch results
        """
        with log_operation(logger, "run_batch_pipeline",
                          input_dir=str(input_dir),
                          pattern=pattern):
            
            logger.info(f"Batch processing: {input_dir}")
            logger.info(f"Pattern: {pattern}")
            
            # Find input files
            input_files = sorted(input_dir.glob(pattern))
            logger.info(f"Found {len(input_files)} files")
            
            if not input_files:
                logger.error("No input files found")
                return {
                    'status': 'error',
                    'message': 'No input files found',
                    'total_files': 0,
                }
            
            if self.dry_run:
                logger.info("[DRY RUN] Would process these files:")
                for f in input_files:
                    logger.info(f"  - {f.name}")
                return {
                    'status': 'dry_run',
                    'total_files': len(input_files),
                    'files': [f.name for f in input_files],
                }
            
            # Process each file
            results = {
                'total_files': len(input_files),
                'processed': [],
                'failed': [],
                'partial': [],
            }
            
            # Use progress bar
            for input_file in create_progress_bar(input_files, desc="Processing files"):
                try:
                    result = self.run_single(input_file, start_stage, end_stage)
                    
                    if result['status'] == 'completed':
                        results['processed'].append(input_file.name)
                    elif result['status'] == 'partial':
                        results['partial'].append({
                            'file': input_file.name,
                            'errors': result['errors'],
                        })
                    else:
                        results['failed'].append({
                            'file': input_file.name,
                            'errors': result['errors'],
                        })
                    
                except Exception as e:
                    logger.error(f"Failed to process {input_file.name}: {e}")
                    results['failed'].append({
                        'file': input_file.name,
                        'error': str(e),
                    })
                    
                    if not continue_on_error:
                        logger.error("Stopping batch processing due to error")
                        break
            
            # Summary
            log_section(logger, "BATCH PROCESSING SUMMARY", "INFO")
            
            summary_metrics = {
                'total_files': results['total_files'],
                'fully_processed': len(results['processed']),
                'partially_processed': len(results['partial']),
                'failed': len(results['failed']),
                'success_rate': f"{len(results['processed']) / results['total_files']:.1%}" if results['total_files'] > 0 else "0%",
            }
            
            log_metrics(logger, summary_metrics, "Batch Results")
            
            if results['failed']:
                logger.warning("\nFailed files:")
                for item in results['failed']:
                    logger.warning(f"  - {item['file']}")
            
            if results['partial']:
                logger.warning("\nPartially processed files:")
                for item in results['partial']:
                    logger.warning(f"  - {item['file']}")
            
            results['status'] = 'completed'
            
            return results
    
    def _run_stage(self, stage: str, input_path: Path) -> Path:
        """Run a single pipeline stage."""
        processor = self._get_processor(stage)
        
        # Get output directory
        output_dir = self._get_stage_output_dir(stage)
        
        # Stage-specific processing with flexible method names
        if stage == PipelineStage.STRUCTURAL:
            # Try different method names
            if hasattr(processor, 'process_pdf'):
                return processor.process_pdf(input_path, output_dir)
            elif hasattr(processor, 'process'):
                return processor.process(input_path, output_dir)
            else:
                raise AttributeError(f"Processor has no process method")
        
        elif stage in [PipelineStage.STRUCTURE_DETECT, PipelineStage.SUMMARIZE, 
                       PipelineStage.EXTENDED, PipelineStage.FINALIZE, PipelineStage.CHUNK]:
            # Try different method names
            if hasattr(processor, 'process_dataset'):
                return processor.process_dataset(input_path, output_dir)
            elif hasattr(processor, 'process'):
                return processor.process(input_path, output_dir)
            else:
                raise AttributeError(f"Processor has no process method")
        
        elif stage == PipelineStage.EMBED:
            # Embed stage uses automatic output paths from PathManager
            if hasattr(processor, 'process_chunks'):
                return processor.process_chunks(input_path, output_dir=None)
            elif hasattr(processor, 'process'):
                return processor.process(input_path, output_dir=None)
            else:
                raise AttributeError(f"Processor has no process method")
        
        else:
            raise ValueError(f"Unknown stage: {stage}")
    
    def _validate_output(self, stage: str, output_path: Path) -> Dict[str, Any]:
        """Validate stage output."""
        if not self.validator:
            return {'valid': True}
        
        try:
            result = self.validator.validate_dataset(output_path, stage)
            
            if not result.get('valid', False):
                logger.warning(
                    f"Validation issues: {result.get('error_count', 0)} errors, "
                    f"{result.get('warning_count', 0)} warnings"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                'valid': False,
                'error_count': 1,
                'warning_count': 0,
                'error': str(e),
            }
    
    def _get_stage_output_dir(self, stage: str) -> Path:
        """Get output directory for stage."""
        stage_dirs = {
            PipelineStage.STRUCTURAL: self.path_manager.dataset_structural,
            PipelineStage.STRUCTURE_DETECT: self.path_manager.dataset_structured,
            PipelineStage.SUMMARIZE: self.path_manager.dataset_summarized,
            PipelineStage.EXTENDED: self.path_manager.dataset_extended,
            PipelineStage.FINALIZE: self.path_manager.dataset_final,
            PipelineStage.CHUNK: self.path_manager.dataset_chunks,
            PipelineStage.EMBED: self.path_manager.index_faiss,
        }

        output_dir = stage_dirs.get(stage, self.path_manager.root / 'data' / stage)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def _get_stage_sequence(self, start: str, end: str) -> List[str]:
        """Get sequence of stages from start to end."""
        try:
            start_idx = PipelineStage.ALL.index(start)
            end_idx = PipelineStage.ALL.index(end)
            
            if start_idx > end_idx:
                raise ValueError(f"Start stage {start} comes after end stage {end}")
            
            return PipelineStage.ALL[start_idx:end_idx + 1]
            
        except ValueError as e:
            raise ValueError(f"Invalid stage: {e}")
    
    def _is_critical_stage(self, stage: str) -> bool:
        """Check if stage is critical (pipeline stops on failure)."""
        critical_stages = {
            PipelineStage.STRUCTURAL,
            PipelineStage.FINALIZE,
        }
        return stage in critical_stages
    
    def generate_reports(self) -> None:
        """Generate quality and performance reports."""
        log_section(logger, "📊 FINAL REPORTS", "INFO")
        
        # Performance summary
        log_performance_summary(logger)
        
        # Error summary
        log_error_summary(logger)
        
        # Quality report
        if self.quality_tracker:
            logger.info("")  # Empty line
            try:
                self.quality_tracker.print_report()
            except Exception as e:
                logger.warning(f"Failed to print quality report: {e}")
        
        # Validation report
        if self.validator:
            logger.info("")  # Empty line
            try:
                self.validator.print_summary()
            except Exception as e:
                logger.warning(f"Failed to print validation summary: {e}")


# ============================================
# CLI
# ============================================

def main():
    """CLI interface."""
    parser = argparse.ArgumentParser(
        description=f'{PRODUCT_NAME} {VERSION} - RAG Pipeline Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single PDF (full pipeline)
  python run_mvp.py -i book.pdf
  
  # Process directory (batch mode)
  python run_mvp.py -i pdfs/ --batch
  
  # Resume from specific stage
  python run_mvp.py -i data/datasets/structural/book.dataset.jsonl \\
    --start structure_detect
  
  # Run specific stages only
  python run_mvp.py -i book.pdf --start structural --end chunk
  
  # Dry run (plan only, no execution)
  python run_mvp.py -i book.pdf --dry-run
  
  # Disable validation (faster, less safe)
  python run_mvp.py -i book.pdf --no-validation
  
  # Custom config
  python run_mvp.py -i book.pdf -c config/mvp_quality.yaml
"""
    )
    
    # Input/output
    parser.add_argument('-i', '--input', required=True,
                       help='Input PDF file or directory')
    parser.add_argument('-c', '--config',
                       help='Config file path')
    
    # Mode
    parser.add_argument('--batch', action='store_true',
                       help='Batch mode (process directory)')
    parser.add_argument('--pattern', default='*.pdf',
                       help='File pattern for batch mode (default: *.pdf)')
    
    # Stage control
    parser.add_argument('--start', default='structural',
                       choices=PipelineStage.ALL,
                       help='Start stage (default: structural)')
    parser.add_argument('--end', default='embed',
                       choices=PipelineStage.ALL,
                       help='End stage (default: embed)')
    
    # Options
    parser.add_argument('--no-quality-check', action='store_true',
                       help='Disable quality checking')
    parser.add_argument('--no-validation', action='store_true',
                       help='Disable output validation')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run (plan only, no execution)')
    parser.add_argument('--stop-on-error', action='store_true',
                       help='Stop batch processing on first error')
    
    # Reporting
    parser.add_argument('--report-only', action='store_true',
                       help='Generate reports and exit (no processing)')
    
    args = parser.parse_args()
    
    # Reset tracking
    reset_tracking()
    
    # Initialize orchestrator
    config_path = Path(args.config) if args.config else None
    
    try:
        orchestrator = PipelineOrchestrator(
            config_path=config_path,
            quality_check=not args.no_quality_check,
            validate_stages=not args.no_validation,
            dry_run=args.dry_run
        )
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        sys.exit(1)
    
    # Report-only mode
    if args.report_only:
        orchestrator.generate_reports()
        sys.exit(0)
    
    # Process
    input_path = Path(args.input)
    
    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        sys.exit(1)
    
    try:
        if args.batch or input_path.is_dir():
            # Batch mode
            if not input_path.is_dir():
                logger.error("Batch mode requires directory input")
                sys.exit(1)
            
            results = orchestrator.run_batch(
                input_path,
                pattern=args.pattern,
                start_stage=args.start,
                end_stage=args.end,
                continue_on_error=not args.stop_on_error
            )
            
            # Generate reports
            if not args.dry_run:
                orchestrator.generate_reports()
            
            # Exit code
            if results.get('failed'):
                sys.exit(1)
        
        else:
            # Single file mode
            results = orchestrator.run_single(
                input_path,
                start_stage=args.start,
                end_stage=args.end
            )
            
            # Generate reports
            if not args.dry_run:
                orchestrator.generate_reports()
            
            # Exit code
            if results.get('errors'):
                sys.exit(1)
        
        # Success
        log_section(logger, "✅ PIPELINE COMPLETED SUCCESSFULLY", "INFO")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Pipeline interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        logger.error(f"\n❌ Pipeline failed: {e}")
        logger.exception("Error details:")
        sys.exit(1)


if __name__ == '__main__':
    main()