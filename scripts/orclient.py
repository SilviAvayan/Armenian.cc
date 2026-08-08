#!/usr/bin/env python3
"""Tiny OpenRouter client (stdlib only). Reads key from .env."""
import json, os, time, urllib.request, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
def _key():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for line in (HERE/".env").read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=",1)[1].strip()
    raise SystemExit("no OPENROUTER_API_KEY")

KEY = _key()
URL = "https://openrouter.ai/api/v1/chat/completions"

def chat(model, messages, temperature=0.0, max_tokens=512, retries=4, json_mode=False):
    body = {"model": model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body).encode()
    hdr = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
           "HTTP-Referer": "https://armenian.cc", "X-Title": "armenian.cc-eval"}
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(URL, data=data, headers=hdr)
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read().decode())
            ch = j.get("choices")
            if not ch:                       # transient null-choices (retryable)
                raise RuntimeError("null choices: " + json.dumps(j)[:160])
            return ch[0]["message"]["content"]
        except Exception as e:
            last = e
            try:
                body_err = e.read().decode()[:300]  # type: ignore
            except Exception:
                body_err = ""
            time.sleep(1.5*(a+1))
    raise RuntimeError(f"chat failed: {last} {body_err if 'body_err' in dir() else ''}")

if __name__ == "__main__":
    import sys
    m = sys.argv[1] if len(sys.argv) > 1 else "google/gemini-2.0-flash-001"
    print("model:", m)
    print(chat(m, [{"role":"user","content":"Reply with exactly: OK"}], max_tokens=10))
