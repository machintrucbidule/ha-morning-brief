"""Markdown rendering of the canonical brief (Section 28).

Pure function: takes the canonical JSON dict and returns a string. Used
by the persistent notification, the optional `markdown` Lovelace card,
and any consumer that wants a no-custom-card view (D17).

Localisation of section headers (`Alerts`, `Verdict`, etc.) is a
Phase 11 polish — for now the labels are English-only; the body text
(field labels, AI insights, verdict) is already in the instance
language because the AI replied in it.
"""

from __future__ import annotations

from typing import Any

_SECTION_HEADERS = {
    "alerts": "🚨 Alerts",
    "verdict": "Verdict",
}


def _format_field_line(field: dict[str, Any]) -> str:
    """One bullet per field: `- 🤍 Label: **value** _comparison summary_`."""
    icon = field.get("icon", "")
    label = field.get("label", "")
    value = field.get("value", {})
    formatted = value.get("formatted", "—")
    stale = value.get("stale", False)
    bullet = f"- {icon} {label}: **{formatted}**".strip()
    if stale:
        bullet += " _(stale)_"
    deltas = []
    for c in field.get("comparisons", []) or []:
        delta = c.get("delta_formatted") or ""
        ctype = c.get("type", "")
        if delta:
            deltas.append(f"{ctype} {delta}")
    if deltas:
        bullet += " _(" + " · ".join(deltas) + ")_"
    return bullet


def _format_category_block(category: dict[str, Any]) -> str:
    header = f"## {category.get('icon', '')} {category.get('label', '')}".strip()
    fields = category.get("fields", []) or []
    if not fields:
        return ""
    lines = [header]
    for f in fields:
        lines.append(_format_field_line(f))
    return "\n".join(lines)


def _format_alerts_block(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return ""
    lines = [f"## {_SECTION_HEADERS['alerts']}"]
    for a in alerts:
        severity = a.get("severity", "warning").upper()
        message = a.get("message", "")
        lines.append(f"- [{severity}] {message}")
    return "\n".join(lines)


def render_markdown(brief: dict[str, Any]) -> str:
    """Render the canonical brief dict as markdown (Section 28.1)."""
    meta = brief.get("meta", {}) or {}
    title = f"# {meta.get('instance_name', 'Brief')} — {meta.get('logical_date', '')}"

    parts: list[str] = [title]
    alerts = _format_alerts_block(brief.get("alerts", []) or [])
    if alerts:
        parts.append(alerts)

    for category in brief.get("categories", []) or []:
        block = _format_category_block(category)
        if block:
            parts.append(block)

    ai = brief.get("ai_output", {}) or {}
    weather = ai.get("weather_synthesis", "")
    if weather:
        parts.append(f"## 🌤️ Weather\n{weather}")

    verdict = ai.get("verdict", "")
    if verdict:
        parts.append(f"> **{_SECTION_HEADERS['verdict']}**: {verdict}")

    parts.append(f"---\n_Logical date {meta.get('logical_date', '')}_")
    return "\n\n".join(parts)
