"""Collect answers from an OpenAI-compatible chat endpoint.

The API key is read from the environment or a file path you pass.
It is never written into the JSONL.
"""
from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path


def load_key(env: str, path: str | None) -> str:
    if path:
        key = Path(path).read_text(encoding="utf-8").strip()
    else:
        key = os.environ.get(env, "").strip()
    if not key:
        raise SystemExit(f"missing API key: set {env} or pass --key-file")
    return key


def chat(base_url: str, key: str, model: str, system: str, user: str, timeout: float) -> tuple[bool, str]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 64,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        return False, f"http {exc.code}: {detail}"
    except urllib.error.URLError as exc:
        return False, f"network: {exc.reason}"
    try:
        text = raw["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return False, "malformed response"
    return True, text


def run_habits(base_url: str, key: str, model: str, probes: dict, repeats: int, timeout: float, sink) -> None:
    for item in probes["items"]:
        for index in range(repeats):
            ok, text = chat(base_url, key, model, item["system"], item["user"], timeout)
            sink({
                "kind": "habit",
                "probe_id": item["id"],
                "repeat": index,
                "model": model,
                "ok": ok,
                "text": text if ok else "",
                "error": "" if ok else text,
            })


def run_blind(base_url: str, key: str, model: str, tasks: dict, timeout: float, sink, nonce: str | None = None) -> str:
    nonce = nonce or secrets.token_hex(8)
    for item in tasks["items"]:
        user = item.get("user", "").replace("{nonce}", nonce)
        if item["kind"] == "sum":
            user = f"Compute {item['a']} + {item['b']}. Reply with the integer only."
            system = "Reply with digits only."
        else:
            system = "Follow the user instruction exactly."
        ok, text = chat(base_url, key, model, system, user, timeout)
        from .score import grade_blind
        passed = grade_blind(item, text, nonce) if ok else False
        sink({
            "kind": "blind",
            "task_id": item["id"],
            "nonce": nonce,
            "model": model,
            "ok": ok,
            "passed": passed,
            "text": text if ok else "",
            "error": "" if ok else text,
        })
    return nonce
