"""Utility functions for generating patches with Groq.

This module contains reusable utilities to read source files,
build prompts for the Groq LLM, call the model, and compute a unified
diff patch between the original and corrected code.  It is intended
to be imported by CLI scripts, web applications or other tooling
that needs to produce patches from issue descriptions.
"""

from __future__ import annotations

import os
import difflib
from pathlib import Path
from typing import Iterable

try:
    from groq import Groq 
except ImportError as exc:   
    raise SystemExit(
        "The 'groq' package is required. Install it with 'pip install groq'."
    ) from exc

__all__ = [
    "read_file",
    "read_issue",
    "build_prompt",
    "call_groq",
    "generate_patch",
    "detect_language",
    "build_refactor_prompt",
    "build_summary_prompt",
    "build_code_summary_prompt",
    "build_comment_code_prompt",
    "build_conversion_prompt",
]


def read_file(path: Path) -> str:
    """Return the contents of ``path`` as a string.

    Raises ``SystemExit`` with a descriptive message if reading fails.
    """
    try:
        return path.read_text()
    except Exception as e:   
        raise SystemExit(f"Failed to read {path}: {e}")


def read_issue(path: Path) -> str:
    """Return the trimmed contents of the issue description file."""
    try:
        return path.read_text().strip()
    except Exception as e:   
        raise SystemExit(f"Failed to read issue description {path}: {e}")


def build_prompt(issue: str, file_content: str, file_name: str) -> str:
    """Construct a prompt for the LLM to fix code based on an issue description."""
    return (
        "You are a senior Python developer.  A user has reported an issue with"
        f" the file '{file_name}'.  The description of the correct behavior is"
        " provided below.  Please fix the bug(s) in the file and return"
        " only the full corrected code.  Do not include any commentary.\n\n"
        "ISSUE DESCRIPTION:\n"
        f"{issue}\n\n"
        f"CURRENT CONTENT OF {file_name}:\n"
        f"{file_content}"
    )


def detect_language(file_name: str) -> str:
    """Return a human-readable language name based on the file extension."""
    ext = Path(file_name).suffix.lower().lstrip(".")
    return {
        "py": "Python",
        "java": "Java",
        "js": "JavaScript",
    }.get(ext, "programming language")


def build_refactor_prompt(issue: str, file_content: str, file_name: str) -> str:
    """Construct a prompt for refactoring/fixing code in any language."""
    lang = detect_language(file_name)
    # If no issue is provided, instruct the model to perform a general cleanup
    if issue.strip():
        issue_section = (
            "ISSUE DESCRIPTION:\n"
            f"{issue}\n\n"
        )
        intro = (
            f"You are a senior {lang} developer. A user has reported an issue with"
            f" the file '{file_name}'. The description of the correct behavior is"
            " provided below. Please fix any bugs and refactor the code to be clean,"
            f" idiomatic {lang}. Return only the full corrected code without any"
            " commentary.\n\n"
        )
    else:
        # No specific issue: general refactoring and bug fixing
        issue_section = ""
        intro = (
            f"You are a senior {lang} developer. No specific issue has been provided for"
            f" the file '{file_name}'. Please review the code, fix any bugs or inefficiencies,"
            f" and refactor it to be clean and idiomatic {lang}. Return only the full"
            " corrected code without any commentary.\n\n"
        )
    return (
        intro + issue_section + f"CURRENT CONTENT OF {file_name}:\n" + f"{file_content}"
    )


def build_summary_prompt(original_code: str, corrected_code: str, file_name: str) -> str:
    """Construct a prompt to summarise changes between original and corrected code."""
    lang = detect_language(file_name)
    return (
        f"You are documenting changes to a {lang} file named {file_name}.\n"
        "Below is the original code followed by the corrected code."
        " Summarise the key changes and improvements for documentation in plain"
        " language. Provide bullet points for each significant modification."
        " Do not include the code itself in your summary.\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code}\n\n"
        "CORRECTED CODE:\n"
        f"{corrected_code}"
    )


def build_code_summary_prompt(file_content: str, file_name: str) -> str:
    """Construct a prompt to summarise what the code in a file does."""
    lang = detect_language(file_name)
    return (
        f"You are a senior {lang} developer reviewing the file {file_name}.\n"
        "Please provide a concise summary (no more than three sentences) describing"
        " what the code in this file does. Focus on the overall purpose and major"
        " functions rather than line-by-line details. Do not include the code"
        " itself in your summary.\n\n"
        "FILE CONTENT:\n"
        f"{file_content}"
    )


def build_comment_code_prompt(file_content: str, file_name: str) -> str:
    """Construct a prompt to add explanatory comments to the code."""
    lang = detect_language(file_name)
    return (
        f"You are a senior {lang} developer reviewing the file {file_name}."
        " Please add clear and informative comments to the code to explain"
        " what each significant part does. Preserve the original code structure"
        " and style, but insert comments where helpful. Return only the"
        " commented code.\n\n"
        "FILE CONTENT:\n"
        f"{file_content}"
    )


def build_conversion_prompt(file_content: str, file_name: str) -> str:
    """Construct a prompt to translate code to Python.

    Regardless of the source language, this prompt instructs the LLM
    to convert the given code into clean, idiomatic Python.  It
    preserves the original logic and asks for no commentary.  The
    source language is inferred from the file extension when possible,
    and is included in the prompt for clarity.
    """
    lang = detect_language(file_name)
    target_lang = "Python"
    return (
        f"You are a senior developer proficient in {lang} and {target_lang}."
        f" Translate the following {lang} code to {target_lang}. Ensure that"
        " the translated code is clean, idiomatic {target_lang} and preserves the logic"
        " of the original. Do not include any commentary or explanation;"
        " return only the translated {target_lang} code.\n\n"
        f"ORIGINAL {lang} CODE:\n"
        f"{file_content}"
    )


def call_groq(prompt: str, model: str = "llama-3.1-8b-instant", temperature: float = 0.0) -> str:
    """Send a prompt to Groq's chat API and return the LLM's response.

    Requires that the ``GROQ_API_KEY`` environment variable be set.  Raises
    ``SystemExit`` if the API key is missing or the response format is
    unexpected.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:  
        raise SystemExit(
            "Environment variable GROQ_API_KEY is not set. Please set it to your Groq API key."
        )
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    try:
        return resp.choices[0].message.content  # type: ignore
    except (AttributeError, IndexError) as e:  
        raise SystemExit(f"Unexpected response format from Groq API: {e}") from e


def generate_patch(
    original: str,
    corrected: str,
    fromfile: str,
    tofile: str,
    ) -> str:
    """Return a unified diff patch between ``original`` and ``corrected``."""
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        corrected.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
    )
    return "".join(diff)