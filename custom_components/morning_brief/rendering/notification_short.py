"""Short notification rendering (Section 27).

3-line format:

```
Line 1 (only if alerts > 0): 🚨 N alert(s)
Line 2: emoji+value · emoji+value · …  (3-4 pinned key metrics)
Line 3 (only if verdict non-empty): first sentence of verdict
```

The "pinned" metrics are picked via the optional
``notification_pinned_fields`` (list of field_ids); fallback to the
first 3 fields in display order.
"""

from __future__ import annotations

from typing import Any

_DEFAULT_PINNED_COUNT = 3


def _walk_fields(brief: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten categories → fields in display order."""
    out: list[dict[str, Any]] = []
    for cat in sorted(
        brief.get("categories", []) or [], key=lambda c: int(c.get("order", 0))
    ):
        for f in sorted(
            cat.get("fields", []) or [], key=lambda r: int(r.get("order", 0))
        ):
            out.append(f)
    return out


def _pinned_fields(
    brief: dict[str, Any], pinned_ids: list[str] | None
) -> list[dict[str, Any]]:
    fields = _walk_fields(brief)
    if not pinned_ids:
        return fields[:_DEFAULT_PINNED_COUNT]
    by_id = {f.get("id"): f for f in fields}
    out: list[dict[str, Any]] = []
    for fid in pinned_ids:
        f = by_id.get(fid)
        if f is not None:
            out.append(f)
    return out


def _first_sentence(text: str) -> str:
    """Return the first sentence-ish chunk of ``text``."""
    text = text.strip()
    if not text:
        return ""
    for sep in (". ", "? ", "! "):
        if sep in text:
            return text.split(sep, 1)[0] + sep[0]
    return text


def render_notification_short(
    brief: dict[str, Any], pinned_field_ids: list[str] | None = None
) -> str:
    """Build the 1–3 line short notification body for ``brief``."""
    lines: list[str] = []
    alerts = brief.get("alerts", []) or []
    if alerts:
        lines.append(f"🚨 {len(alerts)} alert(s)")
    bits: list[str] = []
    for f in _pinned_fields(brief, pinned_field_ids):
        icon = f.get("icon", "")
        formatted = (f.get("value", {}) or {}).get("formatted", "—")
        bits.append(f"{icon} {formatted}".strip())
    if bits:
        lines.append(" · ".join(bits))
    verdict = (brief.get("ai_output", {}) or {}).get("verdict", "")
    head = _first_sentence(verdict)
    if head:
        lines.append(head)
    return "\n".join(lines)
