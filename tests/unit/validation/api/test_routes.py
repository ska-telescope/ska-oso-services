from http import HTTPStatus
from unittest import mock

from ska_oso_services.validation.api.routes import ValidationResponse
from ska_oso_services.validation.model import ValidationIssue
from tests.unit.conftest import APP_BASE_API_URL
from tests.unit.util import VALID_MID_SBDEFINITION_JSON

VALIDATE_API = f"{APP_BASE_API_URL}/validate"


@mock.patch("ska_oso_services.validation.api.routes.validate_sbdefinition")
def test_validate_valid_sbd(mock_validate, client):
    """
    Check the validate_sbd handles a valid return value from the
    validation layer and creates the correct response
    """
    mock_validate.return_value = []
    response = client.post(
        f"{VALIDATE_API}/sbd",
        data=VALID_MID_SBDEFINITION_JSON,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json() == {"valid": True, "issues": []}


@mock.patch("ska_oso_services.validation.api.routes.validate_sbdefinition")
def test_validate_invalid_sbd(mock_validate, client):
    """
    Check the validate_sbd handles an invalid result from the
    validation layer and creates the correct response
    """
    validate_result = [ValidationIssue(message="test invalid result")]
    mock_validate.return_value = validate_result

    response = client.post(
        f"{VALIDATE_API}/sbd",
        data=VALID_MID_SBDEFINITION_JSON,
        headers={"Content-type": "application/json"},
    )

    assert response.status_code == HTTPStatus.OK
    expected = ValidationResponse(valid=False, issues=validate_result)
    assert response.json() == expected.model_dump(mode="json")
