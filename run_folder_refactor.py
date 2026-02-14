"""Convenience script to refactor an entire folder using defaults.

This script provides a simplified interface for refactoring and
documenting an entire repository folder.  Instead of specifying
individual parameters, you pass only the path to the folder.  The
script expects to find an ``issue.txt`` file in that folder describing
the desired behavior.  It then processes all supported files
(``.py``, ``.java``, ``.js``) using Groq, writing unified diff patches
into a ``patches`` subdirectory and change summaries into a
``summaries`` subdirectory.  The original files are not modified.

Example::

    export GROQ_API_KEY=sk-your-key
    pip install groq
    python run_folder_refactor.py my_repo

This will read ``my_repo/issue.txt``, refactor all supported source
files, and write results to ``my_repo/patches`` and ``my_repo/summaries``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from groq_fix_utils import read_issue
from multi_language_refactor_cli import process_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refactor an entire folder using Groq (default settings)")
    parser.add_argument("folder", type=Path, help="Path to the repository folder containing issue.txt and code files")
    parser.add_argument(
        "--languages",
        type=str,
        default="py,java,js",
        help="Comma-separated list of extensions to process (default: py,java,js)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama-3.1-8b-instant",
        help="Groq model to use",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for the model",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    folder = args.folder.resolve()
    issue_file = folder / "issue.txt"
    if not issue_file.exists():
        raise SystemExit(f"Expected an issue.txt file in {folder} to describe the desired behavior")
    patch_dir = folder / "patches"
    summary_dir = folder / "summaries"
    languages = {ext.strip().lower() for ext in args.languages.split(",") if ext.strip()}
    issue_desc = read_issue(issue_file)
    process_files(
        repo_dir=folder,
        issue_desc=issue_desc,
        patch_dir=patch_dir,
        summary_dir=summary_dir,
        model=args.model,
        temperature=args.temperature,
        languages=languages,
    )


if __name__ == "__main__":  
    main()