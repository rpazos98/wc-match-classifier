from datetime import timedelta
from zoneinfo import ZoneInfo
from . import BaseScorer, ScoringContext
from ..models import TimeWindow

_GRACE = timedelta(minutes=30)


def _kickoff_in_window(kickoff_utc, window: TimeWindow) -> float:
    """Return 1.0 (inside), 0.5 (marginal ±30 min), or 0.0 (outside)."""
    local = kickoff_utc.astimezone(window.timezone)

    # Date/weekday gate
    if window.date is not None:
        if local.date() != window.date:
            return 0.0
    elif window.weekday is not None:
        if local.weekday() != window.weekday:
            return 0.0

    hour = local.hour + local.minute / 60.0
    if window.start_hour <= hour < window.end_hour:
        return 1.0

    grace_hours = _GRACE.seconds / 3600
    if (window.start_hour - grace_hours) <= hour < window.start_hour:
        return 0.5
    if window.end_hour <= hour < (window.end_hour + grace_hours):
        return 0.5

    return 0.0


class TimeAvailabilityScorer(BaseScorer):
    name   = "Time Availability"
    weight = 0.10

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        windows = ctx.profile.time_windows
        if not windows:
            return 0.5, ""  # abstain: user set no windows

        best = 0.0
        best_window: TimeWindow | None = None

        for w in windows:
            val = _kickoff_in_window(ctx.match.kickoff_utc, w)
            if val > best:
                best = val
                best_window = w

        if best == 0.0:
            return 0.0, "Partido fuera de tu horario disponible"

        local = ctx.match.kickoff_utc.astimezone(best_window.timezone)  # type: ignore[union-attr]
        tz_name = str(best_window.timezone)  # type: ignore[union-attr]
        time_str = local.strftime("%d %b %H:%M")
        qualifier = "" if best == 1.0 else " (horario marginal)"
        return best, f"Partido a las {time_str} {tz_name}{qualifier} — dentro de tu ventana"
