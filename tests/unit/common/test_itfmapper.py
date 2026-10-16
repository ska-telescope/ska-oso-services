import shutil
from pathlib import Path
from unittest import mock

import pytest

import ska_oso_services.settings as settings_module
from ska_oso_services.common import itfmapper
from ska_oso_services.common.itfmapper import Station, SubarrayDetail, get_itf_subarrays
from ska_oso_services.settings import get_settings

ITF_TMDATA_DIR = Path(__file__).parents[2] / "tmdata_itf"


@pytest.fixture(autouse=True)
def clear_itf_cache():
    itfmapper._CACHE.clear()
    yield
    itfmapper._CACHE.clear()


def _settings_with_low_itf_tmdata(value):
    return mock.patch.object(
        settings_module,
        "SETTINGS",
        get_settings().model_copy(update={"low_itf_tmdata": value}),
    )


def test_get_itf_subarrays_returns_a_subarray_for_each_environment():
    result = get_itf_subarrays()

    assert result == [
        SubarrayDetail(
            name="SKA-Low-ITF-CI",
            allowed_stations=[
                Station(id=51, label="ci5-1"),
                Station(id=52, label="ci5-2"),
            ],
        ),
        SubarrayDetail(
            name="SKA-Low-ITF-EM",
            allowed_stations=[
                Station(id=31, label="em3-1"),
                Station(id=32, label="em3-2"),
                Station(id=41, label="em4-1"),
                Station(id=42, label="em4-2"),
            ],
        ),
    ]


def test_get_itf_subarrays_caches_successful_result():
    get_itf_subarrays()

    with mock.patch.object(itfmapper, "TMData") as mock_tmdata:
        result = get_itf_subarrays()

    mock_tmdata.assert_not_called()
    assert len(result) == 2


def test_get_itf_subarrays_returns_empty_list_without_env():
    with _settings_with_low_itf_tmdata(None):
        with mock.patch.object(itfmapper, "TMData") as mock_tmdata:
            result = get_itf_subarrays()

    mock_tmdata.assert_not_called()
    assert result == []


def test_get_itf_subarrays_returns_empty_list_for_bad_source(tmp_path):
    with _settings_with_low_itf_tmdata(f"file://{tmp_path}/does-not-exist"):
        assert get_itf_subarrays() == []


def test_get_itf_subarrays_returns_empty_list_for_missing_files(tmp_path):
    with _settings_with_low_itf_tmdata(f"file://{tmp_path}"):
        assert get_itf_subarrays() == []


def test_get_itf_subarrays_does_not_cache_failure():
    with mock.patch.object(itfmapper, "TMData", side_effect=RuntimeError("unreachable")):
        assert get_itf_subarrays() == []

    # Immediately after a failure the source is not tried again...
    with mock.patch.object(itfmapper, "TMData") as mock_tmdata:
        assert get_itf_subarrays() == []
    mock_tmdata.assert_not_called()

    # ...but once the retry interval has passed the data is retrieved
    itfmapper._CACHE.retry_after = 0.0
    assert len(get_itf_subarrays()) == 2


def test_get_itf_subarrays_discovers_new_environments(tmp_path):
    shutil.copytree(ITF_TMDATA_DIR, tmp_path, dirs_exist_ok=True)
    new_environment = tmp_path / "new"
    new_environment.mkdir()
    (new_environment / "array.yaml").write_text(
        "platform:\n  array:\n    name: SKA-Low-ITF-NEW\n    stations:\n    - new6-1\n"
    )
    (new_environment / "stations.yaml").write_text(
        "platform:\n  stations:\n    new6-1:\n      id: 61\n"
    )

    with _settings_with_low_itf_tmdata(f"file://{tmp_path}"):
        result = get_itf_subarrays()

    assert [subarray.name for subarray in result] == [
        "SKA-Low-ITF-CI",
        "SKA-Low-ITF-EM",
        "SKA-Low-ITF-NEW",
    ]
    assert result[-1].allowed_stations == [Station(id=61, label="new6-1")]


