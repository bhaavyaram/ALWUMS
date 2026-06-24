# ALWUMS — Universal Multi-Agent Self-Discovering Upgrader

One-line summary
----------------
ALWUMS is a Python-based multi-agent upgrader that uses modular prompt templates and an LLM backend to automatically analyze, generate, and validate upgrades for legacy codebases, with an optional Vite+React demo UI included.

Why this repo exists
--------------------
It provides a reproducible pipeline for:
- Discovering outdated/deprecated/security issues in a codebase,
- Constructing a per-file upgrade plan,
- Executing the upgrade using LLM-guided transformation steps,
- Self-testing the transformed files (language-specific validators),
- Iteratively fixing failures with a "finalizer" step,
- Emitting a report and packaged upgraded project as a ZIP.

This README documents the architecture, internals, configuration, runtime flows, limitations, and operational guidance for developers and operators.

Contents & high-level architecture
---------------------------------
- universal_upgrader.py — Python orchestrator and FastAPI server.
- agents/ — modular prompt templates that define the agent roles and instructions:
  - discovery_agent.txt
  - manager.txt
  - pipeline_prompt_maker.txt
  - pipeline_prompt_executioner.txt
  - finalizer.txt
  - verifier.txt
- checkpoints/ — run artifacts (llm cache, progress).
  - llm_cache.json (LLM responses cache)
  - progress.json (run progress metadata)
- project/
  - input_code/ (example/seed input)
  - output_code/ (transformed output examples)
  - project_requirements.txt (currently a human note — replace with concrete deps)
  - reports/ (report outputs)
- proj/project/ — frontend demo (Vite + React + TypeScript)
  - src/, package.json, vite.config.ts, tailwind.config.js
- proj/project/project.zip — archived frontend bundle (large)
- config.json — runtime configuration (required for universal_upgrader.py; see configuration section)

Core runtime flow (function-level view)
--------------------------------------
The primary runtime is in universal_upgrader.py. Key components and their responsibilities:

- Configuration loader (top of file)
  - Required keys in repo: api_keys, model, temperature, input_dir, output_dir, report_dir, agent_dir, checkpoint_file, cache_file.
  - The script will exit immediately if config.json is missing or invalid.

- LLM client wrapper: call_llm(prompt, retries=2, use_cache=True)
  - Caching: prompt -> key via SHA-256 (make_key), stored in CACHE_FILE (JSON).
  - Payload: sends JSON as:
    {
      "contents": [{"role":"user","parts":[{"text": prompt}]}],
      "generationConfig": {"temperature": TEMPERATURE}
    }
  - Response interpretation: expects "candidates" -> candidates[0].content.parts[0].text.
  - Markdown fence stripping: removes triple-backtick fences from results.
  - Resilience:
    - Exponential backoff starting at 2s, doubled up to 30s on retry.
    - Multi-key rotation: keeps a list of API_KEYS and cycles on 429, 5xx, or exceptions; logs which key is being used.
    - If all keys are exhausted, returns and caches the offline placeholder:
      "# [OFFLINE] LLM unavailable; skipping.\n"

- Simple local cache API
  - cache_get(key) and cache_set(key, value) persist _LLM_CACHE to CACHE_FILE.

- Discovery phase: discovery_phase(all_files, discovery_agent_template, batch_size=8)
  - Collects file snippets (first ~200 lines) and language heuristics.
  - Batches files to avoid huge prompts.
  - Builds a prompt using discovery_agent_template and expects JSON mapping filename -> "NO_ISSUES" or a short list of issues.
  - Robust parsing: first attempts to extract JSON substring (first/last brace), otherwise falls back to line-based "name: value" parsing.

- Manager phase / task generation
  - For each file not already marked passed, manager template is filled with:
    - PROJECT_CONTEXT (list of filenames)
    - FILE_NAME & CODE_CONTENT
    - AUTOMATED_FINDINGS (from discovery)
  - If Manager returns "NO UPGRADE NEEDED" the file is copied to OUTPUT_DIR and marked Pass.

