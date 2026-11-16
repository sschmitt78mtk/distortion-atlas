"""Dot-by-dot scotoma test: trial plan, timing and per-position verdicts.

The module is pure: every call takes ``now_ms`` and nothing here reads the clock
itself, imports a GUI toolkit or renders a frame. That is what lets the 1500 ms
response window and the randomised inter-trial gaps be driven by a fake clock in
the tests while the Qt presenter only samples the real one (design D1).

The test walks a rectangular lattice anchored on the fixation position. All
inner 5x5 positions except the centre are tested first, then a seeded random
sample of the rest of the field. A missed position is retried once; a second
miss marks it blind and queues its eight neighbours, so a confirmed blind region
is mapped outward until the surround is seen (design D2/D4).

Both presentation variants share this state machine: the standard variant lights
one dot on a dark field, while the inverse variant draws dark dots on a bright
field and blinks the probed dot between absent and present at a fixed
half-period (design D1/D2/D7).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable

from .geometry import DEFAULT_MARGIN_PX, Scale
from .patterns import anchor

#: Slot between the presentation and its retry, in queue positions.
DEFAULT_RETRY_SPACING = 5

#: How far ahead of the queue head a neighbour probe is inserted.
DEFAULT_PROBE_OFFSET = 2

#: A run with this many or fewer seen inner-ring dots is not interpretable.
MIN_CENTRAL_SEEN = 3

#: Position verdicts and presentation outcomes.
UNSEEN = "untested"
SEEN = "seen"
BLIND = "blind"

SEEN_OUTCOME = "seen"
MISS_OUTCOME = "miss"
ABORTED_OUTCOME = "aborted"

#: Presentation variants: a lit dot on black, or dark dots on a bright field
#: with the probed dot blinking away (design D1/D2).
STANDARD = "standard"
INVERSE = "inverse"
VARIANT_NAMES: tuple[str, ...] = (STANDARD, INVERSE)

#: Half-period of the inverse variant's blink, in milliseconds (design D7).
INVERSE_BLINK_MS = 500

#: Shortest allowed blink half-period, so the stimulus cannot become a strobe.
MIN_BLINK_MS = 100


@dataclass(frozen=True)
class BlindSpotSettings:
    """Every knob of one run, with the defaults from design D2/D4."""

    window_ms: int = 1500
    gap: tuple[int, int] = (500, 3000)
    retries: int = 1
    retry_spacing: int = DEFAULT_RETRY_SPACING
    probe_offset: int = DEFAULT_PROBE_OFFSET
    inner: int = 5
    outside_sample: int = 75
    dot_px: int = 8
    trial_cap: int = 400
    deadline_ms: int = 1_200_000
    seed: int | None = None
    variant: str = STANDARD
    blink_ms: int = 0

    def __post_init__(self) -> None:
        if int(self.window_ms) < 1:
            raise ValueError(f"window_ms must be positive, got {self.window_ms!r}")
        low, high = (int(self.gap[0]), int(self.gap[1]))
        if low < 0 or high < low:
            raise ValueError(
                f"gap must be (low, high) with 0 <= low <= high, got {self.gap!r}"
            )
        if int(self.retries) < 0:
            raise ValueError(f"retries must not be negative, got {self.retries!r}")
        if int(self.inner) < 1:
            raise ValueError(f"inner must be at least 1, got {self.inner!r}")
        if int(self.outside_sample) < 0:
            raise ValueError(
                f"outside_sample must not be negative, got {self.outside_sample!r}"
            )
        if int(self.dot_px) < 1:
            raise ValueError(f"dot_px must be positive, got {self.dot_px!r}")
        if int(self.trial_cap) < 1:
            raise ValueError(f"trial_cap must be positive, got {self.trial_cap!r}")
        if int(self.deadline_ms) < 1:
            raise ValueError(f"deadline_ms must be positive, got {self.deadline_ms!r}")
        if self.variant not in VARIANT_NAMES:
            raise ValueError(
                f"variant must be one of {VARIANT_NAMES}, got {self.variant!r}"
            )
        if int(self.blink_ms) < 0:
            raise ValueError(f"blink_ms must not be negative, got {self.blink_ms!r}")
        if int(self.blink_ms) and not (
            MIN_BLINK_MS <= int(self.blink_ms) <= int(self.window_ms) // 2
        ):
            raise ValueError(
                f"blink_ms must be 0 or between {MIN_BLINK_MS} and "
                f"{int(self.window_ms) // 2}, got {self.blink_ms!r}"
            )


@dataclass
class Attempt:
    """One presentation of a position: onset, optional latency and outcome."""

    onset_ms: int
    response_ms: int | None = None
    outcome: str = MISS_OUTCOME

    def to_dict(self) -> dict:
        return {
            "onset_ms": int(self.onset_ms),
            "response_ms": None if self.response_ms is None else int(self.response_ms),
            "outcome": self.outcome,
        }


@dataclass
class Position:
    """One lattice position and everything the run learned about it."""

    col: int
    row: int
    x_px: int
    y_px: int
    verdict: str = UNSEEN
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def key(self) -> tuple[int, int]:
        return (int(self.col), int(self.row))

    def to_dict(self) -> dict:
        return {
            "col": int(self.col),
            "row": int(self.row),
            "x_px": int(self.x_px),
            "y_px": int(self.y_px),
            "verdict": self.verdict,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


@dataclass(frozen=True)
class Lattice:
    """Rectangular test lattice aligned to the lines pattern's anchor."""

    origin_px: tuple[int, int]
    columns: int
    rows: int
    spacing_px: int
    x_half_px: int
    y_half_px: int

    @property
    def centre_col(self) -> int:
        return int(self.columns) // 2

    @property
    def centre_row(self) -> int:
        return int(self.rows) // 2

    def position_xy(self, col: int, row: int) -> tuple[int, int]:
        x = int(self.origin_px[0]) + (int(col) - self.centre_col) * int(self.spacing_px)
        y = int(self.origin_px[1]) + (int(row) - self.centre_row) * int(self.spacing_px)
        return x, y

    def as_dict(self) -> dict:
        return {
            "origin_px": [int(self.origin_px[0]), int(self.origin_px[1])],
            "columns": int(self.columns),
            "rows": int(self.rows),
            "spacing_px": int(self.spacing_px),
            "x_half_px": int(self.x_half_px),
            "y_half_px": int(self.y_half_px),
        }


def build_lattice(
    width: int,
    height: int,
    dot_pitch: int,
    margin_px: int = DEFAULT_MARGIN_PX,
) -> Lattice:
    """A rectangular lattice centred on ``anchor(width, height)``.

    The spacing is twice the lines pattern's ``dot_pitch`` so every test
    position is also a dot of the static lines lattice, and the field reaches
    the buffer edge minus the standard margin on each axis (design D2).
    """
    origin_x, origin_y = anchor(width, height)
    spacing = 2 * max(1, int(dot_pitch))
    x_half = int(width) // 2 - int(margin_px)
    y_half = int(height) // 2 - int(margin_px)
    if x_half < 0 or y_half < 0:
        raise ValueError(
            f"buffer {width}×{height} px is too small for a {margin_px} px margin"
        )
    half_columns = x_half // spacing
    half_rows = y_half // spacing
    return Lattice(
        origin_px=(origin_x, origin_y),
        columns=2 * half_columns + 1,
        rows=2 * half_rows + 1,
        spacing_px=spacing,
        x_half_px=x_half,
        y_half_px=y_half,
    )


class BlindSpotTest:
    """One scotoma-test run, driven entirely by caller-supplied timestamps.

    States are ``waiting`` (random gap), ``active`` (one dot in its 1500 ms
    window), ``paused`` (frozen clock) and ``finished``. :meth:`tick` returns
    whether the frame changed so the presenter repaints only on a transition.
    """

    def __init__(
        self,
        settings: BlindSpotSettings | None = None,
        width: int = 1920,
        height: int = 1080,
        dot_pitch: int = 50,
        now_ms: int | float | None = None,
    ) -> None:
        self.settings = settings or BlindSpotSettings()
        self.lattice = build_lattice(width, height, dot_pitch)
        self.width = int(width)
        self.height = int(height)

        self.seed = (
            int(self.settings.seed)
            if self.settings.seed is not None
            else random.SystemRandom().randrange(1 << 31)
        )
        self._rng = random.Random(self.seed)

        self._positions: dict[tuple[int, int], Position] = {}
        for row in range(self.lattice.rows):
            for col in range(self.lattice.columns):
                x, y = self.lattice.position_xy(col, row)
                position = Position(col=col, row=row, x_px=x, y_px=y)
                self._positions[position.key] = position
        self.positions: list[Position] = list(self._positions.values())
        #: The fixation mark sits here; this position is never presented.
        self._centre_key = (self.lattice.centre_col, self.lattice.centre_row)

        self._inner_keys = self._build_inner_ring()
        self.queue: list[tuple[int, int, int]] = self._build_initial_queue()
        self._queued: set[tuple[int, int]] = {
            (col, row) for col, row, _ in self.queue
        }
        self._presented: set[tuple[int, int]] = set()

        self.state = "waiting"
        self.current: Position | None = None
        self.current_entry: tuple[int, int, int] | None = None
        self.onset_ms: int | None = None
        self.window_end_ms: int | None = None
        self.gap_end_ms: int | None = None
        #: Whether the probe signal is on screen: a lit dot in the standard
        #: variant, an erased dot in the inverse variant.
        self.probe_shown = False
        self.started_at_ms: int | None = None
        self.stopped_at_ms: int | None = None
        self.presentations = 0
        self.late_responses = 0
        self.last_latency_ms: int | None = None

        self._paused_at_ms: int | None = None
        self._resume_with_gap = False

        if now_ms is not None:
            self._begin(float(now_ms))

    # -- construction helpers ------------------------------------------------
    def _build_inner_ring(self) -> set[tuple[int, int]]:
        half = int(self.settings.inner) // 2
        centre_col, centre_row = self._centre_key
        keys: set[tuple[int, int]] = set()
        for row in range(centre_row - half, centre_row + half + 1):
            for col in range(centre_col - half, centre_col + half + 1):
                key = (col, row)
                if key == self._centre_key or key not in self._positions:
                    continue
                keys.add(key)
        return keys

    def _build_initial_queue(self) -> list[tuple[int, int, int]]:
        inner = sorted(self._inner_keys, key=lambda key: (key[1], key[0]))
        outside = sorted(
            (
                key
                for key in self._positions
                if key not in self._inner_keys and key != self._centre_key
            ),
            key=lambda key: (key[1], key[0]),
        )
        sample_size = min(int(self.settings.outside_sample), len(outside))
        sample = self._rng.sample(outside, sample_size) if sample_size else []
        entries = [(col, row, 1) for col, row in inner + list(sample)]
        self._rng.shuffle(entries)
        return entries

    # -- state inspection ----------------------------------------------------
    @property
    def finished(self) -> bool:
        return self.state == "finished"

    @property
    def paused(self) -> bool:
        return self.state == "paused"

    @property
    def lit(self) -> bool:
        """Whether a presentation is open (the probe is in its window)."""
        return self.state == "active" and self.current is not None

    @property
    def running(self) -> bool:
        return not self.finished

    @property
    def inner_ring_total(self) -> int:
        return len(self._inner_keys)

    def position(self, col: int, row: int) -> Position | None:
        return self._positions.get((int(col), int(row)))

    # -- clock ---------------------------------------------------------------
    def _begin(self, now_ms: float) -> None:
        self.started_at_ms = float(now_ms)
        self.state = "waiting"
        self.gap_end_ms = float(now_ms) + self._next_gap_ms()

    def _next_gap_ms(self) -> int:
        low, high = (int(self.settings.gap[0]), int(self.settings.gap[1]))
        return self._rng.randint(low, high)

    def _relative_ms(self, when_ms: float) -> int:
        start = self.started_at_ms if self.started_at_ms is not None else 0.0
        return int(round(float(when_ms) - start))

    def tick(self, now_ms: int | float) -> bool:
        """Advance the clock; return whether the presented frame changed."""
        now = float(now_ms)
        if self.state in ("finished", "paused"):
            return False
        if self.started_at_ms is None:
            self._begin(now)
            return True

        if now - self.started_at_ms >= float(self.settings.deadline_ms):
            self.stop(now)
            return True

        changed = False
        for _ in range(1000):
            if self.state == "waiting":
                if now < float(self.gap_end_ms or 0.0):
                    break
                if not self.queue or self.presentations >= int(self.settings.trial_cap):
                    self.stop(now)
                    changed = True
                    break
                self._start_presentation(now)
                changed = True
                continue
            if self.state == "active":
                if now < float(self.window_end_ms or 0.0):
                    shown = self._probe_shown(now)
                    if shown != self.probe_shown:
                        self.probe_shown = shown
                        changed = True
                    break
                self._record_miss(now)
                changed = True
                continue
            break
        return changed

    def _start_presentation(self, now: float) -> None:
        col, row, attempt_no = self.queue.pop(0)
        key = (col, row)
        self._queued.discard(key)
        self._presented.add(key)
        self.current_entry = (col, row, attempt_no)
        self.current = self._positions[key]
        self.onset_ms = now
        self.window_end_ms = now + float(self.settings.window_ms)
        self.presentations += 1
        self.state = "active"
        self.probe_shown = self._probe_shown(now)

    def _probe_shown(self, now_ms: float) -> bool:
        """Whether the probe signal is on screen at ``now_ms`` (design D7).

        The phase is anchored at the presentation onset, so every presentation
        of a position blinks identically and the sampler's jitter cannot shift
        the pattern. The signal starts on at onset — the erased dot's
        disappearance is the onset transient — so an even phase keeps it on.
        """
        blink = int(self.settings.blink_ms)
        if not blink or self.onset_ms is None:
            return True
        phase = int((float(now_ms) - float(self.onset_ms)) // blink)
        return phase % 2 == 0

    def _clear_presentation(self) -> None:
        self.current = None
        self.current_entry = None
        self.onset_ms = None
        self.window_end_ms = None
        self.probe_shown = False

    def _record_miss(self, now: float) -> None:
        position = self.current
        entry = self.current_entry
        if position is None or entry is None:
            self._clear_presentation()
            self.state = "waiting"
            self.gap_end_ms = now + self._next_gap_ms()
            return
        _, _, attempt_no = entry
        self._append_attempt(
            position,
            Attempt(
                self._relative_ms(float(self.onset_ms or now)),
                None,
                MISS_OUTCOME,
            ),
        )
        self._clear_presentation()
        self.state = "waiting"
        self.gap_end_ms = now + self._next_gap_ms()

        if attempt_no <= int(self.settings.retries):
            self._insert_entry(
                (position.col, position.row, attempt_no + 1),
                self.settings.retry_spacing,
            )
        else:
            position.verdict = BLIND
            self._queue_neighbours(position)

    def _append_attempt(self, position: Position, attempt: Attempt) -> None:
        position.attempts.append(attempt)

    def _insert_entry(self, entry: tuple[int, int, int], index: int) -> None:
        key = (entry[0], entry[1])
        if key in self._queued:
            return
        slot = max(0, min(int(index), len(self.queue)))
        self.queue.insert(slot, entry)
        self._queued.add(key)

    def _queue_neighbours(self, position: Position) -> None:
        for dcol in (-1, 0, 1):
            for drow in (-1, 0, 1):
                if dcol == 0 and drow == 0:
                    continue
                key = (position.col + dcol, position.row + drow)
                if key not in self._positions or key == self._centre_key:
                    continue
                if key in self._queued or key in self._presented:
                    continue
                self._insert_entry(
                    (key[0], key[1], 1), self.settings.probe_offset
                )

    # -- responses -----------------------------------------------------------
    def respond(self, now_ms: int | float) -> bool:
        """Score a ``Space`` press; return whether a position was marked seen."""
        now = float(now_ms)
        if (
            self.state != "active"
            or self.current is None
            or self.window_end_ms is None
            or now > self.window_end_ms
        ):
            self.late_responses += 1
            return False

        latency = int(round(now - float(self.onset_ms or now)))
        self.last_latency_ms = latency
        position = self.current
        self._append_attempt(
            position,
            Attempt(
                self._relative_ms(float(self.onset_ms or now)),
                latency,
                SEEN_OUTCOME,
            ),
        )
        position.verdict = SEEN
        self._clear_presentation()
        self.state = "waiting"
        self.gap_end_ms = now + self._next_gap_ms()
        return True

    # -- pause / stop --------------------------------------------------------
    def pause(self, now_ms: int | float) -> bool:
        """Freeze the clock; an open presentation is discarded, not missed."""
        if self.state in ("finished", "paused"):
            return False
        now = float(now_ms)
        self._paused_at_ms = now
        self._resume_with_gap = self.state == "active"
        if (
            self.state == "active"
            and self.current is not None
            and self.current_entry is not None
        ):
            col, row, attempt_no = self.current_entry
            self._append_attempt(
                self.current,
                Attempt(
                    self._relative_ms(float(self.onset_ms or now)),
                    None,
                    ABORTED_OUTCOME,
                ),
            )
            self._clear_presentation()
            # The same trial goes back to the end; it never recorded a miss.
            self.queue.append((col, row, attempt_no))
            self._queued.add((col, row))
        self.state = "paused"
        return True

    def resume(self, now_ms: int | float) -> bool:
        """Unfreeze the clock, preserving the remaining gap."""
        if self.state != "paused":
            return False
        now = float(now_ms)
        paused_for = max(0.0, now - float(self._paused_at_ms or now))
        if self.started_at_ms is not None:
            self.started_at_ms += paused_for
        if self._resume_with_gap or self.gap_end_ms is None:
            self.gap_end_ms = now + self._next_gap_ms()
        else:
            self.gap_end_ms = float(self.gap_end_ms) + paused_for
        self.state = "waiting"
        self._paused_at_ms = None
        self._resume_with_gap = False
        return True

    def stop(self, now_ms: int | float | None = None) -> bool:
        """End the run; the queue remainder stays untested."""
        if self.state == "finished":
            return False
        now = float(now_ms) if now_ms is not None else 0.0
        if self.state == "active" and self.current is not None:
            self._append_attempt(
                self.current,
                Attempt(
                    self._relative_ms(float(self.onset_ms or now)),
                    None,
                    ABORTED_OUTCOME,
                ),
            )
        self._clear_presentation()
        self._paused_at_ms = None
        self.gap_end_ms = None
        self.state = "finished"
        self.stopped_at_ms = now
        return True

    # -- results -------------------------------------------------------------
    def counts(self) -> dict[str, int]:
        seen = sum(1 for position in self.positions if position.verdict == SEEN)
        blind = sum(1 for position in self.positions if position.verdict == BLIND)
        return {
            "seen": seen,
            "blind": blind,
            "untested": len(self.positions) - seen - blind,
        }

    def central_seen(self) -> int:
        return sum(
            1 for key in self._inner_keys if self._positions[key].verdict == SEEN
        )

    def latencies(self) -> list[int]:
        return [
            int(attempt.response_ms)
            for position in self.positions
            for attempt in position.attempts
            if attempt.outcome == SEEN_OUTCOME and attempt.response_ms is not None
        ]

    def median_latency_ms(self) -> int | None:
        values = sorted(self.latencies())
        if not values:
            return None
        middle = len(values) // 2
        if len(values) % 2:
            return int(values[middle])
        return int(round((values[middle - 1] + values[middle]) / 2.0))

    def interpretable(self) -> bool:
        return self.central_seen() >= MIN_CENTRAL_SEEN

    def clusters(self, scale: Scale) -> list[dict]:
        """Eight-connected blind clusters, with centre and extent in degrees."""
        blind = {
            position.key for position in self.positions if position.verdict == BLIND
        }
        visited: set[tuple[int, int]] = set()
        components: list[list[tuple[int, int]]] = []
        for key in sorted(blind, key=lambda item: (item[1], item[0])):
            if key in visited:
                continue
            stack = [key]
            component: list[tuple[int, int]] = []
            visited.add(key)
            while stack:
                col, row = stack.pop()
                component.append((col, row))
                for dcol in (-1, 0, 1):
                    for drow in (-1, 0, 1):
                        if dcol == 0 and drow == 0:
                            continue
                        neighbour = (col + dcol, row + drow)
                        if neighbour in blind and neighbour not in visited:
                            visited.add(neighbour)
                            stack.append(neighbour)
            components.append(sorted(component, key=lambda item: (item[1], item[0])))

        origin_x, origin_y = self.lattice.origin_px
        result: list[dict] = []
        for component in components:
            points = [self._positions[key] for key in component]
            xs = [point.x_px for point in points]
            ys = [point.y_px for point in points]
            centre_x = sum(xs) / len(xs)
            centre_y = sum(ys) / len(ys)
            result.append(
                {
                    "dots": len(points),
                    "centre_deg": [
                        round(scale.degrees_for_px(centre_x - origin_x), 1),
                        round(scale.degrees_for_px(centre_y - origin_y), 1),
                    ],
                    "extent_deg": [
                        round(scale.degrees_for_px(max(xs) - min(xs)), 1),
                        round(scale.degrees_for_px(max(ys) - min(ys)), 1),
                    ],
                }
            )
        result.sort(
            key=lambda cluster: (
                -cluster["dots"],
                cluster["centre_deg"][1],
                cluster["centre_deg"][0],
            )
        )
        return result

    def results(self, scale: Scale) -> dict:
        counts = self.counts()
        return {
            "seen": counts["seen"],
            "blind": counts["blind"],
            "untested": counts["untested"],
            "central_seen": f"{self.central_seen()}/{self.inner_ring_total}",
            "interpretable": self.interpretable(),
            "late_responses": int(self.late_responses),
            "median_latency_ms": self.median_latency_ms(),
            "clusters": self.clusters(scale),
        }

    def progress_text(self) -> str:
        counts = self.counts()
        return (
            f"scotoma test {self.presentations} presented, "
            f"{len(self.queue)} queued, {counts['seen']} seen, "
            f"{counts['blind']} blind"
        )

    def record(self, scale: Scale) -> dict:
        """The ``blindspot`` block of the exported JSON record."""
        settings = self.settings
        return {
            "variant": settings.variant,
            "settings": {
                "window_ms": int(settings.window_ms),
                "gap_ms": [int(settings.gap[0]), int(settings.gap[1])],
                "spacing_px": int(self.lattice.spacing_px),
                "dot_px": int(settings.dot_px),
                "inner": int(settings.inner),
                "outside_sample": int(settings.outside_sample),
                "retries": int(settings.retries),
                "retry_spacing": int(settings.retry_spacing),
                "probe_offset": int(settings.probe_offset),
                "trial_cap": int(settings.trial_cap),
                "deadline_ms": int(settings.deadline_ms),
                "blink_ms": int(settings.blink_ms),
            },
            "seed": int(self.seed),
            "lattice": self.lattice.as_dict(),
            "positions": [position.to_dict() for position in self.positions],
            "summary": self.results(scale),
        }


def initial_queue(
    settings: BlindSpotSettings,
    width: int,
    height: int,
    dot_pitch: int,
) -> list[tuple[int, int, int]]:
    """Convenience wrapper returning a run's initial queue, for reproducibility."""
    test = BlindSpotTest(settings, width=width, height=height, dot_pitch=dot_pitch)
    return list(test.queue)


def position_keys(entries: Iterable[tuple[int, int, int]]) -> list[tuple[int, int]]:
    """Just the ``(col, row)`` pairs of a queue, in order."""
    return [(int(col), int(row)) for col, row, _ in entries]
