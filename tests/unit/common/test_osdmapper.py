from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ska_oso_pdm._shared.spfrx import PeriodicNoiseDiodeConfig, PseudoRandomNoiseDiodeConfig
from ska_ost_osd.osd.common.constant import Telescope
from ska_ost_osd.osd.models.constraints import Constraints
from ska_ost_osd.osd.models.defaults import SPFRxParameters
from ska_ost_osd.osd.views.odt import (
    ConfigurationLowCBFMetrics,
    ConfigurationLowQualityAttributeMetrics,
)

from ska_oso_services.common.osdmapper import (
    configuration_from_osd,
    get_default_pdm_target_spfrx,
    osd_repository,
)


def test_configuration_from_osd_returns_constraints():
    value = configuration_from_osd()
    assert type(value.ska_low.constraints) is Constraints
    assert type(value.ska_mid.constraints) is Constraints


def test_configuration_from_osd_returns_low_cbf_metrics():
    value = configuration_from_osd()
    assert type(value.ska_low.quality_attribute_metrics) is ConfigurationLowQualityAttributeMetrics

    assert type(value.ska_low.quality_attribute_metrics.cbf) is ConfigurationLowCBFMetrics
    cbf = value.ska_low.quality_attribute_metrics.cbf

    assert cbf.processors_ready_percent is not None, "processors_ready_percent must be present"


def test_configuration_from_osd_returns_mid_spfrx_defaults():
    value = configuration_from_osd()
    assert type(value.ska_mid.spfrx_defaults) is SPFRxParameters


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
