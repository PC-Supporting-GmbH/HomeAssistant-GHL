"""Historical data import for the GHL integration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import math

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    STATISTIC_UNIT_TO_UNIT_CONVERTER,
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api import GHLAPI, GHLAPIError
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
from .discovery import GHLDiscoveredResource

_LOGGER = logging.getLogger(__name__)

_SENSOR_ERROR_MASK = 512 | 1024
_HISTORY_RESOURCE_TYPES = {
    "SENSOR",
    "KHDIRECTOR",
    "IONDIRECTOR",
}


@dataclass(frozen=True)
class GHLHistoryRecord:
    """One GHL DATARECORD entry."""

    timestamp: int
    values: tuple[float, float, float]
    status: int


@dataclass(frozen=True)
class GHLHistoryImportResult:
    """Result of importing one GHL history source."""

    success: bool
    records_found: int
    records_filtered: int
    statistics_hours: int


def history_resource_key(resource: GHLDiscoveredResource) -> str | None:
    """Return the stable key for a DATARECORD-capable resource."""

    if resource.resource not in _HISTORY_RESOURCE_TYPES:
        return None

    if resource.resource == "KHDIRECTOR":
        return "KHDIRECTOR"

    if resource.index is None:
        return None

    return f"{resource.resource}:{resource.index}"


def history_resource_keys(
    resources: list[GHLDiscoveredResource],
) -> set[str]:
    """Return keys for discovered DATARECORD-capable resources."""

    return {
        key
        for resource in resources
        if (key := history_resource_key(resource)) is not None
    }


def history_resource_map(
    resources: list[GHLDiscoveredResource],
) -> dict[str, GHLDiscoveredResource]:
    """Return DATARECORD-capable resources indexed by stable key."""

    result: dict[str, GHLDiscoveredResource] = {}

    for resource in resources:
        key = history_resource_key(resource)

        if key is not None:
            result[key] = resource

    return result


def sensor_history_is_configured(
    entry: ConfigEntry,
    resource: GHLDiscoveredResource,
) -> bool:
    """Return whether an indexed GHL sensor has completed sensor setup."""

    if resource.resource != "SENSOR" or resource.index is None:
        return True

    sensor_types = entry.options.get(CONF_SENSOR_TYPES, {})

    return str(resource.index) in sensor_types


def sensor_history_should_import(
    entry: ConfigEntry,
    resource: GHLDiscoveredResource,
) -> bool:
    """Return whether an indexed GHL sensor should have history imported."""

    if resource.resource != "SENSOR" or resource.index is None:
        return True

    sensor_type = entry.options.get(
        CONF_SENSOR_TYPES,
        {},
    ).get(str(resource.index))

    return sensor_type not in {
        SENSOR_TYPE_HIDDEN,
        SENSOR_TYPE_UNKNOWN,
        None,
    }


def history_entity_is_registered(
    hass: HomeAssistant,
    entry: ConfigEntry,
    resource: GHLDiscoveredResource,
) -> bool:
    """Return whether the resource's measurement entity is registered."""

    unique_id = _measurement_unique_id(entry, resource)

    if unique_id is None:
        return True

    entity_registry = er.async_get(hass)

    return (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            unique_id,
        )
        is not None
    )