- Pipeline creation and execution
  - pipeline_prompt_maker -> transforms manager tasks into a concise 1-3 sentence instruction "PROMPT".
  - pipeline_prompt_executioner -> is invoked with PROJECT_CONTEXT, RELATED_SNIPPETS, FILE_NAME, CODE_CONTENT, PROMPT; expects to return the whole upgraded file content (plain text).
  - extract_related_snippets(target_rel, all_files, max_chars=800):
    - Tokenizes filename tokens, scans files in same directory or same extension.
    - Extracts nearby matches to tokens and header patterns (class/def/function/const/...).
    - Returns up to max_chars concatenated snippets for contextual compatibility.

- Validation & Finalizer loop
  - validator_output(path) performs language-dependent validation:
    - Python: python -m py_compile
    - JavaScript: node --check (if node available)
    - PHP: php -l (if php available)
    - Returns (ok: bool, output: str)
  - If validation fails, finalizer (prompt finalizer.txt) is invoked up to 3 attempts:
    - finalizer receives OLD_CODE, CODE_CONTENT (broken), and REMARKS (validator output).
    - If finalizer also fails or LLM unavailable, file is left as Fail for manual review.

- Checkpointing & reporting
  - load_checkpoint() / save_checkpoint(report) manage CHECKPOINT_FILE:
    - save_checkpoint writes:
      {
        "completed_files": [...],
        "report": [ {file, status, issues, time}, ... ],
        "last_run": "<timestamp>"
      }
  - write_report_html(report, outpath) generates a minimal HTML table of files/status/errors and is written to REPORT_DIR/report_latest.html.
  - The API and CLI both use these artifacts.

- FastAPI server
  - Endpoint: POST /upgrade
    - Parameters: run_id (string), file (ZIP UploadFile)
    - Behavior:
      - Validates .zip extension.
      - Deletes previous INPUT_DIR and OUTPUT_DIR contents, creates fresh directories.
      - Saves uploaded zip to INPUT_DIR, extracts it, deletes zip file.
      - Calls run_pipeline(run_id).
      - Creates an output ZIP containing files under OUTPUT_DIR and the report (report_latest.html).
      - Returns StreamingResponse with attachment filename upgraded_project_{run_id}.zip
  - CORS middleware configured to allow all origins (allow_origins=["*"]).

- CLI mode
  - Running the script with `--cli` calls run_pipeline("cli-run").
  - Otherwise it boots a uvicorn server on 0.0.0.0:8000.

Configuration (example)
-----------------------
A minimal example config.json (place in repository root) — adjust to your environment:

```json
{
  "api_keys": ["YOUR_KEY_1", "YOUR_KEY_2"],
  "model": "models/text-bison-001",
  "temperature": 0.0,
  "input_dir": "project/input_code",
  "output_dir": "project/output_code",
  "report_dir": "project/reports",
  "agent_dir": "agents",
  "checkpoint_file": "checkpoints/progress.json",
  "cache_file": "checkpoints/llm_cache.json"
}
```

Notes:
- api_keys: multiple keys are supported; the script rotates keys on rate limits or failures.
- model: used to format the base URL (BASE_URL_TEMPLATE). Ensure it matches your LLM provider / API shape expected by the script.
- The script expects config.json to be present and valid JSON; otherwise it prints an error and exits.

How to run (developer-friendly)
-------------------------------
1) Set up Python environment (Linux/macOS example)
```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# Install runtime dependencies (not listed in repo root — infer required libs)
pip install fastapi uvicorn requests python-multipart
# If you use the frontend, install Node and npm separately
```

2) Edit config.json (placeholders replaced with real values, see above). Ensure AGENT_DIR points to agents.

3) Run in CLI mode (single run):
```bash
python universal_upgrader.py --cli
# This will run run_pipeline("cli-run") and operate using directories in config.json
```

4) Run as a long-running server:
```bash
python universal_upgrader.py
# or explicitly:
uvicorn universal_upgrader:app --host 0.0.0.0 --port 8000 --reload
```

