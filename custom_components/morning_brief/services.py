"""Service handlers for the morning_brief integration (Section 18.2)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse

from .const import DOMAIN
from .exceptions import MorningBriefError

_LOGGER = logging.getLogger(__name__)

SERVICE_GENERATE = "generate"
SERVICE_PREVIEW = "preview"
SERVICE_ADVANCE_DAY = "advance_day"
SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_TEST_AI_PROVIDER = "test_ai_provider"
SERVICE_GET_LAST_BRIEF = "get_last_brief"
SERVICE_GET_BRIEF_BY_UUID = "get_brief_by_uuid"
SERVICE_REORDER_FIELDS = "reorder_fields"

_BASE_SCHEMA = vol.Schema({vol.Required("instance_id"): str}, extra=vol.REMOVE_EXTRA)


def _coordinator_for(hass: HomeAssistant, instance_id: str) -> Any:
    """Locate the coordinator for ``instance_id`` or raise."""
    coordinators = hass.data.get(DOMAIN, {})
    coord = coordinators.get(instance_id)
    if coord is None:
        raise MorningBriefError(f"No morning_brief instance with id={instance_id}")
    return coord


async def _handle_generate(call: ServiceCall) -> ServiceResponse:
    coord = _coordinator_for(call.hass, call.data["instance_id"])
    canonical = await coord.async_generate_brief(force=bool(call.data.get("force", False)))
    return {"canonical_json": canonical} if call.return_response else None


async def _handle_preview(call: ServiceCall) -> ServiceResponse:
    coord = _coordinator_for(call.hass, call.data["instance_id"])
    canonical = await coord.async_preview_brief()
    return {"canonical_json": canonical} if call.return_response else None


async def _handle_advance_day(call: ServiceCall) -> ServiceResponse:
    coord = _coordinator_for(call.hass, call.data["instance_id"])
    strategy = coord.logical_day_strategy
    advance = getattr(strategy, "advance_day", None)
    if advance is None:
        raise MorningBriefError(
            "Active strategy doesn't support advance_day (only `manual` does)"
        )
    from homeassistant.util import dt as dt_util  # noqa: PLC0415 — local to avoid setup cost

    new_date = advance(dt_util.now().date())
    return {"logical_date": new_date.isoformat()} if call.return_response else None


async def _handle_clear_history(call: ServiceCall) -> ServiceResponse:
    coord = _coordinator_for(call.hass, call.data["instance_id"])
    await coord.store.clear()
    return None


async def _handle_test_ai_provider(call: ServiceCall) -> ServiceResponse:
    coord = _coordinator_for(call.hass, call.data["instance_id"])
    provider = coord.ai_provider
    if provider is None:
        return {"ok": False, "reason": "no_ai_provider"} if call.return_response else None
    ok = await provider.validate_credentials()
    return {"ok": bool(ok)} if call.return_response else None


async def _handle_get_last_brief(call: ServiceCall) -> ServiceResponse:
    coord = _coordinator_for(call.hass, call.data["instance_id"])
    latest = await coord.store.get_latest()
    return {"brief": latest} if call.return_response else None


async def _handle_get_brief_by_uuid(call: ServiceCall) -> ServiceResponse:
    coord = _coordinator_for(call.hass, call.data["instance_id"])
    brief = await coord.store.get_brief(str(call.data["uuid"]))
    return {"brief": brief} if call.return_response else None


async def _handle_reorder_fields(call: ServiceCall) -> ServiceResponse:
    coord = _coordinator_for(call.hass, call.data["instance_id"])
    ordered_ids = list(call.data.get("ordered_field_ids", []) or [])
    # The actual subentry-write happens once HA exposes the subentry update API
    # we want; for now we mutate the coordinator's in-memory `fields` list so
    # the next brief reflects the new order.
    by_id = {f.get("field_id"): f for f in coord.fields}
    new_order: list[dict[str, Any]] = []
    for i, fid in enumerate(ordered_ids):
        f = by_id.get(fid)
        if f is None:
            continue
        f = dict(f)
        f["order"] = (i + 1) * 10
        new_order.append(f)
    # Append any field not listed at the end, preserving relative order.
    listed = set(ordered_ids)
    tail = [f for f in coord.fields if f.get("field_id") not in listed]
    coord.fields = new_order + tail
    return None


_SERVICES: dict[str, tuple[Any, vol.Schema, SupportsResponse]] = {
    SERVICE_GENERATE: (
        _handle_generate,
        _BASE_SCHEMA.extend({vol.Optional("force", default=False): bool}),
        SupportsResponse.OPTIONAL,
    ),
    SERVICE_PREVIEW: (
        _handle_preview,
        _BASE_SCHEMA,
        SupportsResponse.ONLY,
    ),
    SERVICE_ADVANCE_DAY: (
        _handle_advance_day,
        _BASE_SCHEMA,
        SupportsResponse.OPTIONAL,
    ),
    SERVICE_CLEAR_HISTORY: (_handle_clear_history, _BASE_SCHEMA, SupportsResponse.NONE),
    SERVICE_TEST_AI_PROVIDER: (
        _handle_test_ai_provider,
        _BASE_SCHEMA,
        SupportsResponse.ONLY,
    ),
    SERVICE_GET_LAST_BRIEF: (
        _handle_get_last_brief,
        _BASE_SCHEMA,
        SupportsResponse.ONLY,
    ),
    SERVICE_GET_BRIEF_BY_UUID: (
        _handle_get_brief_by_uuid,
        _BASE_SCHEMA.extend({vol.Required("uuid"): str}),
        SupportsResponse.ONLY,
    ),
    SERVICE_REORDER_FIELDS: (
        _handle_reorder_fields,
        _BASE_SCHEMA.extend({vol.Required("ordered_field_ids"): [str]}),
        SupportsResponse.NONE,
    ),
}


def async_register_services(hass: HomeAssistant) -> None:
    """Register every morning_brief.* service. Idempotent across entries."""
    for name, (handler, schema, supports) in _SERVICES.items():
        if hass.services.has_service(DOMAIN, name):
            continue
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=supports
        )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove every morning_brief.* service (no-op if not last entry)."""
    # Only remove when the integration is unloaded entirely.
    if hass.data.get(DOMAIN):
        return
    for name in _SERVICES:
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)
