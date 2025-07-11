"""Transform and update proposal data.
This module contains functions to transform and update proposal data
for submission and creation processes.
"""

from datetime import datetime, timezone

from ska_oso_pdm.proposal import Proposal

EXAMPLE_OSD_DATA = {
    "observatory_policy": {
        "cycle_number": 1,
        "cycle_description": "Science Verification",
        "cycle_information": {
            "cycle_id": "SKAO_2027_1",
            "proposal_open": "20260327T12:00:00.000Z",
            "proposal_close": "20260512T15:00:00.000z",
        },
        "cycle_policies": {"normal_max_hours": 100.0},
        "telescope_capabilities": {"Mid": "AA2", "Low": "AA2"},
    },
    "capabilities": {
        "mid": {
            "basic_capabilities": {
                "dish_elevation_limit_deg": 15.0,
                "receiver_information": [
                    {
                        "rx_id": "Band_1",
                        "min_frequency_hz": 350000000.0,
                        "max_frequency_hz": 1050000000.0,
                    },
                    {
                        "rx_id": "Band_2",
                        "min_frequency_hz": 950000000.0,
                        "max_frequency_hz": 1760000000.0,
                    },
                    {
                        "rx_id": "Band_3",
                        "min_frequency_hz": 1650000000.0,
                        "max_frequency_hz": 3050000000.0,
                    },
                    {
                        "rx_id": "Band_4",
                        "min_frequency_hz": 2800000000.0,
                        "max_frequency_hz": 5180000000.0,
                    },
                    {
                        "rx_id": "Band_5a",
                        "min_frequency_hz": 4600000000.0,
                        "max_frequency_hz": 8500000000.0,
                    },
                    {
                        "rx_id": "Band_5b",
                        "min_frequency_hz": 8300000000.0,
                        "max_frequency_hz": 15400000000.0,
                    },
                ],
            },
            "AA2": {
                "available_receivers": ["Band_1", "Band_2", "Band_5a", "Band_5b"],
                "number_ska_dishes": 64,
                "number_meerkat_dishes": 4,
                "number_meerkatplus_dishes": 0,
                "max_baseline_km": 110.0,
                "available_bandwidth_hz": 800000000.0,
                "number_channels": 14880,
                "cbf_modes": ["CORR", "PST_BF", "PSS_BF"],
                "number_zoom_windows": 16,
                "number_zoom_channels": 14880,
                "number_pss_beams": 384,
                "number_pst_beams": 6,
                "ps_beam_bandwidth_hz": 800000000.0,
                "number_fsps": 4,
            },
        },
        "low": {
            "basic_capabilities": {
                "min_frequency_hz": 50000000.0,
                "max_frequency_hz": 350000000.0,
            },
            "AA2": {
                "number_stations": 64,
                "number_substations": 720,
                "number_beams": 8,
                "max_baseline_km": 40.0,
                "available_bandwidth_hz": 150000000.0,
                "channel_width_hz": 5400,
                "cbf_modes": ["vis", "pst", "pss"],
                "number_zoom_windows": 16,
                "number_zoom_channels": 1800,
                "number_pss_beams": 30,
                "number_pst_beams": 4,
                "number_vlbi_beams": 0,
                "ps_beam_bandwidth_hz": 118000000.0,
                "number_fsps": 10,
            },
        },
    },
}

EXAMPLE_PROPOSAL = {
    "prsl_id": "prp-ska01-202204-02",
    "status": "draft",
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
