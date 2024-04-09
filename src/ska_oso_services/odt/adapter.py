"""
These functions are a temporary measure to map between the models generated
from the OpenAPI document and the model defined in ska-oso-pdm. Rather than map
fields individually, JSON is used as an intermediate.

Ultimately, these models will be consolidated, with the ODA API using the
OpenAPI generated model
"""

from ska_oso_pdm.entities.common.sb_definition import SBDefinition
from ska_oso_pdm.generated.models.sb_definition import (
    SBDefinition as GeneratedSBDefinition,
)
from ska_oso_pdm.openapi import CODEC as OPENAPI_CODEC
from ska_oso_pdm.schemas import CODEC as MARSHMALLOW_CODEC


def pdm_from_generated_model(model: GeneratedSBDefinition) -> SBDefinition:
    """
    Adapt an instance of the generated SBDefinition model
    into an SBDefinition from the PDM
    """
    model_string = OPENAPI_CODEC.dumps(model)
    return MARSHMALLOW_CODEC.loads(SBDefinition, model_string)


def generated_model_from_pdm(pdm_sb: SBDefinition) -> GeneratedSBDefinition:
    """
    Adapt an instance of the generated SBDefinition from the PDM
    into an SBDefinition model
    """
    pdm_string = MARSHMALLOW_CODEC.dumps(pdm_sb)
    return OPENAPI_CODEC.loads(GeneratedSBDefinition, pdm_string)
