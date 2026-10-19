"""Repairs support for the GHL integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import (
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_SENSOR_TYPE,
    CONF_SENSOR_TYPES,
    CONF_SENSOR_UNIT,
    CONF_SENSOR_UNITS,
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


class GHLNewSensorsRepairFlow(RepairsFlow):
    """Handle configuration of newly discovered GHL sensors."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the repair flow."""

        self._entry_id = entry_id
        self._entry = None
        self._sensors = []
        self._sensor_index = 0
        self._sensor_types = {}
        self._sensor_units = {}

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Initialize the repair flow."""

        self._entry = next(
            (
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.entry_id == self._entry_id
            ),
            None,
        )

        if self._entry is None:
            return self.async_abort(
                reason="entry_not_found",
            )

        entry_data = (
            self.hass.data
            .get(DOMAIN, {})
            .get(self._entry.entry_id)
        )

        if entry_data is None:
            return self.async_abort(
                reason="entry_not_loaded",
            )

        self._sensor_types = dict(
            self._entry.options.get(
                CONF_SENSOR_TYPES,
                {},
            )
        )

        self._sensor_units = dict(
            self._entry.options.get(
                CONF_SENSOR_UNITS,
                {},
            )
        )

        self._sensors = [
            resource
            for resource in entry_data["resources"]
            if (
                resource.resource == "SENSOR"
                and str(resource.index) not in self._sensor_types
            )
        ]

        if not self._sensors:
            return self.async_abort(
                reason="no_new_sensors",
            )

        self._sensor_index = 0

        return await self.async_step_confirm()

    async def async_step_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Confirm configuration of newly discovered GHL sensors."""

        if user_input is not None:
            return await self.async_step_sensor()

        sensor_names = []

        for resource in self._sensors:
            if resource.description is not None:
                sensor_names.append(resource.description)
            else:
                sensor_names.append(
                    f"Sensor {resource.index + 1}"
                )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "sensor_names": ", ".join(sensor_names),
            },
        )

    async def async_step_sensor(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Configure a newly discovered GHL sensor."""

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
                new_options = dict(self._entry.options)

                new_options[CONF_SENSOR_TYPES] = self._sensor_types
                new_options[CONF_SENSOR_UNITS] = self._sensor_units

                self.hass.config_entries.async_update_entry(
                    self._entry,
                    options=new_options,
                )

                await self.hass.config_entries.async_reload(
                    self._entry.entry_id,
                )

                return self.async_create_entry(
                    title="",
                    data={},
                )

        sensor_resource = self._sensors[self._sensor_index]

        sensor_name = (
            sensor_resource.description
            if sensor_resource.description is not None
            else f"Sensor {sensor_resource.index + 1}"
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SENSOR_TYPE,
                    default=SENSOR_TYPE_UNKNOWN,
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

    async def async_step_sensor_unit(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Configure the unit of a seawater conductivity sensor."""

        sensor_resource = self._sensors[self._sensor_index]
        sensor_key = str(sensor_resource.index)

        if user_input is not None:
            self._sensor_units[sensor_key] = user_input[CONF_SENSOR_UNIT]

            self._sensor_index += 1

            if self._sensor_index >= len(self._sensors):
                new_options = dict(self._entry.options)

                new_options[CONF_SENSOR_TYPES] = self._sensor_types
                new_options[CONF_SENSOR_UNITS] = self._sensor_units

                self.hass.config_entries.async_update_entry(
                    self._entry,
                    options=new_options,
                )

                await self.hass.config_entries.async_reload(
                    self._entry.entry_id,
                )

                return self.async_create_entry(
                    title="",
                    data={},
                )

            return await self.async_step_sensor()

        sensor_name = (
            sensor_resource.description
            if sensor_resource.description is not None
            else f"Sensor {sensor_resource.index + 1}"
        )

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

        return self.async_show_form(
            step_id="sensor_unit",
            data_schema=data_schema,
            description_placeholders={
                "sensor_name": sensor_name,
                "sensor_number": str(sensor_resource.index + 1),
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow for a GHL issue."""

    if issue_id.startswith("new_sensors_"):
        entry_id = (
            str(data["entry_id"])
            if data is not None and data.get("entry_id") is not None
            else issue_id.removeprefix("new_sensors_")
        )

        return GHLNewSensorsRepairFlow(
            entry_id=entry_id,
        )

    raise ValueError(
        f"Unsupported GHL repair issue: {issue_id}"
    )