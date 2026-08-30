"""Text platform for the GHL integration."""

from __future__ import annotations

from homeassistant.components.text import (
    TextEntity,
    TextMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACCESS_MODE_FULL_ACCESS,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    DESCRIPTION_TEXT_MAX_LENGTH,
    DEVICE_TYPE_PROFILUX_4,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GHL text entities from a config entry."""

    if entry.data[CONF_ACCESS_MODE] != ACCESS_MODE_FULL_ACCESS:
        return

    if entry.data[CONF_DEVICE_TYPE] != DEVICE_TYPE_PROFILUX_4:
        return

    entry_data = hass.data[DOMAIN][entry.entry_id]

    description_editor = entry_data[
        "description_editor"
    ]

    if not description_editor["resource_order"]:
        return

    async_add_entities(
        [
            GHLDescriptionText(
                entry=entry,
                description_editor=description_editor,
            )
        ]
    )


class GHLDescriptionText(TextEntity):
    """Edit the selected GHL resource description."""

    _attr_has_entity_name = True
    _attr_translation_key = "description_text"
    _attr_native_min = 0
    _attr_native_max = DESCRIPTION_TEXT_MAX_LENGTH
    _attr_mode = TextMode.TEXT

    def __init__(
        self,
        entry: ConfigEntry,
        description_editor: dict,
    ) -> None:
        """Initialize the GHL description text entity."""

        self._entry = entry
        self._description_editor = description_editor

        self._attr_unique_id = (
            f"{entry.entry_id}_description_text"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    async def async_added_to_hass(self) -> None:
        """Register this text entity with the shared editor data."""

        await super().async_added_to_hass()

        self._description_editor[
            "text_entity"
        ] = self

    @property
    def native_value(self) -> str:
        """Return the currently entered description."""

        return self._description_editor[
            "text"
        ]

    async def async_set_value(
        self,
        value: str,
    ) -> None:
        """Set the description to write."""

        self._description_editor[
            "text"
        ] = value

        self.async_write_ha_state()