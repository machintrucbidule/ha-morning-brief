"""Category subentry add/edit flow (Section 21.3).

Single screen: label / icon / order / display_when_empty. The
category_id slug is derived from the label.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

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
            vol.Required("label", default=current.get("label", "")): str,
            vol.Optional("icon", default=current.get("icon", "")): str,
            vol.Optional("order", default=int(current.get("order", 10))): vol.All(
                int, vol.Range(min=0)
            ),
            vol.Optional(
                "display_when_empty",
                default=bool(current.get("display_when_empty", False)),
            ): bool,
            vol.Optional(
                "category_id_override",
                default=str(current.get("category_id", "")),
            ): str,
        }
    )


class CategorySubentryFlow(_SubentryBase):
    """Single-screen add/edit for the `category` subentry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the form; on submit, persist the new subentry."""
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
        return self.async_show_form(step_id="user", data_schema=_category_schema({}))
