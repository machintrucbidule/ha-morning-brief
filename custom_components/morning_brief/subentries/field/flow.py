# rationale: a single-class multi-step flow naturally bundles the 7 spec
# screens (identity / provider params / display / comparisons / anomaly
# / visibility / gate) because they share the `_draft` state. Splitting
# would re-introduce inter-screen plumbing.
"""Field subentry add/edit flow (Section 21.2).

Seven steps. Each writes into ``self._draft`` and the last step calls
``async_create_entry``. Edit is the same flow with the existing data as
defaults.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .schema import (
    anomaly_schema,
    comparisons_schema,
    display_schema,
    gate_schema,
    identity_schema,
    provider_params_schema,
    visibility_schema,
)

# `ConfigSubentryFlow` is a recent HA API (≥ 2024.11). On older HA we fall
# back to `ConfigFlow` so the package still imports — subentries won't be
# operational on those versions but the integration still loads. At
# type-check time we pretend the base is always `ConfigFlow` so mypy
# strict can resolve the inherited signatures.
if TYPE_CHECKING:
    _SubentryBase = config_entries.ConfigFlow
else:
    _SubentryBase = getattr(
        config_entries, "ConfigSubentryFlow", config_entries.ConfigFlow
    )

_LOGGER = logging.getLogger(__name__)


def _categories(
    config_entry: config_entries.ConfigEntry | None,
) -> list[tuple[str, str]]:
    """Pull (category_id, display_label) tuples from the parent entry."""
    from .. import iter_subentries

    out: list[tuple[str, str]] = []
    for sub in iter_subentries(config_entry):
        if getattr(sub, "subentry_type", None) != "category":
            continue
        data = getattr(sub, "data", {}) or {}
        cid = data.get("category_id") or data.get("id")
        if not cid:
            continue
        label = (
            data.get("label") or getattr(sub, "title", None) or str(cid)
        )
        out.append((str(cid), str(label)))
    return out


class FieldSubentryFlow(_SubentryBase):
    """7-step field add/edit flow."""

    def __init__(self) -> None:
        """Build an empty draft; ``async_step_user`` populates it."""
        self._draft: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1 — identity (entity_id + provider_type)."""
        if user_input is not None:
            self._draft.update(user_input)
            return await self.async_step_provider_params()
        return self.async_show_form(
            step_id="user", data_schema=identity_schema(self._draft)
        )

    async def async_step_provider_params(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2 — provider-specific params."""
        if user_input is not None:
            self._draft["provider_config"] = user_input
            return await self.async_step_display()
        return self.async_show_form(
            step_id="provider_params",
            data_schema=provider_params_schema(
                str(self._draft.get("provider_type", "")), self._draft
            ),
        )

    async def async_step_display(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3 — label / icon / category / unit / direction_preference."""
        categories = _categories(self._get_entry())
        if user_input is not None:
            self._draft.update(user_input)
            return await self.async_step_comparisons()
        return self.async_show_form(
            step_id="display",
            data_schema=display_schema(self._draft, categories),
        )

    async def async_step_comparisons(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 4 — comparisons (which + window_days + target)."""
        if user_input is not None:
            enabled = list(user_input.get("enabled_comparisons", []))
            window_days = int(user_input.get("rolling_window_days", 14))
            target = float(user_input.get("target_value", 0.0))
            specs: list[dict[str, Any]] = []
            for ctype in enabled:
                spec: dict[str, Any] = {"type": ctype}
                if ctype in {"rolling_avg", "rolling_min", "rolling_max", "trend"}:
                    spec["window_days"] = window_days
                if ctype == "target_value":
                    spec["target"] = target
                specs.append(spec)
            self._draft["comparisons"] = specs
            return await self.async_step_anomaly()
        return self.async_show_form(
            step_id="comparisons",
            data_schema=comparisons_schema(self._draft),
        )

    async def async_step_anomaly(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 5 — anomaly detection mode + params."""
        if user_input is not None:
            mode = str(user_input.get("mode", "none"))
            cfg: dict[str, Any] = {"mode": mode}
            if mode == "z_score":
                cfg["sigmas"] = float(user_input.get("sigmas", 2.0))
                cfg["window_days"] = int(user_input.get("window_days", 14))
            elif mode == "static_threshold":
                if user_input.get("min_value"):
                    cfg["min_value"] = float(user_input["min_value"])
                if user_input.get("max_value"):
                    cfg["max_value"] = float(user_input["max_value"])
            elif mode == "pct_change_vs_rolling_avg":
                cfg["pct"] = float(user_input.get("pct", 0.0))
                cfg["window_days"] = int(user_input.get("window_days", 14))
            cfg["severity"] = str(user_input.get("severity", "warning"))
            self._draft["anomaly_detection"] = cfg
            return await self.async_step_visibility()
        return self.async_show_form(
            step_id="anomaly", data_schema=anomaly_schema(self._draft)
        )

    async def async_step_visibility(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 6 — visible_in + weekly_aggregation + AI policy."""
        if user_input is not None:
            self._draft.update(user_input)
            return await self.async_step_gate()
        return self.async_show_form(
            step_id="visibility", data_schema=visibility_schema(self._draft)
        )

    async def async_step_gate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 7 — optional availability gate, then finalise."""
        if user_input is not None:
            gate_eid = str(user_input.get("gate_entity_id") or "")
            if gate_eid:
                self._draft["availability_gate"] = {
                    "entity_id": gate_eid,
                    "expected_state": str(user_input.get("gate_expected_state", "off")),
                }
            else:
                self._draft["availability_gate"] = None
            # Normalise the field_id from the label.
            if "field_id" not in self._draft:
                label = str(self._draft.get("label", "field"))
                self._draft["field_id"] = (
                    label.lower().replace(" ", "_") or "field"
                )
            return self.async_create_entry(
                title=str(self._draft.get("label", "Field")),
                data=self._draft,
            )
        return self.async_show_form(
            step_id="gate", data_schema=gate_schema(self._draft)
        )

    def _get_entry(self) -> config_entries.ConfigEntry | None:
        """Resolve the parent config entry for category lookups.

        HA exposes the parent entry through several attribute names
        across versions — try them all defensively. Returns None only on
        very old HA where SubentryFlow isn't even available.
        """
        # HA ≥ 2025.x: source_entry is set by the flow manager on add/edit
        entry = getattr(self, "source_entry", None)
        if entry is not None:
            return entry  # type: ignore[no-any-return]
        # Some versions expose it as config_entry (when not in reconfigure mode)
        entry = getattr(self, "config_entry", None)
        if entry is not None and not isinstance(entry, str):
            return entry  # type: ignore[no-any-return]
        # Fallback: derive from the flow context
        ctx = getattr(self, "context", {}) or {}
        entry_id = ctx.get("source_entry_id") or ctx.get("entry_id")
        hass = getattr(self, "hass", None)
        if entry_id and hass is not None:
            return hass.config_entries.async_get_entry(entry_id)  # type: ignore[no-any-return]
        return None

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Entry point when the user clicks "Reconfigure" on a field subentry.

        Pre-populate the draft from the existing subentry's data so the
        7-step flow restarts with all the user's prior values as defaults.
        """
        try:
            subentry = self._get_reconfigure_subentry()  # type: ignore[attr-defined]
        except AttributeError:
            subentry = None
        if subentry is not None:
            self._draft = dict(getattr(subentry, "data", {}) or {})
        return await self.async_step_user(user_input)


# Silence unused-import for json (reserved for future state_mapping parsing).
_ = json
