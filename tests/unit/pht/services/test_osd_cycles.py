"""
These read the OSD's tmdata at the commit conftest.py pins, as the other OSD
tests do, so they check the PHT's cycles against the real data.
"""

import pytest
from ska_ost_osd.osd.exceptions import CycleNotFoundError

from ska_oso_services.common.osdmapper import osd_repository
from ska_oso_services.pht.service.osd_cycles import osd_data


def test_osd_data_serves_the_capabilities_under_the_policy_name():
    data = osd_data(osd_repository(), "TEST_SKAO_2027_Low_AA2_SV")

    assert data.observatory_policy.cycle_id == "TEST_SKAO_2027_Low_AA2_SV"
    assert data.observatory_policy.telescope_capabilities.Low == "AA2_SV"
    assert data.capabilities.mid is None
    # Only the policy the cycle offers is served, under its name
    assert list(data.capabilities.low.model_extra) == ["AA2_SV"]


def test_osd_data_for_a_cycle_offering_a_policy_named_after_the_array_assembly():
    data = osd_data(osd_repository(), "TEST_SKAO_2027_Low_AA2_Proposal")

    assert data.observatory_policy.telescope_capabilities.Low == "AA2"
    assert list(data.capabilities.low.model_extra) == ["AA2"]


def test_osd_data_raises_for_an_unknown_cycle():
    with pytest.raises(CycleNotFoundError):
        osd_data(osd_repository(), "9999")
