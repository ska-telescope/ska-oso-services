from unittest import mock

from ska_oso_services.common import itfmapper
from ska_oso_services.common.itfmapper import Station, SubarrayDetail
from ska_oso_services.common.osdmapper import (
    Configuration,
    LowFrequencyBand,
    configuration_from_osd,
)
from ska_oso_services.odt.api import configuration as configuration_api
from ska_oso_services.odt.api.configuration import configuration_get
from ska_oso_services.validation.model import ValidationIssue, ValidationIssueType


def test_configuration_get():
    """
    This isn't really a unit test as it actually calls the OSD. Mocking out the
    OSD and returning the same data structure seems more effort than it is worth
    currently. As the OSD becomes better typed with the conversion to FastAPI
    as our use case expands, we can rethink these tests.
    """

    response = configuration_get()

    assert isinstance(response, Configuration)
    assert response.ska_low.frequency_band == LowFrequencyBand(
        min_frequency_hz=50e6,
        max_frequency_hz=350e6,
        min_coarse_channel=64,
        max_coarse_channel=447,
        coarse_channel_width_hz=781250.0,
        number_continuum_channels_per_coarse_channel=144,
        number_zoom_channels_per_coarse_channel=432,
        number_pst_channels_per_coarse_channel=216,
        number_pss_channels_per_coarse_channel=54,
    )
    assert len(response.ska_mid.frequency_band) == 6
    assert len(response.ska_mid.subarrays) == 4
    assert len(response.ska_low.subarrays) == 5
    low_itf = _low_subarray(response, "Low_ITF")
    assert [
        (detail.name, [(station.id, station.label) for station in detail.allowed_stations])
        for detail in low_itf.subarray_details
    ] == [
        ("SKA-Low-ITF-CI", [(51, "ci5-1"), (52, "ci5-2")]),
        ("SKA-Low-ITF-EM", [(31, "em3-1"), (32, "em3-2"), (41, "em4-1"), (42, "em4-2")]),
    ]
    assert all(
        subarray.subarray_details is None
        for subarray in response.ska_low.subarrays
        if subarray.name != "Low_ITF"
    )
    assert len(response.ska_mid.frequency_band[-1].band5b_subbands) == 3


def test_configuration_get_succeeds_when_itf_tmdata_is_unavailable():
    """
    The ITF subarray details are supplementary, so a failure to retrieve them
    should not affect the rest of the configuration.
    """
    itfmapper._CACHE.clear()
    with mock.patch.object(itfmapper, "TMData", side_effect=RuntimeError("unreachable")):
        response = configuration_get()
    itfmapper._CACHE.clear()

    assert _low_subarray(response, "Low_ITF").subarray_details is None
    assert response.issues == []
    assert len(response.ska_low.subarrays) == 5
    assert len(response.ska_mid.subarrays) == 4


def test_configuration_get_reports_stations_not_in_osd_receptors():
    """
    The test ITF stations (31, 32, 41, 42, 51, 52) are not in the OSD Low_ITF
    receptors, so each ITF subarray should be reported as a warning.
    """
    response = configuration_get()

    assert response.issues == [
        ValidationIssue(
            message="The allowed stations [51, 52] of the 'SKA-Low-ITF-CI' subarray are not "
            "in the OSD receptors of the 'Low_ITF' subarray. They have been added to its "
            "receptors, but may fail validation against it.",
            field="$.ska_low.subarrays[4].subarray_details[0].allowed_stations",
            level=ValidationIssueType.WARNING,
        ),
        ValidationIssue(
            message="The allowed stations [31, 32, 41, 42] of the 'SKA-Low-ITF-EM' subarray are "
            "not in the OSD receptors of the 'Low_ITF' subarray. They have been added to its "
            "receptors, but may fail validation against it.",
            field="$.ska_low.subarrays[4].subarray_details[1].allowed_stations",
            level=ValidationIssueType.WARNING,
        ),
    ]


def test_configuration_get_adds_itf_stations_to_low_itf_receptors():
    osd_receptors = _low_subarray(configuration_from_osd(), "Low_ITF").receptors

    response = configuration_get()

    # The OSD receptors come first, followed by the missing ITF stations in TMData order
    assert _low_subarray(response, "Low_ITF").receptors == osd_receptors + [51, 52, 31, 32, 41, 42]
    # The cached OSD configuration and the other subarrays are unchanged
    assert _low_subarray(configuration_from_osd(), "Low_ITF").receptors == osd_receptors
    assert _low_subarray(response, "AA1").receptors == (
        _low_subarray(configuration_from_osd(), "AA1").receptors
    )


def test_configuration_get_does_not_duplicate_receptors_already_in_osd():
    osd_receptors = _low_subarray(configuration_from_osd(), "Low_ITF").receptors
    detail = _detail_with_stations([osd_receptors[0], 1, 1])

    with mock.patch.object(configuration_api, "get_itf_subarrays", return_value=[detail]):
        response = configuration_get()

    assert _low_subarray(response, "Low_ITF").receptors == osd_receptors + [1]


def test_configuration_get_has_no_issues_when_stations_are_in_osd_receptors():
    detail = _detail_with_stations(_low_subarray(configuration_from_osd(), "Low_ITF").receptors)

    with mock.patch.object(
        configuration_api, "get_itf_subarrays", return_value=[detail]
    ) as mock_get_itf_subarrays:
        response = configuration_get()

    assert response.issues == []
    # No mismatch, so no refresh is requested
    mock_get_itf_subarrays.assert_called_once_with()


def test_configuration_get_refreshes_itf_data_when_stations_are_not_in_osd_receptors():
    low_itf_receptors = _low_subarray(configuration_from_osd(), "Low_ITF").receptors
    mismatched = _detail_with_stations([1])
    corrected = _detail_with_stations(low_itf_receptors)

    with mock.patch.object(
        configuration_api, "get_itf_subarrays", side_effect=[[mismatched], [corrected]]
    ) as mock_get_itf_subarrays:
        response = configuration_get()

    assert mock_get_itf_subarrays.call_args_list == [mock.call(), mock.call(refresh=True)]
    assert response.issues == []
    assert _low_subarray(response, "Low_ITF").subarray_details == [corrected]


def _detail_with_stations(station_ids):
    return SubarrayDetail(
        name="SKA-Low-ITF-TEST",
        allowed_stations=[Station(id=station_id, label="s") for station_id in station_ids],
    )


def test_configuration_get_does_not_modify_cached_osd_configuration():
    configuration_get()

    assert _low_subarray(configuration_from_osd(), "Low_ITF").subarray_details is None


def _low_subarray(configuration, name):
    return next(subarray for subarray in configuration.ska_low.subarrays if subarray.name == name)
