"""GHL integration."""
# pyright: reportMissingImports=false

import logging
from time import perf_counter

from copy import deepcopy

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .api import GHLAPI, GHLConnectionError
from .const import (
    ACCESS_MODE_READ_ONLY,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    CONF_HISTORY_PRESENT_RESOURCES,
    CONF_IMPORT_HISTORICAL_DATA,
    CONF_KNOWN_SENSORS,
    CONF_SENSOR_TYPES,
    CONF_SHOW_ALL_RESOURCES,
    DOMAIN,
    SENSOR_TYPE_HIDDEN,
    CONF_INITIAL_HISTORY_PENDING,
    DESCRIPTION_RESOURCE_ORDER,
    DESCRIPTION_RESOURCE_TYPES,
    FEEDPAUSE_COUNT,
    IONDIRECTOR_ACTION_COUNT,
    ISSUE_NEW_SENSORS_PREFIX,
    KHDIRECTOR_ACTION_COUNT,
    LIGHTSCENE_COUNT,
    MAINTENANCE_COUNT,
    PLATFORMS,
    WATERCHANGE_COUNT,
)
from .coordinator import GHLDataUpdateCoordinator
from .discovery import (
    GHLDiscoveredResource,
    async_discover_resources,
)
from .history import (
    async_import_resource_history,
    history_entity_is_registered,
    history_resource_map,
    sensor_history_is_configured,
    sensor_history_should_import,
)

_LOGGER = logging.getLogger(__name__)







