"""Simple Flask-based web interface for Groq code fixes.

This application provides a form where users can paste Python code and
an issue description.  Upon submission, it calls Groq’s Llama 3.1 8 B
model to produce corrected code and displays both the full corrected
code and a unified diff showing the changes.  It relies on the
utilities defined in ``groq_fix_utils.py`` located in the project root
for prompt construction and diff generation.

Requirements:

    pip install flask groq

Ensure that the environment variable ``GROQ_API_KEY`` is set before
running this server.  To start the app, run ``python app.py`` and
visit ``http://localhost:5000`` in your browser.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from flask import Flask, render_template, request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from groq_fix_utils import (
    build_prompt,
    call_groq,
    generate_patch,
    build_refactor_prompt,
    build_summary_prompt,
    build_code_summary_prompt,
    build_comment_code_prompt,
    build_conversion_prompt,
    detect_language,
)
from multi_language_refactor_cli import find_supported_files

# Initialize Flask app
app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    """Render the main page and process form submissions for one or multiple files."""
    mode = None
    # Values for snippet form
    codes: list[str] = []
    file_names: list[str] = []
    results: list[dict[str, str]] | None = None
    issue = ""
    # Values for folder form
    folder_path = None
    folder_issue = None
    languages = None
    folder_results: list[dict[str, str]] | None = None
    # Values for summarize form
    # Initialize as empty lists; using None in templates can cause length errors
    sum_file_names: list[str] | None = None
    sum_codes: list[str] | None = None
    # Values for conversion form
    conv_file_names: list[str] | None = None
    conv_codes: list[str] | None = None
    convert_results: list[dict[str, str]] | None = None
    summarize_results: list[dict[str, str]] | None = None
    error = None
    if request.method == "POST":
        mode = request.form.get("form_mode")
        if mode == "snippet":
            issue = request.form.get("issue", "").strip()
            codes = request.form.getlist("code[]")
            file_names = request.form.getlist("file_name[]")
            # Clean up empty pairs
            paired = [(fn.strip(), cd) for fn, cd in zip(file_names, codes) if fn.strip() or cd.strip()]
            file_names = [p[0] for p in paired]
            codes = [p[1] for p in paired]
            if not issue:
                error = "Please provide an issue description."
            elif not codes:
                error = "Please provide at least one file with code."
            else:
                results = []
                try:
                    for fn, cd in zip(file_names, codes):
                        # Determine language based on file extension and build a refactor prompt
                        file_name = fn if fn else "input"
                        prompt = build_refactor_prompt(issue, cd, file_name)
                        corrected_code = call_groq(
                            prompt, model="llama-3.1-8b-instant", temperature=0.0
                        )
                        diff = generate_patch(
                            cd,
                            corrected_code,
                            fromfile=file_name,
                            tofile=f"{file_name} (patched)",
                        )
                        # Summarize the changes and original code functionality
                        summary_prompt = build_summary_prompt(cd, corrected_code, file_name)
                        summary_text = call_groq(summary_prompt, model="llama-3.1-8b-instant", temperature=0.0)
                        code_summary_prompt = build_code_summary_prompt(cd, file_name)
                        code_summary = call_groq(code_summary_prompt, model="llama-3.1-8b-instant", temperature=0.0)
                        results.append(
                            {
                                "file_name": file_name,
                                "corrected": corrected_code,
                                "diff": diff,
                                "summary": summary_text,
                                "code_summary": code_summary,
                            }
                        )
                except SystemExit as exc:
                    error = str(exc)
        elif mode == "folder":
            # Process folder refactor
            folder_path = request.form.get("folder_path", "").strip()
            folder_issue = request.form.get("folder_issue", "").strip()
            languages = request.form.get("languages", "py,java,js").strip()
            if not folder_path or not folder_issue:
                error = "Please provide both folder path and an issue description."
            else:
                folder_results = []
                lang_set = {ext.strip().lower() for ext in languages.split(",") if ext.strip()}
                try:
                    base = Path(folder_path)
                    if not base.exists():
                        raise SystemExit(f"Folder {folder_path} does not exist")
                    files = list(find_supported_files(base, lang_set))
                    if not files:
                        raise SystemExit("No supported files found in the specified folder")
                    for fpath in files:
                        rel = fpath.relative_to(base)
                        original_code = fpath.read_text()
                        prompt = build_refactor_prompt(folder_issue, original_code, str(rel))
                        corrected = call_groq(prompt, model="llama-3.1-8b-instant", temperature=0.0)
                        diff = generate_patch(
                            original_code,
                            corrected,
                            fromfile=str(rel),
                            tofile=f"{rel} (refactored)",
                        )
                        # Summaries
                        summary_prompt = build_summary_prompt(original_code, corrected, str(rel))
                        summary_text = call_groq(summary_prompt, model="llama-3.1-8b-instant", temperature=0.0)
                        code_summary_prompt = build_code_summary_prompt(original_code, str(rel))
                        code_summary = call_groq(code_summary_prompt, model="llama-3.1-8b-instant", temperature=0.0)
                        folder_results.append({
                            "file_name": str(rel),
                            "corrected": corrected,
                            "diff": diff,
                            "summary": summary_text,
                            "code_summary": code_summary,
                        })
                except SystemExit as exc:
                    error = str(exc)
        elif mode == "summarize":
            # Summarize code with comments
            sum_file_names = request.form.getlist("sum_file_name[]")
            sum_codes = request.form.getlist("sum_code[]")
            # Clean up empty pairs
            pairs = [(fn.strip(), cd) for fn, cd in zip(sum_file_names, sum_codes) if fn.strip() or cd.strip()]
            sum_file_names = [p[0] for p in pairs]
            sum_codes = [p[1] for p in pairs]
            if not sum_codes:
                error = "Please provide at least one file with code to summarize."
            else:
                summarize_results = []
                try:
                    for fn, cd in zip(sum_file_names, sum_codes):
                        file_name = fn if fn else "input"
                        # Code summary
                        code_summary_prompt = build_code_summary_prompt(cd, file_name)
                        code_summary = call_groq(code_summary_prompt, model="llama-3.1-8b-instant", temperature=0.0)
                        # Commented code
                        comment_prompt = build_comment_code_prompt(cd, file_name)
                        commented_code = call_groq(comment_prompt, model="llama-3.1-8b-instant", temperature=0.0)
                        summarize_results.append({
                            "file_name": file_name,
                            "code_summary": code_summary,
                            "commented": commented_code,
                        })
                except SystemExit as exc:
                    error = str(exc)
        elif mode == "convert":
            # Convert code between Python and Java based on file extension
            conv_file_names = request.form.getlist("conv_file_name[]")
            conv_codes = request.form.getlist("conv_code[]")
            # Clean up empty pairs
            pairs = [(fn.strip(), cd) for fn, cd in zip(conv_file_names, conv_codes) if fn.strip() or cd.strip()]
            conv_file_names = [p[0] for p in pairs]
            conv_codes = [p[1] for p in pairs]
            if not conv_codes:
                error = "Please provide at least one file with code to convert."
            else:
                convert_results = []
                try:
                    for fn, cd in zip(conv_file_names, conv_codes):
                        file_name = fn if fn else "input"
                        conv_prompt = build_conversion_prompt(cd, file_name)
                        converted = call_groq(conv_prompt, model="llama-3.1-8b-instant", temperature=0.0)
                        convert_results.append(
                            {
                                "file_name": file_name,
                                "converted": converted,
                            }
                        )
                except SystemExit as exc:
                    error = str(exc)
    else:
        # initialize default values
        codes = [""]
        file_names = [""]
        mode = "snippet"
        # Initialise summarisation lists to avoid None handling in template
        sum_file_names = [""]
        sum_codes = [""]
        # Conversion form defaults
        conv_file_names = [""]
        conv_codes = [""]
    return render_template(
        "index.html",
        mode=mode,
        issue=issue,
        codes=codes,
        file_names=file_names,
        results=results,
        folder_path=folder_path,
        folder_issue=folder_issue,
        folder_results=folder_results,
        languages=languages,
        # Ensure lists are passed to the template; default to empty lists if None
        sum_file_names=sum_file_names or [""],
        sum_codes=sum_codes or [""],
        summarize_results=summarize_results,
        conv_file_names=conv_file_names or [""],
        conv_codes=conv_codes or [""],
        convert_results=convert_results,
        error=error,
    )


if __name__ == "__main__":  
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise SystemExit(
            "Environment variable GROQ_API_KEY must be set before running the server."
        )
    app.run(debug=True, host="0.0.0.0", port=5000)