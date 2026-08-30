"""Number platform for the GHL integration."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.translation import async_get_translations

from .const import (
    ACCESS_MODE_FULL_ACCESS,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_PROFILUX_4,
    DOMAIN,
    SENSOR_TYPE_AIR_TEMPERATURE,
    SENSOR_TYPE_CONDUCTIVITY_FRESHWATER,
    SENSOR_TYPE_CONDUCTIVITY_SEAWATER,
    SENSOR_TYPE_HUMIDITY,
    SENSOR_TYPE_OXYGEN,
    SENSOR_TYPE_PH,
    SENSOR_TYPE_REDOX,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPE_UNKNOWN,
    SENSOR_TYPE_VOLTAGE,
)
from .coordinator import (
    GHLDataUpdateCoordinator,
    iondirector_desvalue_key,
    khdirector_desvalue_key,
    sensor_desvalue_key,
)

THUNDERSTORM_DEFAULT_DURATION = 5
LIGHTSCENE_DEFAULT_FADETIME = 0

SENSOR_SETPOINT_MIN_VALUE = -10000
SENSOR_SETPOINT_MAX_VALUE = 10000
SENSOR_SETPOINT_STEP = 0.000001


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GHL number entities from a config entry."""

    if entry.data[CONF_ACCESS_MODE] != ACCESS_MODE_FULL_ACCESS:
        return

    if entry.data[CONF_DEVICE_TYPE] != DEVICE_TYPE_PROFILUX_4:
        return

    entry_data = hass.data[DOMAIN][entry.entry_id]

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

    sensor_setpoint_editor = entry_data[
        "sensor_setpoint_editor"
    ]

    entities: list[NumberEntity] = [
        GHLThunderstormDurationNumber(
            entry=entry,
            thunderstorm_data=thunderstorm_data,
        ),
        GHLLightSceneFadeTimeNumber(
            entry=entry,
            lightscene_data=lightscene_data,
        ),
    ]

    if sensor_setpoint_editor["resource_order"]:
        translations = await async_get_translations(
            hass,
            hass.config.language,
            "entity",
            {DOMAIN},
        )

        name_default = translations.get(
            (
                f"component.{DOMAIN}.entity.number."
                f"sensor_setpoint_value.name"
            ),
            "Setpoint",
        )

        name_unit = translations.get(
            (
                f"component.{DOMAIN}.entity.number."
                f"sensor_setpoint_value_unit.name"
            ),
            "Setpoint ({unit})",
        )

        name_seawater = translations.get(
            (
                f"component.{DOMAIN}.entity.number."
                f"sensor_setpoint_value_seawater.name"
            ),
            "Setpoint - enter value in mS",
        )

        entities.append(
            GHLSensorSetpointNumber(
                coordinator=coordinator,
                entry=entry,
                sensor_setpoint_editor=sensor_setpoint_editor,
                name_default=name_default,
                name_unit=name_unit,
                name_seawater=name_seawater,
            )
        )

    async_add_entities(entities)


class GHLThunderstormDurationNumber(
    NumberEntity,
    RestoreEntity,
):
    """Representation of the GHL thunderstorm duration."""

    _attr_has_entity_name = True
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX
    _attr_translation_key = "thunderstorm_duration"
    _attr_icon = "mdi:clock-edit-outline"

    def __init__(
        self,
        entry: ConfigEntry,
        thunderstorm_data: dict,
    ) -> None:
        """Initialize the GHL thunderstorm duration."""

        self._entry = entry
        self._thunderstorm_data = thunderstorm_data

        self._attr_unique_id = (
            f"{entry.entry_id}_specialfunction_"
            f"thunderstorm_duration"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self) -> float:
        """Return the selected thunderstorm duration."""

        return float(
            self._thunderstorm_data["duration"]
        )

    async def async_added_to_hass(self) -> None:
        """Restore the previous thunderstorm duration."""

        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()

        if last_state is None:
            return

        try:
            duration = int(float(last_state.state))

        except (TypeError, ValueError):
            return

        if not 1 <= duration <= 60:
            return

        self._thunderstorm_data["duration"] = duration

    async def async_set_native_value(
        self,
        value: float,
    ) -> None:
        """Set the thunderstorm duration used by the start button."""

        self._thunderstorm_data["duration"] = int(value)

        self.async_write_ha_state()


