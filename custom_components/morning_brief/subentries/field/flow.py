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
from typing import Any

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
# operational on those versions but the integration still loads.
_SubentryBase: type = getattr(
    config_entries, "ConfigSubentryFlow", config_entries.ConfigFlow
)

_LOGGER = logging.getLogger(__name__)


def _category_ids(config_entry: config_entries.ConfigEntry) -> list[str]:
    """Pull category ids from the parent entry's category subentries."""
    subentries = getattr(config_entry, "subentries", {}) or {}
    items = subentries.values() if isinstance(subentries, dict) else subentries
    out: list[str] = []
    for sub in items:
        if getattr(sub, "subentry_type", None) != "category":
            continue
        data = getattr(sub, "data", {}) or {}
        cid = data.get("category_id") or data.get("id")
        if cid:
            out.append(str(cid))
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
        category_ids = _category_ids(self._get_entry())
        if user_input is not None:
            self._draft.update(user_input)
            return await self.async_step_comparisons()
        return self.async_show_form(
            step_id="display",
            data_schema=display_schema(self._draft, category_ids),
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

    def _get_entry(self) -> config_entries.ConfigEntry:
        """Resolve the parent config entry for category lookups."""
        # ConfigSubentryFlow exposes `config_entry` on newer HA versions.
        entry = getattr(self, "config_entry", None)
        if entry is None:
            entry = getattr(self, "source_entry", None)
        return entry  # type: ignore[return-value]


# Silence unused-import for json (reserved for future state_mapping parsing).
_ = json
