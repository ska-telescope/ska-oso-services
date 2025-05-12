"""Transform and update proposal data.
This module contains functions to transform and update proposal data
for submission and creation processes.
"""

from datetime import datetime, timezone

from ska_oso_pdm.proposal import Proposal

EXAMPLE_PROPOSAL = {
    "prsl_id": "prp-ska01-202204-02",
    "status": "",
    "cycle": "5000_2023",
    "info": {
        "title": "The Milky Way View",
        "proposal_type": {
            "main_type": "standard_proposal",
            "attributes": ["coordinated_proposal"],
        },
    },
}


def transform_update_proposal(data: Proposal) -> Proposal:
    """
    Transforms and updates a given Proposal model.

    - If prsl_id is "new", sets it to "12345".
    - Sets submitted_on to now if submitted_by is provided.
    - Sets status based on presence of submitted_on.
    - Extracts investigator_refs from info.investigators.
    """

    # TODO : rethink the logic here - may need to move to UI
    if data.submitted_by:
        submitted_on = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "submitted"
    else:
        submitted_on = data.submitted_on
        status = "submitted" if submitted_on else "draft"

    investigator_refs = [inv.investigator_id for inv in data.info.investigators]

    return Proposal(
        prsl_id=data.prsl_id,
        cycle=data.cycle,
        submitted_by=data.submitted_by,
        submitted_on=submitted_on,
        status=status,
        info=data.info,
        investigator_refs=investigator_refs,
    )



