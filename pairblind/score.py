"""Offline scoring. Reads JSONL the collector wrote. Never opens a network."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .stats import counts, js_divergence, mcnemar, mode_share, normalize, separation


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def habit_report(rows: list[dict], reference_rows: list[dict] | None = None) -> dict:
    by_probe: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row.get("kind") == "habit" and row.get("ok"):
            by_probe[row["probe_id"]].append(row.get("text") or "")
    ref: dict[str, list[str]] = defaultdict(list)
    for row in reference_rows or []:
        if row.get("kind") == "habit" and row.get("ok"):
            ref[row["probe_id"]].append(row.get("text") or "")
    probes = {}
    for probe_id, answers in sorted(by_probe.items()):
        sample = counts(answers)
        item = {
            "n": sum(sample.values()),
            "unique": len(sample),
            "mode_share": round(mode_share(sample), 4),
            "top": sample.most_common(5),
        }
        if probe_id in ref:
            baseline = counts(ref[probe_id])
            item["jsd_vs_reference"] = round(js_divergence(baseline, sample), 4)
            item["display_separation"] = round(separation(baseline, sample), 4)
            item["display_note"] = "logistic of JS divergence, not an identity probability"
        probes[probe_id] = item
    return {"habit": probes, "warning": "Habit match is not model identity. Distributions drift."}


def blind_report(rows: list[dict]) -> dict:
    tasks: dict[str, dict] = {}
    for row in rows:
        if row.get("kind") != "blind":
            continue
        bucket = tasks.setdefault(row["task_id"], {"pass": 0, "fail": 0, "errors": 0})
        if not row.get("ok"):
            bucket["errors"] += 1
        elif row.get("passed"):
            bucket["pass"] += 1
        else:
            bucket["fail"] += 1
    return {"blind": tasks}


def compare_endpoints(left_rows: list[dict], right_rows: list[dict]) -> dict:
    """Paired blind-task outcomes. Same task_id + nonce must exist on both sides."""
    def key(row: dict) -> tuple:
        return (row.get("task_id"), row.get("nonce"))

    left = {key(row): row for row in left_rows if row.get("kind") == "blind"}
    right = {key(row): row for row in right_rows if row.get("kind") == "blind"}
    shared = sorted(set(left) & set(right))
    both = only_left = only_right = 0
    for item in shared:
        a = bool(left[item].get("ok") and left[item].get("passed"))
        b = bool(right[item].get("ok") and right[item].get("passed"))
        if a and b:
            both += 1
        elif a and not b:
            only_left += 1
        elif b and not a:
            only_right += 1
    habit_left = habit_report(left_rows)
    habit_right = habit_report(right_rows)
    distances = {}
    for probe_id, block in habit_left["habit"].items():
        other = habit_right["habit"].get(probe_id)
        if not other:
            continue
        # Rebuild counters from the top list only when full rows are present.
        distances[probe_id] = {
            "left_mode_share": block["mode_share"],
            "right_mode_share": other["mode_share"],
        }
    by_probe_l: dict[str, list[str]] = defaultdict(list)
    by_probe_r: dict[str, list[str]] = defaultdict(list)
    for row in left_rows:
        if row.get("kind") == "habit" and row.get("ok"):
            by_probe_l[row["probe_id"]].append(row.get("text") or "")
    for row in right_rows:
        if row.get("kind") == "habit" and row.get("ok"):
            by_probe_r[row["probe_id"]].append(row.get("text") or "")
    for probe_id in sorted(set(by_probe_l) & set(by_probe_r)):
        distances.setdefault(probe_id, {})
        distances[probe_id]["jsd"] = round(js_divergence(counts(by_probe_l[probe_id]), counts(by_probe_r[probe_id])), 4)
    return {
        "paired_blind": mcnemar(both, only_left, only_right),
        "habit_distance": distances,
        "reading": (
            "A small McNemar p means the two endpoints disagree on which blind items they pass. "
            "That is evidence of different behavior, not of which brand name is behind either URL."
        ),
    }


def grade_blind(task: dict, text: str, nonce: str) -> bool:
    kind = task["kind"]
    body = text.strip()
    if kind == "sum":
        digits = "".join(ch for ch in body if ch.isdigit())
        return digits == str(task["expect"])
    if kind == "contains_nonce":
        return nonce in body and normalize(body) == normalize(nonce)
    if kind == "json_keys":
        try:
            value = json.loads(body)
        except json.JSONDecodeError:
            return False
        if not isinstance(value, dict):
            return False
        if sorted(value) != sorted(task["keys"]):
            return False
        return value.get("count") == task["count"] and isinstance(value.get("bird"), str) and bool(value["bird"].strip())
    raise ValueError(f"unknown task kind {kind}")
