"""Sensor platform for the GHL integration."""

from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    EntityCategory,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SENSOR_TYPES,
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
from .coordinator import (
    GHLDataUpdateCoordinator,
    doser_capacity_key,
    doser_filllevel_key,
    flowsensor_flow_key,
    illumination_brightness_key,
    illumination_masterbrightness_key,
    iondirector_actvalue_key,
    iondirector_desvalue_key,
    khdirector_actvalue_key,
    khdirector_desvalue_key,
    last_update_key,
    sensor_desvalue_key,
    switchchannel_current_key,
    system_firmware_key,
    system_serialnumber_key,
    system_unixtime_key,
)
from .discovery import GHLDiscoveredResource

IONDIRECTOR_PARAMETER_KEYS = {
    0: "calcium",
    1: "magnesium",
    2: "potassium",
    3: "sodium",
    4: "nitrate",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GHL sensor entities from a config entry."""

    entry_data = hass.data[DOMAIN][entry.entry_id]

    coordinator: GHLDataUpdateCoordinator = entry_data["coordinator"]
    resources: list[GHLDiscoveredResource] = entry_data["resources"]

    sensor_types = entry.options.get(
        CONF_SENSOR_TYPES,
        {},
    )

    sensor_units = entry.options.get(
        CONF_SENSOR_UNITS,
        {},
    )

    entity_registry = er.async_get(hass)

    entities: list[SensorEntity] = []

    for resource in resources:
        if resource.resource == "SENSOR":
            if resource.index is None:
                continue

            sensor_key = str(resource.index)

            sensor_type = sensor_types.get(
                sensor_key,
                SENSOR_TYPE_UNKNOWN,
            )

            actvalue_unique_id = (
                f"{entry.entry_id}_sensor_"
                f"{resource.index}_actvalue"
            )

            desvalue_unique_id = (
                f"{entry.entry_id}_sensor_"
                f"{resource.index}_desvalue"
            )

            if sensor_type == SENSOR_TYPE_HIDDEN:
                entity_id = entity_registry.async_get_entity_id(
                    "sensor",
                    DOMAIN,
                    actvalue_unique_id,
                )

                if entity_id is not None:
                    entity_registry.async_remove(entity_id)

                entity_id = entity_registry.async_get_entity_id(
                    "sensor",
                    DOMAIN,
                    desvalue_unique_id,
                )

                if entity_id is not None:
                    entity_registry.async_remove(entity_id)

                continue

            sensor_unit = sensor_units.get(
                sensor_key,
                SENSOR_UNIT_MS,
            )

            if resource.features.get("ACTVALUE", False):
                entities.append(
                    GHLSensor(
                        coordinator=coordinator,
                        entry=entry,
                        resource=resource,
                        sensor_type=sensor_type,
                        sensor_unit=sensor_unit,
                    )
                )

            if resource.features.get("DESVALUE", False):
                entities.append(
                    GHLSensorSetpoint(
                        coordinator=coordinator,
                        entry=entry,
                        resource=resource,
                        sensor_type=sensor_type,
                        sensor_unit=sensor_unit,
                    )
                )

            continue

        if resource.resource == "KHDIRECTOR":
            if resource.features.get("ACTVALUE", False):
                entities.append(
                    GHLKHDirectorValueSensor(
                        coordinator=coordinator,
                        entry=entry,
                    )
                )

            if resource.features.get("DESVALUE", False):
                entities.append(
                    GHLKHDirectorSetpointSensor(
                        coordinator=coordinator,
                        entry=entry,
                    )
                )

            continue

        if resource.resource == "IONDIRECTOR":
            if resource.index is None:
                continue

            if resource.index not in IONDIRECTOR_PARAMETER_KEYS:
                continue

            parameter_key = IONDIRECTOR_PARAMETER_KEYS[
                resource.index
            ]

            if resource.features.get("ACTVALUE", False):
                entities.append(
                    GHLIONDirectorValueSensor(
                        coordinator=coordinator,
                        entry=entry,
                        resource=resource,
                        parameter_key=parameter_key,
                    )
                )

            if resource.features.get("DESVALUE", False):
                entities.append(
                    GHLIONDirectorSetpointSensor(
                        coordinator=coordinator,
                        entry=entry,
                        resource=resource,
                        parameter_key=parameter_key,
                    )
                )

            continue

        if resource.resource == "SWITCHCHANNEL":
            if resource.index is None:
                continue

            entities.append(
                GHLSwitchChannelCurrentSensor(
                    coordinator=coordinator,
                    entry=entry,
                    resource=resource,
                )
            )

            continue

        if resource.resource == "DOSER":
            if resource.index is None:
                continue

            entities.append(
                GHLDoserFillLevelSensor(
                    coordinator=coordinator,
                    entry=entry,
                    resource=resource,
                )
            )

            entities.append(
                GHLDoserCapacitySensor(
                    coordinator=coordinator,
                    entry=entry,
                    resource=resource,
                )
            )

            continue

        if resource.resource == "FLOWSENSOR":
            if resource.index is None:
                continue

            entities.append(
                GHLFlowSensor(
                    coordinator=coordinator,
                    entry=entry,
                    resource=resource,
                )
            )

            continue

        if resource.resource == "ILLUMINATION":
            if resource.index is None:
                if resource.features.get(
                    "MASTERBRIGHTNESS",
                    False,
                ):
                    entities.append(
                        GHLIlluminationMasterBrightnessSensor(
                            coordinator=coordinator,
                            entry=entry,
                        )
                    )

                continue

            if not resource.features.get(
                "ACTBRIGHTNESS",
                False,
            ):
                continue

            entities.append(
                GHLIlluminationBrightnessSensor(
                    coordinator=coordinator,
                    entry=entry,
                    resource=resource,
                )
            )

            continue

        if resource.resource == "SYSTEM":
            if resource.features.get("FIRMWARE", False):
                entities.append(
                    GHLSystemFirmwareSensor(
                        coordinator=coordinator,
                        entry=entry,
                    )
                )

            if resource.features.get("SERIALNUMBER", False):
                entities.append(
                    GHLSystemSerialNumberSensor(
                        coordinator=coordinator,
                        entry=entry,
                    )
                )

            if resource.features.get("UNIXTIME", False):
                entities.append(
                    GHLSystemTimeSensor(
                        coordinator=coordinator,
                        entry=entry,
                    )
                )

                entities.append(
                    GHLSystemTimeAbsoluteSensor(
                        coordinator=coordinator,
                        entry=entry,
                    )
                )

    entities.append(
        GHLLastUpdateSensor(
            coordinator=coordinator,
            entry=entry,
        )
    )

    async_add_entities(entities)


class GHLSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
        sensor_type: str,
        sensor_unit: str,
    ) -> None:
        """Initialize the GHL sensor."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource
        self._sensor_type = sensor_type
        self._sensor_unit = sensor_unit

        self._attr_unique_id = (
            f"{entry.entry_id}_sensor_{resource.index}_actvalue"
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
            self._attr_translation_key = "sensor"
            self._attr_translation_placeholders = {
                "index": str(resource.index + 1),
            }

        self._configure_sensor_type()

    @property
    def native_value(self):
        """Return the cached GHL sensor value."""

        return self.coordinator.data.get(
            self._resource.index,
        )

    @property
    def available(self) -> bool:
        """Return whether the sensor is available."""

        return (
            super().available
            and self._resource.index in self.coordinator.data
            and self.coordinator.data[self._resource.index] is not None
        )

    def _configure_sensor_type(self) -> None:
        """Configure device class, state class and unit."""

        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = None
        self._attr_icon = None

        if self._sensor_type == SENSOR_TYPE_UNKNOWN:
            return

        self._attr_state_class = SensorStateClass.MEASUREMENT

        if self._sensor_type in (
            SENSOR_TYPE_TEMPERATURE,
            SENSOR_TYPE_AIR_TEMPERATURE,
        ):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            return

        if self._sensor_type == SENSOR_TYPE_PH:
            self._attr_device_class = SensorDeviceClass.PH
            return

        if self._sensor_type == SENSOR_TYPE_REDOX:
            self._attr_native_unit_of_measurement = (
                UnitOfElectricPotential.MILLIVOLT
            )
            self._attr_icon = "mdi:water-opacity"
            return

        if self._sensor_type == SENSOR_TYPE_CONDUCTIVITY_FRESHWATER:
            self._attr_native_unit_of_measurement = "µS"
            self._attr_icon = "mdi:water-sync"
            return

        if self._sensor_type == SENSOR_TYPE_CONDUCTIVITY_SEAWATER:
            self._attr_icon = "mdi:water-sync"

            if self._sensor_unit == SENSOR_UNIT_PSU:
                self._attr_native_unit_of_measurement = "PSU"
                return

            if self._sensor_unit == SENSOR_UNIT_KG_L:
                self._attr_native_unit_of_measurement = "kg/l"
                return

            self._attr_native_unit_of_measurement = "mS"
            return

        if self._sensor_type == SENSOR_TYPE_OXYGEN:
            self._attr_native_unit_of_measurement = "mg/l"
            self._attr_icon = "mdi:molecule-co2"
            return

        if self._sensor_type == SENSOR_TYPE_HUMIDITY:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
            return

        if self._sensor_type == SENSOR_TYPE_VOLTAGE:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            return


class GHLSensorSetpoint(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL sensor setpoint."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
        sensor_type: str,
        sensor_unit: str,
    ) -> None:
        """Initialize the GHL sensor setpoint."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource
        self._sensor_type = sensor_type
        self._sensor_unit = sensor_unit

        self._attr_unique_id = (
            f"{entry.entry_id}_sensor_{resource.index}_desvalue"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        if resource.description is not None:
            self._attr_translation_key = "sensor_setpoint_named"
            self._attr_translation_placeholders = {
                "name": resource.description,
            }

        else:
            self._attr_translation_key = "sensor_setpoint"
            self._attr_translation_placeholders = {
                "index": str(resource.index + 1),
            }

        self._configure_sensor_type()

    @property
    def native_value(self):
        """Return the cached GHL sensor setpoint."""

        return self.coordinator.data.get(
            sensor_desvalue_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the sensor setpoint is available."""

        key = sensor_desvalue_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )

    def _configure_sensor_type(self) -> None:
        """Configure device class and unit."""

        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_icon = None

        if self._sensor_type == SENSOR_TYPE_UNKNOWN:
            return

        if self._sensor_type in (
            SENSOR_TYPE_TEMPERATURE,
            SENSOR_TYPE_AIR_TEMPERATURE,
        ):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            return

        if self._sensor_type == SENSOR_TYPE_PH:
            self._attr_device_class = SensorDeviceClass.PH
            return

        if self._sensor_type == SENSOR_TYPE_REDOX:
            self._attr_native_unit_of_measurement = (
                UnitOfElectricPotential.MILLIVOLT
            )
            self._attr_icon = "mdi:water-opacity"
            return

        if self._sensor_type == SENSOR_TYPE_CONDUCTIVITY_FRESHWATER:
            self._attr_native_unit_of_measurement = "µS"
            self._attr_icon = "mdi:water-sync"
            return

        if self._sensor_type == SENSOR_TYPE_CONDUCTIVITY_SEAWATER:
            self._attr_icon = "mdi:water-sync"

            if self._sensor_unit == SENSOR_UNIT_PSU:
                self._attr_native_unit_of_measurement = "PSU"
                return

            if self._sensor_unit == SENSOR_UNIT_KG_L:
                self._attr_native_unit_of_measurement = "kg/l"
                return

            self._attr_native_unit_of_measurement = "mS"
            return

        if self._sensor_type == SENSOR_TYPE_OXYGEN:
            self._attr_native_unit_of_measurement = "mg/l"
            self._attr_icon = "mdi:molecule-co2"
            return

        if self._sensor_type == SENSOR_TYPE_HUMIDITY:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
            return

        if self._sensor_type == SENSOR_TYPE_VOLTAGE:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            return


class GHLKHDirectorValueSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of the GHL KH Director value."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "°dKH"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the GHL KH Director value sensor."""

        super().__init__(coordinator)

        self._entry = entry

        self._attr_unique_id = (
            f"{entry.entry_id}_khdirector_actvalue"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        self._attr_translation_key = "khdirector_value"

    @property
    def native_value(self):
        """Return the cached KH Director value."""

        return self.coordinator.data.get(
            khdirector_actvalue_key()
        )

    @property
    def available(self) -> bool:
        """Return whether the KH Director value is available."""

        key = khdirector_actvalue_key()

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLKHDirectorSetpointSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of the GHL KH Director setpoint."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "°dKH"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the GHL KH Director setpoint sensor."""

        super().__init__(coordinator)

        self._entry = entry

        self._attr_unique_id = (
            f"{entry.entry_id}_khdirector_desvalue"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        self._attr_translation_key = "khdirector_setpoint"

    @property
    def native_value(self):
        """Return the cached KH Director setpoint."""

        return self.coordinator.data.get(
            khdirector_desvalue_key()
        )

    @property
    def available(self) -> bool:
        """Return whether the KH Director setpoint is available."""

        key = khdirector_desvalue_key()

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLIONDirectorValueSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL ION Director value."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "mg/l"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
        parameter_key: str,
    ) -> None:
        """Initialize the GHL ION Director value sensor."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource
        self._parameter_key = parameter_key

        self._attr_unique_id = (
            f"{entry.entry_id}_iondirector_"
            f"{resource.index}_actvalue"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        self._attr_translation_key = (
            f"iondirector_{parameter_key}_value"
        )

    @property
    def native_value(self):
        """Return the cached ION Director value."""

        return self.coordinator.data.get(
            iondirector_actvalue_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the ION Director value is available."""

        key = iondirector_actvalue_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLIONDirectorSetpointSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL ION Director setpoint."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "mg/l"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
        parameter_key: str,
    ) -> None:
        """Initialize the GHL ION Director setpoint."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource
        self._parameter_key = parameter_key

        self._attr_unique_id = (
            f"{entry.entry_id}_iondirector_"
            f"{resource.index}_desvalue"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        self._attr_translation_key = (
            f"iondirector_{parameter_key}_setpoint"
        )

    @property
    def native_value(self):
        """Return the cached ION Director setpoint."""

        return self.coordinator.data.get(
            iondirector_desvalue_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the ION Director setpoint is available."""

        key = iondirector_desvalue_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLSwitchChannelCurrentSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL switch channel current."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL switch channel current sensor."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_switchchannel_"
            f"{resource.index}_actcurrent"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        if resource.description is not None:
            self._attr_translation_key = (
                "switchchannel_current_named"
            )

            self._attr_translation_placeholders = {
                "name": resource.description,
            }

        else:
            self._attr_translation_key = (
                "switchchannel_current"
            )

            self._attr_translation_placeholders = {
                "index": str(resource.index + 1),
            }

    @property
    def native_value(self):
        """Return the cached current value."""

        return self.coordinator.data.get(
            switchchannel_current_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the current value is available."""

        key = switchchannel_current_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLDoserFillLevelSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL dosing pump fill level."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL dosing pump fill level sensor."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_doser_"
            f"{resource.index}_filllevel"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        if resource.description is not None:
            self._attr_translation_key = "doser_filllevel"
            self._attr_translation_placeholders = {
                "name": resource.description,
            }

        else:
            self._attr_translation_key = "doser_filllevel_default"
            self._attr_translation_placeholders = {
                "index": str(resource.index + 1),
            }

    @property
    def native_value(self):
        """Return the cached fill level."""

        return self.coordinator.data.get(
            doser_filllevel_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the fill level is available."""

        key = doser_filllevel_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLDoserCapacitySensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL dosing pump capacity."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL dosing pump capacity."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_doser_"
            f"{resource.index}_capacity"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        if resource.description is not None:
            self._attr_translation_key = "doser_capacity"
            self._attr_translation_placeholders = {
                "name": resource.description,
            }

        else:
            self._attr_translation_key = "doser_capacity_default"
            self._attr_translation_placeholders = {
                "index": str(resource.index + 1),
            }

    @property
    def native_value(self):
        """Return the cached capacity."""

        return self.coordinator.data.get(
            doser_capacity_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the capacity is available."""

        key = doser_capacity_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLFlowSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL flow sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL flow sensor."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_flowsensor_"
            f"{resource.index}_actflow"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

        if resource.description is not None:
            self._attr_translation_key = "flowsensor_flow"
            self._attr_translation_placeholders = {
                "name": resource.description,
            }

        else:
            self._attr_translation_key = "flowsensor_flow_default"
            self._attr_translation_placeholders = {
                "index": str(resource.index + 1),
            }

    @property
    def native_value(self):
        """Return the cached flow value."""

        return self.coordinator.data.get(
            flowsensor_flow_key(
                self._resource.index
            )
        )

    @property
    def available(self) -> bool:
        """Return whether the flow value is available."""

        key = flowsensor_flow_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLIlluminationMasterBrightnessSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of the GHL illumination master brightness."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:brightness-percent"
    _attr_translation_key = "illumination_masterbrightness"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the GHL illumination master brightness."""

        super().__init__(coordinator)

        self._entry = entry

        self._attr_unique_id = (
            f"{entry.entry_id}_illumination_masterbrightness"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self):
        """Return the cached illumination master brightness."""

        return self.coordinator.data.get(
            illumination_masterbrightness_key()
        )

    @property
    def available(self) -> bool:
        """Return whether illumination master brightness is available."""

        key = illumination_masterbrightness_key()

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLIlluminationBrightnessSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a GHL illumination channel."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:brightness-5"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
        resource: GHLDiscoveredResource,
    ) -> None:
        """Initialize the GHL illumination channel."""

        super().__init__(coordinator)

        self._entry = entry
        self._resource = resource

        self._attr_unique_id = (
            f"{entry.entry_id}_illumination_"
            f"{resource.index}_actbrightness"
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
            self._attr_translation_key = "illumination"
            self._attr_translation_placeholders = {
                "index": str(resource.index + 1),
            }

    @property
    def native_value(self):
        """Return the cached illumination brightness."""

        return self.coordinator.data.get(
            illumination_brightness_key(
                self._resource.index
            )
        )

    @property
    def extra_state_attributes(self):
        """Return the static illumination curve."""

        return {
            "point_count": self._resource.data.get(
                "point_count",
                0,
            ),
            "curve": self._resource.data.get(
                "curve",
                [],
            ),
        }

    @property
    def available(self) -> bool:
        """Return whether illumination brightness is available."""

        key = illumination_brightness_key(
            self._resource.index
        )

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLSystemFirmwareSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of the GHL system firmware."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "system_firmware"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the GHL system firmware sensor."""

        super().__init__(coordinator)

        self._entry = entry

        self._attr_unique_id = (
            f"{entry.entry_id}_system_firmware"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self):
        """Return the cached GHL firmware version."""

        return self.coordinator.data.get(
            system_firmware_key()
        )

    @property
    def available(self) -> bool:
        """Return whether the firmware version is available."""

        key = system_firmware_key()

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLSystemSerialNumberSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of the GHL system serial number."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "system_serialnumber"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the GHL system serial number sensor."""

        super().__init__(coordinator)

        self._entry = entry

        self._attr_unique_id = (
            f"{entry.entry_id}_system_serialnumber"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self):
        """Return the cached GHL serial number."""

        return self.coordinator.data.get(
            system_serialnumber_key()
        )

    @property
    def available(self) -> bool:
        """Return whether the serial number is available."""

        key = system_serialnumber_key()

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
        )


class GHLSystemTimeSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of the GHL system time."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "system_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the GHL system time sensor."""

        super().__init__(coordinator)

        self._entry = entry

        self._attr_unique_id = (
            f"{entry.entry_id}_system_unixtime"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self):
        """Return the cached GHL system time."""

        value = self.coordinator.data.get(
            system_unixtime_key()
        )

        if value is None:
            return None

        try:
            return datetime.fromtimestamp(
                float(value),
                tz=timezone.utc,
            )

        except (TypeError, ValueError, OverflowError):
            return None

    @property
    def available(self) -> bool:
        """Return whether the system time is available."""

        key = system_unixtime_key()

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
            and self.native_value is not None
        )


class GHLSystemTimeAbsoluteSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of the absolute GHL system time."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "system_time_absolute"

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the absolute GHL system time sensor."""

        super().__init__(coordinator)

        self._entry = entry

        self._attr_unique_id = (
            f"{entry.entry_id}_system_unixtime_absolute"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self):
        """Return the absolute GHL system time as localized text."""

        value = self.coordinator.data.get(
            system_unixtime_key()
        )

        if value is None:
            return None

        try:
            utc_value = datetime.fromtimestamp(
                float(value),
                tz=timezone.utc,
            )

        except (TypeError, ValueError, OverflowError):
            return None

        local_value = dt_util.as_local(utc_value)

        language = (
            self.coordinator.hass.config.language or ""
        ).lower()

        country = (
            self.coordinator.hass.config.country or ""
        ).upper()

        if language.startswith("de"):
            return local_value.strftime(
                "%d.%m.%Y %H:%M:%S"
            )

        if language.startswith("fr"):
            return local_value.strftime(
                "%d/%m/%Y %H:%M:%S"
            )

        if language.startswith("es"):
            return local_value.strftime(
                "%d/%m/%Y %H:%M:%S"
            )

        if language.startswith("en"):
            if country == "US":
                return local_value.strftime(
                    "%m/%d/%Y %I:%M:%S %p"
                )

            return local_value.strftime(
                "%d/%m/%Y %H:%M:%S"
            )

        return local_value.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    @property
    def available(self) -> bool:
        """Return whether the absolute system time is available."""

        key = system_unixtime_key()

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
            and self.native_value is not None
        )


class GHLLastUpdateSensor(
    CoordinatorEntity[GHLDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of the last successful GHL update."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: GHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the last successful GHL update sensor."""

        super().__init__(coordinator)

        self._entry = entry

        self._attr_unique_id = (
            f"{entry.entry_id}_last_update"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GHL",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self):
        """Return the last successful GHL update time."""

        value = self.coordinator.data.get(
            last_update_key()
        )

        if value is None:
            return None

        try:
            return datetime.fromtimestamp(
                float(value),
                tz=timezone.utc,
            )

        except (TypeError, ValueError, OverflowError):
            return None

    @property
    def available(self) -> bool:
        """Return whether the last update time is available."""

        key = last_update_key()

        return (
            super().available
            and key in self.coordinator.data
            and self.coordinator.data[key] is not None
            and self.native_value is not None
        )