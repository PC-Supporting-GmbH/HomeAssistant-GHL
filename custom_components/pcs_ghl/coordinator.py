"""Data update coordinator for the GHL integration."""
# pyright: reportMissingImports=false

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import logging
from time import perf_counter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import GHLAPI, GHLAPIError
from .functions import parse_pointcount
from .const import (
    CONF_KNOWN_SENSORS,
    DESCRIPTION_CHECK_EVERY_N_UPDATES,
    ILLUMINATION_CURVE_CHECK_EVERY_N_UPDATES,
    CONF_SENSOR_TYPES,
    CONF_SENSOR_UNITS,
    DOMAIN,
    SENSOR_TYPE_CONDUCTIVITY_SEAWATER,
    SENSOR_TYPE_HIDDEN,
    SENSOR_UNIT_KG_L,
    SENSOR_UNIT_MS,
    SENSOR_UNIT_PSU,
    UPDATE_INTERVAL_SECONDS,
)
from .discovery import GHLDiscoveredResource

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=UPDATE_INTERVAL_SECONDS)


def sensor_desvalue_key(index: int) -> str:
    """Return the coordinator key for a sensor setpoint."""

    return f"sensor_{index}_desvalue"


def mitras_heatsink_temperature_key() -> str:
    """Return the coordinator key for the Mitras heatsink temperature."""

    return "mitras_heatsink_temperature"


def khdirector_actvalue_key() -> str:
    """Return the coordinator key for the KH Director value."""

    return "khdirector_actvalue"


def khdirector_desvalue_key() -> str:
    """Return the coordinator key for the KH Director setpoint."""

    return "khdirector_desvalue"


def iondirector_actvalue_key(index: int) -> str:
    """Return the coordinator key for an ION Director value."""

    return f"iondirector_{index}_actvalue"


def iondirector_desvalue_key(index: int) -> str:
    """Return the coordinator key for an ION Director setpoint."""

    return f"iondirector_{index}_desvalue"


def switchchannel_state_key(index: int) -> str:
    """Return the coordinator key for a switch channel state."""

    return f"switchchannel_{index}_state"


def switchchannel_current_key(index: int) -> str:
    """Return the coordinator key for a switch channel current."""

    return f"switchchannel_{index}_current"


def doser_filllevel_key(index: int) -> str:
    """Return the coordinator key for a dosing pump fill level."""

    return f"doser_{index}_filllevel"


def doser_capacity_key(index: int) -> str:
    """Return the coordinator key for a dosing pump capacity."""

    return f"doser_{index}_capacity"


def flowsensor_flow_key(index: int) -> str:
    """Return the coordinator key for a flow sensor."""

    return f"flowsensor_{index}_flow"


def levelsensor_state_key(index: int) -> str:
    """Return the coordinator key for a level sensor state."""

    return f"levelsensor_{index}_state"


def illumination_brightness_key(index: int) -> str:
    """Return the coordinator key for illumination brightness."""

    return f"illumination_{index}_brightness"


def illumination_masterbrightness_key() -> str:
    """Return the coordinator key for illumination master brightness."""

    return "illumination_masterbrightness"


def system_firmware_key() -> str:
    """Return the coordinator key for the system firmware."""

    return "system_firmware"


def system_serialnumber_key() -> str:
    """Return the coordinator key for the system serial number."""

    return "system_serialnumber"


def system_unixtime_key() -> str:
    """Return the coordinator key for the system Unix time."""

    return "system_unixtime"


def last_update_key() -> str:
    """Return the coordinator key for the last successful update."""

    return "last_update"


class GHLDescriptionNameMixin:
    """Read resource names from the current description without recreating entities."""

    @property
    def name(self):
        """Return the current device-provided name; HA keeps user overrides."""
        resource = self._resource
        if (
            self.coordinator.description_name_translations is None
            or (
                getattr(self, "_description_resource_type", None) is not None
                and resource.resource != self._description_resource_type
            )
        ):
            return super().name

        default_key, named_key = self._description_name_keys
        if resource.description is not None and named_key is None:
            return resource.description

        translation_key = (
            named_key if resource.description is not None else default_key
        )
        template = self.coordinator.description_name_translations.get(
            f"component.{DOMAIN}.entity.{self._description_platform}."
            f"{translation_key}.name"
        )
        if template is None:
            return super().name
        return template.format(
            name=resource.description,
            index=resource.index + 1,
        )


