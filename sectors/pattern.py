"""Pattern Update: how a named state's price and flow pattern has moved since assignment (v5 "Pattern Update")."""

from dataclasses import dataclass
from typing import Any, Literal

from sectors.freeze import usable_band

Allowed = Literal["positive", "neutral_or_positive", "neutral_or_negative"]
TOLERANCE = 0.25
EPSILON = 1e-9  # support distances are differences of floats; an exact 0.25 change must stay within tolerance
# The allowed range of price and flow for each named state, from the v5 state mapping.
ALLOWED: dict[str, dict[str, Allowed]] = {
    "Ignored Improvement": {"price": "neutral_or_negative", "flow": "neutral_or_positive"},
    "Confirmed Strength": {"price": "positive", "flow": "positive"},
    "Crowded Optimism": {"price": "positive", "flow": "positive"},
    "Early Deterioration": {"price": "neutral_or_positive", "flow": "neutral_or_negative"},
}


NAMES = {"price": "price", "flow": "foreign flow"}


@dataclass(frozen=True)
class PatternUpdate:
    available: bool
    label: str | None
    price_change: float | None
    flow_change: float | None
    note: str


def support_distance(allowed: Allowed, x: float, b: float) -> float:
    """How far inside its allowed range a measure sits, in units of the neutral band."""
    if allowed == "positive":
        return (x - b) / b
    if allowed == "neutral_or_positive":
        return (x + b) / b
    return (b - x) / b


def _inside(allowed: Allowed, distance: float) -> bool:
    # A positive category needs x strictly above the band; neutral-inclusive ranges include their boundary.
    return distance > 0 if allowed == "positive" else distance >= 0


def pattern_update(state: str, then: dict[str, float | None], now: dict[str, float | None],
                   bands: dict[str, Any]) -> PatternUpdate:
    """Compares snapshot price and flow with their values at assignment, using the bands of that assignment."""
    values = [then.get("price"), then.get("flow"), now.get("price"), now.get("flow")]
    usable = {dim: usable_band(bands.get(dim)) for dim in ("price", "flow")}
    if any(v is None for v in values):
        return PatternUpdate(False, None, None, None, "Price or flow is unavailable at assignment or now.")
    if any(b is None for b in usable.values()):
        return PatternUpdate(False, None, None, None, "The recorded neutral band is unusable.")
    t_price, t_flow, n_price, n_flow = (float(v) for v in values if v is not None)
    price_change, flow_change = n_price - t_price, n_flow - t_flow
    if state not in ALLOWED:
        return PatternUpdate(True, None, price_change, flow_change, "Neutral has raw changes only.")
    deltas, outside = [], []
    for dim, x_then, x_now in (("price", t_price, n_price), ("flow", t_flow, n_flow)):
        band = usable[dim]
        assert band is not None
        allowed = ALLOWED[state][dim]
        before, after = support_distance(allowed, x_then, band.half_width), support_distance(allowed, x_now,
                                                                                              band.half_width)
        if not _inside(allowed, after):
            outside.append(dim)
        deltas.append(after - before)
    up = [d > TOLERANCE + EPSILON for d in deltas]
    down = [d < -TOLERANCE - EPSILON for d in deltas]
    if outside:
        label = "Contradicting"
        verb = "sits" if len(outside) == 1 else "sit"
        note = (f"{' and '.join(NAMES[d] for d in outside).capitalize()} now {verb} outside the range {state} "
                "requires, so the market pattern no longer matches the state.")
    elif not any(up) and not any(down):
        label, note = "Stable", f"Price and foreign flow sit about where they did inside the {state} pattern."
    elif all(up):
        label, note = "Strengthening", f"Price and foreign flow both moved further into the {state} pattern."
    elif any(down) and not any(up):
        label = "Weakening"
        moved = " and ".join(NAMES[dim] for dim, d in zip(("price", "flow"), down) if d)
        note = (f"{moved.capitalize()} moved back toward the edge of the {state} pattern, still inside it.")
    else:
        label = "Mixed"
        words = ["moved further into" if u else "moved back toward the edge of" if d else "held about steady in"
                 for u, d in zip(up, down)]
        price_part = f"Price {words[0]} the {state} pattern"
        flow_part = (f"foreign flow {words[1]} it" if not words[1].startswith("held") else "foreign flow held about "
                     "steady")
        if words[0].startswith("held"):
            price_part = "Price held about steady"
            flow_part = f"foreign flow {words[1]} the {state} pattern"
        note = f"{price_part} while {flow_part}."
    if not outside and state == "Ignored Improvement" and down[0]:
        note += " Here that means price catching up with the improved fundamentals, narrowing the divergence."
    return PatternUpdate(True, label, price_change, flow_change, note)