async def async_migrate_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Migrate an old GHL config entry."""

    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=None,
            version=2,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GHL from a config entry."""

    setup_started = perf_counter()
    _LOGGER.debug("GHL setup [%s]: started", entry.entry_id)

    api = GHLAPI(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
    )

    entry.async_on_unload(api.async_close)

    phase_started = perf_counter()
    _LOGGER.debug("GHL setup [%s]: connection check started", entry.entry_id)

    try:
        await api.async_check_connection()

    except GHLConnectionError as err:
        raise ConfigEntryNotReady(
             translation_domain=DOMAIN,
             translation_key="device_unreachable",
             translation_placeholders={
                 "device": entry.title,
             },
        ) from err

    _LOGGER.debug(
        "GHL setup [%s]: connection check completed in %.3f s",
        entry.entry_id, perf_counter() - phase_started,
    )

    phase_started = perf_counter()
    _LOGGER.debug("GHL setup [%s]: resource discovery started", entry.entry_id)

    discovered_resources = await async_discover_resources(
        api=api,
        device_type=entry.data[CONF_DEVICE_TYPE],
        show_all_resources=entry.options.get(
            CONF_SHOW_ALL_RESOURCES,
            False,
        ),
    )

    _LOGGER.debug(
        "GHL setup [%s]: resource discovery completed in %.3f s",
        entry.entry_id, perf_counter() - phase_started,
    )

    discovered_history_resources = history_resource_map(
        discovered_resources
    )
    previous_history_resources = set(
        entry.data.get(
            CONF_HISTORY_PRESENT_RESOURCES,
            [],
        )
    )
    current_history_resources = {
        key
        for key, resource in discovered_history_resources.items()
        if sensor_history_is_configured(entry, resource)
    }
    history_resources_to_import = {
        key
        for key in current_history_resources
        if (
            key not in previous_history_resources
            or (
                sensor_history_should_import(
                    entry,
                    discovered_history_resources[key],
                )
                and not history_entity_is_registered(
                    hass,
                    entry,
                    discovered_history_resources[key],
                )
            )
        )
    }

    discovered_resources = _merge_known_sensors(
        hass=hass,
        entry=entry,
        discovered_resources=discovered_resources,
    )

    coordinator = GHLDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        api=api,
        resources=discovered_resources,
    )

    _async_remove_obsolete_setpoint_entities(hass, entry)

    phase_started = perf_counter()
    _LOGGER.debug("GHL setup [%s]: first data refresh started", entry.entry_id)

    await coordinator.async_config_entry_first_refresh()

    _LOGGER.debug(
        "GHL setup [%s]: first data refresh completed in %.3f s",
        entry.entry_id, perf_counter() - phase_started,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "resources": discovered_resources,
        "coordinator": coordinator,
        "description_editor": _create_description_editor_data(
            discovered_resources
        ),
    }

    _async_check_new_sensors(
        hass=hass,
        entry=entry,
        discovered_resources=discovered_resources,
    )

    phase_started = perf_counter()
    _LOGGER.debug("GHL setup [%s]: platform setup started", entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    _LOGGER.debug(
        "GHL setup [%s]: platform setup completed in %.3f s",
        entry.entry_id, perf_counter() - phase_started,
    )

    phase_started = perf_counter()
    _LOGGER.debug("GHL setup [%s]: historical import phase started", entry.entry_id)

    _LOGGER.debug(
        "GHL setup [%s]: historical import enabled=%s, candidates=%d",
        entry.entry_id, entry.options.get(CONF_IMPORT_HISTORICAL_DATA, False),
        len(history_resources_to_import),
    )

    failed_history_resources: set[str] = set()

    if (
        not entry.data.get(CONF_INITIAL_HISTORY_PENDING, False)
        and entry.options.get(CONF_IMPORT_HISTORICAL_DATA, False)
    ):
        for resource_key in sorted(history_resources_to_import):
            resource = discovered_history_resources[resource_key]

            if not sensor_history_should_import(entry, resource):
                continue

            history_started = perf_counter()
            _LOGGER.debug(
                "GHL setup [%s]: historical import %s started",
                entry.entry_id, resource_key,
            )
            history_result = await async_import_resource_history(
                hass=hass,
                entry=entry,
                api=api,
                resource=resource,
            )
            _LOGGER.debug(
                "GHL setup [%s]: historical import %s completed in %.3f s (success=%s)",
                entry.entry_id, resource_key, perf_counter() - history_started,
                history_result.success,
            )
            if not history_result.success:
                failed_history_resources.add(resource_key)

    _LOGGER.debug(
        "GHL setup [%s]: historical import phase completed in %.3f s",
        entry.entry_id, perf_counter() - phase_started,
    )

    history_resources_to_store = (
        current_history_resources
        - failed_history_resources
    )

    if (
        not entry.data.get(CONF_INITIAL_HISTORY_PENDING, False)
        and set(
            entry.data.get(
                CONF_HISTORY_PRESENT_RESOURCES,
                [],
            )
        ) != history_resources_to_store
    ):
        new_data = dict(entry.data)
        new_data[CONF_HISTORY_PRESENT_RESOURCES] = sorted(
            history_resources_to_store
        )
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
        )

    entry_runtime = hass.data[DOMAIN][entry.entry_id]
    entry_title = entry.title
    entry_options = deepcopy(dict(entry.options))
    connection_data = tuple(
        entry.data.get(key)
        for key in (CONF_HOST, CONF_PORT, CONF_ACCESS_MODE)
    )

    async def async_reload_on_config_change(
        hass: HomeAssistant,
        updated_entry: ConfigEntry,
    ) -> None:
        """Reload for names, options or connection settings, not internal data."""
        nonlocal entry_title, entry_options, connection_data

        updated_options = deepcopy(dict(updated_entry.options))
        updated_connection_data = tuple(
            updated_entry.data.get(key)
            for key in (CONF_HOST, CONF_PORT, CONF_ACCESS_MODE)
        )
        if (
            updated_entry.title == entry_title
            and updated_options == entry_options
            and updated_connection_data == connection_data
        ):
            return

        managed_history_options = (
            updated_entry.title == entry_title
            and updated_connection_data == connection_data
            and entry_runtime.get("history_flow_options") == updated_options
        )
        entry_title = updated_entry.title
        entry_options = updated_options
        connection_data = updated_connection_data
        if managed_history_options:
            return
        hass.config_entries.async_schedule_reload(updated_entry.entry_id)

    entry.async_on_unload(
        entry.add_update_listener(async_reload_on_config_change)
    )

    _LOGGER.debug(
        "GHL setup [%s]: completed in %.3f s",
        entry.entry_id, perf_counter() - setup_started,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a GHL config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if not unload_ok:
        return False

    if DOMAIN in hass.data:
        entry_data = hass.data[DOMAIN].get(entry.entry_id)

        if entry_data is not None:
            if not entry.options.get(
                CONF_SHOW_ALL_RESOURCES,
                False,
            ):
                _async_remove_extra_resource_entities(
                    hass=hass,
                    entry=entry,
                    resources=entry_data["resources"],
                )

            if entry.data.get(
                CONF_ACCESS_MODE
            ) == ACCESS_MODE_READ_ONLY:
                _async_remove_write_entities(
                    hass=hass,
                    entry=entry,
                )

            api = entry_data.get("api")

            if api is not None:
                await api.async_close()

        hass.data[DOMAIN].pop(entry.entry_id, None)

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return True


def _create_description_editor_data(
    resources: list[GHLDiscoveredResource],
) -> dict:
    """Create shared data for the GHL description editor."""

    description_resources = [
        resource
        for resource in resources
        if (
            resource.resource in DESCRIPTION_RESOURCE_TYPES
            and resource.index is not None
        )
    ]

    description_resources.sort(
        key=lambda resource: (
            DESCRIPTION_RESOURCE_ORDER[
                resource.resource
            ],
            resource.index,
        )
    )

    resource_map: dict[str, GHLDiscoveredResource] = {}
    resource_order: list[str] = []

    for resource in description_resources:
        resource_key = (
            f"{resource.resource}:{resource.index}"
        )

        resource_map[resource_key] = resource
        resource_order.append(resource_key)

    selected_key = (
        resource_order[0]
        if resource_order
        else None
    )

    text = ""

    if selected_key is not None:
        selected_resource = resource_map[
            selected_key
        ]

        if selected_resource.description is not None:
            text = selected_resource.description

    return {
        "resource_order": resource_order,
        "resources": resource_map,
        "selected_key": selected_key,
        "text": text,
    }




def _async_remove_obsolete_setpoint_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove the shared editor and the replaced read-only setpoint sensors."""
    registry = er.async_get(hass)
    for platform, suffix in (
        ("number", "sensor_setpoint_value"),
        ("select", "sensor_setpoint_sensor"),
    ):
        entity_id = registry.async_get_entity_id(
            platform, DOMAIN, f"{entry.entry_id}_{suffix}"
        )
        if entity_id is not None:
            registry.async_remove(entity_id)

    for registry_entry in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
        if registry_entry.domain != "sensor" or registry_entry.platform != DOMAIN:
            continue
        unique_id = registry_entry.unique_id
        if unique_id == f"{entry.entry_id}_khdirector_desvalue" or (
            unique_id.startswith((
                f"{entry.entry_id}_sensor_",
                f"{entry.entry_id}_iondirector_",
            ))
            and unique_id.endswith("_desvalue")
        ):
            registry.async_remove(registry_entry.entity_id)


def _async_remove_write_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove entities that require write access."""

    entity_registry = er.async_get(hass)

    for index in range(FEEDPAUSE_COUNT):
        for action in (
            "start",
            "stop",
        ):
            unique_id = (
                f"{entry.entry_id}_specialfunction_"
                f"feedpause_{index}_{action}"
            )

            entity_id = entity_registry.async_get_entity_id(
                "button",
                DOMAIN,
                unique_id,
            )

            if entity_id is not None:
                entity_registry.async_remove(
                    entity_id
                )

    for index in range(MAINTENANCE_COUNT):
        for action in (
            "start",
            "stop",
        ):
            unique_id = (
                f"{entry.entry_id}_specialfunction_"
                f"maintenance_{index}_{action}"
            )

            entity_id = entity_registry.async_get_entity_id(
                "button",
                DOMAIN,
                unique_id,
            )

            if entity_id is not None:
                entity_registry.async_remove(
                    entity_id
                )

    for index in range(WATERCHANGE_COUNT):
        for action in (
            "start",
            "stop",
        ):
            unique_id = (
                f"{entry.entry_id}_specialfunction_"
                f"waterchange_{index}_{action}"
            )

            entity_id = entity_registry.async_get_entity_id(
                "button",
                DOMAIN,
                unique_id,
            )

            if entity_id is not None:
                entity_registry.async_remove(
                    entity_id
                )

    for action in (
        "start",
        "stop",
    ):
        unique_id = (
            f"{entry.entry_id}_specialfunction_"
            f"thunderstorm_{action}"
        )

        entity_id = entity_registry.async_get_entity_id(
            "button",
            DOMAIN,
            unique_id,
        )

        if entity_id is not None:
            entity_registry.async_remove(
                entity_id
            )

    unique_id = (
        f"{entry.entry_id}_specialfunction_"
        f"thunderstorm_duration"
    )

    entity_id = entity_registry.async_get_entity_id(
        "number",
        DOMAIN,
        unique_id,
    )

    if entity_id is not None:
        entity_registry.async_remove(
            entity_id
        )

    for index in range(LIGHTSCENE_COUNT):
        for action in (
            "start",
            "stop",
        ):
            unique_id = (
                f"{entry.entry_id}_specialfunction_"
                f"lightscene_{index}_{action}"
            )

            entity_id = entity_registry.async_get_entity_id(
                "button",
                DOMAIN,
                unique_id,
            )

            if entity_id is not None:
                entity_registry.async_remove(
                    entity_id
                )

    unique_id = (
        f"{entry.entry_id}_specialfunction_"
        f"lightscene_fadetime"
    )

    entity_id = entity_registry.async_get_entity_id(
        "number",
        DOMAIN,
        unique_id,
    )

    if entity_id is not None:
        entity_registry.async_remove(
            entity_id
        )

    for action in range(KHDIRECTOR_ACTION_COUNT):
        unique_id = (
            f"{entry.entry_id}_khdirector_"
            f"startaction_{action}"
        )

        entity_id = entity_registry.async_get_entity_id(
            "button",
            DOMAIN,
            unique_id,
        )

        if entity_id is not None:
            entity_registry.async_remove(
                entity_id
            )

    for action in range(IONDIRECTOR_ACTION_COUNT):
        unique_id = (
            f"{entry.entry_id}_iondirector_"
            f"startaction_{action}"
        )

        entity_id = entity_registry.async_get_entity_id(
            "button",
            DOMAIN,
            unique_id,
        )

        if entity_id is not None:
            entity_registry.async_remove(
                entity_id
            )

    unique_id = (
        f"{entry.entry_id}_description_resource"
    )

    entity_id = entity_registry.async_get_entity_id(
        "select",
        DOMAIN,
        unique_id,
    )

    if entity_id is not None:
        entity_registry.async_remove(
            entity_id
        )

    unique_id = (
        f"{entry.entry_id}_description_text"
    )

    entity_id = entity_registry.async_get_entity_id(
        "text",
        DOMAIN,
        unique_id,
    )

    if entity_id is not None:
        entity_registry.async_remove(
            entity_id
        )

    unique_id = (
        f"{entry.entry_id}_description_write"
    )

    entity_id = entity_registry.async_get_entity_id(
        "button",
        DOMAIN,
        unique_id,
    )

    if entity_id is not None:
        entity_registry.async_remove(
            entity_id
        )

    unique_id = (
        f"{entry.entry_id}_sensor_setpoint_sensor"
    )

    entity_id = entity_registry.async_get_entity_id(
        "select",
        DOMAIN,
        unique_id,
    )

    if entity_id is not None:
        entity_registry.async_remove(
            entity_id
        )

    unique_id = (
        f"{entry.entry_id}_sensor_setpoint_value"
    )

    entity_id = entity_registry.async_get_entity_id(
        "number",
        DOMAIN,
        unique_id,
    )

    if entity_id is not None:
        entity_registry.async_remove(
            entity_id
        )

    unique_id = (
        f"{entry.entry_id}_sensor_setpoint_write"
    )

    entity_id = entity_registry.async_get_entity_id(
        "button",
        DOMAIN,
        unique_id,
    )

    if entity_id is not None:
        entity_registry.async_remove(
            entity_id
        )


def _async_remove_extra_resource_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    resources: list[GHLDiscoveredResource],
) -> None:
    """Remove entities that only exist when all resources are shown."""

    entity_registry = er.async_get(hass)

    for resource in resources:
        if resource.index is None:
            continue

        if (
            resource.resource == "SWITCHCHANNEL"
            and resource.description is None
        ):
            unique_ids = [
                (
                    "binary_sensor",
                    f"{entry.entry_id}_switchchannel_"
                    f"{resource.index}_actstate",
                ),
                (
                    "sensor",
                    f"{entry.entry_id}_switchchannel_"
                    f"{resource.index}_actcurrent",
                ),
            ]

        elif (
            resource.resource == "DOSER"
            and resource.description is None
        ):
            unique_ids = [
                (
                    "sensor",
                    f"{entry.entry_id}_doser_"
                    f"{resource.index}_filllevel",
                ),
                (
                    "sensor",
                    f"{entry.entry_id}_doser_"
                    f"{resource.index}_capacity",
                ),
            ]

        elif (
            resource.resource == "FLOWSENSOR"
            and resource.description is None
        ):
            unique_ids = [
                (
                    "sensor",
                    f"{entry.entry_id}_flowsensor_"
                    f"{resource.index}_actflow",
                ),
            ]

        elif (
            resource.resource == "ILLUMINATION"
            and int(
                resource.data.get(
                    "point_count",
                    0,
                )
            ) <= 0
        ):
            unique_ids = [
                (
                    "sensor",
                    f"{entry.entry_id}_illumination_"
                    f"{resource.index}_actbrightness",
                ),
            ]

        else:
            continue

        for platform, unique_id in unique_ids:
            entity_id = entity_registry.async_get_entity_id(
                platform,
                DOMAIN,
                unique_id,
            )

            if entity_id is not None:
                entity_registry.async_remove(
                    entity_id
                )


