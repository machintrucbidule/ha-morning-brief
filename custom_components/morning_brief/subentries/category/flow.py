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
        """Show the form; on submit, route to the applicable_to picker."""
        if user_input is not None:
            label = str(user_input["label"])
            slug = (
                str(user_input.get("category_id_override") or "").strip()
                or _slugify(label)
            )
            self._draft = {
                "category_id": slug,
                "label": label,
                "icon": str(user_input.get("icon", "")),
                "order": int(user_input.get("order", 10)),
                "display_when_empty": bool(
                    user_input.get("display_when_empty", False)
                ),
            }
            return await self.async_step_applicable_to()
        return self.async_show_form(
            step_id="user", data_schema=_category_schema(self._draft)
        )

    async def async_step_applicable_to(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick which morning_brief instances this category applies to.

        Empty selection = visible in EVERY instance (the default).
        """
        import voluptuous as vol
        from homeassistant.helpers import selector

        from ...const import DOMAIN
        from ...pool import async_get_pool

        if user_input is not None:
            applicable = list(user_input.get("applicable_to") or [])
            pool = async_get_pool(self.hass)  # type: ignore[attr-defined]
            if not pool._loaded:  # noqa: SLF001
                await pool.async_load()
            existing_id: str | None = None
            try:
                subentry = self._get_reconfigure_subentry()  # type: ignore[attr-defined]
            except AttributeError:
                subentry = None
            if subentry is not None:
                src_sid = getattr(subentry, "subentry_id", None)
                for item in pool.list_categories():
                    if item.get("data", {}).get("_migrated_subentry_id") == str(src_sid):
                        existing_id = str(item.get("id"))
                        break
            if existing_id is not None:
                await pool.async_update_category(
                    existing_id, data=dict(self._draft), applicable_to=applicable
                )
            else:
                await pool.async_add_category(
                    dict(self._draft), applicable_to=applicable
                )
            return self._finalise(
                title=str(self._draft.get("label", "Category")),
                data=dict(self._draft),
            )
        hass = getattr(self, "hass", None)
        entries = (
            list(hass.config_entries.async_entries(DOMAIN)) if hass else []
        )
        options = [
            selector.SelectOptionDict(
                value=e.entry_id, label=e.title or e.entry_id
            )
            for e in entries
        ]
        return self.async_show_form(
            step_id="applicable_to",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "applicable_to", default=[]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    def _finalise(self, *, title: str, data: dict[str, Any]) -> ConfigFlowResult:
        """Source ``user`` → create; source ``reconfigure`` → update."""
        source = getattr(self, "source", None)
        if source == "reconfigure":
            update_and_abort = getattr(self, "async_update_and_abort", None)
            if update_and_abort is not None:
                try:
                    subentry = self._get_reconfigure_subentry()  # type: ignore[attr-defined]
                except AttributeError:
                    subentry = None
                if subentry is not None:
                    parent = getattr(self, "source_entry", None) or getattr(
                        self, "config_entry", None
                    )
                    return update_and_abort(  # type: ignore[no-any-return]
                        entry=parent,
                        subentry=subentry,
                        data=data,
                        title=title,
                    )
            return self.async_abort(reason="reconfigure_unsupported")
        return self.async_create_entry(title=title, data=data)

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
