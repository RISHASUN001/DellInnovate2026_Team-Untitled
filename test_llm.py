#!/usr/bin/env python3
"""
Quick test: checks if the OpenRouter LLM is reachable and can answer questions.
Usage:
    python test_llm.py                    # uses .env or env vars
    python test_llm.py "your question"    # custom question
"""

import os
import sys
import json
import urllib.request
import urllib.error
from dotenv import dotenv_values

# ── Load config ──────────────────────────────────────────────────────────────
env = dotenv_values(".env")

API_KEY   = env.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
BASE_URL  = env.get("OPENROUTER_BASE_URL") or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL     = env.get("OPENROUTER_MODEL")    or os.getenv("OPENROUTER_MODEL",    "deepseek/deepseek-chat-v3.1")

QUESTION  = sys.argv[1] if len(sys.argv) > 1 else "What is 2 + 2? Answer in one sentence."

# ── Helpers ──────────────────────────────────────────────────────────────────
def ok(msg):  print(f"  [OK]  {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def info(msg): print(f"  [--]  {msg}")

# ── 1. Check API key present ──────────────────────────────────────────────────
print("\n=== LLM Health Check ===\n")
print(f"Model   : {MODEL}")
print(f"Base URL: {BASE_URL}")
print()

if not API_KEY or API_KEY == "sk-or-placeholder":
    fail("OPENROUTER_API_KEY is missing or is the placeholder value.")
    fail("Set it in your .env file: OPENROUTER_API_KEY=sk-or-v1-...")
    sys.exit(1)
ok(f"API key found: {API_KEY[:12]}...")

# ── 2. Test /models endpoint (connectivity check) ─────────────────────────────
print("\n[1] Checking connectivity to OpenRouter...")
models_url = f"{BASE_URL}/models"
req = urllib.request.Request(
    models_url,
    headers={"Authorization": f"Bearer {API_KEY}"},
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        model_ids = [m["id"] for m in data.get("data", [])]
        ok(f"Reached OpenRouter — {len(model_ids)} models listed.")
        if MODEL in model_ids:
            ok(f"Target model '{MODEL}' is listed as available.")
        else:
            info(f"Target model '{MODEL}' not found in /models list (may still work).")
except urllib.error.HTTPError as e:
    fail(f"HTTP {e.code} from {models_url}: {e.reason}")
    sys.exit(1)
except Exception as e:
    fail(f"Could not reach OpenRouter: {e}")
    sys.exit(1)

# ── 3. Send a chat completion request ────────────────────────────────────────
print(f"\n[2] Sending question to model...")
print(f"    Q: {QUESTION}")

payload = json.dumps({
    "model": MODEL,
    "messages": [{"role": "user", "content": QUESTION}],
    "max_tokens": 200,
}).encode()

chat_url = f"{BASE_URL}/chat/completions"
req = urllib.request.Request(
    chat_url,
    data=payload,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type":  "application/json",
    },
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        answer = data["choices"][0]["message"]["content"].strip()
        usage  = data.get("usage", {})
        ok("Received a response!")
        print(f"\n    A: {answer}")
        if usage:
            print(f"\n    Tokens — prompt: {usage.get('prompt_tokens','?')}, "
                  f"completion: {usage.get('completion_tokens','?')}, "
                  f"total: {usage.get('total_tokens','?')}")
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="replace")
    fail(f"HTTP {e.code}: {e.reason}")
    fail(f"Response body: {body}")
    sys.exit(1)
except Exception as e:
    fail(f"Request failed: {e}")
    sys.exit(1)

print("\n=== All checks passed — LLM is loaded and responding ===\n")
