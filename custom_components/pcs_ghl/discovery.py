"""Discovery for GHL devices."""

from __future__ import annotations

import logging

from dataclasses import dataclass, field

from .api import GHLAPI, GHLAPIError
from .const import (
    DEVICE_TYPE_MITRAS_LX7,
    DEVICE_TYPE_MITRAS_LX8,
    DEVICE_TYPE_PROFILUX_4,
    DISCOVERY_LIMIT,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class GHLDiscoveredResource:
    """A resource discovered on a GHL device."""

    resource: str
    index: int | None
    description: str | None = None
    features: dict[str, bool] = field(default_factory=dict)
    data: dict[str, object] = field(default_factory=dict)


def _parse_ack_value(reply: str) -> str | None:
    """Extract the value from a GHL ACK reply."""

    if not reply.startswith("ACK"):
        return None

    if "<" not in reply or ">" not in reply:
        return None

    value = reply.split("<", 1)[1].rsplit(">", 1)[0]

    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]

    if value == "":
        return None

    return value


def _get_effective_maximum_index(maximum_index: int) -> int:
    """Return the maximum index to use during discovery."""

    if DISCOVERY_LIMIT == 0:
        return maximum_index

    return min(
        maximum_index,
        DISCOVERY_LIMIT - 1,
    )


async def _async_get_description(
    api: GHLAPI,
    resource: str,
    index: int,
) -> str | None:
    """Read the description of an indexed GHL resource."""

    command = f"GET {resource}[{index}] DESCRIPTION"

    try:
        reply = await api.async_command(command)

    except GHLAPIError as err:
        _LOGGER.warning(
            "GHL discovery skipped description for %s[%d]: %s",
            resource,
            index,
            err,
        )
        return None

    if reply.startswith("NACK"):
        return None

    if not reply.startswith("ACK"):
        _LOGGER.warning(
            "GHL discovery received unexpected response for %s: %s",
            command,
            reply,
        )
        return None

    description = _parse_ack_value(reply)

    if description is None:
        return None

    return description.rstrip()


async def _async_get_feature_available(
    api: GHLAPI,
    resource: str,
    index: int,
    feature: str,
) -> bool:
    """Return whether an indexed GHL feature is available."""

    command = f"GET {resource}[{index}] {feature}"

    try:
        reply = await api.async_command(command)

    except GHLAPIError as err:
        _LOGGER.warning(
            "GHL discovery skipped %s for %s[%d]: %s",
            feature,
            resource,
            index,
            err,
        )
        return False

    if reply.startswith("ACK"):
        return True

    if reply.startswith("NACK"):
        return False

    _LOGGER.warning(
        "GHL discovery received unexpected response for %s: %s",
        command,
        reply,
    )

    return False


async def _async_get_single_feature_available(
    api: GHLAPI,
    resource: str,
    feature: str,
) -> bool:
    """Return whether a non-indexed GHL feature is available."""

    command = f"GET {resource} {feature}"

    try:
        reply = await api.async_command(command)

    except GHLAPIError as err:
        _LOGGER.warning(
            "GHL discovery skipped %s for %s: %s",
            feature,
            resource,
            err,
        )
        return False

    if reply.startswith("ACK"):
        return True

    if reply.startswith("NACK"):
        return False

    _LOGGER.warning(
        "GHL discovery received unexpected response for %s: %s",
        command,
        reply,
    )

    return False


async def _async_probe_indexed_resource(
    api: GHLAPI,
    resource: str,
    feature: str,
    maximum_index: int,
    read_description: bool,
    always_include: bool = False,
    require_description: bool = False,
) -> list[GHLDiscoveredResource]:
    """Discover indexed GHL resources."""

    discovered: list[GHLDiscoveredResource] = []

    effective_maximum_index = _get_effective_maximum_index(
        maximum_index
    )

    for index in range(effective_maximum_index + 1):
        command = f"GET {resource}[{index}] {feature}"

        try:
            reply = await api.async_command(command)

        except GHLAPIError as err:
            _LOGGER.warning(
                "GHL discovery skipped %s[%d] due to communication error: %s",
                resource,
                index,
                err,
            )

            if not always_include:
                continue

            reply = ""

        feature_available = False

        if reply.startswith("ACK"):
            feature_available = True

        elif reply.startswith("NACK"):
            feature_available = False

        elif reply != "":
            _LOGGER.warning(
                "GHL discovery received unexpected response for %s: %s",
                command,
                reply,
            )

            if not always_include:
                continue

        description = None

        if read_description:
            description = await _async_get_description(
                api,
                resource,
                index,
            )

        if require_description and description is None:
            continue

        if (
            not always_include
            and not feature_available
            and description is None
        ):
            continue

        discovered.append(
            GHLDiscoveredResource(
                resource=resource,
                index=index,
                description=description,
                features={
                    feature: feature_available,
                    "DESCRIPTION": description is not None,
                },
            )
        )

    return discovered


