
"Functions to transform data for proposal creation and tracking in the ODA."


def transform_create_proposal(data: dict) -> dict:
    """
    Transforms and updates a given data dictionary with specific operations.

    The function performs the following transformations:
    - Sets the 'proposal_id' field to "new" .

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
      
    }
