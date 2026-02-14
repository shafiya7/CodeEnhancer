"""Command-line interface for generating patches using Groq.

This CLI script leverages the utilities in ``groq_fix_utils`` to read a
target Python file and an issue description, prompt Groq’s Llama 3.1 8 B
model to correct the code, and output a unified diff patch.  The
original source file remains untouched; only the patch file is written.

Example usage::

    export GROQ_API_KEY=sk-your-key
    pip install groq
    python single_file_patch_cli.py \
        --repo-dir demo_project \
        --target-file app.py \
        --issue-file demo_project/issue.txt \
        --output-patch demo_project/app.patch

Always review the generated patch before applying it.  For multi-file
projects, consider writing a higher-level script that iterates over
multiple target files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Local import of utilities
from groq_fix_utils import read_file, read_issue, build_prompt, call_groq, generate_patch


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the CLI."""
    parser = argparse.ArgumentParser(
        description="Generate a unified diff patch for a single file using Groq"
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        required=True,
        help="Root of the repository containing the target file",
    )
    parser.add_argument(
        "--target-file",
        type=Path,
        required=True,
        help="Relative path of the file to fix (e.g., app.py)",
    )
    parser.add_argument(
        "--issue-file",
        type=Path,
        required=True,
        help="Path to the text file describing the expected behavior",
    )
    parser.add_argument(
        "--output-patch",
        type=Path,
        required=True,
        help="Where to write the unified diff patch",
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
    full_path = args.repo_dir / args.target_file
    if not full_path.exists():  
        raise SystemExit(f"Target file {full_path} does not exist")
    original_code = read_file(full_path)
    issue_desc = read_issue(args.issue_file)
    prompt = build_prompt(issue_desc, original_code, str(args.target_file))
    corrected_code = call_groq(prompt, model=args.model, temperature=args.temperature)
    patch_str = generate_patch(
        original_code,
        corrected_code,
        fromfile=str(args.target_file),
        tofile=f"{args.target_file} (patched)",
    )
    # Ensure the output directory exists
    args.output_patch.parent.mkdir(parents=True, exist_ok=True)
    try:
        args.output_patch.write_text(patch_str)
    except Exception as e:  
        raise SystemExit(f"Failed to write patch to {args.output_patch}: {e}")


if __name__ == "__main__":  
    main()