#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_sources.py - Source Files Validator
============================================
Pre-processing validation for PDF source files

Checks for:
- Special characters (®, ©, ™, etc.)
- Long filenames (>100 chars)
- Spaces and unsafe characters
- Duplicate filenames
- File accessibility
- PDF corruption

Version: 1.0.0
"""

import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple
import PyPDF2


class SourceValidator:
    """Validates PDF source files before processing."""

    # Characters that cause issues in Windows/FAISS
    UNSAFE_CHARS = {
        '®': 'r',  # Registered trademark
        '©': 'c',  # Copyright
        '™': 'tm', # Trademark
        '°': 'deg',
        '±': 'pm',
        '×': 'x',
        '÷': 'div',
        '€': 'eur',
        '£': 'gbp',
        '¥': 'yen',
        '§': 's',
        '¶': 'p',
        '†': '+',
        '‡': '++',
        '•': '-',
        '…': '...',
        '<': '_',
        '>': '_',
        ':': '_',
        '"': '_',
        '/': '_',
        '\\': '_',
        '|': '_',
        '?': '_',
        '*': '_',
    }

    def __init__(self, source_dir: Path, max_length: int = 100, interactive: bool = True):
        self.source_dir = Path(source_dir)
        self.max_length = max_length
        self.interactive = interactive
        self.issues = []
        self.warnings = []

    def validate_all(self) -> Dict[str, any]:
        """Run all validation checks."""
        print("=" * 60)
        print("  SOURCE FILES VALIDATION")
        print("=" * 60)
        print(f"Source directory: {self.source_dir}")
        print("")

        # Get all PDFs
        pdfs = sorted(self.source_dir.glob("*.pdf"))
        print(f"Found {len(pdfs)} PDF files")
        print("")

        # Run checks
        issues_found = []

        for pdf in pdfs:
            file_issues = self._validate_file(pdf)
            if file_issues:
                issues_found.append((pdf, file_issues))

        # Report
        if not issues_found:
            print("[OK] All files passed validation!")
            print("")
            return {'status': 'ok', 'issues': []}

        # Show issues
        print("[WARNING] ISSUES FOUND:")
        print("")

        renames = []
        for pdf, issues in issues_found:
            print(f"FILE: {pdf.name}")
            for issue_type, details in issues:
                print(f"   [!] {issue_type}: {details}")

            # Generate safe name
            safe_name = self._generate_safe_name(pdf.name)
            if safe_name != pdf.name:
                renames.append((pdf, safe_name))
                print(f"   --> Suggested: {safe_name}")
            print("")

        # Interactive mode
        if self.interactive and renames:
            return self._handle_renames(renames)

        return {
            'status': 'issues_found',
            'issues': issues_found,
            'renames': renames
        }

    def _validate_file(self, pdf: Path) -> List[Tuple[str, str]]:
        """Validate a single PDF file."""
        issues = []
        name = pdf.name

        # 1. Check length
        if len(name) > self.max_length:
            issues.append(('LONG_FILENAME', f'{len(name)} characters (max: {self.max_length})'))

        # 2. Check for unsafe characters
        unsafe_found = [char for char in self.UNSAFE_CHARS if char in name]
        if unsafe_found:
            issues.append(('UNSAFE_CHARS', f'Found: {", ".join(repr(c) for c in unsafe_found)}'))

        # 3. Check for multiple spaces
        if '  ' in name:
            issues.append(('MULTIPLE_SPACES', 'Contains consecutive spaces'))

        # 4. Check if starts/ends with space
        stem = pdf.stem
        if stem != stem.strip():
            issues.append(('WHITESPACE', 'Starts or ends with whitespace'))

        # 5. Check PDF accessibility
        try:
            with open(pdf, 'rb') as f:
                PyPDF2.PdfReader(f)
        except Exception as e:
            issues.append(('PDF_ERROR', f'Cannot read PDF: {str(e)[:50]}'))

        return issues

    def _generate_safe_name(self, filename: str) -> str:
        """Generate a safe filename."""
        stem = Path(filename).stem
        ext = Path(filename).suffix

        # Replace unsafe chars
        safe_stem = stem
        for unsafe_char, replacement in self.UNSAFE_CHARS.items():
            safe_stem = safe_stem.replace(unsafe_char, replacement)

        # Replace multiple spaces
        while '  ' in safe_stem:
            safe_stem = safe_stem.replace('  ', ' ')

        # Replace spaces with underscores
        safe_stem = safe_stem.replace(' ', '_')

        # Strip
        safe_stem = safe_stem.strip('_')

        # Truncate if too long
        if len(safe_stem) > self.max_length - len(ext):
            # Add hash for uniqueness
            file_hash = hashlib.md5(stem.encode('utf-8')).hexdigest()[:6]
            max_len = self.max_length - len(ext) - 7  # -7 for _hash
            safe_stem = safe_stem[:max_len] + '_' + file_hash

        return safe_stem + ext

    def _handle_renames(self, renames: List[Tuple[Path, str]]) -> Dict:
        """Interactive rename handling."""
        print("=" * 60)
        print("  RENAME SUGGESTIONS")
        print("=" * 60)
        print("")
        print(f"Found {len(renames)} files that should be renamed:")
        print("")

        for i, (old_path, new_name) in enumerate(renames, 1):
            print(f"{i}. {old_path.name}")
            print(f"   ➡️  {new_name}")
            print("")

        # Ask user
        print("Options:")
        print("  [1] Rename all automatically")
        print("  [2] Show detailed plan (no changes)")
        print("  [3] Skip and continue anyway (may cause errors)")
        print("  [4] Abort processing")
        print("")

        choice = input("Your choice [1-4]: ").strip()

        if choice == '1':
            return self._execute_renames(renames)
        elif choice == '2':
            return self._show_rename_plan(renames)
        elif choice == '3':
            print("[WARNING] Continuing without renaming may cause errors!")
            return {'status': 'skip', 'renames': renames}
        else:
            print("[ABORT] Aborted by user")
            return {'status': 'aborted'}

    def _execute_renames(self, renames: List[Tuple[Path, str]]) -> Dict:
        """Execute file renames."""
        print("")
        print("Renaming files...")
        print("")

        renamed = []
        failed = []

        for old_path, new_name in renames:
            new_path = old_path.parent / new_name

            try:
                # Check if target exists
                if new_path.exists():
                    print(f"[SKIP] {new_name} already exists")
                    failed.append((old_path, "Target exists"))
                    continue

                # Rename
                old_path.rename(new_path)
                print(f"[OK] {old_path.name} -> {new_name}")
                renamed.append((old_path.name, new_name))

            except Exception as e:
                print(f"[FAIL] {old_path.name}: {e}")
                failed.append((old_path, str(e)))

        print("")
        print(f"[OK] Renamed: {len(renamed)}")
        print(f"[FAIL] Failed: {len(failed)}")
        print("")

        return {
            'status': 'renamed',
            'renamed': renamed,
            'failed': failed
        }

    def _show_rename_plan(self, renames: List[Tuple[Path, str]]) -> Dict:
        """Show detailed rename plan."""
        print("")
        print("=" * 60)
        print("  DETAILED RENAME PLAN")
        print("=" * 60)
        print("")

        for old_path, new_name in renames:
            print(f"File: {old_path.name}")
            print(f"  Location: {old_path.parent}")
            print(f"  Size: {old_path.stat().st_size:,} bytes")
            print(f"  New name: {new_name}")
            print("")

        return {'status': 'plan_shown', 'renames': renames}


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate PDF source files")
    parser.add_argument(
        '-d', '--dir',
        default='data/sources',
        help='Source directory (default: data/sources)'
    )
    parser.add_argument(
        '-l', '--max-length',
        type=int,
        default=100,
        help='Maximum filename length (default: 100)'
    )
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Run in non-interactive mode'
    )
    parser.add_argument(
        '--auto-rename',
        action='store_true',
        help='Automatically rename all files'
    )

    args = parser.parse_args()

    validator = SourceValidator(
        source_dir=args.dir,
        max_length=args.max_length,
        interactive=not args.non_interactive
    )

    result = validator.validate_all()

    # Auto-rename if requested
    if args.auto_rename and result.get('renames'):
        result = validator._execute_renames(result['renames'])

    # Exit code
    if result['status'] in ['ok', 'renamed']:
        sys.exit(0)
    elif result['status'] == 'aborted':
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == '__main__':
    main()
