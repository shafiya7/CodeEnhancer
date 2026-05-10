from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, render_template, request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from groq_fix_utils import (
    call_groq,
    generate_patch,
    build_summary_prompt,
    build_code_summary_prompt,
    build_comment_code_prompt,
    build_conversion_prompt,
)

from multi_language_refactor_cli import find_supported_files

app = Flask(__name__)


def strip_markdown_fences(code: str) -> str:
    """
    Remove markdown code fences like ```python ... ```
    returned by LLM responses.
    """
    code = code.strip()

    if code.startswith("```"):
        lines = code.splitlines()

        # Remove first markdown fence
        lines = lines[1:]

        # Remove ending markdown fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        code = "\n".join(lines)

    return code.strip()


def build_refactor_prompt(issue: str, file_content: str, file_name: str) -> str:
    return f"""
You are a senior software engineer.

USER REQUEST:
{issue}

TASK:
Rewrite/refactor this file based on the user request.

IMPORTANT RULES:
- Return ONLY raw source code
- Do NOT include markdown
- Do NOT wrap code in ```python
- Do NOT add explanations
- Preserve functionality unless explicitly requested otherwise

FILE NAME:
{file_name}

CURRENT CODE:
{file_content}
"""


def build_file_relevance_prompt(
    user_query: str,
    file_name: str,
    file_content: str,
) -> str:
    return f"""
You are deciding whether a source file needs modification.

USER REQUEST:
{user_query}

FILE NAME:
{file_name}

FILE CONTENT:
{file_content[:4000]}

Answer ONLY:
YES
or
NO
"""


def should_modify_file(
    user_query: str,
    file_name: str,
    file_content: str,
) -> bool:
    prompt = build_file_relevance_prompt(
        user_query,
        file_name,
        file_content,
    )

    answer = call_groq(
        prompt,
        model="llama-3.1-8b-instant",
        temperature=0.0,
    )

    answer = strip_markdown_fences(answer)

    return answer.strip().upper().startswith("YES")


def apply_rewritten_code(
    file_path: Path,
    original_code: str,
    rewritten_code: str,
) -> Path:
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")

    backup_path.write_text(original_code)

    file_path.write_text(rewritten_code)

    return backup_path


