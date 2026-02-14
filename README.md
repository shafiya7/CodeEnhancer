## Groq Patch Project

This repository demonstrates a complete workflow for patching Python code
using Groq’s Llama 3.1 8 B model.  It includes:

* **groq_fix_utils.py** – reusable helper functions for building
  prompts, invoking the Groq API, and generating unified diffs.
* **single_file_patch_cli.py** – a command-line interface that reads
  a source file and issue description, and writes a unified diff patch.
* **demo_project/** – a sample project containing a buggy `app.py` and
  an `issue.txt` describing the expected behavior.
* **web_interface/** – a simple Flask front‑end allowing you to paste
  code and an issue description in a browser and receive corrected
  code and a diff.

### Prerequisites

Install the dependencies:

```bash
pip install groq flask
```

Set your Groq API key:

```bash
export GROQ_API_KEY=sk-your-secret-api-key
```

### Command-line usage

Generate a patch for the demo project:

```bash
python single_file_patch_cli.py \
  --repo-dir demo_project \
  --target-file app.py \
  --issue-file demo_project/issue.txt \
  --output-patch demo_project/app.patch
```

Review and apply the patch with a tool like `patch` if you agree with the changes.

### Batch processing multiple files

To generate patches for **all** Python files under a folder in one go, use
`multi_file_patch_cli.py`.  This script traverses a repository, reads
every `.py` file, prompts Groq individually for each, and writes a
`.patch` file for each source file to the specified output directory.  For
example:

```bash
python multi_file_patch_cli.py \
  --repo-dir demo_project \
  --issue-file demo_project/issue.txt \
  --output-dir demo_project/patches
```

After running, `demo_project/patches` will contain a patch for every
Python file under `demo_project`.  Each patch file mirrors the directory
structure of the source and appends the `.patch` extension.

### Refactoring and documentation across languages

If you need to refactor code in multiple languages and produce both
patches and human‑readable summaries, use
`multi_language_refactor_cli.py`.  It supports Python, Java, and
JavaScript files by default (you can specify others), fixes and
refactors each file, and writes both a patch and a markdown summary:

```bash
python multi_language_refactor_cli.py \
  --repo-dir my_repo \
  --issue-file docs/issue.txt \
  --patch-dir out_patches \
  --summary-dir out_summaries \
  --languages py,java,js
```

This command scans `my_repo` for all `.py`, `.java`, and `.js` files,
uses the provided issue description to guide Groq in refactoring and
fixing each file, writes a unified diff patch for each file into
`out_patches`, and writes a plain‑text summary of the changes into
`out_summaries`.  Use these summaries to update your documentation or
release notes.

### One‑command folder refactor

If you simply want to point the tool at a folder and let it handle the
rest, use `run_folder_refactor.py`.  Place your description of the
expected behavior in `issue.txt` at the root of the folder, then run:

```bash
python run_folder_refactor.py path/to/repo
```

The script will process all supported files (`.py`, `.java`, `.js` by
default), write patches into `path/to/repo/patches`, and write
human‑readable summaries into `path/to/repo/summaries`.  You can
override the default languages or model via command-line options.  This
wrapper provides a convenient way to refactor an entire repository with
a single command.

### Web interface

Launch the Flask app:

```bash
cd web_interface
python app.py
```

Open `http://localhost:5000` in your browser.  Paste the code and
issue description, then click **Run** to see the corrected code and a
unified diff.  The server never writes to disk; all computation
happens in memory.