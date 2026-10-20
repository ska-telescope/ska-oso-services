from http import HTTPStatus
from unittest import mock

from ska_ost_osd.osd.models.configuration import Configuration

from tests.conftest import TEST_BASE_API_URL

OSD_API_URL = f"{TEST_BASE_API_URL}/osd"

CONSTRAINTS = {
    "sun_avoidance_angle_deg": 30.0,
    "moon_avoidance_angle_deg": 10.0,
    "jupiter_avoidance_angle_deg": 10.0,
    "min_elevation_deg": 15.0,
    "max_elevation_deg": 85.0,
}

POLICY = {
    "cycle_number": 1,
    "type": "Science Verification",
    "cycle_description": "Science Verification",
    "cycle_information": {
        "cycle_id": "SKAO_2027_1",
        "proposal_open": "2026-03-27T12:00:00.000Z",
        "proposal_close": "2026-05-12T15:00:00.000Z",
    },
    "cycle_policies": {"normal_max_hours": 100.0},
    "telescope_capabilities": {"Mid": None, "Low": "AA2_SV"},
}

CONFIGURATION = Configuration.model_validate(
    {
        "ska_mid": {
            "frequency_band": [
                {"rx_id": "Band_1", "min_frequency_hz": 350e6, "max_frequency_hz": 1050e6}
            ],
            "constraints": CONSTRAINTS,
            "subarrays": [],
            "spfrx_defaults": {
                "target_spfrx": {"noise_diode_options": [], "default_noise_diode_mode": "off"},
                "csp_spfrx": {"sync_pps": "unset", "saturation_threshold": 0.2},
            },
        },
        "ska_low": {
            "frequency_band": {
                "min_frequency_hz": 50e6,
                "max_frequency_hz": 350e6,
                "min_coarse_channel": 64,
                "max_coarse_channel": 447,
                "coarse_channel_width_hz": 781250.0,
                "number_continuum_channels_per_coarse_channel": 144,
                "number_zoom_channels_per_coarse_channel": 432,
                "number_pst_channels_per_coarse_channel": 216,
                "number_pss_channels_per_coarse_channel": 54,
            },
            "constraints": CONSTRAINTS,
            "quality_attribute_metrics": {
                "cbf": {"processors_ready_percent": 100.0, "alveo_configured_percent": 100.0}
            },
            "subarrays": [],
        },
        "observatory_policies": [POLICY, {**POLICY, "cycle_number": 2}],
    }
)


class TestOSD:
    @mock.patch("ska_oso_services.common.api.osd.configuration_from_osd")
    def test_success(self, mock_configuration_from_osd, client):
        """
        Test the OSD configuration is returned unchanged
        """
        mock_configuration_from_osd.return_value = CONFIGURATION

        response = client.get(OSD_API_URL)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == CONFIGURATION.model_dump(mode="json", by_alias=True)

    @mock.patch("ska_oso_services.common.api.osd.configuration_from_osd")
    def test_returns_the_observatory_policies(self, mock_configuration_from_osd, client):
        """
        Test each cycle's observatory policy is returned
        """
        mock_configuration_from_osd.return_value = CONFIGURATION

        response = client.get(OSD_API_URL)

        assert response.status_code == HTTPStatus.OK
        policies = response.json()["observatory_policies"]
        assert [policy["cycle_number"] for policy in policies] == [1, 2]
        assert policies[0]["cycle_information"]["cycle_id"] == "SKAO_2027_1"
        assert policies[0]["telescope_capabilities"] == {"Mid": None, "Low": "AA2_SV"}
