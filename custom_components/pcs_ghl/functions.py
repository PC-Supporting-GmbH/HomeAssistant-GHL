"""Validate text used in GHL commands."""

from __future__ import annotations

from unicodedata import category

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DESCRIPTION_TEXT_MAX_LENGTH, DOMAIN


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


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the common device information for a GHL config entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
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
