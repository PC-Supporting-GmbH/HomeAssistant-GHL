"""Button platform for the GHL integration."""
# pyright: reportMissingImports=false

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GHLAPI, GHLAPIError, GHLCommandUncertainError
from .const import (
    ACCESS_MODE_FULL_ACCESS,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    CONF_KNOWN_SENSORS,
    DESCRIPTION_TEXT_MAX_LENGTH,
    DEVICE_TYPE_MITRAS_LX7,
    DEVICE_TYPE_MITRAS_LX8,
    DEVICE_TYPE_PROFILUX_4,
    DOMAIN,
)

from .functions import device_info, is_valid_description


_LOGGER = logging.getLogger(__name__)

FEEDPAUSE_COUNT = 4
MAINTENANCE_COUNT = 4
WATERCHANGE_COUNT = 4
LIGHTSCENE_COUNT = 8

THUNDERSTORM_DEFAULT_DURATION = 5
LIGHTSCENE_DEFAULT_FADETIME = 0

DESCRIPTION_UPDATE_PLATFORMS = {
    "SENSOR": [
        "sensor",
        "number",
    ],
    "SWITCHCHANNEL": [
        "sensor",
        "binary_sensor",
    ],
    "ILLUMINATION": [
        "sensor",
    ],
    "TIMER": [],
    "DOSER": [
        "sensor",
    ],
    "FLOWSENSOR": [
        "sensor",
    ],
    "LEVELSENSOR": [
        "binary_sensor",
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GHL button entities from a config entry."""

    _async_remove_obsolete_write_buttons(hass, entry)

    if entry.data[CONF_ACCESS_MODE] != ACCESS_MODE_FULL_ACCESS:
        return

    if entry.data[CONF_DEVICE_TYPE] not in (
        DEVICE_TYPE_PROFILUX_4,
        DEVICE_TYPE_MITRAS_LX7,
        DEVICE_TYPE_MITRAS_LX8,
    ):
        return

    entry_data = hass.data[DOMAIN][entry.entry_id]

    api: GHLAPI = entry_data["api"]

    thunderstorm_data = entry_data.setdefault(
        "thunderstorm",
        {
            "duration": THUNDERSTORM_DEFAULT_DURATION,
        },
    )

    lightscene_data = entry_data.setdefault(
        "lightscene",
        {
            "fadetime": LIGHTSCENE_DEFAULT_FADETIME,
        },
    )

    description_editor = entry_data[
        "description_editor"
    ]

    resources = entry_data[
        "resources"
    ]

    entities: list[ButtonEntity] = []

    if entry.data[CONF_DEVICE_TYPE] == DEVICE_TYPE_PROFILUX_4:
        for index in range(FEEDPAUSE_COUNT):
            entities.append(
                GHLFeedPauseButton(
                    api=api,
                    entry=entry,
                    index=index,
                    state=True,
                )
            )

            entities.append(
                GHLFeedPauseButton(
                    api=api,
                    entry=entry,
                    index=index,
                    state=False,
                )
            )

    for index in range(MAINTENANCE_COUNT):
        entities.append(
            GHLMaintenanceButton(
                api=api,
                entry=entry,
                index=index,
                state=True,
            )
        )

        entities.append(
            GHLMaintenanceButton(
                api=api,
                entry=entry,
                index=index,
                state=False,
            )
        )

    if entry.data[CONF_DEVICE_TYPE] == DEVICE_TYPE_PROFILUX_4:
        for index in range(WATERCHANGE_COUNT):
            entities.append(
                GHLWaterChangeButton(
                    api=api,
                    entry=entry,
                    index=index,
                    state=True,
                )
            )

            entities.append(
                GHLWaterChangeButton(
                    api=api,
                    entry=entry,
                    index=index,
                    state=False,
                )
            )

    entities.append(
        GHLThunderstormButton(
            api=api,
            entry=entry,
            thunderstorm_data=thunderstorm_data,
            state=True,
        )
    )

    entities.append(
        GHLThunderstormButton(
            api=api,
            entry=entry,
            thunderstorm_data=thunderstorm_data,
            state=False,
        )
    )

    for index in range(LIGHTSCENE_COUNT):
        entities.append(
            GHLLightSceneButton(
                api=api,
                entry=entry,
                lightscene_data=lightscene_data,
                index=index,
                state=True,
            )
        )

        entities.append(
            GHLLightSceneButton(
                api=api,
                entry=entry,
                lightscene_data=lightscene_data,
                index=index,
                state=False,
            )
        )

    if entry.data[CONF_DEVICE_TYPE] != DEVICE_TYPE_PROFILUX_4:
        async_add_entities(entities)
        return

    khdirector_exists = any(
        resource.resource == "KHDIRECTOR"
        for resource in resources
    )

    if khdirector_exists:
        for action in range(5):
            entities.append(
                GHLKHDirectorActionButton(
                    api=api,
                    entry=entry,
                    action=action,
                )
            )

    iondirector_exists = any(
        resource.resource == "IONDIRECTOR"
        for resource in resources
    )

    if iondirector_exists:
        for action in range(6):
            entities.append(
                GHLIONDirectorActionButton(
                    api=api,
                    entry=entry,
                    action=action,
                )
            )

    if description_editor["resource_order"]:
        entities.append(
            GHLDescriptionWriteButton(
                api=api,
                entry=entry,
                description_editor=description_editor,
            )
        )

    async_add_entities(entities)


def _async_remove_obsolete_write_buttons(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove the obsolete setpoint and master brightness write buttons."""

    registry = er.async_get(hass)

    for suffix in (
        "sensor_setpoint_write",
        "illumination_masterbrightness_write",
    ):
        entity_id = registry.async_get_entity_id(
            "button",
            DOMAIN,
            f"{entry.entry_id}_{suffix}",
        )
        if entity_id is not None:
            registry.async_remove(entity_id)


class GHLFeedPauseButton(ButtonEntity):
    """Representation of a GHL feed pause action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: GHLAPI,
        entry: ConfigEntry,
        index: int,
        state: bool,
    ) -> None:
        """Initialize the GHL feed pause button."""

        self._api = api
        self._entry = entry
        self._index = index
        self._state = state

        action = "start" if state else "stop"

        self._attr_unique_id = (
            f"{entry.entry_id}_specialfunction_"
            f"feedpause_{index}_{action}"
        )

        self._attr_device_info = device_info(entry)

        if state:
            self._attr_translation_key = "feedpause_start"

        else:
            self._attr_translation_key = "feedpause_stop"

        self._attr_translation_placeholders = {
            "index": str(index + 1),
        }

    async def async_press(self) -> None:
        """Execute the GHL feed pause action."""

        state_value = 1 if self._state else 0

        command = (
            f"SET SPECIALFUNCTION "
            f"FEEDPAUSE[{self._index}] {state_value}"
        )

        try:
            reply = await self._api.async_command(
                command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL feed pause %d "
                "command %s: %s",
                self._index + 1,
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL feed pause %d command %s "
                "returned unexpected response: %s",
                self._index + 1,
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )


class GHLMaintenanceButton(ButtonEntity):
    """Representation of a GHL maintenance action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: GHLAPI,
        entry: ConfigEntry,
        index: int,
        state: bool,
    ) -> None:
        """Initialize the GHL maintenance button."""

        self._api = api
        self._entry = entry
        self._index = index
        self._state = state

        action = "start" if state else "stop"

        self._attr_unique_id = (
            f"{entry.entry_id}_specialfunction_"
            f"maintenance_{index}_{action}"
        )

        self._attr_device_info = device_info(entry)

        if state:
            self._attr_translation_key = "maintenance_start"

        else:
            self._attr_translation_key = "maintenance_stop"

        self._attr_translation_placeholders = {
            "index": str(index + 1),
        }

    async def async_press(self) -> None:
        """Execute the GHL maintenance action."""

        state_value = 1 if self._state else 0

        command = (
            f"SET SPECIALFUNCTION "
            f"MAINTENANCE[{self._index}] {state_value}"
        )

        try:
            reply = await self._api.async_command(
                command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL maintenance %d "
                "command %s: %s",
                self._index + 1,
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL maintenance %d command %s "
                "returned unexpected response: %s",
                self._index + 1,
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )


class GHLWaterChangeButton(ButtonEntity):
    """Representation of a GHL water change action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: GHLAPI,
        entry: ConfigEntry,
        index: int,
        state: bool,
    ) -> None:
        """Initialize the GHL water change button."""

        self._api = api
        self._entry = entry
        self._index = index
        self._state = state

        action = "start" if state else "stop"

        self._attr_unique_id = (
            f"{entry.entry_id}_specialfunction_"
            f"waterchange_{index}_{action}"
        )

        self._attr_device_info = device_info(entry)

        if state:
            self._attr_translation_key = "waterchange_start"

        else:
            self._attr_translation_key = "waterchange_stop"

        self._attr_translation_placeholders = {
            "index": str(index + 1),
        }

    async def async_press(self) -> None:
        """Execute the GHL water change action."""

        state_value = 1 if self._state else 0

        command = (
            f"SET SPECIALFUNCTION "
            f"WATERCHANGE[{self._index}] {state_value}"
        )

        try:
            reply = await self._api.async_command(
                command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL water change %d "
                "command %s: %s",
                self._index + 1,
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL water change %d command %s "
                "returned unexpected response: %s",
                self._index + 1,
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )


class GHLThunderstormButton(ButtonEntity):
    """Representation of a GHL thunderstorm action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: GHLAPI,
        entry: ConfigEntry,
        thunderstorm_data: dict,
        state: bool,
    ) -> None:
        """Initialize the GHL thunderstorm button."""

        self._api = api
        self._entry = entry
        self._thunderstorm_data = thunderstorm_data
        self._state = state

        action = "start" if state else "stop"

        self._attr_unique_id = (
            f"{entry.entry_id}_specialfunction_"
            f"thunderstorm_{action}"
        )

        self._attr_device_info = device_info(entry)

        if state:
            self._attr_translation_key = "thunderstorm_start"

        else:
            self._attr_translation_key = "thunderstorm_stop"

    async def async_press(self) -> None:
        """Execute the GHL thunderstorm action."""

        if self._state:
            duration = int(
                self._thunderstorm_data["duration"]
            )

        else:
            duration = 0

        command = (
            f"SET SPECIALFUNCTION "
            f"THUNDERSTORM {duration}"
        )

        try:
            reply = await self._api.async_command(
                command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL thunderstorm "
                "command %s: %s",
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL thunderstorm command %s "
                "returned unexpected response: %s",
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )


