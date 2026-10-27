"""Number platform for the GHL integration."""
# pyright: reportMissingImports=false

from __future__ import annotations

import logging

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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import GHLAPI, GHLAPIError, GHLCommandUncertainError
from .const import (
    ACCESS_MODE_FULL_ACCESS,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    CONF_SENSOR_TYPES,
    DEVICE_TYPE_MITRAS_LX7,
    DEVICE_TYPE_MITRAS_LX8,
    DEVICE_TYPE_PROFILUX_4,
    DOMAIN,
    SENSOR_TYPE_AIR_TEMPERATURE,
    SENSOR_TYPE_CONDUCTIVITY_FRESHWATER,
    SENSOR_TYPE_CONDUCTIVITY_SEAWATER,
    SENSOR_TYPE_HUMIDITY,
    SENSOR_TYPE_HIDDEN,
    SENSOR_TYPE_OXYGEN,
    SENSOR_TYPE_PH,
    SENSOR_TYPE_REDOX,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPE_UNKNOWN,
    SENSOR_TYPE_VOLTAGE,
)
from .discovery import GHLDiscoveredResource
from .coordinator import (
    GHLDescriptionNameMixin,
    GHLDataUpdateCoordinator,
    illumination_masterbrightness_key,
    iondirector_desvalue_key,
    khdirector_desvalue_key,
    sensor_desvalue_key,
)

_LOGGER = logging.getLogger(__name__)

THUNDERSTORM_DEFAULT_DURATION = 5
LIGHTSCENE_DEFAULT_FADETIME = 0

SENSOR_SETPOINT_MIN_VALUE = -10000
SENSOR_SETPOINT_MAX_VALUE = 10000
SENSOR_SETPOINT_STEP = 0.000001