async def async_import_resource_history(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: GHLAPI,
    resource: GHLDiscoveredResource,
) -> GHLHistoryImportResult:
    """Read and import the stored history of one GHL resource."""

    resource_key = history_resource_key(resource) or resource.resource

    if "recorder" not in hass.config.components:
        _LOGGER.warning(
            "Unable to import historical GHL data because Home Assistant "
            "Recorder is not loaded"
        )
        return GHLHistoryImportResult(False, 0, 0, 0)

    try:
        records = await _async_read_history(api, resource)
    except GHLAPIError as err:
        _LOGGER.warning(
            "Unable to read historical GHL data for %s: %s",
            resource_key,
            err,
        )
        return GHLHistoryImportResult(False, 0, 0, 0)

    if records is None:
        return GHLHistoryImportResult(False, 0, 0, 0)

    records_found = len(records)

    if not records:
        _LOGGER.info(
            "Historical GHL data import for %s: 0 records found, "
            "0 records filtered, 0 statistic hours imported",
            resource_key,
        )
        return GHLHistoryImportResult(True, 0, 0, 0)

    entity_id = _measurement_entity_id(
        hass=hass,
        entry=entry,
        resource=resource,
    )

    if entity_id is None:
        _LOGGER.warning(
            "Unable to import historical GHL data for %s because its sensor "
            "entity is not registered",
            resource_key,
        )
        return GHLHistoryImportResult(False, records_found, 0, 0)

    value_index = _value_index(entry, resource)
    unit = _configured_measurement_unit(entry, resource)

    events: list[tuple[int, float | None]] = []
    records_filtered = 0

    for record in records:
        if (
            resource.resource == "SENSOR"
            and record.status & _SENSOR_ERROR_MASK
        ):
            events.append((record.timestamp, None))
            records_filtered += 1
            continue

        value = record.values[value_index]

        if not math.isfinite(value):
            events.append((record.timestamp, None))
            records_filtered += 1
            continue

        events.append((record.timestamp, value))

    statistics = _build_measurement_statistics(events)
    statistics_hours = len(statistics)

    if statistics:
        metadata: StatisticMetaData = {
            "mean_type": StatisticMeanType.ARITHMETIC,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistic_id": entity_id,
            "unit_class": _unit_class(unit),
            "unit_of_measurement": unit,
        }

        async_import_statistics(
            hass,
            metadata,
            statistics,
        )

    _LOGGER.info(
        "Historical GHL data import for %s: %d records found, "
        "%d records filtered, %d statistic hours imported",
        resource_key,
        records_found,
        records_filtered,
        statistics_hours,
    )

    return GHLHistoryImportResult(
        True,
        records_found,
        records_filtered,
        statistics_hours,
    )

async def _async_read_history(
    api: GHLAPI,
    resource: GHLDiscoveredResource,
) -> list[GHLHistoryRecord] | None:
    """Read DATARECORD entries until GHL reports the end of history."""

    resource_name = _api_resource_name(resource)
    records: list[GHLHistoryRecord] = []
    record_index = 0

    while True:
        command = (
            f"GET {resource_name} DATARECORD[{record_index}]"
        )
        reply = await api.async_command(command)

        if reply == "NACK (-104)":
            break

        if reply.startswith("NACK"):
            _LOGGER.warning(
                "GHL history command %s was rejected: %s",
                command,
                reply,
            )
            return None

        value = _parse_ack_value(reply)

        if value is None:
            _LOGGER.warning(
                "GHL history command %s returned an unexpected response: %s",
                command,
                reply,
            )
            return None

        record = _parse_history_record(value)

        if record is None:
            _LOGGER.warning(
                "GHL history command %s returned an invalid DATARECORD: %s",
                command,
                value,
            )
            return None

        records.append(record)
        record_index += 1

    records.sort(key=lambda record: record.timestamp)

    deduplicated: dict[int, GHLHistoryRecord] = {}

    for record in records:
        deduplicated[record.timestamp] = record

    return list(deduplicated.values())


def _parse_ack_value(reply: str) -> str | None:
    """Extract a value from an ACK reply."""

    if not reply.startswith("ACK"):
        return None

    if "<" not in reply or ">" not in reply:
        return None

    value = reply.split("<", 1)[1].rsplit(">", 1)[0]

    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]

    return value


def _parse_history_record(value: str) -> GHLHistoryRecord | None:
    """Parse the five fields of a GHL DATARECORD reply."""

    parts = value.split(",")

    if len(parts) != 5:
        return None

    try:
        timestamp = int(parts[0])
        values = (
            float(parts[1]),
            float(parts[2]),
            float(parts[3]),
        )
        status = int(parts[4])
    except ValueError:
        return None

    return GHLHistoryRecord(
        timestamp=timestamp,
        values=values,
        status=status,
    )


def _api_resource_name(resource: GHLDiscoveredResource) -> str:
    """Return the GHL API resource expression."""

    if resource.index is None:
        return resource.resource

    return f"{resource.resource}[{resource.index}]"


def _measurement_unique_id(
    entry: ConfigEntry,
    resource: GHLDiscoveredResource,
) -> str | None:
    """Return the unique ID of the matching live measurement sensor."""

    if resource.resource == "SENSOR" and resource.index is not None:
        return (
            f"{entry.entry_id}_sensor_"
            f"{resource.index}_actvalue"
        )

    if resource.resource == "KHDIRECTOR":
        return f"{entry.entry_id}_khdirector_actvalue"

    if resource.resource == "IONDIRECTOR" and resource.index is not None:
        return (
            f"{entry.entry_id}_iondirector_"
            f"{resource.index}_actvalue"
        )

    return None


