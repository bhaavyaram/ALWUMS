#!/usr/bin/env python3
"""
universal_upgrader.py — Self-discovering MAS upgrader (no hardcoded rules)
Supports multiple API keys with automatic rotation on rate limits/errors.
"""

import os, json, time, shutil, subprocess, requests, re, hashlib
from datetime import datetime

# ---------- CONFIG ----------
API_KEYS = [
    "AIzaSyCRm4wUFK7ZJkJkBsaXOpD3OK0rorZedGM",  # Primary key
    "AIzaSyC1ysvmuXwMmIpaJaQdL4mJ6zK4fv3eVmk",  # Backup key
    "AIzaSyAaJQCYgdZUUvw0uuHU7Ysaf20-gus1iaE"   # Add more as needed
]
api_key_index = 0  # Start with first key

MODEL = "models/gemini-1.5-flash"
BASE_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={key}"
TEMPERATURE = 0.0

INPUT_DIR = "project/input_code"
OUTPUT_DIR = "project/output_code"
REPORT_DIR = "project/reports"
AGENT_DIR = "agents"
CHECKPOINT_FILE = "checkpoints/progress.json"
CACHE_FILE = "checkpoints/llm_cache.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs("checkpoints", exist_ok=True)

# ---------- SIMPLE CACHE ----------
try:
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        _LLM_CACHE = json.load(f)
except:
    _LLM_CACHE = {}

def cache_get(key): return _LLM_CACHE.get(key)
def cache_set(key, value):
    _LLM_CACHE[key] = value
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_LLM_CACHE, f, indent=2)

def make_key(prompt):
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

# ---------- API KEY MANAGEMENT ----------
def get_base_url():
    return BASE_URL_TEMPLATE.format(model=MODEL, key=API_KEYS[api_key_index])

def rotate_api_key():
    global api_key_index
    api_key_index = (api_key_index + 1) % len(API_KEYS)
    print(f"🔄 Switching to API key #{api_key_index+1} ({API_KEYS[api_key_index][:8]}...)")

# ---------- I/O helpers ----------
def read_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# ---------- markdown fence stripper ----------
def strip_markdown_fences(text):
    text = re.sub(r"```[^\n]*\n(.*?)```", lambda m: m.group(1), text, flags=re.S)
    return text.replace("```", "").strip()

# ---------- binary detector ----------
def is_binary_file(path):
    try:
        with open(path, "rb") as f:
            chunk = f.read(2048)
        return b'\0' in chunk
    except:
        return True

# ---------- LLM call with caching & backoff & key rotation ----------
def call_llm(prompt, retries=3, use_cache=True):
    key_hash = make_key(prompt)
    if use_cache:
        cached = cache_get(key_hash)
        if cached is not None:
            return cached

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": TEMPERATURE}
    }

    wait = 2
    global api_key_index

    for attempt in range(retries * len(API_KEYS)):  # tries all keys
        try:
            resp = requests.post(get_base_url(), json=payload, timeout=30)

            if resp.status_code == 429:  # rate limit
                print(f"⚠ Rate limit on key #{api_key_index+1}, rotating...")
                rotate_api_key()
                time.sleep(wait)
                wait = min(wait * 2, 30)
                continue

            if resp.status_code >= 500:  # server error
                print(f"⚠ Server error on key #{api_key_index+1}, rotating...")
                rotate_api_key()
                time.sleep(wait)
                wait = min(wait * 2, 30)
                continue

            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = strip_markdown_fences(text)
            cache_set(key_hash, text)
            return text

        except Exception as e:
            print(f"⚠ API call failed on key #{api_key_index+1} (Attempt {attempt+1}): {e}")
            rotate_api_key()
            time.sleep(wait)
            wait = min(wait * 2, 30)

    # If all keys fail:
    placeholder = "# [OFFLINE] LLM unavailable; skipping.\n"
    cache_set(key_hash, placeholder)
    return placeholder

# ---------- VALIDATORS ----------
def validator_output(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".py":
            proc = subprocess.run(["python", "-m", "py_compile", path], capture_output=True, text=True, timeout=12)
            return (proc.returncode == 0, (proc.stdout + proc.stderr).strip())
        if ext == ".js" and shutil.which("node"):
            proc = subprocess.run(["node", "--check", path], capture_output=True, text=True, timeout=12)
            return (proc.returncode == 0, (proc.stdout + proc.stderr).strip())
        if ext == ".php" and shutil.which("php"):
            proc = subprocess.run(["php", "-l", path], capture_output=True, text=True, timeout=12)
            return (proc.returncode == 0, (proc.stdout + proc.stderr).strip())
    except Exception as e:
        return (False, str(e))
    return (True, "")

# ---------- detect language heuristically ----------
def detect_language(path, content):
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".php": "PHP",
        ".html": "HTML", ".css": "CSS", ".java": "Java", ".rb": "Ruby",
    }
    if ext in mapping:
        return mapping[ext]
    if content.lstrip().startswith("#!"):
        shebang = content.splitlines()[0]
        if "python" in shebang: return "Python"
        if "node" in shebang or "nodejs" in shebang: return "JavaScript"
    if "<?php" in content: return "PHP"
    if "def " in content and "import " in content: return "Python"
    if "function " in content and "console.log" in content: return "JavaScript"
    return "Unknown"

