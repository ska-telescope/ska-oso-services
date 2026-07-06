"""
Domain service for partitioning a target catalogue into spatial groups.

This module is independent of SBD construction — it operates on per-target
metadata objects and yields groups of those same objects. Conversion of a
group into PDM :class:`~ska_oso_pdm.Target` objects (or any other
representation) is the responsibility of the caller.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, TypeVar

import numpy as np
from astropy.coordinates import SkyCoord
from ska_oso_pdm import ICRSCoordinates


class GroupingMethod(str, Enum):
    """Strategy used to partition targets into SBD groups."""

    SEQUENTIAL = "sequential"
    CONSTRAINED_RA_SWEEP = "constrained_ra_sweep"


DEC_UNIFORMITY_RELATIVE_TOLERANCE = 0.01
DEFAULT_RELATIVE_MIN_SEPARATION = 1.0
DEFAULT_RELATIVE_MAX_SEPARATION = 3.0


@dataclass(frozen=True)
class PointingTarget:
    """Pointing payload: target fields plus beam FWHM in degrees."""

    target_id: str
    name: str
    reference_coordinate: ICRSCoordinates
    fwhm_deg: float


class GroupingTarget(Protocol):
    """Protocol for grouping algorithms that only require target coordinates."""

    target_id: str
    name: str
    reference_coordinate: ICRSCoordinates


class RelativeSeparationGroupingTarget(GroupingTarget, Protocol):
    """Protocol for grouping algorithms that require relative-separation metadata."""

    fwhm_deg: float


# TypeVars parametrising the grouper protocol / implementations. A grouper
# yields groups of the *same* target type it received, so the target type is
# preserved through the group boundary (invariant: appears in both input and
# output positions).
GroupingTargetT = TypeVar("GroupingTargetT", bound=GroupingTarget)
RelativeSeparationGroupingTargetT = TypeVar(
    "RelativeSeparationGroupingTargetT", bound=RelativeSeparationGroupingTarget
)


# ---------------------------------------------------------------------------
# DeclinationQueues — value object describing the ring geometry of a catalogue
# ---------------------------------------------------------------------------


@dataclass
class DeclinationQueues:
    """Derived spatial data from a target catalogue for constrained-RA-sweep grouping."""

    coords: SkyCoord
    ra_deg: np.ndarray
    dec_deg: np.ndarray
    unique_decs: np.ndarray
    delta_dec: float
    first_bin_center_dec: float
    min_separation: float
    max_separation: float
    queues: list[deque[int]] = field(default_factory=list)

    @classmethod
    def _from_coords(
        cls,
        coords: SkyCoord,
    ) -> DeclinationQueues:
        """Shared construction logic from a SkyCoord array."""
        ra_deg = np.asarray(coords.ra.deg)
        dec_deg = np.asarray(coords.dec.deg)

        unique_decs = np.unique(np.round(dec_deg, decimals=5))
        if len(unique_decs) < 2:
            raise ValueError(
                "Constrained-RA-sweep grouping requires targets at two or more "
                "distinct declination values to derive the bin width"
            )
        delta_dec = float(np.min(np.diff(unique_decs)))

        first_bin_center_dec = float(np.min(dec_deg))

        ring_ids = np.floor((dec_deg - first_bin_center_dec) / delta_dec + 0.5).astype(int)
        queues: list[deque[int]] = []
        for ring_id in sorted(np.unique(ring_ids)):
            ring_mask = ring_ids == ring_id
            indices = np.where(ring_mask)[0]
            indices_sorted = indices[np.argsort(ra_deg[indices])]
            queues.append(deque(indices_sorted.tolist()))

        # Derive min/max separation from k-neighbour statistics.
        # For each ring, compute the approximate angular separation
        # between targets at offset k as delta_ra * cos(dec).
        k_global_max: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}
        k_global_min: dict[int, float] = {
            1: float("inf"),
            2: float("inf"),
            3: float("inf"),
        }
        for q in queues:
            if len(q) < 4:
                continue
            indices = list(q)
            ring_ra = ra_deg[indices]
            ring_dec_mean = float(np.mean(dec_deg[indices]))
            cos_dec = float(np.cos(np.radians(ring_dec_mean)))
            for k in (1, 2, 3):
                if len(ring_ra) < k + 1:
                    continue
                seps = (ring_ra[k:] - ring_ra[:-k]) * cos_dec
                k_global_min[k] = min(k_global_min[k], float(np.min(seps)))
                k_global_max[k] = max(k_global_max[k], float(np.max(seps)))

        if k_global_min[2] == float("inf"):
            # Fallback for catalogues with very few targets per ring
            min_separation = delta_dec * 1.2
            max_separation = delta_dec * 2.4
        else:
            min_separation = (k_global_max[1] + k_global_min[2]) / 2.0
            max_separation = (k_global_max[2] + k_global_min[3]) / 2.0

        return cls(
            coords=coords,
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            unique_decs=unique_decs,
            delta_dec=delta_dec,
            first_bin_center_dec=first_bin_center_dec,
            min_separation=min_separation,
            max_separation=max_separation,
            queues=queues,
        )

    @classmethod
    def from_targets(
        cls,
        targets: Sequence[GroupingTarget],
    ) -> DeclinationQueues:
        """Construct DeclinationQueues from a sequence of per-target metadata objects.

        Separation thresholds are derived automatically from the
        k-neighbour spacing statistics of the catalogue.

        Parameters
        ----------
        targets : Sequence[GroupingTarget]
            Input targets with ICRS coordinates.

        Raises
        ------
        ValueError
            If fewer than two distinct declination values are present.
        """
        coords = SkyCoord(
            [t.reference_coordinate.to_sky_coord() for t in targets],
            frame="icrs",
        )
        return cls._from_coords(coords)

    @classmethod
    def from_sky_coord(
        cls,
        coords: SkyCoord,
    ) -> DeclinationQueues:
        """Construct DeclinationQueues from an existing SkyCoord array.

        Separation thresholds are derived automatically from the
        k-neighbour spacing statistics of the catalogue.

        Parameters
        ----------
        coords : SkyCoord
            Sky coordinates for all targets.

        Raises
        ------
        ValueError
            If fewer than two distinct declination values are present.
        """
        return cls._from_coords(coords)

    def validate(
        self,
        *,
        dec_uniformity_tolerance: float = DEC_UNIFORMITY_RELATIVE_TOLERANCE,
    ) -> None:
        """Validate that the catalogue is suitable for constrained-RA-sweep grouping.

        Parameters
        ----------
        dec_uniformity_tolerance : float
            Maximum allowed relative deviation of declination gaps from ``delta_dec``.
            Default is ``DEC_UNIFORMITY_RELATIVE_TOLERANCE`` = 0.01.

        Raises
        ------
        ValueError
            If the catalogue fails any of the structural checks.
        """
        # --- Check 1: No empty rings ---
        expected_num_rings = (
            round((self.unique_decs[-1] - self.unique_decs[0]) / self.delta_dec) + 1
        )
        if len(self.unique_decs) < expected_num_rings:
            raise ValueError(
                f"Empty ring(s) detected: expected {expected_num_rings} rings "
                f"but found {len(self.unique_decs)}. "
                f"The constrained-RA-sweep algorithm requires every declination ring "
                f"between the first and last to contain at least one target."
            )

        # --- Check 2: Uniform declination spacing ---
        dec_diffs = np.diff(self.unique_decs)
        rel_error = np.abs(dec_diffs - self.delta_dec) / self.delta_dec
        max_rel_error = float(np.max(rel_error))
        if max_rel_error > dec_uniformity_tolerance:
            raise ValueError(
                f"Declination spacing is not uniform: maximum relative deviation from "
                f"delta_dec is {max_rel_error:.2%}, exceeding tolerance "
                f"{dec_uniformity_tolerance:.2%}. "
                f"The constrained-RA-sweep algorithm requires near-uniform "
                f"declination spacing between rings."
            )

        # --- Check 3: Intra-ring RA spacing vs separation thresholds ---
        issue_lines: list[str] = []
        failing_dec_count = 0
        for q in self.queues:
            if len(q) < 4:
                continue
            indices = list(q)
            ring_ra = self.ra_deg[indices]
            ring_dec_mean = float(np.mean(self.dec_deg[indices]))
            cos_dec = np.cos(np.radians(ring_dec_mean))

            ra_gaps = np.diff(ring_ra)
            delta_ra = float(np.median(ra_gaps))
            approx_sep_k1 = delta_ra * cos_dec
            approx_sep_k2 = 2.0 * delta_ra * cos_dec
            approx_sep_k3 = 3.0 * delta_ra * cos_dec

            issues: list[str] = []
            if approx_sep_k1 >= self.min_separation:
                issues.append(
                    f"k=1 separation ({approx_sep_k1:.3f}°) >= "
                    f"min_separation ({self.min_separation:.3f}°)"
                )
            if not (self.min_separation <= approx_sep_k2 <= self.max_separation):
                issues.append(
                    f"k=2 separation ({approx_sep_k2:.3f}°) not in "
                    f"[min_separation ({self.min_separation:.3f}°), "
                    f"max_separation ({self.max_separation:.3f}°)]"
                )
            if approx_sep_k3 <= self.max_separation:
                issues.append(
                    f"k=3 separation ({approx_sep_k3:.3f}°) <= "
                    f"max_separation ({self.max_separation:.3f}°)"
                )
            if issues:
                failing_dec_count += 1
                issue_lines.extend(
                    f"ring at dec≈{ring_dec_mean:.1f}°: {issue}" for issue in issues
                )

        if issue_lines:
            shown_lines = issue_lines[:10]
            detail = "\n  ".join(shown_lines)
            remaining = len(issue_lines) - len(shown_lines)
            tail = f"\n  plus {remaining} further issues" if remaining > 0 else ""
            raise ValueError(
                f"RA spacing check failed at {failing_dec_count} declinations. "
                f"Every declination with at least four targets must satisfy "
                f"the k=1/k=2/k=3 separation bounds.\n  {detail}{tail}"
            )


# ---------------------------------------------------------------------------
# TargetGrouper protocol and implementations
# ---------------------------------------------------------------------------


class TargetGrouper(Protocol[GroupingTargetT]):
    """Common interface for target-grouping strategies.

    A grouper partitions its input targets into groups and yields each group
    as a list of the *same* target type it received. Conversion of a group
    into PDM :class:`~ska_oso_pdm.Target` objects (or any other
    representation) is the responsibility of the caller, keeping this module
    independent of SBD construction.

    The protocol is parametrised by the target type so that groupers requiring
    richer metadata can be distinguished from those that do not — for example
    ``TargetGrouper[RelativeSeparationGroupingTarget]`` for a strategy that
    needs per-target beam FWHM.
    """

    def group(
        self, targets: Sequence[GroupingTargetT], group_size: int
    ) -> Iterator[list[GroupingTargetT]]:
        """Yield groups of the input targets, one list per group."""


class SequentialGrouper:
    """Partition targets into sequential, non-overlapping chunks."""

    def group(
        self, targets: Sequence[GroupingTargetT], group_size: int
    ) -> Iterator[list[GroupingTargetT]]:
        """Yield sequential chunks of the input targets."""
        num_targets = len(targets)
        for start in range(0, num_targets, group_size):
            yield list(targets[start : min(start + group_size, num_targets)])


class ConstrainedRaSweepGrouper:
    """Partition targets using a greedy DEC-constrainted RA sweep.

    The algorithm uses greedy local heuristics to generate groups with
    small sky footprints and small LST ranges, with the expectation
    that this will make them easy to schedule.

    **Catalogue geometry assumptions**

    1. **Declination rings** — targets live on a discrete set of
       declination values (rings), approximately equally spaced in
       declination.
    2. **Uniform intra-ring spacing** — within each ring, targets are
       approximately equally spaced in right ascension.
    3. **Similar angular scale** — the RA spacing between neighbouring
       targets on a ring is similar to the declination spacing between
       rings, and similar across all rings.

    Use :meth:`DeclinationQueues.validate` to check whether a catalogue
    satisfies these assumptions before grouping.

    **Algorithm**

    1. Form RA-sorted queues of targets at each declination ring.
    2. Determine ``min_separation`` and ``max_separation`` such that
       k=1 nearest neighbours in each queue are below
       ``min_separation``, k=2 nearest neighbours are between
       ``min_separation`` and ``max_separation``, and k=3 nearest
       neighbours are above ``max_separation``.
    3. Seed a new group with the lowest-RA target amongst all queues.
    4. Iteratively add targets to the group until it is full or no
       candidates remain:

       - A candidate must be more than ``min_separation`` from
         *every* target already in the group.
       - A candidate must be between ``min_separation`` and
         ``max_separation`` from *at least one* target in the group.
       - The candidate with the minimum RA is selected.

    5. Yield the group and repeat from step 3 until all targets are
       assigned.

    Note that within a completed group, some pairs of members may be
    at k=3 distances from each other.  This is expected: each member
    was added because it had at least one k=2-distance neighbour
    already in the group, but it is not required to be close to every
    other member.

    Parameters
    ----------
    dec_queues : DeclinationQueues, optional
        Pre-computed ring data.  If not supplied, it will be derived
        from the targets passed to :meth:`group`.
    """

    def __init__(
        self,
        dec_queues: DeclinationQueues | None = None,
    ) -> None:
        self._dec_queues = dec_queues

    def group(
        self, targets: Sequence[RelativeSeparationGroupingTargetT], group_size: int
    ) -> Iterator[list[RelativeSeparationGroupingTargetT]]:
        """Yield groups of the input targets using constrained-RA-sweep clustering."""
        if self._dec_queues is not None:
            rd = self._dec_queues
        else:
            rd = DeclinationQueues.from_targets(targets)

        coords = rd.coords
        ra_deg = rd.ra_deg
        dec_deg = rd.dec_deg
        relative_min_separation = DEFAULT_RELATIVE_MIN_SEPARATION
        relative_max_separation = DEFAULT_RELATIVE_MAX_SEPARATION
        fwhm_deg = np.asarray([float(target.fwhm_deg) for target in targets], dtype=float)
        if np.any(fwhm_deg <= 0.0):
            raise ValueError("All target fwhm_deg values must be > 0 for relative separation")
        # Conservative angular bound used for geometric frontier pruning.
        max_angular_separation = relative_max_separation * float(np.max(fwhm_deg))
        # Deep-copy queues so the grouper can be called again
        queues = [deque(q) for q in rd.queues]

        def _edge_key(i: int, j: int) -> tuple[int, int]:
            return (i, j) if i < j else (j, i)

        edge_relative_separation: dict[tuple[int, int], float] = {}
        active_nodes: dict[int, None] = {}

        # --- Main grouping loop ---
        while any(q for q in queues) or active_nodes:
            for q in queues:
                if not q:
                    continue
                if active_nodes:
                    graph_min_ra = min(ra_deg[n] for n in active_nodes)
                    if ra_deg[q[0]] >= graph_min_ra:
                        continue
                pid = q.popleft()
                for other_pid in active_nodes:
                    angular_sep_deg = float(coords[pid].separation(coords[other_pid]).degree)
                    pair_avg_fwhm = 0.5 * (fwhm_deg[pid] + fwhm_deg[other_pid])
                    edge_relative_separation[_edge_key(pid, other_pid)] = angular_sep_deg / float(
                        pair_avg_fwhm
                    )
                active_nodes[pid] = None

            if not active_nodes:
                break

            i0 = min(active_nodes, key=lambda n: ra_deg[n])
            group: list[int] = [i0]

            while len(group) < group_size:
                group_dec_min = float(np.min(dec_deg[group])) - max_angular_separation
                group_dec_max = float(np.max(dec_deg[group])) + max_angular_separation
                group_max_ra = float(np.max(ra_deg[group]))

                for q in queues:
                    while q:
                        head_pid = q[0]
                        head_dec = dec_deg[head_pid]
                        if head_dec < group_dec_min or head_dec > group_dec_max:
                            break

                        last_pid = group[-1]
                        head_sep_deg = float(coords[head_pid].separation(coords[last_pid]).degree)
                        head_pair_avg_fwhm = 0.5 * (fwhm_deg[head_pid] + fwhm_deg[last_pid])
                        head_relative_sep = head_sep_deg / float(head_pair_avg_fwhm)
                        if (
                            head_relative_sep > relative_max_separation
                            and ra_deg[head_pid] > group_max_ra
                        ):
                            break

                        pid = q.popleft()
                        for other_pid in active_nodes:
                            angular_sep_deg = float(
                                coords[pid].separation(coords[other_pid]).degree
                            )
                            pair_avg_fwhm = 0.5 * (fwhm_deg[pid] + fwhm_deg[other_pid])
                            edge_relative_separation[_edge_key(pid, other_pid)] = (
                                angular_sep_deg / float(pair_avg_fwhm)
                            )
                        active_nodes[pid] = None

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
                        edge_relative_separation[pair] >= relative_min_separation
                        for pair in proposed_pairs
                    ):
                        continue
                    relative_sep_to_group = [
                        edge_relative_separation[_edge_key(n, g)] for g in group
                    ]
                    if not any(
                        relative_min_separation <= sep <= relative_max_separation
                        for sep in relative_sep_to_group
                    ):
                        continue
                    if ra_deg[n] < best_ra:
                        best_ra = ra_deg[n]
                        best_candidate = n

                if best_candidate is None:
                    break
                group.append(best_candidate)

            yield [targets[int(n)] for n in group]
            removed = set(group)
            for n in group:
                active_nodes.pop(n, None)
            edge_relative_separation = {
                k: v
                for k, v in edge_relative_separation.items()
                if k[0] not in removed and k[1] not in removed
            }

        remaining = [q.popleft() for q in queues for _ in range(len(q))]
        if remaining:
            for start in range(0, len(remaining), group_size):
                yield [targets[int(n)] for n in remaining[start : start + group_size]]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_grouper(
    method: GroupingMethod = GroupingMethod.CONSTRAINED_RA_SWEEP,
    **kwargs,
) -> TargetGrouper[PointingTarget]:
    """Create a :class:`TargetGrouper` for the given method.

    Parameters
    ----------
    method : GroupingMethod
        The grouping strategy to use.
    **kwargs
        Extra keyword arguments forwarded to the grouper constructor
        (e.g. ``dec_queues``).
    """
    if method == GroupingMethod.SEQUENTIAL:
        return SequentialGrouper()
    if method == GroupingMethod.CONSTRAINED_RA_SWEEP:
        return ConstrainedRaSweepGrouper(**kwargs)
    raise ValueError(f"Unknown grouping method: {method}")
