from http import HTTPStatus
from unittest import mock

from tests.unit.conftest import APP_BASE_API_URL

VISIBILITY_API_URL = f"{APP_BASE_API_URL}/visibility"

_FAKE_SVG = b"<svg></svg>"
_COMMON_PARAMS = "ra=10h00m00s&dec=-30d00m00s&array=LOW"


class TestVisibilitySvgEndpoint:
    def test_returns_svg_response(self, client):
        with mock.patch(
            "ska_oso_services.common.api.visibility.render_svg", return_value=_FAKE_SVG
        ):
            response = client.get(f"{VISIBILITY_API_URL}/visibility?{_COMMON_PARAMS}")

        assert response.status_code == HTTPStatus.OK
        assert response.headers["content-type"] == "image/svg+xml"
        assert response.content == _FAKE_SVG

    @mock.patch("ska_oso_services.common.api.visibility.render_svg", return_value=_FAKE_SVG)
    def test_show_ateam_defaults_to_true(self, mock_render, client):
        client.get(f"{VISIBILITY_API_URL}/visibility?{_COMMON_PARAMS}")

        _, kwargs = mock_render.call_args
        assert kwargs["show_ateam"] is True

    @mock.patch("ska_oso_services.common.api.visibility.render_svg", return_value=_FAKE_SVG)
    def test_show_ateam_false_passed_through(self, mock_render, client):
        client.get(f"{VISIBILITY_API_URL}/visibility?{_COMMON_PARAMS}&show_ateam=false")

        _, kwargs = mock_render.call_args
        assert kwargs["show_ateam"] is False

    @mock.patch("ska_oso_services.common.api.visibility.render_svg", return_value=_FAKE_SVG)
    def test_show_ateam_true_passed_through(self, mock_render, client):
        client.get(f"{VISIBILITY_API_URL}/visibility?{_COMMON_PARAMS}&show_ateam=true")

        _, kwargs = mock_render.call_args
        assert kwargs["show_ateam"] is True

    def test_invalid_array_returns_error(self, client):
        response = client.get(
            f"{VISIBILITY_API_URL}/visibility?ra=10h00m00s&dec=-30d00m00s&array=INVALID"
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
