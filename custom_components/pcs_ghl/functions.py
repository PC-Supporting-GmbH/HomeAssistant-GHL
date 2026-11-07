"""Validate text used in GHL commands."""
# pyright: reportMissingImports=false

from __future__ import annotations

from unicodedata import category

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_DEVICE_IDENTIFIER, DESCRIPTION_TEXT_MAX_LENGTH, DOMAIN


def has_control_characters(value: str) -> bool:
    """Return whether text contains Unicode control characters."""

    return any(category(character) == "Cc" for character in value)


def is_valid_description(value: str) -> bool:
    """Allow a description only if it preserves the command structure."""

    return (
        len(value) <= DESCRIPTION_TEXT_MAX_LENGTH
        and '"' not in value
        and not has_control_characters(value)
    )


def device_identifier(entry: ConfigEntry) -> str:
    """Return the persisted physical-device identifier."""
    return entry.data[CONF_DEVICE_IDENTIFIER]


class GHLIdentityMixin:
    """Use the technical identity for generated entity IDs, not the friendly name."""

    @property
    def suggested_object_id(self) -> str | None:
        identifier = next(iter(self._attr_device_info["identifiers"]))[1]
        name = super().suggested_object_id
        if not name:
            return self._attr_unique_id
        return f"{identifier}_{name}"


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the common device information for a GHL config entry."""
    identifier = device_identifier(entry)
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        name=entry.title,
        manufacturer="GHL",
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )


def parse_pointcount(
    value: str, *, invalid_message: str = "POINTCOUNT must be a non-negative integer"
) -> int:
    """Parse a finite, non-negative integer curve point count."""
    numeric_pointcount = float(value)
    if not numeric_pointcount.is_integer() or numeric_pointcount < 0:
        raise ValueError(invalid_message)
    return int(numeric_pointcount)
