"""
OpenAI key / quota diagnostic.
Run: ./venv/bin/python test_openai_key.py

Checks (in order):
  1. Key is present and not a placeholder
  2. Key format looks valid
  3. Can reach api.openai.com (network)
  4. Key authenticates (models list)
  5. gpt-4o is accessible (chat completion, 1 token)
  6. Embedding model is accessible
  7. Quota / rate-limit is not already exhausted

Prints a clear PASS/FAIL for each and a final verdict.
"""
import os, sys, json, socket
from pathlib import Path

# ── Load .env manually (no dotenv dependency needed) ──────────────────────
env_path = Path(__file__).parent / ".env"
env = {}
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

API_KEY   = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
BASE_URL  = env.get("OPENAI_BASE_URL", "").strip()
MODEL     = env.get("OPENAI_MODEL", "gemini-2.5-flash")
PROVIDER  = "Gemini" if "googleapis" in BASE_URL else "OpenAI"

PASS_LIST, FAIL_LIST = [], []

def ok(name, detail=""):
    print(f"  \033[32mPASS\033[0m  {name}" + (f"  → {detail}" if detail else ""))
    PASS_LIST.append(name)

def fail(name, detail=""):
    print(f"  \033[31mFAIL\033[0m  {name}" + (f"  → {detail}" if detail else ""))
    FAIL_LIST.append(name)

def section(t):
    print(f"\n\033[1m{t}\033[0m")

# ── 1. Key present ─────────────────────────────────────────────────────────
section("1. Key presence")
if not API_KEY:
    fail("OPENAI_API_KEY set", "not found in .env or environment")
elif API_KEY in ("sk-placeholder", "your-key-here", "", "PASTE_YOUR_GEMINI_API_KEY_HERE"):
    fail("OPENAI_API_KEY is not a placeholder", f"value is '{API_KEY}'")
else:
    ok("OPENAI_API_KEY set", f"{API_KEY[:8]}…{API_KEY[-4:]}")

section(f"Provider: {PROVIDER}  |  base_url: {BASE_URL or '(OpenAI default)'}")

# ── 2. Format ──────────────────────────────────────────────────────────────
section("2. Key format")
if PROVIDER == "Gemini":
    # Gemini keys from AI Studio can start with AIza... or AQ....
    if (API_KEY.startswith("AIza") or API_KEY.startswith("AQ.")) and len(API_KEY) > 20:
        ok("Gemini key format OK", f"starts with {API_KEY[:5]}…")
    else:
        fail("Gemini key format", f"Unexpected format: {API_KEY[:12]}…")
else:
    if API_KEY.startswith("sk-") and len(API_KEY) > 20:
        ok("Key starts with sk- and is long enough")
    else:
        fail("Key format", f"Expected sk-…, got: {API_KEY[:12]}…")

# ── 3. Network ─────────────────────────────────────────────────────────────
section("3. Network reachability")
try:
    socket.setdefaulttimeout(6)
    socket.getaddrinfo("api.openai.com", 443)
    ok("DNS resolves api.openai.com")
except Exception as e:
    fail("DNS resolves api.openai.com", str(e))

# ── 4–7. Live API calls ─────────────────────────────────────────────────────
if FAIL_LIST:
    print("\n\033[33mSkipping live API checks — fix the issues above first.\033[0m")
