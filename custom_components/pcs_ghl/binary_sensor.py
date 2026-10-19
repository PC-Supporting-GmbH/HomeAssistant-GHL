"""Binary sensor platform for the GHL integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    GHLDataUpdateCoordinator,
    levelsensor_state_key,
    switchchannel_state_key,
)
from .discovery import GHLDiscoveredResource


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GHL binary sensor entities from a config entry."""

    entry_data = hass.data[DOMAIN][entry.entry_id]

    coordinator: GHLDataUpdateCoordinator = entry_data[
        "coordinator"
    ]

    resources: list[GHLDiscoveredResource] = entry_data[
        "resources"
    ]

    entities: list[BinarySensorEntity] = []

    for resource in resources:
        if resource.resource == "SWITCHCHANNEL":
            if resource.index is None:
                continue

            entities.append(
                GHLSwitchChannelBinarySensor(
                    coordinator=coordinator,
                    entry=entry,
                    resource=resource,
                )
            )

            continue

        if resource.resource == "LEVELSENSOR":
            if resource.index is None:
                continue

            entities.append(
                GHLLevelSensorBinarySensor(
                    coordinator=coordinator,
                    entry=entry,
                    resource=resource,
                )
            )

    async_add_entities(entities)


class GHLSwitchChannelBinarySensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Representation of a GHL switch channel state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL switch channel."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_switchchannel_"
            f"{resource.index}_actstate"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        if resource.description is not None:
            self._attr_name = resource.description

        else:
            self._attr_translation_key = "switchchannel"
            self._attr_translation_placeholders = {
                "index": str(resource.index + 1),
            }

    @property
    def is_on(self) -> bool | None:
        """Return the current switch channel state."""

        return self.coordinator.data.get(
            switchchannel_state_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the switch channel is available."""

        key = switchchannel_state_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLLevelSensorBinarySensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Representation of a GHL level sensor state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL level sensor."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_levelsensor_"
            f"{resource.index}_actstate"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        self._attr_translation_key = "levelsensor"
        self._attr_translation_placeholders = {
            "index": str(resource.index + 1),
        }

    @property
    def is_on(self) -> bool | None:
        """Return the current level sensor state."""

        return self.coordinator.data.get(
            levelsensor_state_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the level sensor is available."""

        key = levelsensor_state_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )