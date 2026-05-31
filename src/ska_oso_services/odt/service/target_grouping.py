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
    RING_BUFFER = "ring_buffer"


# ---------------------------------------------------------------------------
# RingData — value object describing the ring geometry of a catalogue
# ---------------------------------------------------------------------------


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

    @classmethod
    def _from_coords(
        cls,
        coords: SkyCoord,
        *,
        min_separation_factor: float = 1.2,
        max_separation_factor: float = 2.4,
    ) -> RingData:
        """Shared construction logic from a SkyCoord array."""
        ra_deg = np.asarray(coords.ra.deg)
        dec_deg = np.asarray(coords.dec.deg)

        unique_decs = np.unique(np.round(dec_deg, decimals=5))
        if len(unique_decs) < 2:
            raise ValueError(
                "Ring-buffer grouping requires targets at two or more "
                "distinct declination values to derive the bin width"
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

        return cls(
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

    @classmethod
    def from_targets(
        cls,
        targets: list[Target],
        *,
        min_separation_factor: float = 1.2,
        max_separation_factor: float = 2.4,
    ) -> RingData:
        """Construct RingData from a list of Target objects.

        Parameters
        ----------
        targets : list[Target]
            Input target list with ICRS coordinates.
        min_separation_factor : float
            Minimum pairwise angular separation as a multiple of
            ``delta_dec``.  Defaults to 1.2.
        max_separation_factor : float
            Maximum angular separation as a multiple of ``delta_dec``.
            Defaults to 2.4.

        Raises
        ------
        ValueError
            If fewer than two distinct declination values are present.
        """
        coords = SkyCoord(
            [t.reference_coordinate.to_sky_coord() for t in targets],
            frame="icrs",
        )
        return cls._from_coords(
            coords,
            min_separation_factor=min_separation_factor,
            max_separation_factor=max_separation_factor,
        )

    @classmethod
    def from_sky_coord(
        cls,
        coords: SkyCoord,
        *,
        min_separation_factor: float = 1.2,
        max_separation_factor: float = 2.4,
    ) -> RingData:
        """Construct RingData from an existing SkyCoord array.

        Parameters
        ----------
        coords : SkyCoord
            Sky coordinates for all targets.
        min_separation_factor : float
            Minimum pairwise angular separation as a multiple of
            ``delta_dec``.  Defaults to 1.2.
        max_separation_factor : float
            Maximum angular separation as a multiple of ``delta_dec``.
            Defaults to 2.4.

        Raises
        ------
        ValueError
            If fewer than two distinct declination values are present.
        """
        return cls._from_coords(
            coords,
            min_separation_factor=min_separation_factor,
            max_separation_factor=max_separation_factor,
        )

    def validate(
        self,
        *,
        dec_uniformity_tolerance: float = 1.5,
        ra_ring_fail_fraction: float = 0.2,
    ) -> None:
        """Validate that the catalogue is suitable for ring-buffer grouping.

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
                f"The ring-buffer algorithm requires approximately equal "
                f"declination spacing between target rings."
            )

        # --- Check 2: No empty rings ---
        expected_ids = set(
            range(int(np.min(self.ring_ids)), int(np.max(self.ring_ids)) + 1)
        )
        actual_ids = set(int(rid) for rid in np.unique(self.ring_ids))
        missing = expected_ids - actual_ids
        if missing:
            raise ValueError(
                f"Empty ring(s) detected at ring id(s) {sorted(missing)}. "
                f"The ring-buffer algorithm requires every declination ring "
                f"between the first and last to contain at least one target."
            )

        # --- Check 3: Intra-ring RA spacing vs separation thresholds ---
        failing_rings: list[str] = []
        for q in self.ring_queues:
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
                failing_rings.append(
                    f"ring at dec≈{ring_dec_mean:.1f}°: {'; '.join(issues)}"
                )

        checkable_rings = sum(1 for q in self.ring_queues if len(q) >= 3)
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

    def group(
        self, targets: list[Target], group_size: int
    ) -> Iterator[list[int]]:
        """Yield lists of indices into *targets*, one per group."""


class SequentialGrouper:
    """Partition targets into sequential, non-overlapping chunks."""

    def group(
        self, targets: list[Target], group_size: int
    ) -> Iterator[list[int]]:
        """Yield sequential chunks of target indices."""
        num_targets = len(targets)
        for start in range(0, num_targets, group_size):
            yield list(range(start, min(start + group_size, num_targets)))


class RingBufferGrouper:
    """Partition targets using ring-buffer spatial clustering.

    Parameters
    ----------
    ring_data : RingData, optional
        Pre-computed ring data.  If not supplied, it will be derived
        from the targets passed to :meth:`group`.
    min_separation_factor : float
        Minimum pairwise angular separation as a multiple of
        ``delta_dec``.  Only used when *ring_data* is not provided.
    max_separation_factor : float
        Maximum angular separation as a multiple of ``delta_dec``.
        Only used when *ring_data* is not provided.
    """

    def __init__(
        self,
        ring_data: RingData | None = None,
        *,
        min_separation_factor: float = 1.2,
        max_separation_factor: float = 2.4,
    ) -> None:
        self._ring_data = ring_data
        self._min_separation_factor = min_separation_factor
        self._max_separation_factor = max_separation_factor

    def group(
        self, targets: list[Target], group_size: int
    ) -> Iterator[list[int]]:
        """Yield groups of target indices using ring-buffer clustering."""
        if self._ring_data is not None:
            rd = self._ring_data
        else:
            rd = RingData.from_targets(
                targets,
                min_separation_factor=self._min_separation_factor,
                max_separation_factor=self._max_separation_factor,
            )

        coords = rd.coords
        ra_deg = rd.ra_deg
        dec_deg = rd.dec_deg
        min_separation = rd.min_separation
        max_separation = rd.max_separation
        # Deep-copy queues so the grouper can be called again
        ring_queues = [deque(q) for q in rd.ring_queues]

        def _edge_key(i: int, j: int) -> tuple[int, int]:
            return (i, j) if i < j else (j, i)

        edge_separation: dict[tuple[int, int], float] = {}
        active_nodes: dict[int, None] = {}

        # --- Main grouping loop ---
        while any(q for q in ring_queues) or active_nodes:
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

            i0 = min(active_nodes, key=lambda n: ra_deg[n])
            group: list[int] = [i0]

            while len(group) < group_size:
                group_dec_min = (
                    float(np.min(dec_deg[group])) - max_separation
                )
                group_dec_max = (
                    float(np.max(dec_deg[group])) + max_separation
                )
                group_max_ra = float(np.max(ra_deg[group]))

                for q in ring_queues:
                    while q:
                        head_pid = q[0]
                        head_dec = dec_deg[head_pid]
                        if (
                            head_dec < group_dec_min
                            or head_dec > group_dec_max
                        ):
                            break

                        last_pid = group[-1]
                        head_sep = float(
                            coords[head_pid]
                            .separation(coords[last_pid])
                            .degree
                        )
                        if (
                            head_sep > max_separation
                            and ra_deg[head_pid] > group_max_ra
                        ):
                            break

                        pid = q.popleft()
                        for other_pid in active_nodes:
                            edge_separation[
                                _edge_key(pid, other_pid)
                            ] = float(
                                coords[pid]
                                .separation(coords[other_pid])
                                .degree
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
                        edge_separation[pair] >= min_separation
                        for pair in proposed_pairs
                    ):
                        continue
                    sep_to_group = [
                        edge_separation[_edge_key(n, g)] for g in group
                    ]
                    if not any(
                        min_separation <= sep <= max_separation
                        for sep in sep_to_group
                    ):
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

        remaining = [
            q.popleft() for q in ring_queues for _ in range(len(q))
        ]
        if remaining:
            for start in range(0, len(remaining), group_size):
                yield remaining[start : start + group_size]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_grouper(
    method: GroupingMethod = GroupingMethod.SEQUENTIAL,
    **kwargs,
) -> TargetGrouper:
    """Create a :class:`TargetGrouper` for the given method.

    Parameters
    ----------
    method : GroupingMethod
        The grouping strategy to use.
    **kwargs
        Extra keyword arguments forwarded to the grouper constructor
        (e.g. ``ring_data``, ``min_separation_factor``).
    """
    if method == GroupingMethod.SEQUENTIAL:
        return SequentialGrouper()
    if method == GroupingMethod.RING_BUFFER:
        return RingBufferGrouper(**kwargs)
    raise ValueError(f"Unknown grouping method: {method}")
