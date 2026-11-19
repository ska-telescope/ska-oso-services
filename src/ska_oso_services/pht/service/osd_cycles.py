"""
Builds the OSD data the PHT UI reads from GET /prsls/osd/cycles and
GET /prsls/osd/{cycle_id}, from the OSD's PHT view.
"""

from typing import Any

from ska_ost_osd.osd.common.constant import Telescope
from ska_ost_osd.osd.repository import OSDRepository
from ska_ost_osd.osd.views import pht

from ska_oso_services.pht.models.domain import Capabilities, Low, Mid, OsdDataModel


def osd_data(osd: OSDRepository, cycle_id: str) -> OsdDataModel:
    """
    A cycle's OSD data: the cycle and, for each telescope it offers, that
    telescope's basic capabilities and the capabilities offered, under the
    policy's name, e.g. "AA2_SV".

    :raises CycleNotFoundError: if there is no cycle with that ID
    :raises OSDQueryError: if the cycle names an array assembly or policy the
        OSD doesn't have
    """
    policy = pht.get_observatory_policy(osd, cycle_id)
    # The policy each telescope offers, and the array assembly each applies to
    names = policy.telescope_capabilities
    telescopes = osd.get_cycle(cycle_id).telescopes

    def offered(telescope: Telescope, name: str) -> dict[str, Any]:
        return {
            "basic_capabilities": pht.get_basic_capabilities(osd, telescope),
            name: pht.get_capabilities(osd, telescope, telescopes[telescope].array_assembly, name),
        }

    return OsdDataModel(
        observatory_policy=policy,
        capabilities=Capabilities(
            mid=Mid(**offered(Telescope.SKA_MID, names.Mid)) if names.Mid else None,
            low=Low(**offered(Telescope.SKA_LOW, names.Low)) if names.Low else None,
        ),
    )
