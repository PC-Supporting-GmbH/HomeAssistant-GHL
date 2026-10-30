"""Binary sensor platform for the GHL integration."""
# pyright: reportMissingImports=false

from __future__ import annotations

from .functions import device_info

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_GHL_DEVICE,
    ATTR_GHL_FEATURE_TYPE,
    ATTR_GHL_RESOURCE_TYPE,
    DOMAIN,
)
from .coordinator import (
    GHLDescriptionNameMixin,
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
    GHLDescriptionNameMixin,
    CoordinatorEntity[GHLDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Representation of a GHL switch channel state."""

    _attr_extra_state_attributes = {
        ATTR_GHL_RESOURCE_TYPE: "switch_channel",
        ATTR_GHL_FEATURE_TYPE: "state",
    }

    _description_platform = 'binary_sensor'
    _description_name_keys = ('switchchannel', None)

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL switch channel."""

        self._attr_extra_state_attributes = {
            **self._attr_extra_state_attributes,
            ATTR_GHL_DEVICE: entry.title,
        }

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_switchchannel_"
            f"{resource.index}_actstate"
        )

        self._attr_device_info = device_info(entry)

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

    _attr_extra_state_attributes = {
        ATTR_GHL_RESOURCE_TYPE: "level_sensor",
        ATTR_GHL_FEATURE_TYPE: "state",
    }

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL level sensor."""

        self._attr_extra_state_attributes = {
            **self._attr_extra_state_attributes,
            ATTR_GHL_DEVICE: entry.title,
        }

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_levelsensor_"
            f"{resource.index}_actstate"
        )

        self._attr_device_info = device_info(entry)

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