5) Use the HTTP endpoint to upload a zip and trigger an upgrade:
```bash
curl -X POST "http://localhost:8000/upgrade?run_id=run123" \
  -F "file=@/path/to/project_zip.zip" \
  --output upgraded_project_run123.zip
```
- Uploaded ZIP should contain the project files at the top level or within a folder; universal_upgrader extracts into INPUT_DIR and treats all text files recursively.

Expected ZIP output structure
- upgraded_project_{run_id}.zip will include:
  - All files produced under OUTPUT_DIR (preserving relative paths)
  - report.html (REPORT_DIR/report_latest.html) if present

Front-end (proj/project) notes
------------------------------
- Framework: Vite + React + TypeScript
- Key files in repo:
  - proj/project/package.json, src/main.tsx, src/App.tsx, src/index.css, vite.config.ts, tailwind.config.js
- Supabase integration:
  - A subfolder proj/project/supabase exists — check the frontend code for environment variable names. Vite convention uses VITE_<NAME> prefix; common names you may need:
    - VITE_SUPABASE_URL
    - VITE_SUPABASE_ANON_KEY
- Typical dev commands:
```bash
cd proj/project
npm install
npm run dev
npm run build
npm run preview
```
- The frontend is likely a demo or simple UI to visualize reports or interact with the upgrader; inspect src/ to confirm integration points and endpoints it calls.

Important internal implementation details (deep dive)
---------------------------------------------------
- LLM payload and expected response:
  - Payload keys: "contents" (role/parts/text) and "generationConfig".
  - The script expects "candidates" in JSON response, grabbing candidates[0].content.parts[0].text.
  - The script strips fenced code blocks and returns only the core text result.

- Cache key:
  - make_key(prompt): sha256(prompt.encode('utf-8')).hexdigest()
  - Cache is stored as a flat JSON mapping key -> response text.

- API Key rotation & backoff:
  - rotate_api_key() increments api_key_index modulo len(API_KEYS).
  - On 429 or 5xx or exceptions: rotate key, sleep with exponential backoff (2 -> 4 -> 8 ... capped at 30s).
  - The script tracks attempted_keys to avoid immediate reuse in one run.

- Validator behavior:
  - Runs up to 3 validation/fix cycles per file:
    - First write the upgraded file and validate.
    - On failure, call finalizer with OLD_CODE, current CODE_CONTENT and REMARKS (validator output) and replace file with finalizer output.
    - If finalizer still fails after final attempt, the file is marked Fail and left for manual review.
  - Validation is intentionally rapid and shallow (compile/lint checks), not full unit/integration tests.

- Language detection heuristics:
  - Uses file extension mapping (.py -> Python, .ts -> TypeScript, etc).
  - Fallbacks: shebang detection, content heuristics ("def " and "import " -> Python, "function " + "console.log" -> JavaScript).
  - Unknown returns "Unknown".

- Related snippets extraction regex:
  - Headers detection via r"^(?:class|def|function|const|var|let|public|private|protected).{0,200}"
  - Token-context matches: r".{0,120}\b{token}\b.{0,120}" to capture occurrences with surrounding context.
  - Returns de-duplicated snippets up to max_chars limit.

- Discovery parsing robustness:
  - Attempts to extract JSON by slicing from first "{" to last "}" before json.loads().
  - If parsing fails, falls back to parsing colon-separated lines.

Configuration & ops checklist
-----------------------------
- Ensure config.json is present and correct.
- Ensure API keys are valid and have sufficient quota.
- Make sure node/php are installed if you expect JS/PHP validation.
- Ensure file permissions allow creating CHECKPOINT_FILE and CACHE_FILE in checkpoints/.
- If running behind a proxy or with restricted egress, validate that the LLM endpoint is reachable.