async def _async_probe_illumination_resources(
    api: GHLAPI,
    maximum_index: int,
    show_all_resources: bool = False,
) -> list[GHLDiscoveredResource]:
    """Discover configured GHL illumination channels."""

    discovered: list[GHLDiscoveredResource] = []

    effective_maximum_index = _get_effective_maximum_index(
        maximum_index
    )

    for index in range(effective_maximum_index + 1):
        pointcount_command = (
            f"GET ILLUMINATION[{index}] POINTCOUNT"
        )

        try:
            pointcount_reply = await api.async_command(
                pointcount_command
            )

        except GHLAPIError as err:
            _LOGGER.warning(
                "GHL discovery skipped ILLUMINATION[%d] "
                "POINTCOUNT due to communication error: %s",
                index,
                err,
            )
            continue

        if pointcount_reply.startswith("NACK"):
            continue

        if not pointcount_reply.startswith("ACK"):
            _LOGGER.warning(
                "GHL discovery received unexpected response for %s: %s",
                pointcount_command,
                pointcount_reply,
            )
            continue

        pointcount_value = _parse_ack_value(
            pointcount_reply
        )

        if pointcount_value is None:
            continue

        try:
            pointcount = int(float(pointcount_value))

        except ValueError:
            _LOGGER.warning(
                "GHL discovery received invalid POINTCOUNT "
                "for ILLUMINATION[%d]: %s",
                index,
                pointcount_value,
            )
            continue

        if pointcount <= 0 and not show_all_resources:
            continue

        description = await _async_get_description(
            api,
            "ILLUMINATION",
            index,
        )

        actbrightness_available = (
            await _async_get_feature_available(
                api=api,
                resource="ILLUMINATION",
                index=index,
                feature="ACTBRIGHTNESS",
            )
        )

        curve: list[dict[str, float | int]] = []

        for curvepoint in range(pointcount):
            time_command = (
                f"GET ILLUMINATION[{index}] "
                f"TIME[{curvepoint}]"
            )

            brightness_command = (
                f"GET ILLUMINATION[{index}] "
                f"BRIGHTNESS[{curvepoint}]"
            )

            try:
                time_reply = await api.async_command(
                    time_command
                )

            except GHLAPIError as err:
                _LOGGER.warning(
                    "GHL discovery could not read "
                    "ILLUMINATION[%d] TIME[%d]: %s",
                    index,
                    curvepoint,
                    err,
                )
                continue

            try:
                brightness_reply = await api.async_command(
                    brightness_command
                )

            except GHLAPIError as err:
                _LOGGER.warning(
                    "GHL discovery could not read "
                    "ILLUMINATION[%d] BRIGHTNESS[%d]: %s",
                    index,
                    curvepoint,
                    err,
                )
                continue

            time_value = _parse_ack_value(time_reply)
            brightness_value = _parse_ack_value(
                brightness_reply
            )

            if (
                time_value is None
                or brightness_value is None
            ):
                continue

            try:
                point_time = int(float(time_value))
                point_brightness = float(
                    brightness_value
                )

            except ValueError:
                _LOGGER.warning(
                    "GHL discovery received invalid curve "
                    "data for ILLUMINATION[%d] point %d",
                    index,
                    curvepoint,
                )
                continue

            curve.append(
                {
                    "time": point_time,
                    "brightness": point_brightness,
                }
            )

        discovered.append(
            GHLDiscoveredResource(
                resource="ILLUMINATION",
                index=index,
                description=description,
                features={
                    "ACTBRIGHTNESS": actbrightness_available,
                    "POINTCOUNT": True,
                    "DESCRIPTION": description is not None,
                },
                data={
                    "point_count": pointcount,
                    "curve": curve,
                },
            )
        )

    return discovered


async def _async_probe_single_resource(
    api: GHLAPI,
    resource: str,
    feature: str,
) -> list[GHLDiscoveredResource]:
    """Discover a GHL resource without an index."""

    command = f"GET {resource} {feature}"

    try:
        reply = await api.async_command(command)

    except GHLAPIError as err:
        _LOGGER.warning(
            "GHL discovery skipped %s due to communication error: %s",
            resource,
            err,
        )
        return []

    if reply.startswith("NACK"):
        return []

    if not reply.startswith("ACK"):
        _LOGGER.warning(
            "GHL discovery received unexpected response for %s: %s",
            command,
            reply,
        )
        return []

    return [
        GHLDiscoveredResource(
            resource=resource,
            index=None,
            features={
                feature: True,
            },
        )
    ]