else:
    try:
        from openai import OpenAI, AuthenticationError, PermissionDeniedError, RateLimitError
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL or None)

        # 4. Authentication — list models
        section("4. Authentication (list models)")
        try:
            models = client.models.list()
            model_ids = [m.id for m in models.data]
            ok("Key authenticates", f"{len(model_ids)} models visible")
        except AuthenticationError as e:
            fail("Key authenticates", f"AuthenticationError: {e}")
        except Exception as e:
            fail("Key authenticates", str(e))

        # 5. Chat completion — gpt-4o
        section(f"5. Chat completion ({MODEL})")
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": "Reply with the single word: working"}],
                max_tokens=5,
                temperature=0,
            )
            reply = resp.choices[0].message.content.strip()
            ok(f"{MODEL} chat completion", f"response: '{reply}'")

            usage = resp.usage
            ok("Token usage returned",
               f"prompt={usage.prompt_tokens} completion={usage.completion_tokens}")
        except AuthenticationError as e:
            fail(f"{MODEL} chat completion", f"AuthenticationError — key is invalid or revoked")
        except PermissionDeniedError as e:
            fail(f"{MODEL} chat completion", f"PermissionDenied — key may not have access to {MODEL}")
        except RateLimitError as e:
            fail(f"{MODEL} chat completion", f"RateLimitError — quota exhausted or rate limited: {e}")
        except Exception as e:
            fail(f"{MODEL} chat completion", str(e))

        # 6. JSON structured output (used by KPI extractor, risk classifier, etc.)
        section("6. JSON response_format (used by pipeline engines)")
        try:
            from app.core.llm_client import chat_complete_json
            parsed = chat_complete_json(
                messages=[{"role": "user",
                           "content": 'Return a JSON object with two fields: "status" set to "ok" and "value" set to 42.'}],
                max_tokens=200,
            )
            ok("json_object response_format works", f"got: {parsed}")
        except Exception as e:
            fail("json_object response_format", str(e))

        # 7. Embeddings — Gemini doesn't expose the embeddings endpoint via the OpenAI compat layer,
        #    so skip for Gemini; the project uses SentenceTransformers locally for embeddings.
        section("7. Embeddings (SentenceTransformers — local, no API needed)")
        try:
            from sentence_transformers import SentenceTransformer
            m = SentenceTransformer("all-MiniLM-L6-v2")
            vec = m.encode("annual report revenue profit")
            ok("SentenceTransformer encodes locally", f"{len(vec)}-dim vector")
        except Exception as e:
            fail("SentenceTransformer", str(e))

    except ImportError:
        fail("openai package importable", "run: pip install openai")

# ── Summary ─────────────────────────────────────────────────────────────────
print(f"\n{'='*52}")
total = len(PASS_LIST) + len(FAIL_LIST)
if not FAIL_LIST:
    print(f"\033[32m\033[1mAll {total} checks passed — OpenAI key is working.\033[0m")
    print(f"\033[32mKPI extraction, risk classification, Q&A, and summaries will all function.\033[0m")
else:
    print(f"\033[1m{len(PASS_LIST)}/{total} passed,  {len(FAIL_LIST)} failed\033[0m")
    print(f"\033[31mFailed checks:\033[0m")
    for f in FAIL_LIST:
        print(f"  • {f}")
    print()
    if any("placeholder" in f.lower() or "not set" in f.lower() or "presence" in f.lower() for f in FAIL_LIST):
        print("\033[33mAction needed:\033[0m Open backend/.env and replace:")
        print("  OPENAI_API_KEY=sk-placeholder")
        print("with your real key from https://platform.openai.com/api-keys")
    elif any("AuthenticationError" in f or "authenticates" in f.lower() for f in FAIL_LIST):
        print("\033[33mAction needed:\033[0m The key was rejected — it may be revoked or copied incorrectly.")
        print("  Generate a new key at https://platform.openai.com/api-keys")
    elif any("RateLimit" in f or "quota" in f.lower() for f in FAIL_LIST):
        print("\033[33mAction needed:\033[0m Quota exhausted.")
        print("  Check usage at https://platform.openai.com/usage")
        print("  Add a payment method or wait for the monthly reset.")
    elif any("Permission" in f for f in FAIL_LIST):
        print(f"\033[33mAction needed:\033[0m Key doesn't have access to {MODEL}.")
        print("  Try changing OPENAI_MODEL=gpt-3.5-turbo in backend/.env")
    sys.exit(1)
