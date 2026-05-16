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
        """Step 1a — entity only (the sensor that backs this field).

        After this step we know the entity, so step 1b
        (``provider_pick``) can offer only the provider types that
        match the entity's profile and highlight the recommended one.
        """
        import voluptuous as vol
        from homeassistant.helpers import selector

        if user_input is not None:
            self._draft["entity_id"] = user_input["entity_id"]
            return await self.async_step_provider_pick()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "entity_id", default=self._draft.get("entity_id", "")
                    ): selector.EntitySelector(selector.EntitySelectorConfig()),
                }
            ),
        )

    async def async_step_provider_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1b — provider_type, filtered to types compatible with the entity.

        Per user spec: "First ask for the sensor, then show all the
        compatible types with a recommendation text". The list is
        narrowed by ``_compatible_provider_types`` (based on the
        entity's state_class / device_class / domain) and the heuristic
        recommendation is shown in the description.
        """
        import voluptuous as vol
        from homeassistant.helpers import selector

        if user_input is not None:
            self._draft["provider_type"] = user_input["provider_type"]
            return await self.async_step_provider_params()
        entity_id = str(self._draft.get("entity_id", ""))
        compatible = _compatible_provider_types(self.hass, entity_id)
        recommended = _recommend_provider_type(self.hass, entity_id)
        rec_msg = (
            f"💡 **Recommandé pour `{entity_id}` : {recommended}**"
            if recommended and recommended in compatible
            else f"_Aucune recommandation automatique pour `{entity_id}`._"
        )
        default = (
            self._draft.get("provider_type")
            or recommended
            or (compatible[0] if compatible else "instantaneous")
        )
        return self.async_show_form(
            step_id="provider_pick",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "provider_type", default=default
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=compatible,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="provider_type",
                        )
                    ),
                }
            ),
            description_placeholders={"recommendation": rec_msg},
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
        """Step 7 — optional availability gate, then applicable_to."""
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
            return await self.async_step_applicable_to()
        return self.async_show_form(
            step_id="gate", data_schema=gate_schema(self._draft)
        )

    async def async_step_applicable_to(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 8 — pick which morning_brief instances this field applies to.

        Empty selection = visible in EVERY instance (default for users
        who don't know what to pick). Otherwise the field shows up only
        in the picked instances.
        """
        import voluptuous as vol
        from homeassistant.helpers import selector

        from ...const import DOMAIN

        if user_input is not None:
            applicable = list(user_input.get("applicable_to") or [])
            self._draft["_pool_applicable_to"] = applicable
            return await self._finalise_with_pool()
        entries = self._hass_entries(DOMAIN)
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
                        "applicable_to",
                        default=self._draft.get("_pool_applicable_to", []),
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

    def _hass_entries(self, domain: str) -> list[Any]:
        hass = getattr(self, "hass", None)
        if hass is None:
            return []
        return list(hass.config_entries.async_entries(domain))

    async def _finalise_with_pool(self) -> ConfigFlowResult:
        """Write the field into the shared pool then close the flow."""
        from ...pool import async_get_pool

        applicable = list(self._draft.pop("_pool_applicable_to", []) or [])
        pool = async_get_pool(self.hass)
        if not pool._loaded:  # noqa: SLF001
            await pool.async_load()
        # Reconfigure: try to find an existing pool item that points at
        # the subentry being edited and update it instead of duplicating.
        existing_id: str | None = None
        try:
            subentry = self._get_reconfigure_subentry()  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            # AttributeError: HA < 2024.11 doesn't expose the method.
            # ValueError: HA raises "Source is user, expected reconfigure"
            # when we're in a create flow (not reconfigure) — we just
            # treat that as "no subentry being reconfigured" silently.
            subentry = None
        if subentry is not None:
            src_sid = getattr(subentry, "subentry_id", None)
            for item in pool.list_fields():
                if item.get("data", {}).get("_migrated_subentry_id") == str(src_sid):
                    existing_id = str(item.get("id"))
                    break
        if existing_id is not None:
            await pool.async_update_field(
                existing_id, data=dict(self._draft), applicable_to=applicable
            )
        else:
            await pool.async_add_field(
                dict(self._draft), applicable_to=applicable
            )
        # Also call the legacy HA subentry create/update so HA UI stays
        # in sync. The on-startup migration deduplicates via the
        # _migrated_subentry_id flag on the pool item.
        return self._finalise()

    def _finalise(self) -> ConfigFlowResult:
        """Persist the draft.

        Source ``user`` → create a brand new subentry via
        ``async_create_entry``.
        Source ``reconfigure`` → update the existing subentry via
        ``async_update_and_abort`` (HA raises ValueError on
        ``async_create_entry`` when called from a reconfigure source).
        """
        title = str(self._draft.get("label", "Field"))
        source = getattr(self, "source", None)
        if source == "reconfigure":
            update_and_abort = getattr(self, "async_update_and_abort", None)
            if update_and_abort is not None:
                try:
                    subentry = self._get_reconfigure_subentry()  # type: ignore[attr-defined]
                except (AttributeError, ValueError):
                    subentry = None
                if subentry is not None:
                    return update_and_abort(  # type: ignore[no-any-return]
                        entry=self._get_entry(),
                        subentry=subentry,
                        data=self._draft,
                        title=title,
                    )
            # Fallback: abort the flow without updating — user can retry.
            return self.async_abort(reason="reconfigure_unsupported")
        return self.async_create_entry(title=title, data=self._draft)

    def _get_entry(self) -> config_entries.ConfigEntry | None:
        """Resolve the parent config entry for category lookups.

        HA exposes the parent entry through several attribute names
        across versions — try them all defensively. As a last resort,
        return any morning_brief entry (single-instance is the common
        case; for multi-instance the slight cross-pollution is better
        than an empty dropdown).
        """
        # HA ≥ 2025.x: source_entry is set by the flow manager on add/edit
        entry = getattr(self, "source_entry", None)
        if entry is not None:
            return entry  # type: ignore[no-any-return]
        # Some versions expose it as config_entry (when not in reconfigure mode)
        entry = getattr(self, "config_entry", None)
        if entry is not None and not isinstance(entry, str):
            return entry  # type: ignore[no-any-return]
        hass = getattr(self, "hass", None)
        if hass is None:
            return None
        # Fallback: derive from the flow context
        ctx = getattr(self, "context", {}) or {}
        entry_id = ctx.get("source_entry_id") or ctx.get("entry_id")
        if entry_id:
            via_ctx = hass.config_entries.async_get_entry(entry_id)
            if via_ctx is not None:
                return via_ctx  # type: ignore[no-any-return]
        # Last-ditch fallback: any morning_brief entry. Single-instance
        # users see the right list; multi-instance users see the union
        # which is better than empty.
        from ...const import DOMAIN

        entries = list(hass.config_entries.async_entries(DOMAIN))
        if entries:
            return entries[0]  # type: ignore[no-any-return]
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
        except (AttributeError, ValueError):
            # AttributeError: HA < 2024.11 doesn't expose the method.
            # ValueError: HA raises "Source is user, expected reconfigure"
            # when we're in a create flow (not reconfigure) — we just
            # treat that as "no subentry being reconfigured" silently.
            subentry = None
        if subentry is not None:
            self._draft = dict(getattr(subentry, "data", {}) or {})
        return await self.async_step_user(user_input)


_ALL_PROVIDER_TYPES = [
    "cumulative",
    "instantaneous",
    "event_based",
    "state",
    "duration",
    "calendar",
    "weather",
    "manual",
]


def _compatible_provider_types(hass: Any, entity_id: str) -> list[str]:
    """Return the subset of provider types compatible with the picked entity.

    Heuristic — we err on the side of *including too many* options
    rather than excluding ones that may legitimately apply. The user
    saw "instantaneous" and "manual" only for a sleep-total sensor in
    rc.9 and complained that "cumulative" was clearly missing.
    """
    if not entity_id:
        return list(_ALL_PROVIDER_TYPES)
    state = hass.states.get(entity_id) if hasattr(hass, "states") else None
    if state is None:
        # Entity unknown or unavailable — offer everything sensible.
        return list(_ALL_PROVIDER_TYPES)
    domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
    attrs = state.attributes or {}
    sc = attrs.get("state_class")
    dc = attrs.get("device_class")
    if domain == "weather":
        return ["weather"]
    if domain == "calendar":
        return ["calendar"]
    if domain == "binary_sensor":
        return ["state"]
    if domain == "input_number":
        return ["manual", "instantaneous", "cumulative", "event_based"]
    if domain == "input_text":
        return ["manual", "state"]
    if domain == "input_datetime":
        return ["manual", "duration"]
    # Sensor domain (or other numeric-ish domains)
    if dc in ("timestamp", "date"):
        return ["duration", "manual"]
    try:
        float(state.state)
        # Numeric current value: offer all numeric-friendly providers.
        # state_class hint biases the order (recommended first) but
        # never restricts.
        if sc in ("total_increasing", "total"):
            return ["cumulative", "instantaneous", "event_based", "manual"]
        return ["instantaneous", "cumulative", "event_based", "manual"]
    except (TypeError, ValueError):
        # Non-numeric state (or unavailable) — still allow manual as a
        # fallback in case the user wants to override the source.
        return ["state", "duration", "manual"]


def _recommend_provider_type(hass: Any, entity_id: str) -> str | None:
    """Heuristic recommendation of provider_type for the picked entity.

    Looks at the entity's current state, state_class, device_class, and
    domain to suggest the most likely provider. Returns None if the
    entity is unknown (state object missing).

    Order of decisions:
    1. Domain-based shortcuts (weather / calendar / input_* / binary_sensor).
    2. state_class + device_class combos (cumulative for energy/water counters).
    3. Numeric vs non-numeric current state (instantaneous vs state).
    """
    # NEVER return None — always pick a safe fallback so the UI shows
    # *some* recommendation instead of "Aucune recommandation".
    if not entity_id:
        return "instantaneous"
    state = hass.states.get(entity_id) if hasattr(hass, "states") else None
    if state is None:
        return "instantaneous"
    domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
    attrs = state.attributes or {}
    state_class = attrs.get("state_class")
    device_class = attrs.get("device_class")
    if domain == "weather":
        return "weather"
    if domain == "calendar":
        return "calendar"
    if domain in ("input_number", "input_text", "input_datetime"):
        return "manual"
    if domain == "binary_sensor":
        return "state"
    if state_class in ("total_increasing", "total") and device_class in (
        "energy",
        "water",
        "gas",
        "monetary",
    ):
        return "cumulative"
    if state_class in ("total_increasing", "total"):
        # Numeric total (sleep minutes, steps, accumulated value) with
        # no specific device_class — still likely a daily counter.
        return "cumulative"
    if state_class == "measurement":
        return "instantaneous"
    # No state_class — branch on whether the current value is numeric.
    try:
        float(state.state)
        # Numeric without state_class: most often it's an instant
        # reading (temperature, weight, HR). event_based is the runner-up.
        return "instantaneous"
    except (TypeError, ValueError):
        return "state"


# Silence unused-import for json (reserved for future state_mapping parsing).
_ = json