class GHLLightSceneFadeTimeNumber(
    NumberEntity,
    RestoreEntity,
):
    """Representation of the GHL light scene fade time."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_translation_key = "lightscene_fadetime"
    _attr_icon = "mdi:clock-edit-outline"

    def __init__(
        self,
        entry: ConfigEntry,
        lightscene_data: dict,
    ) -> None:
        """Initialize the GHL light scene fade time."""

        self._entry = entry
        self._lightscene_data = lightscene_data

        self._attr_unique_id = (
            f"{entry.entry_id}_specialfunction_"
            f"lightscene_fadetime"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self) -> float:
        """Return the selected light scene fade time."""

        return float(
            self._lightscene_data["fadetime"]
        )

    async def async_added_to_hass(self) -> None:
        """Restore the previous light scene fade time."""

        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()

        if last_state is None:
            return

        try:
            fadetime = int(float(last_state.state))

        except (TypeError, ValueError):
            return

        if not 0 <= fadetime <= 255:
            return

        self._lightscene_data["fadetime"] = fadetime

    async def async_set_native_value(
        self,
        value: float,
    ) -> None:
        """Set the fade time used by the light scene buttons."""

        self._lightscene_data["fadetime"] = int(value)

        self.async_write_ha_state()


class GHLSensorSetpointNumber(NumberEntity):
    """Edit the setpoint of the selected GHL sensor."""

    _attr_has_entity_name = True
    _attr_native_min_value = SENSOR_SETPOINT_MIN_VALUE
    _attr_native_max_value = SENSOR_SETPOINT_MAX_VALUE
    _attr_native_step = SENSOR_SETPOINT_STEP
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:square-edit-outline"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_setpoint_editor: dict,
        name_default: str,
        name_unit: str,
        name_seawater: str,
    ) -> None:
        """Initialize the GHL sensor setpoint number."""

        self._coordinator = coordinator
        self._entry = entry
        self._sensor_setpoint_editor = sensor_setpoint_editor
        self._name_default = name_default
        self._name_unit = name_unit
        self._name_seawater = name_seawater

        self._attr_unique_id = (
            f"{entry.entry_id}_sensor_setpoint_value"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    async def async_added_to_hass(self) -> None:
        """Register the setpoint number entity."""

        await super().async_added_to_hass()

        self._sensor_setpoint_editor[
            "number_entity"
        ] = self

        self.async_on_remove(
            self._coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )

        if self._sensor_setpoint_editor[
            "selected_key"
        ] is not None:
            self.refresh_from_selected_sensor()

    async def async_will_remove_from_hass(self) -> None:
        """Remove the setpoint number entity from shared data."""

        if (
            self._sensor_setpoint_editor.get(
                "number_entity"
            )
            is self
        ):
            self._sensor_setpoint_editor.pop(
                "number_entity",
                None,
            )

        await super().async_will_remove_from_hass()

    def _handle_coordinator_update(self) -> None:
        """Handle updated coordinator data."""

        if self._sensor_setpoint_editor[
            "selected_key"
        ] is None:
            return

        self.refresh_from_selected_sensor()

    @property
    def name(self) -> str:
        """Return the dynamic setpoint field name."""

        resource = self._selected_resource()

        if (
            resource is not None
            and resource.resource == "KHDIRECTOR"
        ):
            return self._name_unit.format(
                unit="°dKH",
            )

        sensor_type = self._selected_sensor_type()

        if (
            sensor_type
            == SENSOR_TYPE_CONDUCTIVITY_SEAWATER
        ):
            return self._name_seawater

        unit = self.native_unit_of_measurement

        if unit is None:
            return self._name_default

        return self._name_unit.format(
            unit=unit,
        )

    @property
    def native_value(self) -> float | None:
        """Return the currently entered sensor setpoint."""

        value = self._sensor_setpoint_editor[
            "value"
        ]

        if value is None:
            return None

        return float(value)

    @property
    def device_class(self):
        """Return the dynamic number device class."""

        resource = self._selected_resource()

        if (
            resource is not None
            and resource.resource in (
                "KHDIRECTOR",
                "IONDIRECTOR",
            )
        ):
            return None

        sensor_type = self._selected_sensor_type()

        if sensor_type in (
            SENSOR_TYPE_TEMPERATURE,
            SENSOR_TYPE_AIR_TEMPERATURE,
        ):
            return NumberDeviceClass.TEMPERATURE

        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit for the selected sensor."""

        resource = self._selected_resource()

        if (
            resource is not None
            and resource.resource == "KHDIRECTOR"
        ):
            return "°dKH"

        if (
            resource is not None
            and resource.resource == "IONDIRECTOR"
        ):
            return "mg/l"

        sensor_type = self._selected_sensor_type()

        if sensor_type in (
            SENSOR_TYPE_TEMPERATURE,
            SENSOR_TYPE_AIR_TEMPERATURE,
        ):
            return UnitOfTemperature.CELSIUS

        if sensor_type == SENSOR_TYPE_PH:
            return "pH"

        if sensor_type == SENSOR_TYPE_REDOX:
            return UnitOfElectricPotential.MILLIVOLT

        if sensor_type == SENSOR_TYPE_CONDUCTIVITY_FRESHWATER:
            return "µS"

        if sensor_type == SENSOR_TYPE_CONDUCTIVITY_SEAWATER:
            return "mS"

        if sensor_type == SENSOR_TYPE_OXYGEN:
            return "mg/l"

        if sensor_type == SENSOR_TYPE_HUMIDITY:
            return PERCENTAGE

        if sensor_type == SENSOR_TYPE_VOLTAGE:
            return UnitOfElectricPotential.VOLT

        return None

    async def async_set_native_value(
        self,
        value: float,
    ) -> None:
        """Store the sensor setpoint to write."""

        self._sensor_setpoint_editor[
            "value"
        ] = float(value)

        self.async_write_ha_state()

    def refresh_from_selected_sensor(self) -> None:
        """Load the current setpoint of the selected sensor."""

        resource = self._selected_resource()

        if resource is None:
            return

        if resource.resource == "SENSOR":
            value = self._coordinator.data.get(
                sensor_desvalue_key(
                    resource.index
                )
            )

        elif resource.resource == "KHDIRECTOR":
            value = self._coordinator.data.get(
                khdirector_desvalue_key()
            )

        elif resource.resource == "IONDIRECTOR":
            value = self._coordinator.data.get(
                iondirector_desvalue_key(
                    resource.index
                )
            )

        else:
            return

        if value is None:
            self._sensor_setpoint_editor[
                "value"
            ] = None

            self.async_write_ha_state()
            return

        self._sensor_setpoint_editor[
            "value"
        ] = float(value)

        self.async_write_ha_state()

    def _selected_resource(self):
        """Return the selected GHL sensor resource."""

        selected_key = self._sensor_setpoint_editor[
            "selected_key"
        ]

        if selected_key is None:
            return None

        return self._sensor_setpoint_editor[
            "resources"
        ].get(
            selected_key
        )

    def _selected_sensor_type(self) -> str:
        """Return the configured type of the selected sensor."""

        resource = self._selected_resource()

        if resource is None:
            return SENSOR_TYPE_UNKNOWN

        if resource.resource != "SENSOR":
            return SENSOR_TYPE_UNKNOWN

        return self._sensor_setpoint_editor[
            "sensor_types"
        ].get(
            str(resource.index),
            SENSOR_TYPE_UNKNOWN,
        )