from unittest import mock

import pytest

from ska_oso_services.odt.api.sdp import get_params, get_versions
from tests.unit.conftest import ODT_BASE_API_URL

SDP_API_URL = f"{ODT_BASE_API_URL}/sdp"


class TestGetSdpScriptsAPI:
    def test_get_script_versions_with_helm(self):
        with mock.patch.dict("os.environ", {"SDP_SCRIPT_TMDATA": "file://tests/tmdata"}):
            versions = get_versions("vis-receive")
            assert "5.1.0" in versions
            assert len(versions) == 17

    def test_get_script_versions_with_default_helm(self):
        versions = get_versions("vis-receive")
        assert "5.1.0" in versions

    def test_get_script_with_missing_script(self):
        with mock.patch.dict("os.environ", {"SDP_SCRIPT_TMDATA": "file://tests/tmdata"}):
            versions = get_versions("junk")
            assert len(versions) == 0

    def test_get_script_versions_api(self, client):
        with mock.patch.dict("os.environ", {"SDP_SCRIPT_TMDATA": "file://tests/tmdata"}):
            response = client.get(f"{SDP_API_URL}/scriptVersions/vis-receive")
            assert response.status_code == 200
            assert isinstance(response.json(), list)
            assert "5.1.0" in response.json()

    def test_get_script_versions_with_bad_helm(self):
        with mock.patch.dict("os.environ", {"SDP_SCRIPT_TMDATA": "junk"}):
            with pytest.raises(ValueError) as excinfo:
                get_versions("vis-receive")
                assert "TMData base path error: Base path does not exist" in str(
                    excinfo.value
                )

    def test_get_params_expected_output(self):
        with mock.patch.dict("os.environ", {"SDP_SCRIPT_TMDATA": "file://tests/tmdata"}):
            result = get_params(name="vis-receive", version="5.1.0")
            assert isinstance(result, dict)
            # Check top-level keys
            assert "$defs" in result
            assert "properties" in result
            assert "title" in result
            # Check nested definitions
            assert "NetworkMapping" in result["$defs"]
            assert "PodSettings" in result["$defs"]
            assert "ReceptionNetwork" in result["$defs"]
            assert "SignalDisplay" in result["$defs"]

    def test_get_script_params_api_default_helm(self, client):
        response = client.get(f"{SDP_API_URL}/scriptParams/vis-receive/5.1.0")
        assert response.status_code == 200
        print(response.json())
        assert isinstance(response.json(), dict)
        data = response.json()
        # Check top-level keys
        assert "$defs" in data
        assert "properties" in data
        assert "title" in data
        # Check nested definitions
        assert "NetworkMapping" in data["$defs"]
        assert "PodSettings" in data["$defs"]
        assert "ReceptionNetwork" in data["$defs"]
        assert "SignalDisplay" in data["$defs"]
