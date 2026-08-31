"""Config flow for the GHL integration."""

from __future__ import annotations

import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, FlowType
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.translation import async_get_translations

from .const import (
    ACCESS_MODE_FULL_ACCESS,
    ACCESS_MODE_READ_ONLY,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    CONF_SENSOR_TYPE,
    CONF_SENSOR_TYPES,
    CONF_SENSOR_UNIT,
    CONF_SENSOR_UNITS,
    CONF_SHOW_ALL_RESOURCES,
    DEFAULT_PORT,
    DEVICE_TYPE_MITRAS_LX7,
    DEVICE_TYPE_MITRAS_LX8,
    DEVICE_TYPE_PROFILUX_4,
    DOMAIN,
    SENSOR_TYPE_AIR_TEMPERATURE,
    SENSOR_TYPE_CONDUCTIVITY_FRESHWATER,
    SENSOR_TYPE_CONDUCTIVITY_SEAWATER,
    SENSOR_TYPE_HIDDEN,
    SENSOR_TYPE_HUMIDITY,
    SENSOR_TYPE_OXYGEN,
    SENSOR_TYPE_PH,
    SENSOR_TYPE_REDOX,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPE_UNKNOWN,
    SENSOR_TYPE_VOLTAGE,
    SENSOR_UNIT_KG_L,
    SENSOR_UNIT_MS,
    SENSOR_UNIT_PSU,
)


async def async_test_connection(host: str, port: int) -> str:
    """Test the connection to the GHL API."""

    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port),
        timeout=10,
    )

    try:
        writer.write(b"GET ILLUMINATION MASTERBRIGHTNESS\n")
        await writer.drain()

        reply = await asyncio.wait_for(
            reader.read(256),
            timeout=10,
        )

        return reply.decode().strip()

    finally:
        writer.close()
        await writer.wait_closed()


class GHLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GHL."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GHLOptionsFlow:
        """Create the GHL options flow."""

        return GHLOptionsFlow()

    async def async_on_create_entry(
        self,
        result: ConfigFlowResult,
    ) -> ConfigFlowResult:
        """Start the options flow after the config entry was created."""

        config_entry = result["result"]

        options_result = await self.hass.config_entries.options.async_init(
            config_entry.entry_id,
        )

        result["next_flow"] = (
            FlowType.OPTIONS_FLOW,
            options_result["flow_id"],
        )

        return result

    async def async_step_user(self, user_input=None):
        """Handle the initial configuration step."""

        errors = {}

        if user_input is not None:
            if not user_input["api_enabled"]:
                errors["api_enabled"] = "api_not_enabled"

            else:
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]

                self._async_abort_entries_match(
                    {
                        CONF_HOST: host,
                        CONF_PORT: port,
                    }
                )

                try:
                    reply = await async_test_connection(host, port)

                except (OSError, asyncio.TimeoutError):
                    errors["base"] = "cannot_connect"

                else:
                    if reply == "NACK (-105)":
                        errors["base"] = "api_not_enabled"

                    elif not reply.startswith("ACK"):
                        errors["base"] = "invalid_response"

                    else:
                        data = {
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_PORT: user_input[CONF_PORT],
                            CONF_ACCESS_MODE: user_input[CONF_ACCESS_MODE],
                            CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                        }

                        translations = await async_get_translations(
                            self.hass,
                            self.hass.config.language,
                            "selector",
                            {DOMAIN},
                        )

                        translation_key = (
                            f"component.{DOMAIN}.selector.device_type.options."
                            f"{user_input[CONF_DEVICE_TYPE]}"
                        )

                        device_type_name = translations.get(
                            translation_key,
                            user_input[CONF_DEVICE_TYPE],
                        )

                        return self.async_create_entry(
                            title=f"{device_type_name} ({user_input[CONF_HOST]})",
                            data=data,
                        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(
                    CONF_DEVICE_TYPE,
                    default=DEVICE_TYPE_PROFILUX_4,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            DEVICE_TYPE_PROFILUX_4,
                            DEVICE_TYPE_MITRAS_LX7,
                            DEVICE_TYPE_MITRAS_LX8,
                        ],
                        translation_key="device_type",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_ACCESS_MODE,
                    default=ACCESS_MODE_FULL_ACCESS,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            ACCESS_MODE_READ_ONLY,
                            ACCESS_MODE_FULL_ACCESS,
                        ],
                        translation_key="access_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required("api_enabled", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class GHLOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle GHL options."""

    def __init__(self) -> None:
        """Initialize the GHL options flow."""

        self._sensors = []
        self._sensor_index = 0
        self._sensor_types = {}
        self._sensor_units = {}
        self._show_all_resources = False

    async def async_step_init(self, user_input=None):
        """Initialize GHL options."""

        entry_data = (
            self.hass.data
            .get(DOMAIN, {})
            .get(self.config_entry.entry_id)
        )

        if entry_data is None:
            return self.async_abort(
                reason="entry_not_loaded",
            )

        self._sensors = [
            resource
            for resource in entry_data["resources"]
            if resource.resource == "SENSOR"
        ]

        self._sensor_types = dict(
            self.config_entry.options.get(
                CONF_SENSOR_TYPES,
                {},
            )
        )

        self._sensor_units = dict(
            self.config_entry.options.get(
                CONF_SENSOR_UNITS,
                {},
            )
        )

        self._show_all_resources = self.config_entry.options.get(
            CONF_SHOW_ALL_RESOURCES,
            False,
        )

        self._sensor_index = 0

        if (
            self._sensors
            and not self._sensor_types
        ):
            return self.async_show_menu(
                step_id="initial_sensor_setup",
                menu_options=[
                    "general",
                    "sensors",
                ],
            )

        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "sensors",
            ],
        )

    async def async_step_general(self, user_input=None):
        """Configure general GHL options."""

        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            access_mode = user_input[CONF_ACCESS_MODE]
            show_all_resources = user_input[
                CONF_SHOW_ALL_RESOURCES
            ]

            old_host = self.config_entry.data[CONF_HOST]
            old_port = self.config_entry.data[CONF_PORT]
            old_access_mode = self.config_entry.data[
                CONF_ACCESS_MODE
            ]
            old_show_all_resources = (
                self.config_entry.options.get(
                    CONF_SHOW_ALL_RESOURCES,
                    False,
                )
            )

            connection_changed = (
                host != old_host
                or port != old_port
            )

            data_changed = (
                host != old_host
                or port != old_port
                or access_mode != old_access_mode
            )

            options_changed = (
                show_all_resources
                != old_show_all_resources
            )

            if connection_changed:
                duplicate_entry = next(
                    (
                        entry
                        for entry in self.hass.config_entries.async_entries(
                            DOMAIN
                        )
                        if (
                            entry.entry_id != self.config_entry.entry_id
                            and entry.data.get(CONF_HOST) == host
                            and entry.data.get(CONF_PORT) == port
                        )
                    ),
                    None,
                )

                if duplicate_entry is not None:
                    errors["base"] = "already_configured"

                else:
                    try:
                        reply = await async_test_connection(
                            host,
                            port,
                        )

                    except (OSError, asyncio.TimeoutError):
                        errors["base"] = "cannot_connect"

                    else:
                        if reply == "NACK (-105)":
                            errors["base"] = "api_not_enabled"

                        elif not reply.startswith("ACK"):
                            errors["base"] = "invalid_response"

            if not errors:
                new_data = dict(self.config_entry.data)

                new_data[CONF_HOST] = host
                new_data[CONF_PORT] = port
                new_data[CONF_ACCESS_MODE] = access_mode

                if host != old_host:
                    translations = await async_get_translations(
                        self.hass,
                        self.hass.config.language,
                        "selector",
                        {DOMAIN},
                    )

                    device_type = self.config_entry.data[
                        CONF_DEVICE_TYPE
                    ]

                    translation_key = (
                        f"component.{DOMAIN}."
                        f"selector.device_type.options."
                        f"{device_type}"
                    )

                    device_type_name = translations.get(
                        translation_key,
                        device_type,
                    )

                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=new_data,
                        title=f"{device_type_name} ({host})",
                    )

                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=new_data,
                    )

                self._show_all_resources = (
                    show_all_resources
                )

                if data_changed and not options_changed:
                    self.hass.config_entries.async_schedule_reload(
                        self.config_entry.entry_id
                    )

                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SENSOR_TYPES: self._sensor_types,
                        CONF_SENSOR_UNITS: self._sensor_units,
                        CONF_SHOW_ALL_RESOURCES: (
                            self._show_all_resources
                        ),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=self.config_entry.data[CONF_HOST],
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=self.config_entry.data[CONF_PORT],
                ): int,
                vol.Required(
                    CONF_ACCESS_MODE,
                    default=self.config_entry.data[CONF_ACCESS_MODE],
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            ACCESS_MODE_READ_ONLY,
                            ACCESS_MODE_FULL_ACCESS,
                        ],
                        translation_key="access_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SHOW_ALL_RESOURCES,
                    default=self._show_all_resources,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="general",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_sensors(self, user_input=None):
        """Start GHL sensor configuration."""

        if not self._sensors:
            return self.async_abort(
                reason="no_sensors",
            )

        self._sensor_index = 0

        return await self.async_step_sensor()

    async def async_step_sensor(self, user_input=None):
        """Configure the type of a discovered GHL sensor."""

        if user_input is not None:
            sensor_resource = self._sensors[self._sensor_index]
            sensor_key = str(sensor_resource.index)
            sensor_type = user_input[CONF_SENSOR_TYPE]

            self._sensor_types[sensor_key] = sensor_type

            if sensor_type == SENSOR_TYPE_CONDUCTIVITY_SEAWATER:
                return await self.async_step_sensor_unit()

            self._sensor_units.pop(sensor_key, None)

            self._sensor_index += 1

            if self._sensor_index >= len(self._sensors):
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SENSOR_TYPES: self._sensor_types,
                        CONF_SENSOR_UNITS: self._sensor_units,
                        CONF_SHOW_ALL_RESOURCES: (
                            self._show_all_resources
                        ),
                    },
                )

        sensor_resource = self._sensors[self._sensor_index]

        sensor_name = (
            sensor_resource.description
            if sensor_resource.description is not None
            else f"Sensor {sensor_resource.index + 1}"
        )

        current_sensor_type = self._sensor_types.get(
            str(sensor_resource.index),
            SENSOR_TYPE_UNKNOWN,
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SENSOR_TYPE,
                    default=current_sensor_type,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            SENSOR_TYPE_UNKNOWN,
                            SENSOR_TYPE_HIDDEN,
                            SENSOR_TYPE_TEMPERATURE,
                            SENSOR_TYPE_PH,
                            SENSOR_TYPE_REDOX,
                            SENSOR_TYPE_CONDUCTIVITY_FRESHWATER,
                            SENSOR_TYPE_CONDUCTIVITY_SEAWATER,
                            SENSOR_TYPE_OXYGEN,
                            SENSOR_TYPE_HUMIDITY,
                            SENSOR_TYPE_AIR_TEMPERATURE,
                            SENSOR_TYPE_VOLTAGE,
                        ],
                        translation_key="sensor_type",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="sensor",
            data_schema=data_schema,
            description_placeholders={
                "sensor_name": sensor_name,
                "sensor_number": str(sensor_resource.index + 1),
            },
        )

    async def async_step_sensor_unit(self, user_input=None):
        """Configure the unit of a seawater conductivity sensor."""

        sensor_resource = self._sensors[self._sensor_index]
        sensor_key = str(sensor_resource.index)

        if user_input is not None:
            self._sensor_units[sensor_key] = user_input[CONF_SENSOR_UNIT]

            self._sensor_index += 1

            if self._sensor_index >= len(self._sensors):
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SENSOR_TYPES: self._sensor_types,
                        CONF_SENSOR_UNITS: self._sensor_units,
                        CONF_SHOW_ALL_RESOURCES: (
                            self._show_all_resources
                        ),
                    },
                )

            return await self.async_step_sensor()

        current_sensor_unit = self._sensor_units.get(
            sensor_key,
            SENSOR_UNIT_MS,
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SENSOR_UNIT,
                    default=current_sensor_unit,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            SENSOR_UNIT_MS,
                            SENSOR_UNIT_PSU,
                            SENSOR_UNIT_KG_L,
                        ],
                        translation_key="sensor_unit",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        sensor_name = (
            sensor_resource.description
            if sensor_resource.description is not None
            else f"Sensor {sensor_resource.index + 1}"
        )

        return self.async_show_form(
            step_id="sensor_unit",
            data_schema=data_schema,
            description_placeholders={
                "sensor_name": sensor_name,
                "sensor_number": str(sensor_resource.index + 1),
            },
        )