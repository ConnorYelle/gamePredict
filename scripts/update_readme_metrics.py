#!/usr/bin/env python3
"""Compute validation metrics and insert/update them into README.md.

Places the metrics in README.md between markers:
<!-- METRICS-START --> and <!-- METRICS-END -->

Run: python scripts/update_readme_metrics.py
"""
import os
import sys
from datetime import datetime
from validate_predictions import validate


ROOT = os.path.dirname(os.path.dirname(__file__))
README = os.path.join(ROOT, 'README.md')

MARKER_START = '<!-- METRICS-START -->'
MARKER_END = '<!-- METRICS-END -->'


def format_metrics(m: dict) -> str:
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    lines = [f'{MARKER_START}', '', f'## Model validation (latest)\nGenerated: {ts}', '',
             f'- Predictions parsed: {m["predictions_parsed"]}',
             f'- Actual outcomes parsed: {m["actual_parsed"]}',
             f'- Matched games: {m["matched"]}',
             f'- Unmatched games: {m["unmatched"]}',
             f'- Pick accuracy: {m["pick_accuracy"]:.2%}',
             f'- Average probability assigned to winners: {m["average_prob"]:.2%}',
             f'- Brier score: {m["brier"]:.4f}',
            ]
    if m.get('stats_dir'):
        lines.append(f'- Stats directory used: {m["stats_dir"]}')
    lines.append('')
    lines.append(MARKER_END)
    return '\n'.join(lines) + '\n'


def update_readme(pred_path='outputs/predictions.txt', games_path='outputs/games.txt'):
    metrics = validate(pred_path, games_path)
    block = format_metrics(metrics)

    if not os.path.exists(README):
        print('README.md not found at', README)
        sys.exit(1)

    with open(README, 'r', encoding='utf-8') as f:
        content = f.read()

    if MARKER_START in content and MARKER_END in content:
        pre, rest = content.split(MARKER_START, 1)
        _, post = rest.split(MARKER_END, 1)
        new_content = pre + block + post
    else:
        # append block at end
        new_content = content.rstrip() + '\n\n' + block

    with open(README, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print('Updated README metrics block.')


if __name__ == '__main__':
    update_readme()
