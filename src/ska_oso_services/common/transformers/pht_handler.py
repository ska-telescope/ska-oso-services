from datetime import datetime, timezone


def transform_update_proposal(data: dict) -> dict:
    """
    Transforms and updates a given data dictionary with specific operations.

    The function performs the following transformations:
    - Sets the 'proposal_id' field to "12345" if the original 'proposal_id' is "new".
    - Adds or modifies date-related metadata.
    - Rounds 'right_ascension' and 'declination' in 'targets' to 3 decimal places.
    - Changes the units of 'right_ascension' and 'declination' to degrees.

    Parameters:
    data (dict): A dictionary containing various fields, including 'proposal_id',
                 'submitted_by', 'submitted_on', and nested 'info'
                 which includes 'investigators' and 'targets'.

    Returns:
    dict: The transformed and updated data dictionary.
    """

    if not data:
        return {}

    # Constructing and returning the updated data
    if data.get("submitted_by"):
        # Constructing and returning the updated data
        return {
            "prsl_id": data["prsl_id"] if data["prsl_id"] != "new" else "12345",
            "cycle": data["cycle"],
            "submitted_by": data["submitted_by"],
            "submitted_on": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "submitted" if data["submitted_on"] else "draft",
            "investigator_refs": [
                user["investigator_id"]
                for user in data.get("info", {}).get("investigators", [])
            ],
            "info": data.get("info", {}),
        }
    else:
        return {
            "prsl_id": data["prsl_id"],
            "cycle": data["cycle"],
            "status": "submitted" if data.get("submitted_on") else "draft",
            "investigator_refs": [
                user["investigator_id"]
                for user in data.get("info", {}).get("investigators", [])
            ],
            "info": data.get("info", {}),
        }


def transform_create_proposal(data: dict) -> dict:
    """
    Transforms and updates a given data dictionary with specific operations.

    The function performs the following transformations:
    - Sets the 'proposal_id' field to "new" .
    - Adds or modifies date-related metadata.

    Parameters:
    data (dict): A dictionary containing various fields, including 'proposal_id',
                 'submitted_by', 'submitted_on', and nested 'info'
                 which includes 'investigators' and 'targets'.

    Returns:
    dict: The updated data dictionary.
    """
    return {
        "prsl_id": None,
        "status": "draft",
        "info": data.get("info", {}),
        "cycle": data.get("cycle", {}),
        "investigator_refs": [
            user["investigator_id"]
            for user in data.get("info", {}).get("investigators", [])
        ],
    }