# ---------- read agent templates ----------
def read_agent(name):
    path = os.path.join(AGENT_DIR, name)
    return read_file(path) if os.path.exists(path) else ""

# ---------- checkpoint helpers ----------
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"report": []}

def save_checkpoint(report):
    checkpoint = {
        "completed_files": [r["file"] for r in report if r["status"] == "Pass"],
        "report": report,
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2)

def write_report_html(report, outpath):
    rows = ""
    for r in report:
        issues_html = "<br>".join(r["issues"]) if r["issues"] else "None"
        rows += f"<tr><td>{r['file']}</td><td>{r['status']}</td><td>{issues_html}</td><td>{r['time']}</td></tr>"
    html = f"<html><body><h2>MAS Upgrade Report</h2><table border='1' style='border-collapse:collapse'><tr><th>File</th><th>Status</th><th>Issues</th><th>Time(s)</th></tr>{rows}</table></body></html>"
    write_file(outpath, html)

# ---------- DISCOVERY ----------
def discovery_phase(all_files, discovery_agent_template, batch_size=8):
    discoveries = {}
    file_payloads = []
    for full, rel in all_files:
        content = read_file(full)
        snippet = "\n".join(content.splitlines()[:200])
        lang = detect_language(rel, content)
        file_payloads.append({"rel": rel, "lang": lang, "snippet": snippet})

    for i in range(0, len(file_payloads), batch_size):
        batch = file_payloads[i:i+batch_size]
        prompt = discovery_agent_template + "\n\nFILES:\n"
        for f in batch:
            prompt += f"---FILE_START: {f['rel']} (LANG: {f['lang']})---\n{f['snippet']}\n---FILE_END---\n\n"
        prompt += "\nInstructions: For each file above, return a JSON object mapping filename to either 'NO_ISSUES' or a short list of issues (strings). Return ONLY valid JSON."
        resp = call_llm(prompt)
        parsed = {}
        try:
            obj_text = resp.strip()
            first_brace = obj_text.find('{')
            last_brace = obj_text.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_text = obj_text[first_brace:last_brace+1]
                parsed = json.loads(json_text)
        except:
            lines = resp.splitlines()
            for line in lines:
                if ":" in line:
                    parts = line.split(":", 1)
                    name = parts[0].strip()
                    val = parts[1].strip()
                    parsed[name] = val or "NO_ISSUES"
        for f in batch:
            key = f["rel"]
            discoveries[key] = parsed.get(key, parsed.get(os.path.basename(key), "NO_ISSUES"))
    return discoveries

# ---------- extract related snippets ----------
def extract_related_snippets(target_rel, all_files, max_chars=800):
    tokens = set(re.findall(r"[A-Za-z_]\w+", os.path.basename(target_rel)))
    snippets = []
    chars = 0
    for full, rel in all_files:
        if rel == target_rel: continue
        if os.path.dirname(rel) == os.path.dirname(target_rel) or os.path.splitext(rel)[1] == os.path.splitext(target_rel)[1]:
            txt = read_file(full)
            headers = re.findall(r"^(?:class|def|function|const|var|let|public|private|protected).{0,200}", txt, re.M)
            related = []
            for t in list(tokens)[:4]:
                for m in re.finditer(r".{0,120}\b" + re.escape(t) + r"\b.{0,120}", txt, re.S):
                    related.append(m.group(0).strip())
            chosen = (headers + related)[:6]
            for c in chosen:
                if c and chars < max_chars:
                    snippets.append(c.strip())
                    chars += len(c)
    seen, out = [], []
    for s in snippets:
        if s not in seen:
            out.append(s); seen.append(s)
    return "\n".join(out)[:max_chars]

