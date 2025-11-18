from datetime import datetime, timezone
from unittest import mock

import numpy as np

from ska_oso_services.common import visibility


class TestVisibilityRenderSvg:
    @mock.patch("ska_oso_services.common.visibility.datetime")
    def test_render_svg_returns_valid_svg_bytes(self, mock_datetime):
        fixed_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_now

        svg_bytes = visibility.render_svg(
            ra="10h00m00s",
            dec="-30d00m00s",
            site=visibility.SITES["LOW"].location,
            min_elev=20.0,
            step_s=3600,
        )

        assert isinstance(svg_bytes, bytes)
        assert len(svg_bytes) > 0
        svg_text = svg_bytes.decode("utf-8")
        assert "<svg" in svg_text

    @mock.patch("ska_oso_services.common.visibility._visible_duration")
    @mock.patch("ska_oso_services.common.visibility._alts")
    def test_render_svg_with_mixed_altitudes(self, mock_alts, mock_visible_duration):
        times = [datetime(2025, 1, 1, h, 0, 0, tzinfo=timezone.utc) for h in range(3)]
        alt = np.array([-5.0, 10.0, 30.0], dtype=float)

        mock_alts.return_value = (times, alt)
        mock_visible_duration.return_value = (2 * 3600, 2, 0)

        svg_bytes = visibility.render_svg(
            ra="10h00m00s",
            dec="-30d00m00s",
            site=visibility.SITES["LOW"].location,
            min_elev=20.0,
            step_s=3600,
        )

        assert isinstance(svg_bytes, bytes)
        assert len(svg_bytes) > 0
        assert "<svg" in svg_bytes.decode("utf-8")
