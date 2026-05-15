"""Renderings derived from the canonical JSON (Sections 27 + 28).

The card consumes the canonical JSON directly; these renderings produce
text fallbacks (Markdown body + short notification) for clients that
don't ship the custom card.
"""

from .markdown import render_markdown
from .notification_short import render_notification_short

__all__ = ["render_markdown", "render_notification_short"]
