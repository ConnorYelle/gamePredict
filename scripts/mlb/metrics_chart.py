"""Render the metrics history as a self-contained SVG line chart.

GitHub markdown renders a committed ``.svg`` referenced as an image but strips
inline ``<svg>``, so this writes a standalone file the README links to. No
plotting dependency -- the SVG is built by hand so it stays in the project's
dependency-free spirit (same as the trainer).

The chart is small-multiples: one stacked panel per metric (Brier, accuracy,
log-loss), each on its own y-scale since the metrics live in different ranges.
The x-axis is run order (oldest -> newest). Colours and the dark card background
are baked in so it reads on both GitHub light and dark themes.
"""

# (key, title, "low"|"high" = which direction is better, colour)
PANELS = [
    ("brier", "Brier score", "low", "#f87171"),
    ("accuracy", "Accuracy", "high", "#34d399"),
    ("log_loss", "Log-loss", "low", "#60a5fa"),
]

_W = 760
_PANEL_H = 110
_PAD_TOP = 34          # space above each panel for its title
_PAD_BOTTOM = 18
_M_LEFT = 64
_M_RIGHT = 96
_BG = "#0f172a"
_GRID = "#334155"
_TEXT = "#e2e8f0"
_MUTED = "#94a3b8"


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _fmt(key, v):
    if v is None:
        return "n/a"
    return f"{v:.2%}" if key == "accuracy" else f"{v:.4f}"


def _panel_svg(panel, records, top):
    key, title, better, color = panel
    plot_w = _W - _M_LEFT - _M_RIGHT
    plot_h = _PANEL_H - _PAD_TOP - _PAD_BOTTOM
    y0 = top + _PAD_TOP                 # plot top
    y1 = y0 + plot_h                    # plot bottom (baseline)

    pts = [(i, r.get(key)) for i, r in enumerate(records)
           if isinstance(r.get(key), (int, float))]
    n = len(records)

    def px(i):
        if n <= 1:
            return _M_LEFT + plot_w / 2
        return _M_LEFT + plot_w * i / (n - 1)

    parts = []
    # Title with the latest value and its change from the first recorded run.
    latest = pts[-1][1] if pts else None
    first = pts[0][1] if pts else None
    sub = ""
    if latest is not None:
        sub = _fmt(key, latest)
        if first is not None and len(pts) > 1:
            d = latest - first
            arrow = "improved" if (d < 0) == (better == "low") and d != 0 else \
                    ("flat" if d == 0 else "worse")
            sub += f"  ({d:+.4f} vs first, {arrow})"
    parts.append(
        f'<text x="{_M_LEFT}" y="{top + 20}" fill="{_TEXT}" '
        f'font-size="15" font-weight="bold">{_esc(title)}</text>')
    if sub:
        parts.append(
            f'<text x="{_W - _M_RIGHT}" y="{top + 20}" fill="{color}" '
            f'font-size="13" text-anchor="end">{_esc(sub)}</text>')

    if not pts:
        parts.append(
            f'<text x="{_W/2}" y="{(y0+y1)/2}" fill="{_MUTED}" font-size="13" '
            f'text-anchor="middle">no data yet</text>')
        return "\n".join(parts)

    vals = [v for _, v in pts]
    vmin, vmax = min(vals), max(vals)
    span = (vmax - vmin) or max(abs(vmax), 1e-9)
    pad = span * 0.15
    lo, hi = vmin - pad, vmax + pad

    def py(v):
        return y1 - (v - lo) / (hi - lo) * plot_h

    # y gridlines + labels at the data min and max.
    for val in (vmax, vmin):
        yy = py(val)
        parts.append(f'<line x1="{_M_LEFT}" y1="{yy:.1f}" x2="{_W - _M_RIGHT}" '
                     f'y2="{yy:.1f}" stroke="{_GRID}" stroke-width="1" '
                     f'stroke-dasharray="3 3"/>')
        parts.append(f'<text x="{_M_LEFT - 8}" y="{yy + 4:.1f}" fill="{_MUTED}" '
                     f'font-size="11" text-anchor="end">{_fmt(key, val)}</text>')

    # The line + markers.
    if len(pts) > 1:
        poly = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in pts)
        parts.append(f'<polyline points="{poly}" fill="none" stroke="{color}" '
                     f'stroke-width="2.5"/>')
    for i, v in pts:
        parts.append(f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="3" '
                     f'fill="{color}"/>')
    return "\n".join(parts)


def render_svg(records):
    """Return an SVG document string charting every metric in PANELS over the
    given history records (oldest first). Handles 0, 1, or many points."""
    height = _PANEL_H * len(PANELS) + 56
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" '
           f'height="{height}" viewBox="0 0 {_W} {height}" '
           f'font-family="Arial, sans-serif">',
           f'<rect width="{_W}" height="{height}" rx="14" fill="{_BG}"/>',
           f'<text x="{_M_LEFT}" y="28" fill="{_TEXT}" font-size="18" '
           f'font-weight="bold">Model metrics history</text>']

    if not records:
        out.append(f'<text x="{_W/2}" y="{height/2}" fill="{_MUTED}" '
                   f'font-size="14" text-anchor="middle">'
                   f'No runs recorded yet — run train_weights.py or '
                   f'track_metrics.py.</text>')
    else:
        for idx, panel in enumerate(PANELS):
            out.append(_panel_svg(panel, records, 44 + idx * _PANEL_H))
        # x-axis caption.
        out.append(f'<text x="{_W - _M_RIGHT}" y="{height - 8}" fill="{_MUTED}" '
                   f'font-size="11" text-anchor="end">'
                   f'{len(records)} run(s), oldest → newest</text>')

    out.append("</svg>")
    return "\n".join(out)