def _merge_known_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    discovered_resources: list[GHLDiscoveredResource],
) -> list[GHLDiscoveredResource]:
    """Merge currently discovered sensors with permanently known sensors."""

    known_sensors = {
        key: dict(value)
        for key, value in entry.data.get(
            CONF_KNOWN_SENSORS,
            {},
        ).items()
    }

    current_sensors = {
        resource.index: resource
        for resource in discovered_resources
        if (
            resource.resource == "SENSOR"
            and resource.index is not None
        )
    }

    known_sensors_changed = False

    for index, resource in current_sensors.items():
        sensor_key = str(index)

        known_sensor = known_sensors.get(
            sensor_key,
            {},
        )

        known_description = known_sensor.get(
            "description",
        )

        description = (
            resource.description
            if resource.description is not None
            else known_description
        )

        known_features = dict(
            known_sensor.get(
                "features",
                {},
            )
        )

        merged_features = dict(known_features)

        for feature, available in resource.features.items():
            merged_features[feature] = (
                merged_features.get(feature, False)
                or available
            )

        resource.description = description
        resource.features = merged_features

        sensor_data = {
            "description": description,
            "features": merged_features,
        }

        if known_sensors.get(sensor_key) != sensor_data:
            known_sensors[sensor_key] = sensor_data
            known_sensors_changed = True

    for sensor_key, sensor_data in known_sensors.items():
        index = int(sensor_key)

        if index in current_sensors:
            continue

        discovered_resources.append(
            GHLDiscoveredResource(
                resource="SENSOR",
                index=index,
                description=sensor_data.get(
                    "description",
                ),
                features=dict(
                    sensor_data.get(
                        "features",
                        {},
                    )
                ),
            )
        )

    if known_sensors_changed:
        new_data = dict(entry.data)

        new_data[CONF_KNOWN_SENSORS] = known_sensors

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
        )

    return discovered_resources


def _async_check_new_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    discovered_resources,
) -> None:
    """Create or remove a repair issue for newly discovered sensors."""

    issue_id = f"{ISSUE_NEW_SENSORS_PREFIX}_{entry.entry_id}"

    if CONF_SENSOR_TYPES not in entry.options:
        ir.async_delete_issue(
            hass,
            DOMAIN,
            issue_id,
        )
        return

    configured_sensor_types = entry.options.get(
        CONF_SENSOR_TYPES,
        {},
    )

    unconfigured_sensors = [
        resource
        for resource in discovered_resources
        if (
            resource.resource == "SENSOR"
            and resource.index is not None
            and str(resource.index) not in configured_sensor_types
        )
    ]

    if not unconfigured_sensors:
        ir.async_delete_issue(
            hass,
            DOMAIN,
            issue_id,
        )
        return

    sensor_names = []

    for resource in unconfigured_sensors:
        if resource.description is not None:
            sensor_names.append(resource.description)
        else:
            sensor_names.append(
                f"Sensor {resource.index + 1}"
            )

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="new_sensors",
        translation_placeholders={
            "sensor_names": ", ".join(sensor_names),
        },
        data={
            "entry_id": entry.entry_id,
        },
    )