class GHLDataUpdateCoordinator(
    DataUpdateCoordinator[
        dict[int | str, float | str | bool | None]
    ]
):
    """Coordinate updates from the GHL device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: GHLAPI,
        resources: list[GHLDiscoveredResource],
    ) -> None:
        """Initialize the GHL coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )

        self.api = api
        self.entry = entry
        self.resources = resources
        self._entity_registry = er.async_get(hass)
        self._curve_update_count = 0
        self._description_update_count = 0
        self.description_name_translations = None

    @property
    def description_updates_remaining(self) -> int:
        """Return completed polling cycles still needed before the next check."""
        return max(
            0, DESCRIPTION_CHECK_EVERY_N_UPDATES - self._description_update_count,
        )

    @property
    def curve_updates_remaining(self) -> int:
        """Return polling cycles remaining until the next curve check."""
        return max(
            0, ILLUMINATION_CURVE_CHECK_EVERY_N_UPDATES - self._curve_update_count,
        )

    async def _async_check_illumination_curves(self) -> list[str]:
        """Refresh known channel curves sequentially, keeping old data on error."""
        errors: list[str] = []
        started = perf_counter()
        for resource in self.resources:
            if resource.resource != "ILLUMINATION" or resource.index is None:
                continue
            channel = f"ILLUMINATION[{resource.index}]"
            try:
                value = await self.api.async_get(channel, "POINTCOUNT")
                if value is None:
                    raise ValueError("missing POINTCOUNT")
                pointcount = parse_pointcount(
                    value, invalid_message=f"invalid POINTCOUNT: {value!r}"
                )
                if pointcount > 24:
                    _LOGGER.warning(
                        "GHL curve check received POINTCOUNT %d for %s; "
                        "reading only curve points 0-23",
                        pointcount, channel,
                    )
                    pointcount = 24
                curve: list[dict[str, float | int]] = []
                for curvepoint in range(pointcount):
                    time_value = await self.api.async_get(
                        channel, f"TIME[{curvepoint}]"
                    )
                    brightness_value = await self.api.async_get(
                        channel, f"BRIGHTNESS[{curvepoint}]"
                    )
                    if time_value is None or brightness_value is None:
                        raise ValueError(f"missing curve point {curvepoint}")
                    point_time = int(float(time_value))
                    point_brightness = float(brightness_value)
                    if not math.isfinite(point_brightness):
                        raise ValueError(f"invalid brightness at point {curvepoint}")
                    curve.append({"time": point_time, "brightness": point_brightness})
            except (GHLAPIError, ValueError, OverflowError) as err:
                errors.append(f"Unable to update GHL {channel} curve: {err}")
                continue
            resource.data["point_count"] = pointcount
            resource.data["curve"] = curve
        _LOGGER.debug(
            "GHL curve check for %s completed in %.3f s (failed=%d)",
            self.entry.title, perf_counter() - started, len(errors),
        )
        return errors

    async def _async_check_descriptions(self) -> list[str]:
        """Refresh all known indexed descriptions in one sequential pass."""
        started = perf_counter()
        errors: list[str] = []
        changed = 0
        checked = 0
        editor = (
            self.hass.data.get(DOMAIN, {})
            .get(self.entry.entry_id, {})
            .get("description_editor")
        )
        if self.description_name_translations is None:
            self.description_name_translations = await async_get_translations(
                self.hass, self.hass.config.language, "entity", {DOMAIN},
            )

        changed_sensors = {}
        for resource in self.resources:
            if resource.index is None or resource.resource not in {
                "SENSOR", "SWITCHCHANNEL", "ILLUMINATION", "TIMER",
                "DOSER", "FLOWSENSOR", "LEVELSENSOR",
            }:
                continue

            checked += 1
            previous_description = resource.description
            try:
                description = await self.api.async_get(
                    f"{resource.resource}[{resource.index}]", "DESCRIPTION",
                )
            except GHLAPIError as err:
                errors.append(
                    f"Unable to update GHL {resource.resource}"
                    f"[{resource.index}] DESCRIPTION: {err}"
                )
                continue

            # None means NACK or an unusable response, not a cleared description.
            if description is None:
                continue
            description = description.rstrip() or None
            # Do not replace a description written locally while this read waited.
            if resource.description != previous_description:
                continue
            if description == previous_description:
                continue

            resource.description = description
            changed += 1
            if resource.resource == "SENSOR":
                changed_sensors[str(resource.index)] = resource

            resource_key = f"{resource.resource}:{resource.index}"
            if editor is not None:
                if editor["selected_key"] == resource_key:
                    # Preserve a description the user has already started editing.
                    if editor["text"] == (previous_description or ""):
                        editor["text"] = description or ""
                        if (text_entity := editor.get("text_entity")) is not None:
                            text_entity.async_write_ha_state()
                editor_resource = editor["resources"].get(resource_key)
                if editor_resource is not None:
                    editor_resource.description = description

        if changed_sensors:
            new_data = dict(self.entry.data)
            known_sensors = {
                key: dict(value)
                for key, value in new_data.get(CONF_KNOWN_SENSORS, {}).items()
            }
            for sensor_key, resource in changed_sensors.items():
                sensor_data = dict(known_sensors.get(sensor_key, {}))
                sensor_data["description"] = resource.description
                sensor_data.setdefault("features", dict(resource.features))
                known_sensors[sensor_key] = sensor_data
            new_data[CONF_KNOWN_SENSORS] = known_sensors
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        if changed and editor is not None:
            if (select_entity := editor.get("select_entity")) is not None:
                select_entity.refresh_resource_options()
        _LOGGER.debug(
            "GHL description check for %s completed in %.3f s "
            "(checked=%d, changed=%d, failed=%d)",
            self.entry.title, perf_counter() - started, checked, changed, len(errors),
        )
        return errors

    def _entity_is_enabled(
        self,
        platform: str,
        unique_id: str,
    ) -> bool:
        """Return whether an entity is enabled in Home Assistant."""

        entity_id = self._entity_registry.async_get_entity_id(
            platform,
            DOMAIN,
            unique_id,
        )

        if entity_id is None:
            return True

        registry_entry = self._entity_registry.async_get(
            entity_id
        )

        if registry_entry is None:
            return True

        return registry_entry.disabled_by is None

    async def _async_update_data(
        self,
    ) -> dict[int | str, float | str | bool | None]:
        """Fetch all GHL sensor values."""

        sensor_types = self.entry.options.get(
            CONF_SENSOR_TYPES,
            {},
        )

        sensor_units = self.entry.options.get(
            CONF_SENSOR_UNITS,
            {},
        )

        data: dict[int | str, float | str | bool | None] = {}
        update_errors: list[str] = []

        for resource in self.resources:
            if resource.resource == "SENSOR":
                if resource.index is None:
                    if (
                        resource.features.get("ACTVALUE", False)
                        and self._entity_is_enabled(
                            "sensor",
                            f"{self.entry.entry_id}_mitras_heatsink_temperature",
                        )
                    ):
                        key = mitras_heatsink_temperature_key()

                        try:
                            value = await self.api.async_get(
                                "SENSOR",
                                "ACTVALUE",
                            )

                        except GHLAPIError as err:
                            update_errors.append(
                                "Unable to update GHL Mitras heatsink temperature: %s"
                                % (err,)
                            )

                            data[key] = None

                        else:
                            if value is None:
                                data[key] = None
                            else:
                                data[key] = _convert_value(
                                    value
                                )

                    continue

                sensor_key = str(resource.index)

                sensor_type = sensor_types.get(
                    sensor_key,
                )

                if sensor_type == SENSOR_TYPE_HIDDEN:
                    continue

                sensor_unit = sensor_units.get(
                    sensor_key,
                    SENSOR_UNIT_MS,
                )

                actvalue_unique_id = (
                    f"{self.entry.entry_id}_sensor_"
                    f"{resource.index}_actvalue"
                )

                desvalue_unique_id = (
                    f"{self.entry.entry_id}_sensor_"
                    f"{resource.index}_desvalue"
                )

                if (
                    resource.features.get("ACTVALUE", False)
                    and self._entity_is_enabled(
                        "sensor",
                        actvalue_unique_id,
                    )
                ):
                    value_index = 0

                    if sensor_type == SENSOR_TYPE_CONDUCTIVITY_SEAWATER:
                        if sensor_unit == SENSOR_UNIT_PSU:
                            value_index = 1

                        elif sensor_unit == SENSOR_UNIT_KG_L:
                            value_index = 2

                    try:
                        value = await self.api.async_get(
                            f"SENSOR[{resource.index}]",
                            f"ACTVALUE[{value_index}]",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL SENSOR[%d]: %s"
                            % (resource.index, err,)
                        )

                        data[resource.index] = None

                    else:
                        if value is None:
                            data[resource.index] = None
                        else:
                            data[resource.index] = _convert_value(
                                value
                            )

                if (
                    resource.features.get("DESVALUE", False)
                    and self._entity_is_enabled(
                        "number",
                        desvalue_unique_id,
                    )
                ):
                    desvalue_key = sensor_desvalue_key(
                        resource.index
                    )

                    try:
                        desvalue = await self.api.async_get(
                            f"SENSOR[{resource.index}]",
                            "DESVALUE",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "SENSOR[%d] DESVALUE: %s"
                            % (resource.index, err,)
                        )

                        data[desvalue_key] = None

                    else:
                        if desvalue is None:
                            data[desvalue_key] = None
                        else:
                            data[desvalue_key] = _convert_value(
                                desvalue
                            )

                continue

            if resource.resource == "KHDIRECTOR":
                actvalue_unique_id = (
                    f"{self.entry.entry_id}_khdirector_actvalue"
                )

                desvalue_unique_id = (
                    f"{self.entry.entry_id}_khdirector_desvalue"
                )

                if (
                    resource.features.get("ACTVALUE", False)
                    and self._entity_is_enabled(
                        "sensor",
                        actvalue_unique_id,
                    )
                ):
                    try:
                        actvalue = await self.api.async_get(
                            "KHDIRECTOR",
                            "ACTVALUE",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "KHDIRECTOR ACTVALUE: %s"
                            % (err,)
                        )

                        data[khdirector_actvalue_key()] = None

                    else:
                        if actvalue is None:
                            data[khdirector_actvalue_key()] = None
                        else:
                            data[khdirector_actvalue_key()] = (
                                _convert_value(actvalue)
                            )

                if (
                    resource.features.get("DESVALUE", False)
                    and self._entity_is_enabled(
                        "number",
                        desvalue_unique_id,
                    )
                ):
                    try:
                        desvalue = await self.api.async_get(
                            "KHDIRECTOR",
                            "DESVALUE",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "KHDIRECTOR DESVALUE: %s"
                            % (err,)
                        )

                        data[khdirector_desvalue_key()] = None

                    else:
                        if desvalue is None:
                            data[khdirector_desvalue_key()] = None
                        else:
                            data[khdirector_desvalue_key()] = (
                                _convert_value(desvalue)
                            )

                continue

            if resource.resource == "IONDIRECTOR":
                if resource.index is None:
                    continue

                actvalue_unique_id = (
                    f"{self.entry.entry_id}_iondirector_"
                    f"{resource.index}_actvalue"
                )

                desvalue_unique_id = (
                    f"{self.entry.entry_id}_iondirector_"
                    f"{resource.index}_desvalue"
                )

                actvalue_key = iondirector_actvalue_key(
                    resource.index
                )

                desvalue_key = iondirector_desvalue_key(
                    resource.index
                )

                if (
                    resource.features.get("ACTVALUE", False)
                    and self._entity_is_enabled(
                        "sensor",
                        actvalue_unique_id,
                    )
                ):
                    try:
                        actvalue = await self.api.async_get(
                            f"IONDIRECTOR[{resource.index}]",
                            "ACTVALUE",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "IONDIRECTOR[%d] ACTVALUE: %s"
                            % (resource.index, err,)
                        )

                        data[actvalue_key] = None

                    else:
                        if actvalue is None:
                            data[actvalue_key] = None
                        else:
                            data[actvalue_key] = _convert_value(
                                actvalue
                            )

                if (
                    resource.features.get("DESVALUE", False)
                    and self._entity_is_enabled(
                        "number",
                        desvalue_unique_id,
                    )
                ):
                    try:
                        desvalue = await self.api.async_get(
                            f"IONDIRECTOR[{resource.index}]",
                            "DESVALUE",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "IONDIRECTOR[%d] DESVALUE: %s"
                            % (resource.index, err,)
                        )

                        data[desvalue_key] = None

                    else:
                        if desvalue is None:
                            data[desvalue_key] = None
                        else:
                            data[desvalue_key] = _convert_value(
                                desvalue
                            )

                continue

            if resource.resource == "SWITCHCHANNEL":
                if resource.index is None:
                    continue

                state_unique_id = (
                    f"{self.entry.entry_id}_switchchannel_"
                    f"{resource.index}_actstate"
                )

                current_unique_id = (
                    f"{self.entry.entry_id}_switchchannel_"
                    f"{resource.index}_actcurrent"
                )

                state_key = switchchannel_state_key(
                    resource.index
                )

                current_key = switchchannel_current_key(
                    resource.index
                )

                if self._entity_is_enabled(
                    "binary_sensor",
                    state_unique_id,
                ):
                    try:
                        state = await self.api.async_get(
                            f"SWITCHCHANNEL[{resource.index}]",
                            "ACTSTATE",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "SWITCHCHANNEL[%d] ACTSTATE: %s"
                            % (resource.index, err,)
                        )

                        data[state_key] = None

                    else:
                        if state is None:
                            data[state_key] = None
                        else:
                            data[state_key] = (
                                _convert_switch_state(state, binary_only=True)
                            )

                if self._entity_is_enabled(
                    "sensor",
                    current_unique_id,
                ):
                    try:
                        current = await self.api.async_get(
                            f"SWITCHCHANNEL[{resource.index}]",
                            "ACTCURRENT",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "SWITCHCHANNEL[%d] ACTCURRENT: %s"
                            % (resource.index, err,)
                        )

                        data[current_key] = None

                    else:
                        if current is None:
                            data[current_key] = None
                        else:
                            data[current_key] = _convert_value(
                                current
                            )

                continue

            if resource.resource == "DOSER":
                if resource.index is None:
                    continue

                filllevel_unique_id = (
                    f"{self.entry.entry_id}_doser_"
                    f"{resource.index}_filllevel"
                )

                capacity_unique_id = (
                    f"{self.entry.entry_id}_doser_"
                    f"{resource.index}_capacity"
                )

                filllevel_key = doser_filllevel_key(
                    resource.index
                )

                capacity_key = doser_capacity_key(
                    resource.index
                )

                if self._entity_is_enabled(
                    "sensor",
                    filllevel_unique_id,
                ):
                    try:
                        filllevel = await self.api.async_get(
                            f"DOSER[{resource.index}]",
                            "FILLLEVEL",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "DOSER[%d] FILLLEVEL: %s"
                            % (resource.index, err,)
                        )

                        data[filllevel_key] = None

                    else:
                        if filllevel is None:
                            data[filllevel_key] = None
                        else:
                            data[filllevel_key] = _convert_value(
                                filllevel
                            )

                if self._entity_is_enabled(
                    "sensor",
                    capacity_unique_id,
                ):
                    try:
                        capacity = await self.api.async_get(
                            f"DOSER[{resource.index}]",
                            "CAPACITY",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "DOSER[%d] CAPACITY: %s"
                            % (resource.index, err,)
                        )

                        data[capacity_key] = None

                    else:
                        if capacity is None:
                            data[capacity_key] = None
                        else:
                            data[capacity_key] = _convert_value(
                                capacity
                            )

                continue

            if resource.resource == "FLOWSENSOR":
                if resource.index is None:
                    continue

                flow_unique_id = (
                    f"{self.entry.entry_id}_flowsensor_"
                    f"{resource.index}_actflow"
                )

                flow_key = flowsensor_flow_key(
                    resource.index
                )

                if self._entity_is_enabled(
                    "sensor",
                    flow_unique_id,
                ):
                    try:
                        flow = await self.api.async_get(
                            f"FLOWSENSOR[{resource.index}]",
                            "ACTFLOW",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "FLOWSENSOR[%d] ACTFLOW: %s"
                            % (resource.index, err,)
                        )

                        data[flow_key] = None

                    else:
                        if flow is None:
                            data[flow_key] = None
                        else:
                            data[flow_key] = _convert_value(
                                flow
                            )

                continue

            if resource.resource == "LEVELSENSOR":
                if resource.index is None:
                    continue

                state_unique_id = (
                    f"{self.entry.entry_id}_levelsensor_"
                    f"{resource.index}_actstate"
                )

                state_key = levelsensor_state_key(
                    resource.index
                )

                if self._entity_is_enabled(
                    "binary_sensor",
                    state_unique_id,
                ):
                    try:
                        state = await self.api.async_get(
                            f"LEVELSENSOR[{resource.index}]",
                            "ACTSTATE",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "LEVELSENSOR[%d] ACTSTATE: %s"
                            % (resource.index, err,)
                        )

                        data[state_key] = None

                    else:
                        if state is None:
                            data[state_key] = None
                        else:
                            data[state_key] = (
                                _convert_switch_state(state)
                            )

                continue

            if resource.resource == "ILLUMINATION":
                if resource.index is None:
                    if not resource.features.get(
                        "MASTERBRIGHTNESS",
                        False,
                    ):
                        continue

                    masterbrightness_unique_id = (
                        f"{self.entry.entry_id}_illumination_"
                        "masterbrightness"
                    )

                    masterbrightness_key = (
                        illumination_masterbrightness_key()
                    )

                    if self._entity_is_enabled(
                        "sensor",
                        masterbrightness_unique_id,
                    ):
                        try:
                            masterbrightness = await self.api.async_get(
                                "ILLUMINATION",
                                "MASTERBRIGHTNESS",
                            )

                        except GHLAPIError as err:
                            update_errors.append(
                                "Unable to update GHL "
                                "ILLUMINATION MASTERBRIGHTNESS: %s"
                                % (err,)
                            )

                            data[masterbrightness_key] = None

                        else:
                            if masterbrightness is None:
                                data[masterbrightness_key] = None
                            else:
                                data[masterbrightness_key] = _convert_value(
                                    masterbrightness
                                )
                                if (
                                    data[masterbrightness_key] is not None
                                    and not 0 <= data[masterbrightness_key] <= 100
                                ):
                                    _LOGGER.warning(
                                        "GHL received MASTERBRIGHTNESS outside "
                                        "the documented range 0-100: %r",
                                        masterbrightness,
                                    )
                                    data[masterbrightness_key] = None

                    continue

                if not resource.features.get(
                    "ACTBRIGHTNESS",
                    False,
                ):
                    continue

                brightness_unique_id = (
                    f"{self.entry.entry_id}_illumination_"
                    f"{resource.index}_actbrightness"
                )

                brightness_key = illumination_brightness_key(
                    resource.index
                )

                if self._entity_is_enabled(
                    "sensor",
                    brightness_unique_id,
                ):
                    try:
                        brightness = await self.api.async_get(
                            f"ILLUMINATION[{resource.index}]",
                            "ACTBRIGHTNESS",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "ILLUMINATION[%d] ACTBRIGHTNESS: %s"
                            % (resource.index, err,)
                        )

                        data[brightness_key] = None

                    else:
                        if brightness is None:
                            data[brightness_key] = None
                        else:
                            data[brightness_key] = _convert_value(
                                brightness
                            )

                continue

            if resource.resource == "SYSTEM":
                firmware_unique_id = (
                    f"{self.entry.entry_id}_system_firmware"
                )

                serialnumber_unique_id = (
                    f"{self.entry.entry_id}_system_serialnumber"
                )

                unixtime_unique_id = (
                    f"{self.entry.entry_id}_system_unixtime"
                )

                unixtime_absolute_unique_id = (
                    f"{self.entry.entry_id}_system_unixtime_absolute"
                )

                if (
                    resource.features.get("FIRMWARE", False)
                    and self._entity_is_enabled(
                        "sensor",
                        firmware_unique_id,
                    )
                ):
                    try:
                        firmware = await self.api.async_get(
                            "SYSTEM",
                            "FIRMWARE",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "SYSTEM FIRMWARE: %s"
                            % (err,)
                        )

                        data[system_firmware_key()] = None

                    else:
                        data[system_firmware_key()] = firmware

                if (
                    resource.features.get("SERIALNUMBER", False)
                    and self._entity_is_enabled(
                        "sensor",
                        serialnumber_unique_id,
                    )
                ):
                    try:
                        serialnumber = await self.api.async_get(
                            "SYSTEM",
                            "SERIALNUMBER",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "SYSTEM SERIALNUMBER: %s"
                            % (err,)
                        )

                        data[system_serialnumber_key()] = None

                    else:
                        data[system_serialnumber_key()] = (
                            serialnumber
                        )

                if (
                    resource.features.get("UNIXTIME", False)
                    and (
                        self._entity_is_enabled(
                            "sensor",
                            unixtime_unique_id,
                        )
                        or self._entity_is_enabled(
                            "sensor",
                            unixtime_absolute_unique_id,
                        )
                    )
                ):
                    try:
                        unixtime = await self.api.async_get(
                            "SYSTEM",
                            "UNIXTIME",
                        )

                    except GHLAPIError as err:
                        update_errors.append(
                            "Unable to update GHL "
                            "SYSTEM UNIXTIME: %s"
                            % (err,)
                        )

                        data[system_unixtime_key()] = None

                    else:
                        data[system_unixtime_key()] = unixtime

        if any(value is not None for value in data.values()):
            data[last_update_key()] = datetime.now(
                timezone.utc
            ).timestamp()

        entry_data = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if entry_data is not None and entry_data.get("coordinator") is self:
            self._description_update_count += 1
            if self._description_update_count >= DESCRIPTION_CHECK_EVERY_N_UPDATES:
                self._description_update_count = 0
                update_errors.extend(await self._async_check_descriptions())
            self._curve_update_count += 1
            if self._curve_update_count >= ILLUMINATION_CURVE_CHECK_EVERY_N_UPDATES:
                self._curve_update_count = 0
                update_errors.extend(await self._async_check_illumination_curves())

        if update_errors:
            _LOGGER.warning(
                "GHL update for %s completed with %d failed queries: %s",
                self.entry.title,
                len(update_errors),
                "; ".join(update_errors),
            )

        _LOGGER.debug(
            "GHL coordinator update completed: %s",
            data,
        )

        return data


def _convert_value(value: str) -> float | None:
    """Convert a numeric GHL API value, rejecting invalid measurements."""

    try:
        converted = float(value)
    except ValueError:
        _LOGGER.warning("GHL received invalid numeric value: %r", value)
        return None

    if not math.isfinite(converted):
        _LOGGER.warning("GHL received non-finite numeric value: %r", value)
        return None

    return converted


def _convert_switch_state(
    value: str, *, binary_only: bool = False
) -> bool | None:
    """Convert a state; enforce 0/1 only where documented by the API."""

    converted = _convert_value(value)
    if converted is None:
        return None

    if binary_only and converted not in (0, 1):
        _LOGGER.warning("GHL received invalid SWITCHCHANNEL ACTSTATE: %r", value)
        return None

    return converted != 0