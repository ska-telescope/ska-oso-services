"""
Generator of SBDefinitions for the Global Sky Model survery commissioning use case.

This will take pointings from an input file, along with other parameters, and generates
(number of pointings / (num_subarray_beams * num_scans)) SBDefinitions
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from math import floor

import numpy as np

# pylint: disable=no-member
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.units import Quantity
from ska_oso_pdm import ICRSCoordinates, SBDefinition, SubArrayLOW, Target, TelescopeType
from ska_oso_pdm.sb_definition import (
    CSPConfiguration,
    MCCSAllocation,
    ScanDefinition,
    SDPConfiguration,
    SDPScript,
)
from ska_oso_pdm.sb_definition.csp import LowCBFConfiguration
from ska_oso_pdm.sb_definition.csp.lowcbf import Correlation
from ska_oso_pdm.sb_definition.mccs.mccs_allocation import Aperture, SubarrayBeamConfiguration
from ska_oso_pdm.sb_definition.procedures import GitScript

from ska_oso_services.common.astro import low_frequency_to_coarse_channel
from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
from ska_oso_services.odt.service.sbd_generator import _sbd_internal_id

DEFAULT_SUBARRAY = SubArrayLOW.AA2_ALL


class GroupingMethod(str, Enum):
    """Strategy used to partition targets into SBD groups."""

    SEQUENTIAL = "sequential"
    RING_BUFFER = "ring_buffer"


def sequential_grouping(num_targets: int, group_size: int) -> Iterator[list[int]]:
    """Yield sequential, non-overlapping chunks of target indices.

    Each yielded list contains up to ``group_size`` indices. The final
    group may be shorter if ``num_targets`` is not evenly divisible.
    """
    for start in range(0, num_targets, group_size):
        yield list(range(start, min(start + group_size, num_targets)))


@dataclass
class RingData:
    """Derived spatial data from a target catalogue for ring-buffer grouping."""

    coords: SkyCoord
    ra_deg: np.ndarray
    dec_deg: np.ndarray
    unique_decs: np.ndarray
    delta_dec: float
    first_bin_center_dec: float
    min_separation: float
    max_separation: float
    ring_ids: np.ndarray
    ring_queues: list[deque[int]] = field(default_factory=list)


def _build_ring_data(
    targets: list[Target],
    *,
    min_separation_factor: float = 1.2,
    max_separation_factor: float = 2.4,
) -> RingData:
    """Build coordinate arrays, derive delta_dec, and bin targets into ring queues.

    Parameters
    ----------
    targets : list[Target]
        Input target list with ICRS coordinates.
    min_separation_factor : float
        Minimum pairwise angular separation as a multiple of ``delta_dec``.
    max_separation_factor : float
        Maximum angular separation as a multiple of ``delta_dec``.

    Returns
    -------
    RingData
        Derived spatial data ready for grouping or validation.

    Raises
    ------
    ValueError
        If fewer than two distinct declination values are present.
    """
    coords = SkyCoord(
        [t.reference_coordinate.to_sky_coord() for t in targets], frame="icrs"
    )
    ra_deg = np.asarray(coords.ra.deg)
    dec_deg = np.asarray(coords.dec.deg)

    unique_decs = np.unique(np.round(dec_deg, decimals=5))
    if len(unique_decs) < 2:
        raise ValueError(
            "ring_buffer_grouping requires targets at two or more distinct "
            "declination values to derive the bin width"
        )
    delta_dec = float(np.min(np.diff(unique_decs)))

    first_bin_center_dec = float(np.min(dec_deg))
    min_separation = delta_dec * min_separation_factor
    max_separation = delta_dec * max_separation_factor

    ring_ids = np.floor(
        (dec_deg - first_bin_center_dec) / delta_dec + 0.5
    ).astype(int)
    ring_queues: list[deque[int]] = []
    for ring_id in sorted(np.unique(ring_ids)):
        ring_mask = ring_ids == ring_id
        indices = np.where(ring_mask)[0]
        indices_sorted = indices[np.argsort(ra_deg[indices])]
        ring_queues.append(deque(indices_sorted.tolist()))

    return RingData(
        coords=coords,
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        unique_decs=unique_decs,
        delta_dec=delta_dec,
        first_bin_center_dec=first_bin_center_dec,
        min_separation=min_separation,
        max_separation=max_separation,
        ring_ids=ring_ids,
        ring_queues=ring_queues,
    )


def _validate_ring_catalogue(
    rd: RingData,
    *,
    dec_uniformity_tolerance: float = 1.5,
    ra_ring_fail_fraction: float = 0.2,
) -> None:
    """Validate that a target catalogue is suitable for ring-buffer grouping.

    Parameters
    ----------
    rd : RingData
        Pre-computed ring data from :func:`_build_ring_data`.
    dec_uniformity_tolerance : float
        Maximum allowed ratio of the largest to smallest gap between
        successive unique declination values.  Defaults to 1.5.
    ra_ring_fail_fraction : float
        Maximum fraction of rings allowed to violate the RA-spacing
        checks before a ``ValueError`` is raised.  Defaults to 0.2.

    Raises
    ------
    ValueError
        If the catalogue fails any of the structural checks.
    """
    # --- Check 1: Uniform declination spacing ---
    dec_diffs = np.diff(rd.unique_decs)
    ratio = float(np.max(dec_diffs) / np.min(dec_diffs))
    if ratio > dec_uniformity_tolerance:
        raise ValueError(
            f"Declination spacing is not uniform: max/min gap ratio is "
            f"{ratio:.2f}, exceeding tolerance {dec_uniformity_tolerance}. "
            f"The ring-buffer algorithm requires approximately equal "
            f"declination spacing between target rings."
        )

    # --- Check 2: No empty rings ---
    all_ring_ids = rd.ring_ids
    expected_ids = set(range(int(np.min(all_ring_ids)), int(np.max(all_ring_ids)) + 1))
    actual_ids = set(int(rid) for rid in np.unique(all_ring_ids))
    missing = expected_ids - actual_ids
    if missing:
        raise ValueError(
            f"Empty ring(s) detected at ring id(s) {sorted(missing)}. "
            f"The ring-buffer algorithm requires every declination ring "
            f"between the first and last to contain at least one target."
        )

    # --- Check 3: Intra-ring RA spacing vs separation thresholds ---
    failing_rings: list[str] = []
    for q in rd.ring_queues:
        if len(q) < 3:
            continue
        indices = list(q)
        ring_ra = rd.ra_deg[indices]
        ring_dec_mean = float(np.mean(rd.dec_deg[indices]))
        cos_dec = np.cos(np.radians(ring_dec_mean))

        ra_gaps = np.diff(ring_ra)
        delta_ra = float(np.median(ra_gaps))
        approx_sep_k1 = delta_ra * cos_dec
        approx_sep_k2 = 2.0 * delta_ra * cos_dec
        approx_sep_k3 = 3.0 * delta_ra * cos_dec

        issues: list[str] = []
        if approx_sep_k1 >= rd.min_separation:
            issues.append(
                f"k=1 separation ({approx_sep_k1:.3f}°) >= "
                f"min_separation ({rd.min_separation:.3f}°)"
            )
        if not (rd.min_separation <= approx_sep_k2 <= rd.max_separation):
            issues.append(
                f"k=2 separation ({approx_sep_k2:.3f}°) not in "
                f"[{rd.min_separation:.3f}°, {rd.max_separation:.3f}°]"
            )
        if approx_sep_k3 <= rd.max_separation:
            issues.append(
                f"k=3 separation ({approx_sep_k3:.3f}°) <= "
                f"max_separation ({rd.max_separation:.3f}°)"
            )
        if issues:
            failing_rings.append(
                f"ring at dec≈{ring_dec_mean:.1f}°: {'; '.join(issues)}"
            )

    checkable_rings = sum(1 for q in rd.ring_queues if len(q) >= 3)
    if checkable_rings > 0:
        fail_frac = len(failing_rings) / checkable_rings
        if fail_frac > ra_ring_fail_fraction:
            detail = "\n  ".join(failing_rings[:5])
            raise ValueError(
                f"RA spacing check failed for {len(failing_rings)}/{checkable_rings} "
                f"rings ({fail_frac:.0%}), exceeding tolerance "
                f"{ra_ring_fail_fraction:.0%}. Examples:\n  {detail}"
            )


def ring_buffer_grouping(
    targets: list[Target],
    group_size: int,
    *,
    min_separation_factor: float = 1.2,
    max_separation_factor: float = 2.4,
) -> Iterator[list[int]]:
    """Yield groups of target indices using ring-buffer spatial clustering.

    Targets are binned by declination into ring queues sorted by RA.
    Groups are built greedily, seeding from the lowest-RA frontier node
    and growing by selecting the valid candidate with the lowest RA.

    The declination bin width (``delta_dec``) is derived automatically as
    the smallest gap between successive unique declination values in the
    catalogue.  Separation thresholds are then expressed as multiples of
    that bin width.

    Parameters
    ----------
    targets : list[Target]
        Input target list with ICRS coordinates.
    group_size : int
        Maximum number of targets per group.
    min_separation_factor : float
        Minimum pairwise angular separation expressed as a multiple of
        ``delta_dec``.  Defaults to 1.2.
    max_separation_factor : float
        Maximum angular separation for neighbour detection expressed as
        a multiple of ``delta_dec``.  Defaults to 2.4.
    """
    rd = _build_ring_data(
        targets,
        min_separation_factor=min_separation_factor,
        max_separation_factor=max_separation_factor,
    )
    _validate_ring_catalogue(rd)
    coords = rd.coords
    ra_deg = rd.ra_deg
    dec_deg = rd.dec_deg
    min_separation = rd.min_separation
    max_separation = rd.max_separation
    ring_queues = rd.ring_queues

    def _edge_key(i: int, j: int) -> tuple[int, int]:
        return (i, j) if i < j else (j, i)

    edge_separation: dict[tuple[int, int], float] = {}
    active_nodes: dict[int, None] = {}

    # --- Main grouping loop ---
    while any(q for q in ring_queues) or active_nodes:
        # Step 1: Yield at most one head point per queue, gated by current
        # graph-min RA so that the active set stays spatially compact.
        for q in ring_queues:
            if not q:
                continue
            if active_nodes:
                graph_min_ra = min(ra_deg[n] for n in active_nodes)
                if ra_deg[q[0]] >= graph_min_ra:
                    continue
            pid = q.popleft()
            for other_pid in active_nodes:
                edge_separation[_edge_key(pid, other_pid)] = float(
                    coords[pid].separation(coords[other_pid]).degree
                )
            active_nodes[pid] = None

        if not active_nodes:
            break

        # Step 2: Seed a new group with the globally lowest-RA frontier node.
        i0 = min(active_nodes, key=lambda n: ra_deg[n])
        group: list[int] = [i0]

        # Step 3: Grow group until full or no valid candidate remains.
        while len(group) < group_size:
            # 3a: Compute frontier bounds from the current group.
            group_dec_min = float(np.min(dec_deg[group])) - max_separation
            group_dec_max = float(np.max(dec_deg[group])) + max_separation
            group_max_ra = float(np.max(ra_deg[group]))

            # 3b: Expand graph by yielding queue heads within dec/RA/separation.
            for q in ring_queues:
                while q:
                    head_pid = q[0]
                    head_dec = dec_deg[head_pid]
                    if head_dec < group_dec_min or head_dec > group_dec_max:
                        break

                    last_pid = group[-1]
                    head_sep = float(
                        coords[head_pid]
                        .separation(coords[last_pid])
                        .degree
                    )
                    if head_sep > max_separation and ra_deg[head_pid] > group_max_ra:
                        break

                    pid = q.popleft()
                    for other_pid in active_nodes:
                        edge_separation[_edge_key(pid, other_pid)] = float(
                            coords[pid]
                            .separation(coords[other_pid])
                            .degree
                        )
                    active_nodes[pid] = None

            # 3c: Score candidates (RA-only mode).
            best_candidate: int | None = None
            best_ra: float = float("inf")
            for n in active_nodes:
                if n in group:
                    continue
                proposed = group + [n]
                proposed_pairs = [
                    _edge_key(a, b)
                    for idx, a in enumerate(proposed)
                    for b in proposed[idx + 1 :]
                ]
                if not all(
                    edge_separation[pair] >= min_separation for pair in proposed_pairs
                ):
                    continue
                sep_to_group = [edge_separation[_edge_key(n, g)] for g in group]
                if not any(
                    min_separation <= sep <= max_separation for sep in sep_to_group
                ):
                    continue
                if ra_deg[n] < best_ra:
                    best_ra = ra_deg[n]
                    best_candidate = n

            if best_candidate is None:
                break
            group.append(best_candidate)

        # Step 4: Yield group, then remove its nodes from the active graph
        # and clean up edge_separation entries referencing them.
        yield [int(n) for n in group]
        removed = set(group)
        for n in group:
            active_nodes.pop(n, None)
        edge_separation = {
            k: v
            for k, v in edge_separation.items()
            if k[0] not in removed and k[1] not in removed
        }

    # Yield any targets still sitting in queues that were never activated
    # (possible when the spatial constraints prevented them from joining
    # any group during the main loop).
    remaining = [q.popleft() for q in ring_queues for _ in range(len(q))]
    if remaining:
        for start in range(0, len(remaining), group_size):
            yield remaining[start : start + group_size]


def _low_default_subarray_parameters() -> tuple[list[int], Quantity]:
    station_ids = get_subarray_specific_parameter_from_osd(
        TelescopeType.SKA_LOW, DEFAULT_SUBARRAY, "receptors"
    )
    total_bandwidth = (
        get_subarray_specific_parameter_from_osd(
            TelescopeType.SKA_LOW, DEFAULT_SUBARRAY, "available_bandwidth_hz"
        )
        * u.Hz
    )
    return station_ids, total_bandwidth


CALIBRATOR_TARGET = Target(
    target_id="calibrator-00000",
    name="Polaris Australis",
    reference_coordinate=ICRSCoordinates(ra_str="21:08:46.8636", dec_str="-88:57:23.398"),
)


def generate_gsm_survey_sbds(
    input_targets: list[Target],
    centre_frequency: Quantity,
    scan_duration: timedelta,
    num_subarray_beams: int,
    num_scans: int,
    num_calibrator_beams: int,
    grouping: GroupingMethod = GroupingMethod.SEQUENTIAL,
    ring_buffer_kwargs: dict | None = None,
) -> list[SBDefinition]:

    sbds = []
    station_ids, total_bandwidth = _low_default_subarray_parameters()

    number_of_channels = _get_number_of_channels_for_each_subarray_beam(
        num_subarray_beams + num_calibrator_beams, total_bandwidth
    )

    total_targets = len(input_targets)

    csp_configuration = _csp_configuration(
        centre_frequency=centre_frequency, number_of_channels=number_of_channels
    )

    apertures = [
        Aperture(station_id=station_id, weighting_key="uniform", substation_id=1)
        for station_id in station_ids
    ]

    num_targets_per_sbd = num_scans * num_subarray_beams

    if grouping == GroupingMethod.SEQUENTIAL:
        groups = sequential_grouping(total_targets, num_targets_per_sbd)
    elif grouping == GroupingMethod.RING_BUFFER:
        kwargs = ring_buffer_kwargs or {}
        groups = ring_buffer_grouping(input_targets, num_targets_per_sbd, **kwargs)
    else:
        raise ValueError(f"Unknown grouping method: {grouping}")

    for group_indices in groups:
        targets_for_sbd = [input_targets[i] for i in group_indices]

        if len(targets_for_sbd) == num_targets_per_sbd:
            sbd_beams = num_subarray_beams
            sbd_scans = num_scans
        else:
            sbd_beams, sbd_scans = _compute_remainder_layout(
                len(targets_for_sbd), num_subarray_beams
            )

        sbds.append(
            _sbd_for_calibrator_targets(
                targets_for_sbd,
                csp_configuration,
                scan_duration,
                sbd_beams,
                sbd_scans,
                apertures,
                num_calibrator_beams,
            )
        )

    return sbds


def _compute_remainder_layout(num_remaining: int, max_beams: int) -> tuple[int, int]:
    """
    Find the best (num_beams, scans_per_beam) layout for leftover targets.

    Each subarray beam in an SBD must have the same number of scans, so
    we need num_remaining = num_beams * scans_per_beam.  We pick the
    largest num_beams <= max_beams that divides the num_remainingevenly.
    """
    for beams in range(min(max_beams, num_remaining), 0, -1):
        if num_remaining % beams == 0:
            return beams, num_remaining // beams
    return 1, num_remaining


def _get_number_of_channels_for_each_subarray_beam(
    num_subarray_beams: int, total_bandwidth: Quantity
) -> int:
    """
    The number_of_channels in the CSPConfiguration for each scan must be a multiple
    of 8 coarse channels.

    Given the SBD generation wants to make use of the full bandwidth available, splitting this
    across any num_subarray_beams given in the input may result in an invalid number_of_channels.

    This function will return the closest valid number_of_channels for the num_subarray_beams.
    """

    exact_coarse_channel = low_frequency_to_coarse_channel(total_bandwidth / num_subarray_beams)

    return floor(exact_coarse_channel / 8) * 8


def _csp_configuration(centre_frequency: Quantity, number_of_channels: int) -> CSPConfiguration:
    return CSPConfiguration(
        config_id="csp-configuration-12345",
        name=f"CSP {centre_frequency}, {number_of_channels} channels",
        lowcbf=LowCBFConfiguration(
            do_pst=False,
            correlation_spws=[
                Correlation(
                    spw_id=1,
                    number_of_channels=number_of_channels,
                    centre_frequency=centre_frequency.to(u.Hz).value,
                    integration_time_ms=timedelta(seconds=849e-3),
                    logical_fsp_ids=[],
                    zoom_factor=0,
                )
            ],
        ),
    )


def _sbd_for_calibrator_targets(
    targets: list[Target],
    csp_configuration: CSPConfiguration,
    scan_duration: timedelta,
    num_subarray_beams: int,
    num_scans: int,
    apertures: list[Aperture],
    num_calibrator_beams: int,
) -> SBDefinition:
    """
    Creates a single SBD for the input targets, creating a number of scans
    for each subarray beam (i.e. this assumes len(targets) == num_subarray_beams * num_scans)
    """
    if len(targets) != num_subarray_beams * num_scans:
        raise ValueError(
            f"Expected {num_subarray_beams * num_scans} targets "
            f"({num_subarray_beams} beams x {num_scans} scans), "
            f"but got {len(targets)}"
        )

    subarray_beams = []

    for subarray_beam_index in range(0, num_subarray_beams):

        targets_for_subarray_beam = targets[
            subarray_beam_index * num_scans : (subarray_beam_index + 1) * num_scans
        ]

        subarray_beam_scan_sequence = [
            ScanDefinition(
                scan_definition_id=_sbd_internal_id(ScanDefinition),
                scan_duration_ms=scan_duration,
                target_ref=target.target_id,
                csp_configuration_ref=csp_configuration.config_id,
                scan_intent="Science",
            )
            for target in targets_for_subarray_beam
        ]

        subarray_beams.append(
            SubarrayBeamConfiguration(
                apertures=apertures,
                subarray_beam_id=subarray_beam_index + 1,
                scan_sequence=subarray_beam_scan_sequence,
            )
        )

    for _ in range(0, num_calibrator_beams):
        subarray_beam_scan_sequence = [
            ScanDefinition(
                scan_definition_id=_sbd_internal_id(ScanDefinition),
                scan_duration_ms=scan_duration,
                target_ref=CALIBRATOR_TARGET.target_id,
                csp_configuration_ref=csp_configuration.config_id,
                scan_intent="Calibrator",
            )
            for _ in range(0, num_scans)
        ]

        subarray_beams.append(
            SubarrayBeamConfiguration(
                apertures=apertures,
                subarray_beam_id=len(subarray_beams) + 1,
                scan_sequence=subarray_beam_scan_sequence,
            )
        )

    mccs_allocation = MCCSAllocation(
        mccs_allocation_id=_sbd_internal_id(MCCSAllocation),
        selected_subarray_definition=DEFAULT_SUBARRAY,
        subarray_beams=subarray_beams,
    )

    sdp_configurations = [
        SDPConfiguration(
            sdp_script=SDPScript.VIS_RECEIVE,
            script_version="latest",
            script_parameters={},
        )
    ]

    if num_calibrator_beams is not None and num_calibrator_beams > 0:
        targets += [CALIBRATOR_TARGET]

    return SBDefinition(
        telescope=TelescopeType.SKA_LOW,
        activities=_default_activities(),
        mccs_allocation=mccs_allocation,
        csp_configurations=[csp_configuration],
        sdp_configurations=sdp_configurations,
        targets=targets,
    )


def _default_activities() -> dict[str, GitScript]:
    return {
        "observe": GitScript(
            repo="https://gitlab.com/ska-telescope/oso/ska-oso-scripting.git",
            path="git://scripts/allocate_and_observe_sb.py",
            branch="master",
            commit=None,
        )
    }