Recommended improvements & TODOs
-------------------------------
- Replace human-text project/project_requirements.txt with a real requirements.txt or pyproject.toml with pinned versions.
- Add unit tests:
  - Mock LLM responses for deterministic tests of discovery, manager, maker, execution, finalizer loops.
  - Regression tests: for each example input (project/input_code/*) assert equality or equivalence with project/output_code/*.
- Harden LLM response parsing and schema validation (e.g., JSON schema for discovery/manager outputs).
- Implement per-key rate-limiting counters and smarter backoff (not just global backoff).
- Add concurrency controls and a queue for large codebases (currently run_pipeline processes files sequentially).
- Add security scanning of checkpoints/llm_cache.json before public release (may contain sensitive fragments).
- Add a LICENSE file and contribution guidelines (CONTRIBUTING.md).

Security & privacy considerations
--------------------------------
- Do not commit API keys or secrets. Use environment variables or a secrets manager.
- The local LLM cache may contain snippets that include private or sensitive code; scrub before sharing.
- The service extracts and processes arbitrary ZIP uploads — if you expose the API publicly, enforce authentication and input sanitization.
- The FastAPI server currently allows CORS from any origin; restrict allow_origins in production.

Example troubleshooting scenarios
--------------------------------
- "Script exits with 'config.json not found'":
  - Create config.json at repo root with required keys (see example above).
- "LLM returns offline placeholder or tasks fail":
  - Check API keys, quotas, network egress; review checkpoints/llm_cache.json to see cached offline placeholder.
- "Validation fails repeatedly for a file":
  - Inspect report_latest.html for validator messages and the last saved upgraded file in project/output_code/. Test finalizer manually by providing OLD_CODE/CODE_CONTENT to a test LLM sequence.
- "Frontend cannot find Supabase":
  - Ensure VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are set in environment or .env and that frontend build picks them up (Vite requires VITE_ prefix).

Report / checkpoint schema (concrete)
------------------------------------
- CHECKPOINT_FILE (JSON) layout written by save_checkpoint(report):
{
  "completed_files": ["path/relative/to/input/file.py", ...],
  "report": [
    {
      "file": "relative/path.py",
      "status": "Pass" | "Fail",
      "issues": ["issue 1", "issue 2", ...],
      "time": 1.23   // elapsed seconds for processing
    },
    ...
  ],
  "last_run": "YYYY-MM-DD HH:MM:SS"
}
- CACHE_FILE layout: { "<sha256_of_prompt>": "<text response>", ... }

Developer checklist for making changes
-------------------------------------
- When modifying agents/*.txt (prompts), add or update a regression test:
  - Add an input under project/input_code/
  - Add expected output under project/output_code/
  - Create a small test runner that runs universal_upgrader.run_pipeline on that input and asserts equivalence or behavior.
- If changing config keys rename or add migration logic to read both new and legacy keys.
- If changing the LLM API payload/response schema, update call_llm() to:
  - Adjust BASE_URL_TEMPLATE and the expected JSON shape,
  - Update strip_markdown_fences if provider uses different fence patterns.

Contributing
------------
- Fork, branch, and open PRs with clear change descriptions.
- Include tests for behavioral changes, especially for prompt/template modifications and parsing logic.
- Add a LICENSE file (MIT/Apache-2.0) if open-sourcing.

Appendix: Example curl usage to trigger /upgrade
------------------------------------------------
```bash
# from machine that can reach the service
curl -X POST "http://localhost:8000/upgrade?run_id=test001" \
  -F "file=@/path/to/project.zip" \
  -o upgraded_project_test001.zip
```
- The uploaded ZIP will be extracted into INPUT_DIR. The result ZIP contains upgraded files and report.html.

Closing notes
-------------
This README enumerates the repository's runtime behaviour, configuration, file formats, and implementation details discovered by inspection of universal_upgrader.py and the agents/ templates. If you want, I can:
- produce a ready-to-use example config.json with placeholder keys,
- add small unit/integration test harness that mocks the LLM (so CI can run without external API access),
- create a lightweight Dockerfile and docker-compose example to containerize the upgrader + optional frontend.
