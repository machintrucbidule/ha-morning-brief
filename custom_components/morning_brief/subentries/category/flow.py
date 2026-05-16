"""Category subentry add/edit flow (Section 21.3).

Single screen: label / icon / order / display_when_empty. The
category_id slug is derived from the label.

Supports reconfigure (edit) via ``async_step_reconfigure`` — the form
re-opens with the existing data as defaults so the user can change
*any* field (not just the title).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

# See subentries/field/flow.py for the rationale on this defensive alias.
if TYPE_CHECKING:
    _SubentryBase = config_entries.ConfigFlow
else:
    _SubentryBase = getattr(
        config_entries, "ConfigSubentryFlow", config_entries.ConfigFlow
    )


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", label.lower()).strip("_")
    return slug or "category"


def _category_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "label", default=current.get("label", "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Optional(
                "icon", default=current.get("icon", "")
            ): selector.IconSelector(),
            vol.Optional(
                "order", default=int(current.get("order", 10))
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=999, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "display_when_empty",
                default=bool(current.get("display_when_empty", False)),
            ): selector.BooleanSelector(),
            vol.Optional(
                "category_id_override",
                default=str(current.get("category_id", "")),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )


class CategorySubentryFlow(_SubentryBase):
    """Single-screen add/edit for the `category` subentry."""

    def __init__(self) -> None:
        """Initialise an empty draft so reconfigure can prime it."""
        self._draft: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the form; on submit, persist the new (or updated) subentry."""
        if user_input is not None:
            label = str(user_input["label"])
            slug = (
                str(user_input.get("category_id_override") or "").strip()
                or _slugify(label)
            )
            data: dict[str, Any] = {
                "category_id": slug,
                "label": label,
                "icon": str(user_input.get("icon", "")),
                "order": int(user_input.get("order", 10)),
                "display_when_empty": bool(
                    user_input.get("display_when_empty", False)
                ),
            }
            return self.async_create_entry(title=label, data=data)
        return self.async_show_form(
            step_id="user", data_schema=_category_schema(self._draft)
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit entry point. Pre-populate from existing subentry data."""
        try:
            subentry = self._get_reconfigure_subentry()  # type: ignore[attr-defined]
        except AttributeError:
            subentry = None
        if subentry is not None:
            self._draft = dict(getattr(subentry, "data", {}) or {})
        return await self.async_step_user(user_input)
