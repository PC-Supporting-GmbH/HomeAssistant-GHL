"""Select platform for the GHL integration."""
# pyright: reportMissingImports=false

from __future__ import annotations

from .functions import device_info

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.translation import async_get_translations

from .const import (
    ACCESS_MODE_FULL_ACCESS,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_PROFILUX_4,
    DOMAIN,
)

DESCRIPTION_RESOURCE_TRANSLATION_KEYS = {
    "SENSOR": "description_resource_sensor",
    "SWITCHCHANNEL": "description_resource_switchchannel",
    "ILLUMINATION": "description_resource_illumination",
    "TIMER": "description_resource_timer",
    "DOSER": "description_resource_doser",
    "FLOWSENSOR": "description_resource_flowsensor",
    "LEVELSENSOR": "description_resource_levelsensor",
}

DESCRIPTION_RESOURCE_FALLBACKS = {
    "SENSOR": "Sensor {index}",
    "SWITCHCHANNEL": "Switch Channel {index}",
    "ILLUMINATION": "Illumination {index}",
    "TIMER": "Timer {index}",
    "DOSER": "Dosing Pump {index}",
    "FLOWSENSOR": "Flow Sensor {index}",
    "LEVELSENSOR": "Level Sensor {index}",
}



async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GHL select entities from a config entry."""

    if entry.data[CONF_ACCESS_MODE] != ACCESS_MODE_FULL_ACCESS:
        return

    if entry.data[CONF_DEVICE_TYPE] != DEVICE_TYPE_PROFILUX_4:
        return

    entry_data = hass.data[DOMAIN][entry.entry_id]

    description_editor = entry_data[
        "description_editor"
    ]

    translations = await async_get_translations(
        hass,
        hass.config.language,
        "entity",
        {DOMAIN},
    )

    entities: list[SelectEntity] = []

    if description_editor["resource_order"]:
        resource_templates = {}

        for resource_type, translation_key in (
            DESCRIPTION_RESOURCE_TRANSLATION_KEYS.items()
        ):
            full_translation_key = (
                f"component.{DOMAIN}."
                f"entity.select."
                f"{translation_key}.name"
            )

            resource_templates[resource_type] = (
                translations.get(
                    full_translation_key,
                    DESCRIPTION_RESOURCE_FALLBACKS[
                        resource_type
                    ],
                )
            )

        entities.append(
            GHLDescriptionResourceSelect(
                entry=entry,
                description_editor=description_editor,
                resource_templates=resource_templates,
            )
        )

    async_add_entities(entities)


class GHLDescriptionResourceSelect(SelectEntity):
    """Select a GHL resource whose description should be edited."""

    _attr_has_entity_name = True
    _attr_translation_key = "description_resource"

    def __init__(
        self,
        entry: ConfigEntry,
        description_editor: dict,
        resource_templates: dict[str, str],
    ) -> None:
        """Initialize the GHL description resource select."""

        self._entry = entry
        self._description_editor = description_editor
        self._resource_templates = resource_templates

        self._option_to_key: dict[str, str] = {}
        self._key_to_option: dict[str, str] = {}

        self._attr_unique_id = (
            f"{entry.entry_id}_description_resource"
        )

        self._attr_device_info = device_info(entry)

        self._rebuild_options()

    async def async_added_to_hass(self) -> None:
        """Register the select entity with the shared editor data."""

        await super().async_added_to_hass()

        self._description_editor[
            "select_entity"
        ] = self

    async def async_will_remove_from_hass(self) -> None:
        """Remove the select entity from the shared editor data."""

        if (
            self._description_editor.get(
                "select_entity"
            )
            is self
        ):
            self._description_editor.pop(
                "select_entity",
                None,
            )

        await super().async_will_remove_from_hass()

    def _rebuild_options(self) -> None:
        """Rebuild visible select options."""

        options: list[str] = []
        option_to_key: dict[str, str] = {}
        key_to_option: dict[str, str] = {}

        for resource_key in self._description_editor[
            "resource_order"
        ]:
            resource = self._description_editor[
                "resources"
            ][resource_key]

            template = self._resource_templates[
                resource.resource
            ]

            option = template.format(
                index=resource.index + 1,
            )

            if resource.description is not None:
                option = (
                    f"{option} - "
                    f"{resource.description}"
                )

            options.append(option)
            option_to_key[option] = resource_key
            key_to_option[resource_key] = option

        self._option_to_key = option_to_key
        self._key_to_option = key_to_option
        self._attr_options = options

    def refresh_resource_options(self) -> None:
        """Refresh visible resource labels."""

        self._rebuild_options()

        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the currently selected GHL resource."""

        selected_key = self._description_editor[
            "selected_key"
        ]

        if selected_key is None:
            return None

        return self._key_to_option.get(
            selected_key
        )

    async def async_select_option(
        self,
        option: str,
    ) -> None:
        """Select a GHL resource."""

        resource_key = self._option_to_key.get(option)

        if resource_key is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="description_resource_unavailable",
            )

        resource = self._description_editor["resources"].get(resource_key)

        if resource is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="description_resource_unavailable",
            )

        self._description_editor[
            "selected_key"
        ] = resource_key

        self._description_editor[
            "text"
        ] = (
            resource.description
            if resource.description is not None
            else ""
        )

        text_entity = self._description_editor.get(
            "text_entity"
        )

        if text_entity is not None:
            text_entity.async_write_ha_state()

        self.async_write_ha_state()


