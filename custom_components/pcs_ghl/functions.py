"""Validate text used in GHL commands."""

from __future__ import annotations

from unicodedata import category

from .const import DESCRIPTION_TEXT_MAX_LENGTH


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
