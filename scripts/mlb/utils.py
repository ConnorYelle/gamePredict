"""Pure numeric helpers shared across the package (no I/O, no state)."""


def to_float(value, default=0.0):
    """Coerce ``value`` to float, returning ``default`` on bad/missing input."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ip_to_float(ip):
    """Convert MLB innings-pitched notation ('6.2' = 6 + 2/3) to a float."""
    try:
        whole, _, frac = str(ip).partition(".")
        outs = int(frac) if frac else 0
        return int(whole) + outs / 3.0
    except (ValueError, TypeError):
        return 0.0