# ProfiLux 4 programming manual, 2021-11-22, section 5.2, page 45.
# Only types with documented setpoint limits matching the current native unit.
SENSOR_SETPOINT_LIMITS = {
    SENSOR_TYPE_PH: (4.5, 9.5, 0.1),
    SENSOR_TYPE_TEMPERATURE: (1.0, 36.0, 0.1),
    SENSOR_TYPE_REDOX: (-300, 600, 1),
    SENSOR_TYPE_CONDUCTIVITY_FRESHWATER: (10, 1900, 1),
    SENSOR_TYPE_CONDUCTIVITY_SEAWATER: (0.5, 99.5, 0.1),
    SENSOR_TYPE_HUMIDITY: (2.0, 98.0, 0.1),
    SENSOR_TYPE_AIR_TEMPERATURE: (0.0, 50.0, 0.1),
    SENSOR_TYPE_VOLTAGE: (0.0, 10.0, 0.01),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GHL number entities from a config entry."""

    if entry.data[CONF_DEVICE_TYPE] == DEVICE_TYPE_PROFILUX_4:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        sensor_types = entry.options.get(CONF_SENSOR_TYPES, {})
        registry = er.async_get(hass)
        setpoint_entities: list[NumberEntity] = []

        for resource in entry_data["resources"]:
            if resource.resource == "SENSOR":
                if resource.index is None:
                    continue
                if sensor_types.get(str(resource.index)) == SENSOR_TYPE_HIDDEN:
                    entity_id = registry.async_get_entity_id(
                        "number",
                        DOMAIN,
                        f"{entry.entry_id}_sensor_{resource.index}_desvalue",
                    )
                    if entity_id is not None:
                        registry.async_remove(entity_id)
                    continue
            elif resource.resource == "IONDIRECTOR":
                if resource.index not in range(5):
                    continue
            elif resource.resource != "KHDIRECTOR":
                continue

            if not resource.features.get("DESVALUE", False):
                continue

            setpoint_entities.append(
                GHLSensorSetpointNumber(
                    coordinator=entry_data["coordinator"],
                    entry=entry,
                    resource=resource,
                    api=entry_data["api"],
                )
            )

        async_add_entities(setpoint_entities)

    if entry.data[CONF_ACCESS_MODE] != ACCESS_MODE_FULL_ACCESS:
        return

    if entry.data[CONF_DEVICE_TYPE] not in (
        DEVICE_TYPE_PROFILUX_4,
        DEVICE_TYPE_MITRAS_LX7,
        DEVICE_TYPE_MITRAS_LX8,
    ):
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

    resources = entry_data[
        "resources"
    ]

    masterbrightness_available = any(
        resource.resource == "ILLUMINATION"
        and resource.index is None
        and resource.features.get(
            "MASTERBRIGHTNESS",
            False,
        )
        for resource in resources
    )

    masterbrightness_data = entry_data.setdefault(
        "masterbrightness",
        {
            "value": coordinator.data.get(
                illumination_masterbrightness_key()
            ),
        },
    )

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

    if masterbrightness_available:
        entities.append(
            GHLIlluminationMasterBrightnessNumber(
                entry=entry,
                api=entry_data["api"],
                coordinator=coordinator,
                masterbrightness_data=masterbrightness_data,
            )
        )

    async_add_entities(entities)


class GHLIlluminationMasterBrightnessNumber(
    NumberEntity,
    RestoreEntity,
):
    """Representation of the GHL master brightness value to write."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.BOX
    _attr_translation_key = "illumination_masterbrightness_value"
    _attr_icon = "mdi:brightness-percent"

    def __init__(
        self,
        entry: ConfigEntry,
        masterbrightness_data: dict,
        api: GHLAPI,
        coordinator: GHLDataUpdateCoordinator,
    ) -> None:
        """Initialize the GHL master brightness value."""

        self._entry = entry
        self._masterbrightness_data = masterbrightness_data
        self._api = api
        self._coordinator = coordinator

        self._attr_unique_id = (
            f"{entry.entry_id}_illumination_"
            f"masterbrightness_value"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self) -> float | None:
        """Return the selected master brightness value."""

        value = self._masterbrightness_data["value"]

        if value is None:
            return None

        return float(value)

    async def async_added_to_hass(self) -> None:
        """Load the device value and listen for updates without writing."""

        await super().async_added_to_hass()

        self.async_on_remove(
            self._coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Update the displayed master brightness from device data."""

        self._masterbrightness_data["value"] = self._coordinator.data.get(
            illumination_masterbrightness_key()
        )
        self.async_write_ha_state()

    async def async_set_native_value(
        self,
        value: float,
    ) -> None:
        """Write the GHL master brightness immediately."""

        command = (
            f"SET ILLUMINATION MASTERBRIGHTNESS "
            f"{int(value)}"
        )

        try:
            reply = await self._api.async_command(
                command,
                retry_safe=True,
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "Unable to execute GHL master brightness "
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
                "GHL master brightness command %s "
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
            illumination_masterbrightness_key()
        ] = float(value)

        self._coordinator.async_set_updated_data(
            new_data
        )


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


class GHLSensorSetpointNumber(
    GHLDescriptionNameMixin,
    CoordinatorEntity[GHLDataUpdateCoordinator],
    NumberEntity,
):
    """Represent the setpoint of one GHL sensor or Director parameter."""

    _description_platform = 'number'
    _description_name_keys = ('sensor_setpoint', 'sensor_setpoint_named')
    _description_resource_type = "SENSOR"

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
        resource: GHLDiscoveredResource,
        api: GHLAPI,
    ) -> None:
        """Initialize the number for a fixed setpoint resource."""
        super().__init__(coordinator)

        self._coordinator = coordinator
        self._entry = entry
        self._resource = resource
        self._api = api
        self._sensor_type = entry.options.get(CONF_SENSOR_TYPES, {}).get(
            str(resource.index), SENSOR_TYPE_UNKNOWN
        )

        if resource.resource == "SENSOR":
            if limits := SENSOR_SETPOINT_LIMITS.get(self._sensor_type):
                (
                    self._attr_native_min_value,
                    self._attr_native_max_value,
                    self._attr_native_step,
                ) = limits

            self._attr_unique_id = (
                f"{entry.entry_id}_sensor_{resource.index}_desvalue"
            )
            self._data_key = sensor_desvalue_key(resource.index)
            if resource.description is not None:
                self._attr_translation_key = "sensor_setpoint_named"
                self._attr_translation_placeholders = {"name": resource.description}
            else:
                self._attr_translation_key = "sensor_setpoint"
                self._attr_translation_placeholders = {"index": str(resource.index + 1)}
        elif resource.resource == "KHDIRECTOR":
            self._attr_unique_id = f"{entry.entry_id}_khdirector_desvalue"
            self._data_key = khdirector_desvalue_key()
            self._attr_translation_key = "khdirector_setpoint"
        else:
            parameter_key = (
                "calcium", "magnesium", "potassium", "sodium", "nitrate"
            )[resource.index]
            self._attr_unique_id = (
                f"{entry.entry_id}_iondirector_{resource.index}_desvalue"
            )
            self._data_key = iondirector_desvalue_key(resource.index)
            self._attr_translation_key = f"iondirector_{parameter_key}_setpoint"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self) -> float | None:
        """Return the setpoint read from the device."""
        return self.coordinator.data.get(self._data_key)

    @property
    def available(self) -> bool:
        """Return whether this setpoint is available."""
        return (
            super().available
            and self.coordinator.data.get(self._data_key) is not None
        )

    @property
    def device_class(self):
        """Return the dynamic number device class."""

        resource = self._resource

        if (
            resource is not None
            and resource.resource in (
                "KHDIRECTOR",
                "IONDIRECTOR",
            )
        ):
            return None

        sensor_type = self._sensor_type

        if sensor_type in (
            SENSOR_TYPE_TEMPERATURE,
            SENSOR_TYPE_AIR_TEMPERATURE,
        ):
            return NumberDeviceClass.TEMPERATURE

        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit for the selected sensor."""

        resource = self._resource

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

        sensor_type = self._sensor_type

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
        """Write this GHL sensor setpoint immediately."""

        if self._entry.data[CONF_ACCESS_MODE] != ACCESS_MODE_FULL_ACCESS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="setpoint_read_only",
            )

        resource = self._resource

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
                command,
                retry_safe=True,
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
                translation_key=(
                    "command_execution_uncertain"
                    if isinstance(err, GHLCommandUncertainError)
                    else "command_communication_error"
                ),
            ) from err

        if reply.replace(" ", "").startswith("NACK(-105)"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="setpoint_read_only",
            )

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

