"""Transform and update proposal data.
This module contains functions to transform and update proposal data
for submission and creation processes.
"""

from typing import Any, Optional

from ska_ser_skuid import EntityType, mint_skuid

from ska_oso_services.common.error_handling import DuplicateError


def generate_entity_id(entity_name: str) -> str:
    """
    Generate a unique ID for an entity with the given prefix using SKUID.

    Args:
        entity_name (str): The name/prefix for the entity (e.g., "pnl", "rvw",
            "pnld", "prpacc").

    Returns:
        str: A unique ID in SKUID short form format "<prefix>-<shorthash>".
    """
    # Map entity name prefixes to EntityType
    entity_type_map = {
        "pnl": EntityType.PNL,
        "rvw": EntityType.RVW,
        "pnld": EntityType.PNLD,
        "prpacc": EntityType.PRP,  # No specific PROPOSAL_ACCESS type, use PRP
        "prp": EntityType.PRP,
    }

    # Get entity type or default to PRP if not found
    entity_type = entity_type_map.get(entity_name.lower(), EntityType.PRP)

    return str(mint_skuid(entity_type=entity_type))


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