class GHLLightSceneButton(ButtonEntity):
    """Representation of a GHL light scene action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: GHLAPI,
        entry: ConfigEntry,
        lightscene_data: dict,
        index: int,
        state: bool,
    ) -> None:
        """Initialize the GHL light scene button."""

        self._api = api
        self._entry = entry
        self._lightscene_data = lightscene_data
        self._index = index
        self._state = state

        action = "start" if state else "stop"

        self._attr_unique_id = (
            f"{entry.entry_id}_specialfunction_"
            f"lightscene_{index}_{action}"
        )

        self._attr_device_info = device_info(entry)

        if state:
            self._attr_translation_key = "lightscene_start"

        else:
            self._attr_translation_key = "lightscene_stop"

        self._attr_translation_placeholders = {
            "index": str(index + 1),
        }

    async def async_press(self) -> None:
        """Execute the GHL light scene action."""

        state_value = 1 if self._state else 0

        fadetime = int(
            self._lightscene_data["fadetime"]
        )

        command = (
            f"SET SPECIALFUNCTION "
            f"LIGHTSCENE[{self._index}] "
            f"{state_value}, {fadetime}"
        )

        try:
            reply = await self._api.async_command(
                command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL light scene %d "
                "command %s: %s",
                self._index + 1,
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL light scene %d command %s "
                "returned unexpected response: %s",
                self._index + 1,
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )


class GHLKHDirectorActionButton(ButtonEntity):
    """Representation of a GHL KH Director action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: GHLAPI,
        entry: ConfigEntry,
        action: int,
    ) -> None:
        """Initialize the GHL KH Director action button."""

        self._api = api
        self._entry = entry
        self._action = action

        translation_keys = {
            0: "khdirector_action_stop",
            1: "khdirector_action_measurement",
            2: "khdirector_action_vent_reagent",
            3: "khdirector_action_flush_cell",
            4: "khdirector_action_empty_cell",
        }

        self._attr_translation_key = translation_keys[
            action
        ]

        self._attr_unique_id = (
            f"{entry.entry_id}_khdirector_"
            f"startaction_{action}"
        )

        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        """Execute the GHL KH Director action."""

        command = (
            f"SET KHDIRECTOR "
            f"STARTACTION {self._action}"
        )

        try:
            reply = await self._api.async_command(
                command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL KH Director "
                "action %d command %s: %s",
                self._action,
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL KH Director action %d command %s "
                "returned unexpected response: %s",
                self._action,
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )


