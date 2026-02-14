"""Refactor and patch multiple files across languages using Groq.

This script accepts a repository directory containing source files in
Python, Java, JavaScript, or other languages, an issue description,
and output directories for patches and summaries.  It iterates over
all files with supported extensions (``.py``, ``.java``, ``.js``),
generates a corrected version for each using Groq, writes a unified
diff patch to the patch output directory, and writes a human-readable
summary of the changes to the summary output directory.  The
original files are not modified.

Example usage::

    export GROQ_API_KEY=sk-your-key
    pip install groq
    python multi_language_refactor_cli.py \
        --repo-dir src \
        --issue-file issue.txt \
        --patch-dir patches \
        --summary-dir summaries \
        --languages py,java,js

The script will produce ``.patch`` files under ``patch-dir`` and
``.md`` summary files under ``summary-dir`` mirroring the input
directory structure.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from groq_fix_utils import (
    read_file,
    read_issue,
    build_refactor_prompt,
    build_summary_prompt,
    call_groq,
    generate_patch,
)


def find_supported_files(base: Path, exts: set[str]) -> Iterable[Path]:
    """Yield files under ``base`` whose extension is in ``exts``."""
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower().lstrip(".") in exts:
            yield path


def process_files(
    repo_dir: Path,
    issue_desc: str,
    patch_dir: Path,
    summary_dir: Path,
    model: str,
    temperature: float,
    languages: set[str],
) -> None:
    files = list(find_supported_files(repo_dir, languages))
    if not files:
        raise SystemExit(f"No supported files found under {repo_dir}")
    for file_path in files:
        rel_path = file_path.relative_to(repo_dir)
        original_code = read_file(file_path)
        prompt = build_refactor_prompt(issue_desc, original_code, str(rel_path))
        corrected_code = call_groq(prompt, model=model, temperature=temperature)
        # Write patch
        diff = generate_patch(
            original_code,
            corrected_code,
            fromfile=str(rel_path),
            tofile=f"{rel_path} (refactored)",
        )
        patch_path = patch_dir / rel_path.with_suffix(rel_path.suffix + ".patch")
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(diff)
        # Write summary
        summary_prompt = build_summary_prompt(original_code, corrected_code, str(rel_path))
        summary_text = call_groq(summary_prompt, model=model, temperature=temperature)
        summary_file = summary_dir / rel_path.with_suffix(
            rel_path.suffix + ".md"
        )
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(summary_text)
        print(f"Processed {rel_path}: patch -> {patch_path}, summary -> {summary_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refactor and patch multiple files using Groq")
    parser.add_argument("--repo-dir", type=Path, required=True, help="Root directory to scan for source files")
    parser.add_argument("--issue-file", type=Path, required=True, help="Text file describing desired behavior")
    parser.add_argument("--patch-dir", type=Path, required=True, help="Directory to output patch files")
    parser.add_argument("--summary-dir", type=Path, required=True, help="Directory to output summary markdown files")
    parser.add_argument(
        "--languages",
        type=str,
        default="py,java,js",
        help="Comma-separated list of file extensions to process (without dots)",
    )
    parser.add_argument("--model", type=str, default="llama-3.1-8b-instant", help="Groq model to use")
    parser.add_argument("--temperature", type=float, default=0.0, help="Model sampling temperature")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    languages = {ext.strip().lower() for ext in args.languages.split(",") if ext.strip()}
    issue_desc = read_issue(args.issue_file)
    process_files(
        args.repo_dir,
        issue_desc,
        args.patch_dir,
        args.summary_dir,
        args.model,
        args.temperature,
        languages,
    )


if __name__ == "__main__":  
    main()