"""Button entities for the morning_brief integration (Section 18.1).

Two buttons per instance:
- ``button.morning_brief_<slug>_generate`` — fires the generate service.
- ``button.morning_brief_<slug>_preview`` — fires the preview service.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MorningBriefCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for a morning_brief config entry."""
    coordinator: MorningBriefCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [MorningBriefGenerateButton(coordinator), MorningBriefPreviewButton(coordinator)]
    )


class _CoordinatorButton(CoordinatorEntity[MorningBriefCoordinator], ButtonEntity):
    """Shared base — both buttons read instance_name from the coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MorningBriefCoordinator, suffix: str) -> None:
        """Bind to the coordinator and label the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_button_{suffix}"


class MorningBriefGenerateButton(_CoordinatorButton):
    """Pressing this button generates a brief (forced — bypasses dedup)."""

    def __init__(self, coordinator: MorningBriefCoordinator) -> None:
        """Pass the suffix used in the unique id + display name."""
        super().__init__(coordinator, "generate")
        self._attr_name = f"{coordinator.instance_name or 'Morning Brief'} generate"

    async def async_press(self) -> None:
        """Generate a new brief on press."""
        await self.coordinator.async_generate_brief(force=True)


class MorningBriefPreviewButton(_CoordinatorButton):
    """Pressing this button runs a preview (no persist / no notify)."""

    def __init__(self, coordinator: MorningBriefCoordinator) -> None:
        """Pass the suffix used in the unique id + display name."""
        super().__init__(coordinator, "preview")
        self._attr_name = f"{coordinator.instance_name or 'Morning Brief'} preview"

    async def async_press(self) -> None:
        """Run a preview on press — the JSON isn't stored anywhere."""
        await self.coordinator.async_preview_brief()
