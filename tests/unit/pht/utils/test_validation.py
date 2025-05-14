from tests.unit.util import TestDataFactory
from ska_oso_services.pht.utils.validation import validate_proposal

def test_validate_proposal_no_errors():
    p = TestDataFactory.complete_proposal()
    res = validate_proposal(p)
    
    expected = {'result': True, 'validation_errors': []}
    assert expected == res

def test_validate_proposal_no_observation_sets():
    p = TestDataFactory.complete_proposal()
    p.info.observation_sets = []
    
    res = validate_proposal(p)
    
    expected = {'result': False, 'validation_errors': ['This proposal has no observation sets']}
    assert expected == res


def test_validate_proposal_target_with_no_sensitivity():
    p = TestDataFactory.complete_proposal()
    
    p.info.targets[0].target_id = "wrong"

    res = validate_proposal(p)
    
    expected = {'result': False, 'validation_errors': ['Target wrong has no valid sensitivity/integration time results or is not linked to an observation']}
    assert expected == res
    
def test_validate_proposal_observation_set_no_target():
    p = TestDataFactory.complete_proposal()
    p.info.observation_sets[0].observation_set_id = "wrong too"
    
    res = validate_proposal(p)
    
    expected = {'result': False, 'validation_errors': ['Observation Set wrong too has no Targets linked in Results']}
    assert expected == res
    