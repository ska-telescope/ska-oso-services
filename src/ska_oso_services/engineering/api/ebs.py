import logging

from fastapi import APIRouter
from ska_db_oda.common.uow import UnitOfWork
from ska_db_oda.postgres.mapping import StatusLabel
from ska_db_oda.repository.status import Status
from ska_oso_pdm import OSOExecutionBlock as ExecutionBlock
from ska_oso_pdm import TelescopeType
from ska_oso_pdm.execution_block import RequestResponse

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/ebs")

NOTEBOOK_USER = "NotebookUser"


@router.get(
    "/{eb_id}",
    summary="Get an ExecutionBlock for a given identifier",
    response_model=ExecutionBlock,
)
def get_eb(eb_id: str, oda: UnitOfWork) -> ExecutionBlock:
    with oda as uow:
        retrieved_eb = uow.ebs.get(eb_id)
    return retrieved_eb


@router.post(
    "/{telescope}",
    summary="Create a new ExecutionBlock at the start of an observing session",
    response_model=ExecutionBlock,
)
def create_eb(telescope: TelescopeType, oda: UnitOfWork) -> ExecutionBlock:
    eb = ExecutionBlock(telescope=telescope)
    with oda as uow:
        persisted_eb = uow.ebs.add(eb)
        uow.commit()

    return persisted_eb


@router.patch(
    "/{eb_id}/request_response",
    summary="Add a RequestResponse to an ExecutionBlock",
    response_model=ExecutionBlock,
)
def add_request_response(
    eb_id: str, request_response: RequestResponse, oda: UnitOfWork
) -> ExecutionBlock:
    with oda as uow:
        eb = uow.ebs.get(eb_id)
        if eb.request_responses is None:
            eb.request_responses = [request_response]
        else:
            eb.request_responses.append(request_response)
        persisted_eb = uow.ebs.add(eb)
        uow.commit()

    return persisted_eb


@router.put(
    "/{eb_id}/status/observed",
    summary="Set an ExecutionBlock status to Observed",
    response_model=Status,
)
def set_eb_status_observed(eb_id: str, oda: UnitOfWork) -> Status:
    with oda as uow:
        uow.status.update_status(
            entity_id=eb_id, status=StatusLabel.OBSERVED, updated_by=NOTEBOOK_USER
        )
        uow.commit()
        return uow.status.get_current_status(entity_id=eb_id)


@router.put(
    "/{eb_id}/status/failed",
    summary="Set an ExecutionBlock status to Failed",
    response_model=Status,
)
def set_eb_status_failed(eb_id: str, oda: UnitOfWork) -> Status:
    with oda as uow:
        uow.status.update_status(
            entity_id=eb_id, status=StatusLabel.OBSERVING_FAILED, updated_by=NOTEBOOK_USER
        )
        uow.commit()
        return uow.status.get_current_status(entity_id=eb_id)
