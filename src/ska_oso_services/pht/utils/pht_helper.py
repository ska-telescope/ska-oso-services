"""Transform and update proposal data.
This module contains functions to transform and update proposal data
for submission and creation processes.
"""

import uuid
from typing import Any, Optional

from ska_oso_services.common.error_handling import DuplicateError


def generate_entity_id(entity_name: str) -> str:
    """
    Generate a unique ID for an entity with the given prefix.

    Args:
        entity_name (str): The name/prefix for the entity, e.g., "panel", "prsl".

    Returns:
        str: A unique ID in the format "<entity_name>-<uuid-part>".
    """
    # TODO: Remove this once the uuid generator by Brendan works!
    return f"{entity_name.lower()}-skao-{uuid.uuid4().hex[:9]}"


def _get_attr_or_key(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def get_latest_entity_by_id(entities: Optional[list[Any]], entity_id: str) -> list[Any]:
    """
    Returns the latest version of each entity based on a unique identifier.
    Works for dicts and objects.
    """
    if not entities:
        return []

    latest = {}
    for entity in entities:
        key = _get_attr_or_key(entity, entity_id)
        metadata = _get_attr_or_key(entity, "metadata", {})
        version = _get_attr_or_key(metadata, "version", 0)
        if key is None:
            continue  # skip entities with no key
        # Only keep new version
        old_version = 0
        if key in latest:
            old_metadata = _get_attr_or_key(latest[key], "metadata", {})
            old_version = _get_attr_or_key(old_metadata, "version", 0)
        if key not in latest or version > old_version:
            latest[key] = entity

    return list(latest.values())


def validate_duplicates(collection: list, field: str) -> list:
    """Validates the collection does not have field attributes duplicates
    and if so raises the DuplicateError.
    """

    result = []
    seen = set()
    duplicates = set()

    for obj in collection:
        element = getattr(obj, field)

        result.append(element)

        if element in seen:
            duplicates.add(element)
        else:
            seen.add(element)

    if duplicates:
        msg = f"Duplicate {field} are not allowed: {duplicates}"
        raise DuplicateError(msg)

    return result
