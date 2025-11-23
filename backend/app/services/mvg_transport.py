"""Parsing helpers for MVG transport types."""

from __future__ import annotations

from collections.abc import Iterable

from mvg import TransportType


def parse_transport_types(raw_values: Iterable[str]) -> list[TransportType]:
    """Parse transport type strings with deduplication and order preservation.

    Normalizes input strings to TransportType enum values, handling synonyms
    and case variations. Duplicates and synonym collisions are collapsed to
    the first-seen TransportType value, preserving input order for unique types.

    Args:
        raw_values: Iterable of transport type strings (e.g., ["UBAHN", "S-Bahn"])

    Returns:
        List of unique TransportType enums in order of first appearance

    Raises:
        ValueError: If any input string cannot be mapped to a TransportType
    """
    transport_map = {}
    for transport_type in TransportType:
        name_lower = transport_type.name.lower()
        transport_map[name_lower] = transport_type

        if transport_type.value:
            display = transport_type.value[0].lower()
            transport_map[display] = transport_type
            transport_map[display.replace("-", "").replace(" ", "")] = transport_type

    result: list[TransportType] = []
    seen_types: set[TransportType] = set()

    for raw in raw_values:
        key = raw.strip().lower()
        if not key:
            continue

        transport_type = transport_map.get(key)
        if not transport_type:
            clean_key = key.replace("-", "").replace(" ", "")
            transport_type = transport_map.get(clean_key)

        if not transport_type:
            raise ValueError(f"Unsupported transport type '{raw}'.")

        if transport_type not in seen_types:
            result.append(transport_type)
            seen_types.add(transport_type)

    return result


__all__ = ["parse_transport_types"]
