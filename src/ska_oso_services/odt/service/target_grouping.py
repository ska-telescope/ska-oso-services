"""
Domain service for partitioning a target catalogue into spatial groups.

This module is independent of SBD construction — it operates purely on
:class:`~ska_oso_pdm.Target` objects and yields groups of target indices.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import numpy as np
from astropy.coordinates import SkyCoord
from ska_oso_pdm import Target


class GroupingMethod(str, Enum):
    """Strategy used to partition targets into SBD groups."""

    SEQUENTIAL = "sequential"
    CONSTRAINED_RA_SWEEP = "constrained_ra_sweep"


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
        targets: list[Target],
    ) -> DeclinationQueues:
        """Construct DeclinationQueues from a list of Target objects.

        Separation thresholds are derived automatically from the
        k-neighbour spacing statistics of the catalogue.

        Parameters
        ----------
        targets : list[Target]
            Input target list with ICRS coordinates.

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
        dec_uniformity_tolerance: float = 1.5,
        ra_ring_fail_fraction: float = 0.2,
    ) -> None:
        """Validate that the catalogue is suitable for constrained-RA-sweep grouping.

        Parameters
        ----------
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
        dec_diffs = np.diff(self.unique_decs)
        ratio = float(np.max(dec_diffs) / np.min(dec_diffs))
        if ratio > dec_uniformity_tolerance:
            raise ValueError(
                f"Declination spacing is not uniform: max/min gap ratio is "
                f"{ratio:.2f}, exceeding tolerance {dec_uniformity_tolerance}. "
                f"The constrained-RA-sweep algorithm requires approximately equal "
                f"declination spacing between target rings."
            )

        # --- Check 2: No empty rings ---
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

        # --- Check 3: Intra-ring RA spacing vs separation thresholds ---
        failing_rings: list[str] = []
        for q in self.queues:
            if len(q) < 3:
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
                    f"[{self.min_separation:.3f}°, {self.max_separation:.3f}°]"
                )
            if approx_sep_k3 <= self.max_separation:
                issues.append(
                    f"k=3 separation ({approx_sep_k3:.3f}°) <= "
                    f"max_separation ({self.max_separation:.3f}°)"
                )
            if issues:
                failing_rings.append(f"ring at dec≈{ring_dec_mean:.1f}°: {'; '.join(issues)}")

        checkable_rings = sum(1 for q in self.queues if len(q) >= 3)
        if checkable_rings > 0:
            fail_frac = len(failing_rings) / checkable_rings
            if fail_frac > ra_ring_fail_fraction:
                detail = "\n  ".join(failing_rings[:5])
                raise ValueError(
                    f"RA spacing check failed for "
                    f"{len(failing_rings)}/{checkable_rings} "
                    f"rings ({fail_frac:.0%}), exceeding tolerance "
                    f"{ra_ring_fail_fraction:.0%}. Examples:\n  {detail}"
                )


# ---------------------------------------------------------------------------
# TargetGrouper protocol and implementations
# ---------------------------------------------------------------------------


class TargetGrouper(Protocol):
    """Common interface for target-grouping strategies."""

    def group(self, targets: list[Target], group_size: int) -> Iterator[list[int]]:
        """Yield lists of indices into *targets*, one per group."""


class SequentialGrouper:
    """Partition targets into sequential, non-overlapping chunks."""

    def group(self, targets: list[Target], group_size: int) -> Iterator[list[int]]:
        """Yield sequential chunks of target indices."""
        num_targets = len(targets)
        for start in range(0, num_targets, group_size):
            yield list(range(start, min(start + group_size, num_targets)))


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

    def group(self, targets: list[Target], group_size: int) -> Iterator[list[int]]:
        """Yield groups of target indices using constrained-RA-sweep clustering."""
        if self._dec_queues is not None:
            rd = self._dec_queues
        else:
            rd = DeclinationQueues.from_targets(targets)

        coords = rd.coords
        ra_deg = rd.ra_deg
        dec_deg = rd.dec_deg
        min_separation = rd.min_separation
        max_separation = rd.max_separation
        # Deep-copy queues so the grouper can be called again
        queues = [deque(q) for q in rd.queues]

        def _edge_key(i: int, j: int) -> tuple[int, int]:
            return (i, j) if i < j else (j, i)

        edge_separation: dict[tuple[int, int], float] = {}
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
                    edge_separation[_edge_key(pid, other_pid)] = float(
                        coords[pid].separation(coords[other_pid]).degree
                    )
                active_nodes[pid] = None

            if not active_nodes:
                break

            i0 = min(active_nodes, key=lambda n: ra_deg[n])
            group: list[int] = [i0]

            while len(group) < group_size:
                group_dec_min = float(np.min(dec_deg[group])) - max_separation
                group_dec_max = float(np.max(dec_deg[group])) + max_separation
                group_max_ra = float(np.max(ra_deg[group]))

                for q in queues:
                    while q:
                        head_pid = q[0]
                        head_dec = dec_deg[head_pid]
                        if head_dec < group_dec_min or head_dec > group_dec_max:
                            break

                        last_pid = group[-1]
                        head_sep = float(coords[head_pid].separation(coords[last_pid]).degree)
                        if head_sep > max_separation and ra_deg[head_pid] > group_max_ra:
                            break

                        pid = q.popleft()
                        for other_pid in active_nodes:
                            edge_separation[_edge_key(pid, other_pid)] = float(
                                coords[pid].separation(coords[other_pid]).degree
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
                    if not all(edge_separation[pair] >= min_separation for pair in proposed_pairs):
                        continue
                    sep_to_group = [edge_separation[_edge_key(n, g)] for g in group]
                    if not any(min_separation <= sep <= max_separation for sep in sep_to_group):
                        continue
                    if ra_deg[n] < best_ra:
                        best_ra = ra_deg[n]
                        best_candidate = n

                if best_candidate is None:
                    break
                group.append(best_candidate)

            yield [int(n) for n in group]
            removed = set(group)
            for n in group:
                active_nodes.pop(n, None)
            edge_separation = {
                k: v
                for k, v in edge_separation.items()
                if k[0] not in removed and k[1] not in removed
            }

        remaining = [q.popleft() for q in queues for _ in range(len(q))]
        if remaining:
            for start in range(0, len(remaining), group_size):
                yield remaining[start : start + group_size]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_grouper(
    method: GroupingMethod = GroupingMethod.CONSTRAINED_RA_SWEEP,
    **kwargs,
) -> TargetGrouper:
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
