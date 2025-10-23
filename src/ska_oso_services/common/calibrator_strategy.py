from datetime import timedelta
from enum import Enum

from ska_oso_pdm._shared import TimedeltaMs

from ska_oso_services.common.model import AppModel


class CalibrationWhen(str, Enum):
    BEFORE_EACH_SCAN = "before_each_scan"
    AFTER_EACH_SCAN = "after_each_scan"


class CalibratorChoice(str, Enum):
    CLOSEST = "closest"


class CalibrationStrategy(AppModel):
    """
    This model defines the parameters that a generic calibrator strategy can take.

    Some strategies that are predefined by the observatory can then exist as instances
    of this model, and eventually a user defined strategy might also use this model.

    This can get as complex as required - for example the calibrator_choice
    might take into account elevation
    or flux, or allow a specific target to be named.

    Potentially this could be part of the PDM, and included in the
    Proposal Observation Set.
    """

    calibration_strategy_id: str
    when: list[CalibrationWhen]
    duration_ms: TimedeltaMs
    calibrator_choice: CalibratorChoice


OBSERVATORY_CALIBRATION_STRATEGIES: list[CalibrationStrategy] = [
    CalibrationStrategy(
        calibration_strategy_id="default",
        when=[CalibrationWhen.BEFORE_EACH_SCAN, CalibrationWhen.AFTER_EACH_SCAN],
        calibrator_choice=CalibratorChoice.CLOSEST,
        duration_ms=timedelta(minutes=10),
    )
]


def lookup_observatory_calibration_strategy(
    calibration_strategy_id: str,
) -> CalibrationStrategy:
    """
    Lookup a Calibration Strategy that is predefined by the observatory.

    :param calibration_strategy_id: the unique identifier of a strategy
    defined by the observatory
    :returns: the CalibrationStrategy with the given identifier
    :raises: KeyError is the calibration_strategy_id does not exist
    """
    try:
        return [
            strategy
            for strategy in OBSERVATORY_CALIBRATION_STRATEGIES
            if strategy.calibration_strategy_id == calibration_strategy_id
        ][0]
    except IndexError:
        raise KeyError(
            f"Observatory Calibration Strategy with calibration_strategy_id "
            f"{calibration_strategy_id} not found."
        )
