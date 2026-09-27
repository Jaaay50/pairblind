"""pairblind command line.

Examples:
  pairblind collect --base-url http://127.0.0.1:8080/v1 --model demo --key-file ~/.keys/demo --out run.jsonl
  pairblind score run.jsonl --reference official.jsonl
  pairblind compare left.jsonl right.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .collect import load_key, run_blind, run_habits
from .score import blind_report, compare_endpoints, habit_report, load_jsonl


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cmd_collect(args: argparse.Namespace) -> int:
    key = load_key(args.key_env, args.key_file)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    handle = out.open("a", encoding="utf-8")

    def sink(row: dict) -> None:
        row["base_host"] = args.base_url.split("://", 1)[-1].split("/", 1)[0]
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        flag = "ok" if row.get("ok") and row.get("passed", True) else "fail"
        print(f"{flag} {row['kind']} {row.get('probe_id') or row.get('task_id')}", flush=True)

    try:
        if not args.blind_only:
            run_habits(args.base_url, key, args.model, _read(args.probes), args.repeats, args.timeout, sink)
        if not args.habit_only:
            nonce = run_blind(args.base_url, key, args.model, _read(args.tasks), args.timeout, sink, nonce=args.nonce)
            print(f"nonce {nonce}")
    finally:
        handle.close()
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    rows = load_jsonl(Path(args.run))
    reference = load_jsonl(Path(args.reference)) if args.reference else None
    report = {"habits": habit_report(rows, reference), "blind": blind_report(rows)}
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    report = compare_endpoints(load_jsonl(Path(args.left)), load_jsonl(Path(args.right)))
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pairblind")
    sub = parser.add_subparsers(dest="cmd", required=True)

    collect = sub.add_parser("collect", help="call one endpoint and append JSONL")
    collect.add_argument("--base-url", required=True)
    collect.add_argument("--model", required=True)
    collect.add_argument("--key-env", default="PAIRBLIND_API_KEY")
    collect.add_argument("--key-file")
    collect.add_argument("--out", required=True)
    collect.add_argument("--probes", default=str(Path(__file__).resolve().parents[1] / "probes" / "v1.json"))
    collect.add_argument("--tasks", default=str(Path(__file__).resolve().parents[1] / "tasks" / "blind-v1.json"))
    collect.add_argument("--repeats", type=int, default=20)
    collect.add_argument("--timeout", type=float, default=60)
    collect.add_argument("--nonce", help="reuse a nonce so two endpoints are paired")
    collect.add_argument("--habit-only", action="store_true")
    collect.add_argument("--blind-only", action="store_true")
    collect.set_defaults(func=_cmd_collect)

    score = sub.add_parser("score", help="summarize one JSONL offline")
    score.add_argument("run")
    score.add_argument("--reference")
    score.set_defaults(func=_cmd_score)

    compare = sub.add_parser("compare", help="paired comparison of two JSONL runs")
    compare.add_argument("left")
    compare.add_argument("right")
    compare.set_defaults(func=_cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
