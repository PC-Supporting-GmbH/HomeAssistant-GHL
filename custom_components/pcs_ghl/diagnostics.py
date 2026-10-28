"""Provide GHL diagnostics through Home Assistant's standard download."""
# pyright: reportMissingImports=false

from __future__ import annotations

import math
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    CONF_IMPORT_HISTORICAL_DATA,
    CONF_KNOWN_SENSORS,
    CONF_SENSOR_TYPES,
    CONF_SENSOR_UNITS,
    CONF_SHOW_ALL_RESOURCES,
    DESCRIPTION_CHECK_EVERY_N_UPDATES,
    DOMAIN,
    ILLUMINATION_CURVE_CHECK_EVERY_N_UPDATES,
    UPDATE_INTERVAL_SECONDS,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return cached diagnostic information without querying the GHL device.

    Build the report from selected fields only. Never copy connection data,
    titles, descriptions, serial numbers, editor contents or exception messages.
    """
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id) or {}
    coordinator = runtime.get("coordinator")
    resources = runtime.get("resources", [])
    history = hass.data.get(f"{DOMAIN}_history_imports", {}).get(entry.entry_id)
    worker = getattr(history, "_history_worker", None)

    resource_details = [
        {
            "resource": resource.resource,
            "index": resource.index,
            "features": dict(resource.features),
            **(
                {
                    "point_count": resource.data.get("point_count", 0),
                    "cached_curve_points": len(resource.data.get("curve", [])),
                }
                if resource.resource == "ILLUMINATION" and resource.index is not None
                else {}
            ),
        }
        for resource in resources
    ]
    known_sensors = [
        {"index": index, "features": dict(sensor.get("features", {}))}
        for index, sensor in entry.data.get(CONF_KNOWN_SENSORS, {}).items()
    ]
    # Numeric cached values aid troubleshooting; exclude identifying SYSTEM data.
    measurements = {
        str(key): value
        for key, value in (getattr(coordinator, "data", None) or {}).items()
        if not str(key).startswith("system_")
        and isinstance(value, (int, float, bool))
        and (not isinstance(value, float) or math.isfinite(value))
    }
    last_exception = getattr(coordinator, "last_exception", None)

    return {
        "device_type": entry.data.get(CONF_DEVICE_TYPE),
        "entry_state": entry.state.value,
        "settings": {
            "access_mode": entry.data.get(CONF_ACCESS_MODE),
            "show_all_resources": entry.options.get(CONF_SHOW_ALL_RESOURCES, False),
            "import_historical_data": entry.options.get(
                CONF_IMPORT_HISTORICAL_DATA, True
            ),
            "sensor_types": dict(entry.options.get(CONF_SENSOR_TYPES, {})),
            "sensor_units": dict(entry.options.get(CONF_SENSOR_UNITS, {})),
            "update_interval_seconds": UPDATE_INTERVAL_SECONDS,
            "description_check_every_n_updates": DESCRIPTION_CHECK_EVERY_N_UPDATES,
            "curve_check_every_n_updates": ILLUMINATION_CURVE_CHECK_EVERY_N_UPDATES,
        },
        "resources": resource_details,
        "known_sensors": known_sensors,
        "update": {
            "coordinator_available": coordinator is not None,
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "last_exception_type": (
                type(last_exception).__name__ if last_exception is not None else None
            ),
            "description_updates_remaining": getattr(
                coordinator, "description_updates_remaining", None
            ),
            "curve_updates_remaining": getattr(
                coordinator, "curve_updates_remaining", None
            ),
            "cached_measurements": measurements,
        },
        "history_import": {
            "running": worker is not None and not worker.done(),
            "initial": getattr(history, "_history_initial", None),
            "source_number": getattr(history, "_history_source_number", None),
            "source_total": getattr(history, "_history_source_total", None),
            "records_read_current_source": getattr(history, "_history_records", None),
            "had_errors": getattr(history, "_history_import_failed", None),
        },
    }
