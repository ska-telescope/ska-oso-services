from ska_oso_services.pht.utils.pht_handler import (
    join_proposals_panels_reviews_decisions,
)
from tests.unit.util import REVIEWERS, TestDataFactory

def test_join_proposals_panels_reviews_decisions():
    proposal1 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00001")
    proposal2 = TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00002")
    panel = TestDataFactory.panel(reviewer_id=REVIEWERS[0]["id"], panel_id="panel-test-20250616-00001", prsl_id_1=proposal1.prsl_id, prsl_id_2=proposal2.prsl_id)
    decision = TestDataFactory.panel_decision(prsl_id = proposal1.prsl_id)
    reviews = TestDataFactory.reviews(prsl_id=proposal1.prsl_id)
    
    rows = join_proposals_panels_reviews_decisions( proposals=[proposal1, proposal2],panels=[panel], reviews=[reviews], decisions=[decision] )

    assert isinstance(rows, list)
    assert len(rows) == 2
  