def _measurement_entity_id(
    hass: HomeAssistant,
    entry: ConfigEntry,
    resource: GHLDiscoveredResource,
) -> str | None:
    """Return the registered entity ID for the matching live sensor."""

    unique_id = _measurement_unique_id(entry, resource)

    if unique_id is None:
        return None

    return er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        unique_id,
    )


def _configured_measurement_unit(
    entry: ConfigEntry,
    resource: GHLDiscoveredResource,
) -> str | None:
    """Return the unit used by the matching live Home Assistant sensor."""

    if resource.resource == "KHDIRECTOR":
        return "°dKH"

    if resource.resource == "IONDIRECTOR":
        return "mg/l"

    if resource.resource != "SENSOR" or resource.index is None:
        return None

    sensor_key = str(resource.index)
    sensor_type = entry.options.get(
        CONF_SENSOR_TYPES,
        {},
    ).get(sensor_key)

    if sensor_type in (
        SENSOR_TYPE_TEMPERATURE,
        SENSOR_TYPE_AIR_TEMPERATURE,
    ):
        return UnitOfTemperature.CELSIUS

    if sensor_type == SENSOR_TYPE_PH:
        return None

    if sensor_type == SENSOR_TYPE_REDOX:
        return UnitOfElectricPotential.MILLIVOLT

    if sensor_type == SENSOR_TYPE_CONDUCTIVITY_FRESHWATER:
        return "µS"

    if sensor_type == SENSOR_TYPE_CONDUCTIVITY_SEAWATER:
        sensor_unit = entry.options.get(
            CONF_SENSOR_UNITS,
            {},
        ).get(
            sensor_key,
            SENSOR_UNIT_MS,
        )

        if sensor_unit == SENSOR_UNIT_PSU:
            return "PSU"

        if sensor_unit == SENSOR_UNIT_KG_L:
            return "kg/l"

        return "mS"

    if sensor_type == SENSOR_TYPE_OXYGEN:
        return "mg/l"

    if sensor_type == SENSOR_TYPE_HUMIDITY:
        return PERCENTAGE

    if sensor_type == SENSOR_TYPE_VOLTAGE:
        return UnitOfElectricPotential.VOLT

    return None


def _unit_class(unit: str | None) -> str | None:
    """Return Home Assistant's statistics unit class for a unit."""

    converter = STATISTIC_UNIT_TO_UNIT_CONVERTER.get(unit)

    if converter is None:
        return None

    return converter.UNIT_CLASS


def _value_index(
    entry: ConfigEntry,
    resource: GHLDiscoveredResource,
) -> int:
    """Return the DATARECORD value field matching the configured live sensor."""

    if resource.resource != "SENSOR" or resource.index is None:
        return 0

    sensor_key = str(resource.index)
    sensor_type = entry.options.get(
        CONF_SENSOR_TYPES,
        {},
    ).get(sensor_key)

    if sensor_type != SENSOR_TYPE_CONDUCTIVITY_SEAWATER:
        return 0

    sensor_unit = entry.options.get(
        CONF_SENSOR_UNITS,
        {},
    ).get(
        sensor_key,
        SENSOR_UNIT_MS,
    )

    if sensor_unit == SENSOR_UNIT_PSU:
        return 1

    if sensor_unit == SENSOR_UNIT_KG_L:
        return 2

    return 0


def _build_measurement_statistics(
    events: list[tuple[int, float | None]],
) -> list[StatisticData]:
    """Build completed hourly mean/min/max statistics from actual GHL records."""

    if not events:
        return []

    now = datetime.now(timezone.utc)
    current_hour = now.replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    cutoff = int(current_hour.timestamp())

    hourly_values: dict[int, list[float]] = defaultdict(list)

    for timestamp, value in sorted(events, key=lambda item: item[0]):
        if timestamp >= cutoff:
            break

        if value is None:
            continue

        hour_start = timestamp - (timestamp % 3600)
        hourly_values[hour_start].append(value)

    statistics: list[StatisticData] = []

    for hour_start in sorted(hourly_values):
        values = hourly_values[hour_start]

        if not values:
            continue

        statistics.append(
            {
                "start": datetime.fromtimestamp(
                    hour_start,
                    tz=timezone.utc,
                ),
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
            }
        )

    return statistics