@app.route("/", methods=["GET", "POST"])
def index():
    mode = "snippet"

    results = None
    folder_results = None
    summarize_results = None
    convert_results = None

    error = None

    if request.method == "POST":
        mode = request.form.get("form_mode", "snippet")

        # =========================
        # SNIPPET MODE
        # =========================
        if mode == "snippet":
            issue = request.form.get("issue", "").strip()
            code = request.form.get("code", "").strip()
            file_name = request.form.get("file_name", "input.py").strip()

            if not issue or not code:
                error = "Issue and code are required."
            else:
                try:
                    prompt = build_refactor_prompt(
                        issue,
                        code,
                        file_name,
                    )

                    corrected_code = call_groq(
                        prompt,
                        model="llama-3.1-8b-instant",
                        temperature=0.0,
                    )

                    corrected_code = strip_markdown_fences(corrected_code)

                    diff = generate_patch(
                        code,
                        corrected_code,
                        fromfile=file_name,
                        tofile=f"{file_name} (rewritten)",
                    )

                    results = [
                        {
                            "file_name": file_name,
                            "corrected": corrected_code,
                            "diff": diff,
                        }
                    ]

                except Exception as exc:
                    error = str(exc)

        # =========================
        # FOLDER MODE
        # =========================
        elif mode == "folder":
            folder_path = request.form.get("folder_path", "").strip()
            folder_issue = request.form.get("folder_issue", "").strip()
            languages = request.form.get("languages", "py").strip()

            apply_changes = request.form.get("apply_changes") == "yes"

            selective_update = (
                request.form.get("selective_update") == "yes"
            )

            if not folder_path or not folder_issue:
                error = "Folder path and issue are required."

            else:
                try:
                    base = Path(folder_path)

                    if not base.exists():
                        raise Exception("Folder does not exist")

                    lang_set = {
                        ext.strip().lower()
                        for ext in languages.split(",")
                        if ext.strip()
                    }

                    files = list(find_supported_files(base, lang_set))

                    folder_results = []

                    # Relevance check only for large folders
                    USE_RELEVANCE_CHECK = len(files) > 5

                    for fpath in files:
                        rel = fpath.relative_to(base)

                        original_code = fpath.read_text()

                        # =========================
                        # Selective Update
                        # =========================
                        if selective_update and USE_RELEVANCE_CHECK:
                            relevant = should_modify_file(
                                folder_issue,
                                str(rel),
                                original_code,
                            )

                            if not relevant:
                                folder_results.append(
                                    {
                                        "file_name": str(rel),
                                        "status": "skipped",
                                        "summary": "Skipped because file is not relevant.",
                                        "backup": "",
                                        "corrected": "",
                                        "diff": "",
                                    }
                                )

                                continue

                        # =========================
                        # Rewrite file
                        # =========================
                        prompt = build_refactor_prompt(
                            folder_issue,
                            original_code,
                            str(rel),
                        )

                        rewritten_code = call_groq(
                            prompt,
                            model="llama-3.1-8b-instant",
                            temperature=0.0,
                        )

                        rewritten_code = strip_markdown_fences(
                            rewritten_code
                        )

                        # =========================
                        # Validate Python syntax
                        # =========================
                        if str(rel).endswith(".py"):
                            try:
                                compile(
                                    rewritten_code,
                                    str(rel),
                                    "exec",
                                )
                            except SyntaxError as e:
                                folder_results.append(
                                    {
                                        "file_name": str(rel),
                                        "status": "syntax_error",
                                        "summary": str(e),
                                        "backup": "",
                                        "corrected": rewritten_code,
                                        "diff": "",
                                    }
                                )
                                continue

                        diff = generate_patch(
                            original_code,
                            rewritten_code,
                            fromfile=str(rel),
                            tofile=f"{rel} (rewritten)",
                        )

                        status = "preview"
                        backup_path = ""

                        # =========================
                        # Apply changes
                        # =========================
                        if apply_changes:
                            backup = apply_rewritten_code(
                                fpath,
                                original_code,
                                rewritten_code,
                            )

                            backup_path = str(backup)

                            status = "updated"

                        folder_results.append(
                            {
                                "file_name": str(rel),
                                "status": status,
                                "summary": f"Processed using instruction: {folder_issue}",
                                "backup": backup_path,
                                "corrected": rewritten_code,
                                "diff": diff,
                            }
                        )

                except Exception as exc:
                    error = str(exc)

        # =========================
        # SUMMARIZE MODE
        # =========================
        elif mode == "summarize":
            code = request.form.get("sum_code", "").strip()
            file_name = request.form.get(
                "sum_file_name",
                "input.py",
            ).strip()

            try:
                code_summary_prompt = build_code_summary_prompt(
                    code,
                    file_name,
                )

                code_summary = call_groq(
                    code_summary_prompt,
                    model="llama-3.1-8b-instant",
                    temperature=0.0,
                )

                comment_prompt = build_comment_code_prompt(
                    code,
                    file_name,
                )

                commented_code = call_groq(
                    comment_prompt,
                    model="llama-3.1-8b-instant",
                    temperature=0.0,
                )

                commented_code = strip_markdown_fences(
                    commented_code
                )

                summarize_results = [
                    {
                        "file_name": file_name,
                        "code_summary": code_summary,
                        "commented": commented_code,
                    }
                ]

            except Exception as exc:
                error = str(exc)

        # =========================
        # CONVERT MODE
        # =========================
        elif mode == "convert":
            code = request.form.get("conv_code", "").strip()
            file_name = request.form.get(
                "conv_file_name",
                "Example.java",
            ).strip()

            try:
                conv_prompt = build_conversion_prompt(
                    code,
                    file_name,
                )

                converted = call_groq(
                    conv_prompt,
                    model="llama-3.1-8b-instant",
                    temperature=0.0,
                )

                converted = strip_markdown_fences(converted)

                convert_results = [
                    {
                        "file_name": file_name,
                        "converted": converted,
                    }
                ]

            except Exception as exc:
                error = str(exc)

    return render_template(
        "index.html",
        mode=mode,
        results=results,
        folder_results=folder_results,
        summarize_results=summarize_results,
        convert_results=convert_results,
        error=error,
    )


if __name__ == "__main__":
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise SystemExit(
            "GROQ_API_KEY environment variable must be set."
        )

    app.run(debug=True, host="0.0.0.0", port=5000)