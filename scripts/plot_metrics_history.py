#!/usr/bin/env python3
"""Render the metrics history to an SVG and embed it in README.md (CLI).

Reads data/metrics_history.jsonl (written by train_weights.py / track_metrics.py),
writes docs/metrics_history.svg, and refreshes the chart + latest-values line in
README.md between the METRICS-HISTORY markers. Run it after recording new runs:

    python scripts/plot_metrics_history.py

CLI facade over :mod:`mlb.metrics_log` and :mod:`mlb.metrics_chart`.
"""

from datetime import datetime, timezone

from mlb import config, metrics_chart, metrics_log

SVG_REL = "docs/metrics_history.svg"
SVG_PATH = config.ROOT / "docs" / "metrics_history.svg"
README = config.ROOT / "README.md"

MARK_START = "<!-- METRICS-HISTORY-START -->"
MARK_END = "<!-- METRICS-HISTORY-END -->"


def latest_summary(records):
    """One markdown line summarising the most recent recorded run."""
    if not records:
        return ("_No runs recorded yet — run `python scripts/train_weights.py` "
                "or `python scripts/track_metrics.py`._")
    r = records[-1]
    acc = r.get("accuracy")
    brier = r.get("brier")
    ll = r.get("log_loss")
    acc_s = f"{acc:.2%}" if isinstance(acc, (int, float)) else "n/a"
    brier_s = f"{brier:.4f}" if isinstance(brier, (int, float)) else "n/a"
    ll_s = f"{ll:.4f}" if isinstance(ll, (int, float)) else "n/a"
    label = r.get("note") or (f"val {r.get('season')}" if r.get("season") else "latest")
    git = r.get("git") or "?"
    return (f"_Latest ({label}, git `{git}`): accuracy {acc_s} · Brier {brier_s} "
            f"· log-loss {ll_s} — {len(records)} run(s) recorded._")


def build_block(records):
    return (f"{MARK_START}\n\n"
            f"![Model metrics history]({SVG_REL})\n\n"
            f"{latest_summary(records)}\n\n"
            f"{MARK_END}")


def update_readme(records):
    if not README.exists():
        print("README.md not found; wrote SVG only.")
        return
    content = README.read_text(encoding="utf-8")
    block = build_block(records)
    if MARK_START in content and MARK_END in content:
        pre, rest = content.split(MARK_START, 1)
        _, post = rest.split(MARK_END, 1)
        content = pre + block + post
    else:
        section = f"\n## Metrics history\n\n{block}\n"
        content = content.rstrip() + "\n" + section
    README.write_text(content, encoding="utf-8")


def main():
    records = metrics_log.load_history()
    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(metrics_chart.render_svg(records), encoding="utf-8")
    update_readme(records)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Wrote {SVG_REL} ({len(records)} run(s)) and refreshed README "
          f"[{stamp}].")


if __name__ == "__main__":
    main()