class GHLIONDirectorActionButton(ButtonEntity):
    """Representation of a GHL ION Director action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: GHLAPI,
        entry: ConfigEntry,
        action: int,
    ) -> None:
        """Initialize the GHL ION Director action button."""

        self._api = api
        self._entry = entry
        self._action = action

        translation_keys = {
            0: "iondirector_action_stop",
            1: "iondirector_action_measurement",
            2: "iondirector_action_prepare_cell",
            3: "iondirector_action_empty_cell",
            4: "iondirector_action_sensor_test",
            5: "iondirector_action_prime_cell",
        }

        self._attr_translation_key = translation_keys[
            action
        ]

        self._attr_unique_id = (
            f"{entry.entry_id}_iondirector_"
            f"startaction_{action}"
        )

        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        """Execute the GHL ION Director action."""

        command = (
            f"SET IONDIRECTOR[0] "
            f"STARTACTION {self._action}"
        )

        try:
            reply = await self._api.async_command(
                command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL ION Director "
                "action %d command %s: %s",
                self._action,
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL ION Director action %d command %s "
                "returned unexpected response: %s",
                self._action,
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )


class GHLDescriptionWriteButton(ButtonEntity):
    """Representation of the GHL description write action."""

    _attr_has_entity_name = True
    _attr_translation_key = "description_write"

    def __init__(
        self,
        api: GHLAPI,
        entry: ConfigEntry,
        description_editor: dict,
    ) -> None:
        """Initialize the GHL description write button."""

        self._api = api
        self._entry = entry
        self._description_editor = description_editor

        self._attr_unique_id = (
            f"{entry.entry_id}_description_write"
        )

        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        """Write the selected GHL resource description."""

        selected_key = self._description_editor[
            "selected_key"
        ]

        if selected_key is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="description_selection_required",
            )

        resource = self._description_editor["resources"].get(selected_key)

        if resource is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="description_resource_unavailable",
            )

        description = self._description_editor[
            "text"
        ]

        if not is_valid_description(description):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_description",
            )

        padded_description = description.ljust(
            DESCRIPTION_TEXT_MAX_LENGTH
        )

        command = (
            f'SET {resource.resource}'
            f'[{resource.index}] '
            f'DESCRIPTION "{padded_description}"'
        )

        try:
            reply = await self._api.async_command(
                command,
                retry_safe=True,
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL description "
                "command %s: %s",
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if reply.replace(" ", "").startswith("NACK(-105)"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="write_access_denied",
            )

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL description command %s "
                "returned unexpected response: %s",
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )

        await self._api.async_close()

        resource.description = (
            description
            if description != ""
            else None
        )

        if resource.resource == "SENSOR":
            known_sensors = {
                key: dict(value)
                for key, value in self._entry.data.get(
                    CONF_KNOWN_SENSORS,
                    {},
                ).items()
            }

            sensor_key = str(
                resource.index
            )

            sensor_data = dict(
                known_sensors.get(
                    sensor_key,
                    {},
                )
            )

            sensor_data["description"] = (
                resource.description
            )

            if "features" not in sensor_data:
                sensor_data["features"] = dict(
                    resource.features
                )

            known_sensors[sensor_key] = sensor_data

            new_data = dict(
                self._entry.data
            )

            new_data[
                CONF_KNOWN_SENSORS
            ] = known_sensors

            self.hass.config_entries.async_update_entry(
                self._entry,
                data=new_data,
            )

        select_entity = self._description_editor.get(
            "select_entity"
        )

        if select_entity is not None:
            select_entity.refresh_resource_options()

        platforms = DESCRIPTION_UPDATE_PLATFORMS.get(
            resource.resource,
            [],
        )

        if not platforms:
            return

        unload_ok = await self.hass.config_entries.async_unload_platforms(
            self._entry,
            platforms,
        )

        if not unload_ok:
            _LOGGER.warning(
                "Unable to reload GHL platform(s) %s "
                "after changing description of %s[%d]",
                ", ".join(platforms),
                resource.resource,
                resource.index,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="description_display_update_failed",
            )

        await self.hass.config_entries.async_forward_entry_setups(
            self._entry,
            platforms,
        )
