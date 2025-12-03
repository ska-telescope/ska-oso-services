"""
Component level tests for the /validation paths of ska-oso-services API.

These will run from a test pod inside a kubernetes cluster, making requests
to a deployment of ska-oso-services in the same cluster
"""

# pylint: disable=missing-timeout
from http import HTTPStatus

from ska_oso_pdm import ICRSCoordinates
from ska_oso_pdm.builders import LowSBDefinitionBuilder
from ska_oso_pdm.builders.target_builder import LowTargetBuilder

from . import OSO_SERVICES_URL


def test_sbd_validate(authrequests):
    """
    Test that the POST /sbds/validate path receives the request
    and returns the correct response
    """

    sbd = LowSBDefinitionBuilder(
        targets=[
            LowTargetBuilder(
                name="JVAS 1938+666",
                reference_coordinate=ICRSCoordinates(
                    ra_str="19:38:25.2890", dec_str="+66:48:52.915"
                ),
            )
        ]
    )

    response = authrequests.post(
        f"{OSO_SERVICES_URL}/validate/sbd",
        data=sbd.model_dump_json(),
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result["valid"] is False
    assert result["issues"] == [
        {
            "field": "targets.0",
            "level": "error",
            "message": "Source never rises above the horizon",
        }
    ]
