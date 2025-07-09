from collections import defaultdict

from ska_oso_pdm import Project, Proposal
from ska_oso_pdm.project import ObservingBlock, ScienceProgramme
from ska_oso_pdm.proposal import Info, ObservationSets


def generate_project(proposal: Proposal) -> Project:
    """
    This is the main algorithm for creating a Project from a Proposal.

    Currently, the Project contains an Info object that in turn contains
    a list of ObservationSets.These observation sets are be linked to
    Targets (via the Results) and DataProductSDP.

    Also, the ObservationSets can be linked to each other by sharing a group_id.

    The resulting Project contains a list of ObservingBlocks, each with a list
    of ScienceProgrammes. There should be an ObservingBlock for each group of
    ObservationSets in the Proposal (so if there are no groups, there will be as
     many ObservingBlocks as ObservationSets).

    The ScienceProgramme is essentially a copy of the ObservationSet, plus those
    Targets, Results and DataProductSDP that are linked to that ObservationSet

    Note: this is a first pass at the Project generation. There will likely be
        refactoring to both the Proposal and Project model to reduce the
        complexity and duplication in this mapping.
    """
    grouped_observation_sets = _group_observation_sets(proposal)

    observing_blocks = []
    # Create an ObservingBlock for each group of ObservationSets
    for index, observation_set_group in enumerate(grouped_observation_sets):

        # Now create a ScienceProgramme for each ObservationSet in the group
        science_programmes = [
            science_programme_from_observation_set(observation_set, proposal.info)
            for observation_set in observation_set_group
        ]

        observing_blocks.append(
            ObservingBlock(
                obs_block_id=f"obs-block-{index:5}",
                science_programmes=science_programmes,
            )
        )

    return Project(prsl_ref=proposal.prsl_id, obs_blocks=observing_blocks)


def _group_observation_sets(proposal: Proposal) -> list[list[ObservationSets]]:
    """
    The ObservationSets in the Proposal Info is a list of objects that
    are linked by group_id.

    This function turns that list into a 2d array with each inner list
    being the grouped ObservationSets
    """
    grouped_observation_sets = defaultdict(list)
    for observation_set in proposal.info.observation_sets:
        group_id = observation_set.group_id
        grouped_observation_sets[group_id].append(observation_set)

    return list(grouped_observation_sets.values())


def science_programme_from_observation_set(
    observation_set: ObservationSets, proposal_info: Info
) -> ScienceProgramme:
    """
    Create a ScienceProgramme by copying the ObservationSet over and the other
     relevant parts of the Info that are linked with that ObservationSet
    """
    observation_set_id = observation_set.observation_set_id

    results_for_observation_set = list(
        filter(
            lambda result_detail: result_detail.observation_set_ref
            == observation_set_id,
            proposal_info.result_details,
        )
    )

    # The ObservationSet <-> Target link is via the Results
    target_ids = list(
        map(lambda result_detail: result_detail.target_ref, results_for_observation_set)
    )
    targets_for_observation_set = list(
        filter(lambda target: target.target_id in target_ids, proposal_info.targets)
    )

    sdp_data_products_for_observation_set = list(
        filter(
            lambda data_product: observation_set_id
            in data_product.observation_set_refs,
            proposal_info.data_product_sdps,
        )
    )

    return ScienceProgramme(
        observation_sets=[observation_set.model_copy(deep=True)],
        result_details=results_for_observation_set,
        targets=targets_for_observation_set,
        data_product_sdps=sdp_data_products_for_observation_set,
    )
