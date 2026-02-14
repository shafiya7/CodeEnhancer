"""Batch patch generator for multiple Python files using Groq.

This script traverses a repository directory, identifies all Python files,
and generates a unified diff patch for each file based on a single
issue description.  Each patch is written to a mirror location under
the specified output directory, preserving the relative path and
appending a ``.patch`` extension.  The original source files are
never modified.

Example usage::

    export GROQ_API_KEY=sk-your-key
    pip install groq
    python multi_file_patch_cli.py \
        --repo-dir path/to/repo \
        --issue-file issue.txt \
        --output-dir patches

After running, the ``patches`` directory will contain a ``*.patch`` file
for each Python source file found under ``repo-dir``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

from groq_fix_utils import read_file, read_issue, build_prompt, call_groq, generate_patch


def find_python_files(base: Path) -> Iterable[Path]:
    """Yield all Python files under ``base`` recursively."""
    for path in base.rglob("*.py"):
        if path.is_file():
            yield path


def generate_patches(repo_dir: Path, issue_desc: str, output_dir: Path, model: str, temperature: float) -> None:
    """Generate patches for all Python files under ``repo_dir``.

    For each file, compute the corrected code and write a unified diff
    patch to the corresponding path in ``output_dir``.
    """
    files = list(find_python_files(repo_dir))
    if not files:
        raise SystemExit(f"No Python files found under {repo_dir}")
    for file_path in files:
        rel_path = file_path.relative_to(repo_dir)
        original_code = read_file(file_path)
        prompt = build_prompt(issue_desc, original_code, str(rel_path))
        corrected_code = call_groq(prompt, model=model, temperature=temperature)
        diff = generate_patch(
            original_code,
            corrected_code,
            fromfile=str(rel_path),
            tofile=f"{rel_path} (patched)",
        )
        # Determine output patch path and ensure directory exists
        patch_path = output_dir / rel_path.with_suffix(rel_path.suffix + ".patch")
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(diff)
        print(f"Wrote patch for {rel_path} -> {patch_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate patches for all Python files in a folder using Groq")
    parser.add_argument("--repo-dir", type=Path, required=True, help="Root directory of the repository to scan")
    parser.add_argument("--issue-file", type=Path, required=True, help="Path to the issue description file")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to write patch files")
    parser.add_argument("--model", type=str, default="llama-3.1-8b-instant", help="Groq model to use")
    parser.add_argument("--temperature", type=float, default=0.0, help="Model sampling temperature")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    issue_desc = read_issue(args.issue_file)
    generate_patches(args.repo_dir, issue_desc, args.output_dir, args.model, args.temperature)


if __name__ == "__main__":  
    main()