"""Run the same labeled cases in offline rule mode or live Groq mode."""
import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from copilot import handle, route_demo, route_groq
from store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("demo", "groq"), default="demo")
    parser.add_argument("--output", type=Path, default=Path("reports/evaluation.json"))
    args = parser.parse_args()
    key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    route = route_demo
    if args.mode == "groq":
        if not key:
            parser.error("Set GROQ_API_KEY first.")

        def route(message):
            return route_groq(message, model, key)

    cases_path = Path(__file__).with_name("data") / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    rows = []
    with TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "test.sqlite3")
        for case in cases:
            result = handle(store, "demo-a", case["message"], route)
            expected = case["expected"]
            # Confirmation tokens are transient and never included in the report.
            actual = {key: value for key, value in result.items() if key != "confirmation_token"}
            unavailable = actual.get("reason") == "router_unavailable"
            matched = all(actual.get(key) == value for key, value in expected.items() if key != "reply_contains")
            matched = matched and expected.get("reply_contains", "") in actual["reply"]
            rows.append({"id": case["id"], "expected": expected, "actual": actual,
                         "result": "router_error" if unavailable else "pass" if matched else "fail"})
    counts = {label: sum(row["result"] == label for row in rows) for label in ("pass", "fail", "router_error")}
    report = {"mode": args.mode, "model": model if args.mode == "groq" else None, "counts": counts, "cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.mode}: {counts} | Report: {args.output}")
    return 2 if counts["router_error"] else int(bool(counts["fail"]))


if __name__ == "__main__":
    raise SystemExit(main())