# ---------- MAIN pipeline ----------
def run_pipeline():
    print("🚀 Starting self-discovery MAS upgrader")
    discovery_template = read_agent("discovery_agent.txt")
    manager_template = read_agent("manager.txt")
    maker_template = read_agent("pipeline_prompt_maker.txt")
    exec_template = read_agent("pipeline_prompt_executioner.txt")
    final_template = read_agent("finalizer.txt")

    all_files = []
    for root, _, files in os.walk(INPUT_DIR):
        for f in files:
            full = os.path.join(root, f)
            if is_binary_file(full): continue
            rel = os.path.relpath(full, INPUT_DIR)
            all_files.append((full, rel))

    if not all_files:
        print("No text files found under", INPUT_DIR)
        return

    checkpoint = load_checkpoint()
    report = checkpoint.get("report", [])
    passed = {r["file"] for r in report if r["status"] == "Pass"}

    print("🔎 Running discovery phase (batch detection of issues)...")
    discoveries = discovery_phase(all_files, discovery_template, batch_size=6)
    requirements = {k: v for k, v in discoveries.items() if not (isinstance(v, str) and v.strip().upper() in ("NO_ISSUES", "NONE"))}
    print(f"Discovery found {len(requirements)} files with potential issues.")

    print("🧭 Manager: breaking discoveries into tasks (per-file)...")
    for full, rel in all_files:
        if rel in passed:
            print(f"⏩ Skipping {rel} (already passed)")
            continue

        discovered = discoveries.get(rel, "NO_ISSUES")
        if isinstance(discovered, str) and discovered.strip().upper() in ("NO_ISSUES", "NONE"):
            manager_prompt = manager_template.replace("PROJECT_CONTEXT", "\n".join([a[1] for a in all_files[:40]])) \
                                             .replace("FILE_NAME", rel) \
                                             .replace("CODE_CONTENT", read_file(full)) \
                                             .replace("AUTOMATED_FINDINGS", "NO_ISSUES")
        else:
            manager_prompt = manager_template.replace("PROJECT_CONTEXT", "\n".join([a[1] for a in all_files[:40]])) \
                                             .replace("FILE_NAME", rel) \
                                             .replace("CODE_CONTENT", read_file(full)) \
                                             .replace("AUTOMATED_FINDINGS", discovered if isinstance(discovered, str) else json.dumps(discovered))
        manager_resp = call_llm(manager_prompt)
        if manager_resp and "NO UPGRADE NEEDED" in manager_resp.upper():
            print(f"✅ Manager: NO UPGRADE NEEDED for {rel}")
            dest_path = os.path.join(OUTPUT_DIR, rel)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(full, dest_path)  # Always copy original
            report = [r for r in report if r["file"] != rel]
            report.append({"file": rel, "status": "Pass", "issues": ["No upgrade needed"], "time": 0})
            save_checkpoint(report); write_report_html(report, os.path.join(REPORT_DIR, "report_latest.html"))
            continue

        tasks_text = manager_resp.strip()
        print(f"   🔹 Tasks for {rel}:\n{tasks_text[:400]}")

        maker_prompt = maker_template.replace("PROJECT_CONTEXT", "\n".join([a[1] for a in all_files[:40]])) \
                                     .replace("FILE_CONTEXT", f"{rel} ({detect_language(rel, read_file(full))})") \
                                     .replace("TASK", tasks_text)
        maker_out = call_llm(maker_prompt)
        if maker_out and maker_out.strip().upper() == "NO UPGRADE NEEDED":
            print(f"✅ Maker decided no upgrade needed for {rel}")
            dest_path = os.path.join(OUTPUT_DIR, rel)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(full, dest_path)  # Always copy original
            report = [r for r in report if r["file"] != rel]
            report.append({"file": rel, "status": "Pass", "issues": ["No upgrade needed"], "time": 0})
            save_checkpoint(report); write_report_html(report, os.path.join(REPORT_DIR, "report_latest.html"))
            continue

        snippets = extract_related_snippets(rel, all_files, max_chars=800)
        exec_prompt = exec_template.replace("PROJECT_CONTEXT", "\n".join([a[1] for a in all_files[:40]])) \
                                   .replace("RELATED_SNIPPETS", snippets) \
                                   .replace("FILE_NAME", rel) \
                                   .replace("CODE_CONTENT", read_file(full)) \
                                   .replace("PROMPT", maker_out)
        new_code = call_llm(exec_prompt)
        out_path = os.path.join(OUTPUT_DIR, rel)
        write_file(out_path, new_code)

        status = "Pass"; issues = []; start = time.time()
        for attempt in range(3):
            ok, out = validator_output(out_path)
            if ok:
                print(f"   ✅ Self-test passed for {rel} (attempt {attempt+1})")
                break
            else:
                print(f"   ❌ Self-test failed for {rel} (attempt {attempt+1}) -> {out[:400]}")
                final_prompt = final_template.replace("OLD_CODE", read_file(full)) \
                                             .replace("CODE_CONTENT", read_file(out_path)) \
                                             .replace("REMARKS", out)
                fixed = call_llm(final_prompt, use_cache=False)
                write_file(out_path, fixed)
                if attempt == 2:
                    status = "Fail"; issues.append("Self-test failed after finalizer attempts")
                    print("   ⚠ Finalizer failed; leaving file for manual review.")
        elapsed = round(time.time() - start, 2)
        report = [r for r in report if r["file"] != rel]
        report.append({"file": rel, "status": status, "issues": issues, "time": elapsed})
        save_checkpoint(report); write_report_html(report, os.path.join(REPORT_DIR, "report_latest.html"))

    print("✅ Run complete. Report:", os.path.join(REPORT_DIR, "report_latest.html"))

if __name__ == "__main__":
    run_pipeline()