def test_get_itf_subarrays_ignores_directories_that_are_not_environments(tmp_path):
    shutil.copytree(ITF_TMDATA_DIR, tmp_path, dirs_exist_ok=True)
    # No stations.yaml alongside the array.yaml
    (tmp_path / "incomplete").mkdir()
    shutil.copy(ITF_TMDATA_DIR / "em" / "array.yaml", tmp_path / "incomplete" / "array.yaml")
    # Files nested below the top level directories
    shutil.copytree(ITF_TMDATA_DIR / "em", tmp_path / "other" / "nested")

    with _settings_with_low_itf_tmdata(f"file://{tmp_path}"):
        result = get_itf_subarrays()

    assert [subarray.name for subarray in result] == ["SKA-Low-ITF-CI", "SKA-Low-ITF-EM"]


def test_get_itf_subarrays_omits_a_malformed_environment(tmp_path):
    shutil.copytree(ITF_TMDATA_DIR, tmp_path, dirs_exist_ok=True)
    (tmp_path / "em" / "stations.yaml").write_text("platform:\n  stations: {}\n")

    with _settings_with_low_itf_tmdata(f"file://{tmp_path}"):
        result = get_itf_subarrays()

    assert [subarray.name for subarray in result] == ["SKA-Low-ITF-CI"]


def test_get_itf_subarrays_retries_a_malformed_environment_once_fixed(tmp_path):
    shutil.copytree(ITF_TMDATA_DIR, tmp_path, dirs_exist_ok=True)
    em_stations = tmp_path / "em" / "stations.yaml"
    em_stations.write_text("platform:\n  stations: {}\n")

    with _settings_with_low_itf_tmdata(f"file://{tmp_path}"):
        assert [subarray.name for subarray in get_itf_subarrays()] == ["SKA-Low-ITF-CI"]

        shutil.copy(ITF_TMDATA_DIR / "em" / "stations.yaml", em_stations)

        # Within the retry interval the partial result is returned...
        assert [subarray.name for subarray in get_itf_subarrays()] == ["SKA-Low-ITF-CI"]

        # ...but once it has passed the fixed environment is retrieved
        itfmapper._CACHE.retry_after = 0.0
        assert [subarray.name for subarray in get_itf_subarrays()] == [
            "SKA-Low-ITF-CI",
            "SKA-Low-ITF-EM",
        ]

        # and as the result is now complete the source is not tried again
        with mock.patch.object(itfmapper, "TMData") as mock_tmdata:
            itfmapper._CACHE.retry_after = 0.0
            assert len(get_itf_subarrays()) == 2
        mock_tmdata.assert_not_called()


def test_get_itf_subarrays_refresh_reloads_complete_result_once_per_interval(tmp_path):
    shutil.copytree(ITF_TMDATA_DIR, tmp_path, dirs_exist_ok=True)

    with _settings_with_low_itf_tmdata(f"file://{tmp_path}"):
        assert len(get_itf_subarrays()) == 2

        shutil.rmtree(tmp_path / "ci")

        # A refresh within the retry interval of the last fetch returns the cached result...
        with mock.patch.object(itfmapper, "TMData") as mock_tmdata:
            assert len(get_itf_subarrays(refresh=True)) == 2
        mock_tmdata.assert_not_called()

        # ...but once it has passed the source is fetched again
        itfmapper._CACHE.retry_after = 0.0
        result = get_itf_subarrays(refresh=True)
        assert [subarray.name for subarray in result] == ["SKA-Low-ITF-EM"]

        # and the next refresh is blocked for another interval
        with mock.patch.object(itfmapper, "TMData") as mock_tmdata:
            get_itf_subarrays(refresh=True)
        mock_tmdata.assert_not_called()


def test_get_itf_subarrays_keeps_partial_result_when_retry_fails(tmp_path):
    shutil.copytree(ITF_TMDATA_DIR, tmp_path, dirs_exist_ok=True)
    (tmp_path / "em" / "stations.yaml").write_text("platform:\n  stations: {}\n")

    with _settings_with_low_itf_tmdata(f"file://{tmp_path}"):
        get_itf_subarrays()

        itfmapper._CACHE.retry_after = 0.0
        with mock.patch.object(itfmapper, "TMData", side_effect=RuntimeError("unreachable")):
            result = get_itf_subarrays()

    assert [subarray.name for subarray in result] == ["SKA-Low-ITF-CI"]
