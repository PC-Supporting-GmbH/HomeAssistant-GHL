"""Button platform for the GHL integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GHLAPI, GHLAPIError
from .const import (
    ACCESS_MODE_FULL_ACCESS,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    CONF_KNOWN_SENSORS,
    DESCRIPTION_TEXT_MAX_LENGTH,
    DEVICE_TYPE_PROFILUX_4,
    DOMAIN,
)
from .coordinator import (
    GHLDataUpdateCoordinator,
    iondirector_desvalue_key,
    khdirector_desvalue_key,
    sensor_desvalue_key,
)

_LOGGER = logging.getLogger(__name__)

FEEDPAUSE_COUNT = 4
MAINTENANCE_COUNT = 4
LIGHTSCENE_COUNT = 8

THUNDERSTORM_DEFAULT_DURATION = 5
LIGHTSCENE_DEFAULT_FADETIME = 0

DESCRIPTION_UPDATE_PLATFORMS = {
    "SENSOR": [
        "sensor",
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

    if entry.data[CONF_ACCESS_MODE] != ACCESS_MODE_FULL_ACCESS:
        return

    if entry.data[CONF_DEVICE_TYPE] != DEVICE_TYPE_PROFILUX_4:
        return

    entry_data = hass.data[DOMAIN][entry.entry_id]

    api: GHLAPI = entry_data["api"]

    coordinator: GHLDataUpdateCoordinator = entry_data[
        "coordinator"
    ]

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

    sensor_setpoint_editor = entry_data[
        "sensor_setpoint_editor"
    ]

    resources = entry_data[
        "resources"
    ]

    entities: list[ButtonEntity] = []

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

    if sensor_setpoint_editor["resource_order"]:
        entities.append(
            GHLSensorSetpointWriteButton(
                api=api,
                coordinator=coordinator,
                entry=entry,
                sensor_setpoint_editor=sensor_setpoint_editor,
            )
        )

    async_add_entities(entities)


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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

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
                translation_key="command_communication_error",
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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

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
                translation_key="command_communication_error",
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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

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
                translation_key="command_communication_error",
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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

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
                translation_key="command_communication_error",
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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

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
                translation_key="command_communication_error",
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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

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
                translation_key="command_communication_error",
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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    async def async_press(self) -> None:
        """Write the selected GHL resource description."""

        selected_key = self._description_editor[
            "selected_key"
        ]

        if selected_key is None:
            return

        resource = self._description_editor[
            "resources"
        ][selected_key]

        description = self._description_editor[
            "text"
        ]

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
                command
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
                translation_key="command_communication_error",
            ) from err

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

            return

        await self.hass.config_entries.async_forward_entry_setups(
            self._entry,
            platforms,
        )


class GHLSensorSetpointWriteButton(ButtonEntity):
    """Representation of the GHL sensor setpoint write action."""

    _attr_has_entity_name = True
    _attr_translation_key = "sensor_setpoint_write"

    def __init__(
        self,
        api: GHLAPI,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_setpoint_editor: dict,
    ) -> None:
        """Initialize the GHL sensor setpoint write button."""

        self._api = api
        self._coordinator = coordinator
        self._entry = entry
        self._sensor_setpoint_editor = sensor_setpoint_editor

        self._attr_unique_id = (
            f"{entry.entry_id}_sensor_setpoint_write"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    async def async_press(self) -> None:
        """Write the selected GHL sensor setpoint."""

        selected_key = self._sensor_setpoint_editor[
            "selected_key"
        ]

        if selected_key is None:
            return

        resource = self._sensor_setpoint_editor[
            "resources"
        ][selected_key]

        value = self._sensor_setpoint_editor[
            "value"
        ]

        if value is None:
            return

        value_text = format(
            float(value),
            ".15g",
        )

        if resource.resource == "SENSOR":
            command = (
                f"SET SENSOR[{resource.index}] "
                f"DESVALUE {value_text}"
            )

            data_key = sensor_desvalue_key(
                resource.index
            )

        elif resource.resource == "KHDIRECTOR":
            command = (
                f"SET KHDIRECTOR "
                f"DESVALUE {value_text}"
            )

            data_key = khdirector_desvalue_key()

        elif resource.resource == "IONDIRECTOR":
            command = (
                f"SET IONDIRECTOR[{resource.index}] "
                f"DESVALUE {value_text}"
            )

            data_key = iondirector_desvalue_key(
                resource.index
            )

        else:
            return

        try:
            reply = await self._api.async_command(
                command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL setpoint "
                "command %s: %s",
                command,
                err,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_communication_error",
            ) from err

        if not reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL setpoint command %s "
                "returned unexpected response: %s",
                command,
                reply,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
            )

        new_data = dict(
            self._coordinator.data
        )

        new_data[
            data_key
        ] = float(value)

        self._coordinator.async_set_updated_data(
            new_data
        )