async def async_discover_resources(
    api: GHLAPI,
    device_type: str,
    show_all_resources: bool = False,
) -> list[GHLDiscoveredResource]:
    """Discover resources available on a GHL device."""

    discovered: list[GHLDiscoveredResource] = []

    if device_type == DEVICE_TYPE_PROFILUX_4:
        sensor_resources = await _async_probe_indexed_resource(
            api=api,
            resource="SENSOR",
            feature="ACTVALUE",
            maximum_index=31,
            read_description=True,
        )

        for resource in sensor_resources:
            if resource.index is None:
                continue

            resource.features["DESVALUE"] = (
                await _async_get_feature_available(
                    api=api,
                    resource="SENSOR",
                    index=resource.index,
                    feature="DESVALUE",
                )
            )

        discovered.extend(sensor_resources)

        discovered.extend(
            await _async_probe_indexed_resource(
                api=api,
                resource="SWITCHCHANNEL",
                feature="ACTSTATE",
                maximum_index=63,
                read_description=True,
                require_description=not show_all_resources,
            )
        )

        discovered.extend(
            await _async_probe_illumination_resources(
                api=api,
                maximum_index=31,
                show_all_resources=show_all_resources,
            )
        )

        discovered.extend(
            await _async_probe_indexed_resource(
                api=api,
                resource="DOSER",
                feature="FILLLEVEL",
                maximum_index=31,
                read_description=True,
                require_description=not show_all_resources,
            )
        )

        discovered.extend(
            await _async_probe_indexed_resource(
                api=api,
                resource="FLOWSENSOR",
                feature="ACTFLOW",
                maximum_index=3,
                read_description=True,
                require_description=not show_all_resources,
            )
        )

        discovered.extend(
            await _async_probe_indexed_resource(
                api=api,
                resource="LEVELSENSOR",
                feature="ACTSTATE",
                maximum_index=15,
                read_description=True,
                always_include=True,
            )
        )

        khdirector_resources = await _async_probe_single_resource(
            api=api,
            resource="KHDIRECTOR",
            feature="ACTVALUE",
        )

        for resource in khdirector_resources:
            resource.features["DESVALUE"] = (
                await _async_get_single_feature_available(
                    api=api,
                    resource="KHDIRECTOR",
                    feature="DESVALUE",
                )
            )

        discovered.extend(khdirector_resources)

        iondirector_resources = await _async_probe_indexed_resource(
            api=api,
            resource="IONDIRECTOR",
            feature="ACTVALUE",
            maximum_index=4,
            read_description=False,
        )

        for resource in iondirector_resources:
            if resource.index is None:
                continue

            resource.features["DESVALUE"] = (
                await _async_get_feature_available(
                    api=api,
                    resource="IONDIRECTOR",
                    index=resource.index,
                    feature="DESVALUE",
                )
            )

        discovered.extend(iondirector_resources)

    elif device_type == DEVICE_TYPE_MITRAS_LX7:
        discovered.extend(
            await _async_probe_single_resource(
                api=api,
                resource="SENSOR",
                feature="ACTVALUE",
            )
        )

        discovered.extend(
            await _async_probe_illumination_resources(
                api=api,
                maximum_index=8,
                show_all_resources=show_all_resources,
            )
        )

    elif device_type == DEVICE_TYPE_MITRAS_LX8:
        discovered.extend(
            await _async_probe_single_resource(
                api=api,
                resource="SENSOR",
                feature="ACTVALUE",
            )
        )

        discovered.extend(
            await _async_probe_illumination_resources(
                api=api,
                maximum_index=12,
                show_all_resources=show_all_resources,
            )
        )

    else:
        raise GHLAPIError(
            f"Unsupported GHL device type: {device_type}"
        )

    discovered.extend(
        await _async_probe_single_resource(
            api=api,
            resource="ILLUMINATION",
            feature="MASTERBRIGHTNESS",
        )
    )

    system_resources = await _async_probe_single_resource(
        api=api,
        resource="SYSTEM",
        feature="FIRMWARE",
    )

    for resource in system_resources:
        resource.features["SERIALNUMBER"] = (
            await _async_get_single_feature_available(
                api=api,
                resource="SYSTEM",
                feature="SERIALNUMBER",
            )
        )

        resource.features["UNIXTIME"] = (
            await _async_get_single_feature_available(
                api=api,
                resource="SYSTEM",
                feature="UNIXTIME",
            )
        )

    discovered.extend(system_resources)

    return discovered