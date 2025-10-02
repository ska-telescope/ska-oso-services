from unittest import mock

import pytest

from ska_oso_services.common.error_handling import OSDError
from ska_oso_services.odt.api.sdp import get_params, get_versions


class TestGetSdpScriptsAPI:
    def test_get_script_versions_with_helm(self):
        with mock.patch.dict("os.environ", {"SDP_SCRIPT_TMDATA": "file://tmdata"}):
            versions = get_versions()
            assert {
                "name": "vis-receive",
                "version": "5.1.0",
                "params": "vis-receive/vis-receive-params-2.json",
            } in versions

    def test_get_script_versions_with_bad_helm(self):
        with mock.patch.dict("os.environ", {"SDP_SCRIPT_TMDATA": "junk"}):
            with pytest.raises(OSDError) as excinfo:
                get_versions()
                assert " Failed to fetch SDP script versions" in str(excinfo.value)

    def test_get_script_versions_with_default(self):
        versions = get_versions()
        assert {
            "name": "vis-receive",
            "version": "5.1.0",
            "params": "vis-receive/vis-receive-params-2.json",
        } in versions

    def test_get_script_versions_exception(self):
        with mock.patch(
            "ska_oso_services.odt.api.sdp.get_scriptVersions",
            side_effect=Exception("Failed"),
        ):
            with pytest.raises(Exception) as excinfo:
                get_versions()
            assert "Failed" in str(excinfo.value)

    def test_get_params_expected_output(self):
        expected = {
            "channels_per_port": 1,
            "processes_per_node": 1,
            "max_ports_per_node": None,
            "num_nodes": None,
            "port_start": 21000,
            "transport_protocol": "udp",
            "use_network_definition": None,
            "reception_network": "auto",
            "dry_run": False,
            "telstate": None,
            "processors": {"mswriter": {}},
        }
        with mock.patch(
            "ska_oso_services.odt.api.sdp.get_scriptParams", return_value=expected
        ):
            result = get_params(name="vis-receive", version="2")
            assert isinstance(result, dict)
            assert result["channels_per_port"] == 1
            assert result["processes_per_node"] == 1
            assert result["max_ports_per_node"] is None
            assert result["num_nodes"] is None
            assert result["port_start"] == 21000
            assert result["transport_protocol"] == "udp"
            assert result["use_network_definition"] is None
            assert result["reception_network"] == "auto"
            assert result["dry_run"] is False
            assert result["telstate"] is None
            assert isinstance(result["processors"], dict)
            assert "mswriter" in result["processors"]
            assert result["processors"]["mswriter"] == {}

    def test_get_params_exception(self):
        with pytest.raises(OSDError) as excinfo:
            get_params("bad", "input")
        assert "Failed to fetch SDP script parameters" in str(excinfo.value)
