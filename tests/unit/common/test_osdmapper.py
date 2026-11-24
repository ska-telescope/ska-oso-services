from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from ska_oso_pdm._shared.spfrx import PeriodicNoiseDiodeConfig, PseudoRandomNoiseDiodeConfig
from ska_ost_osd.osd.common.constant import Telescope
from ska_ost_osd.osd.exceptions import ArrayAssemblyNotFoundError
from ska_ost_osd.osd.views.odt import (
    Constraints,
    LowCBFMetrics,
    LowQualityAttributeMetrics,
    SPFRxParameters,
)

import ska_oso_services.settings as settings_module
from ska_oso_services.common.osdmapper import (
    SUBARRAYS,
    array_assembly_and_policy,
    configuration_from_osd,
    get_capabilities,
    get_default_pdm_target_spfrx,
    osd_repository,
)
from ska_oso_services.settings import Settings, get_settings

OSDMAPPER_MODULE = "ska_oso_services.common.osdmapper"


def test_osd_tmdata_defaults_to_osd_main_in_the_car(monkeypatch):
    # conftest.py pins the tests' OSD_TMDATA, so unset it to see the default
    monkeypatch.delenv("OSD_TMDATA", raising=False)

    assert Settings().osd_tmdata == ("car:ost/ska-ost-osd?main#tmdata",)


def test_osd_tmdata_is_read_from_the_osd_tmdata_environment_variable(monkeypatch):
    # As the Helm chart sets it, from a list joined with commas
    monkeypatch.setenv("OSD_TMDATA", "file:///tmdata, car:ost/ska-ost-osd?main#tmdata")

    assert Settings().osd_tmdata == ("file:///tmdata", "car:ost/ska-ost-osd?main#tmdata")


@pytest.mark.parametrize("value", ["", " , "])
def test_osd_tmdata_must_name_a_source(monkeypatch, value):
    # Given no sources, TMData would read its own defaults, which don't hold the OSD
    monkeypatch.setenv("OSD_TMDATA", value)

    with pytest.raises(ValidationError):
        Settings()


def test_osd_repository_reads_the_osd_tmdata_sources():
    sources = ("file:///tmdata", "car:ost/ska-ost-osd?main#tmdata")
    settings = get_settings().model_copy(update={"osd_tmdata": sources})
    # osd_repository() is cached, so clear it before and after to read these sources
    # without leaving the mock for the other tests
    osd_repository.cache_clear()
    try:
        with (
            patch.object(settings_module, "SETTINGS", settings),
            patch(f"{OSDMAPPER_MODULE}.TMData") as tmdata,
            patch(f"{OSDMAPPER_MODULE}.TMDataRepository") as repository,
        ):
            assert osd_repository() is repository.return_value
    finally:
        osd_repository.cache_clear()

    tmdata.assert_called_once_with(sources, update=True)
    repository.assert_called_once_with(tmdata.return_value)


def test_configuration_from_osd_returns_constraints():
    value = configuration_from_osd()
    assert type(value.ska_low.constraints) is Constraints
    assert type(value.ska_mid.constraints) is Constraints


def test_configuration_from_osd_returns_low_cbf_metrics():
    value = configuration_from_osd()
    assert type(value.ska_low.quality_attribute_metrics) is LowQualityAttributeMetrics

    assert type(value.ska_low.quality_attribute_metrics.cbf) is LowCBFMetrics
    cbf = value.ska_low.quality_attribute_metrics.cbf

    assert cbf.processors_ready_percent is not None, "processors_ready_percent must be present"


def test_configuration_from_osd_returns_mid_spfrx_defaults():
    value = configuration_from_osd()
    assert type(value.ska_mid.spfrx_defaults) is SPFRxParameters


@pytest.mark.parametrize("telescope", [Telescope.SKA_MID, Telescope.SKA_LOW])
def test_configuration_from_osd_lists_the_odt_subarrays_by_name(telescope):
    value = configuration_from_osd()
    subarrays = (
        value.ska_mid.subarrays if telescope == Telescope.SKA_MID else value.ska_low.subarrays
    )

    # Each subarray is named after its policy, or else its array assembly
    expected_names = [policy or array_assembly for array_assembly, policy in SUBARRAYS[telescope]]
    assert [subarray.name for subarray in subarrays] == expected_names


@pytest.mark.parametrize(
    "telescope,name,expected",
    [
        pytest.param(Telescope.SKA_LOW, "AA1", ("AA1", None), id="low array assembly"),
        pytest.param(Telescope.SKA_LOW, "AA2_SV", ("AA2", "AA2_SV"), id="low policy"),
        pytest.param(Telescope.SKA_MID, "AA2", ("AA2", None), id="mid array assembly"),
    ],
)
def test_array_assembly_and_policy(telescope, name, expected):
    assert array_assembly_and_policy(telescope, name) == expected


def test_get_capabilities_applies_the_policy_for_aa2_sv():
    capabilities = get_capabilities(Telescope.SKA_LOW, "AA2_SV")

    assert capabilities.array_assembly == "AA2"
    assert capabilities.policy == "AA2_SV"


def test_get_capabilities_raises_for_an_unknown_array_assembly():
    with pytest.raises(ArrayAssemblyNotFoundError):
        get_capabilities(Telescope.SKA_LOW, "AA9")


def _repository_with_default_noise_diode_mode(mode):
    target_spfrx = osd_repository().get_defaults(Telescope.SKA_MID).spfrx_defaults.target_spfrx
    modified = target_spfrx.model_copy(update={"default_noise_diode_mode": mode})

    return SimpleNamespace(
        get_defaults=lambda telescope: SimpleNamespace(
            spfrx_defaults=SimpleNamespace(target_spfrx=modified)
        )
    )


@pytest.mark.parametrize(
    "mode,expected_type",
    [
        pytest.param("off", type(None), id="off"),
        pytest.param("periodic", PeriodicNoiseDiodeConfig, id="periodic"),
        pytest.param("pseudo_random", PseudoRandomNoiseDiodeConfig, id="pseudo_random"),
    ],
)
def test_default_noise_diode_mode_sets_expected_diode(mode, expected_type):
    repository = _repository_with_default_noise_diode_mode(mode)

    with patch("ska_oso_services.common.osdmapper.osd_repository", return_value=repository):
        result = get_default_pdm_target_spfrx()

    assert type(result.noise_diode) is expected_type


def test_an_invalid_default_causes_a_value_error():
    repository = _repository_with_default_noise_diode_mode("blah")

    with patch("ska_oso_services.common.osdmapper.osd_repository", return_value=repository):
        with pytest.raises(ValueError):
            get_default_pdm_target_spfrx()
