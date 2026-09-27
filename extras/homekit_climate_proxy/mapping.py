"""Map Gree's six manual fan speeds to HomeKit's three exposed speeds."""

HOMEKIT_FAN_MODES = ("low", "medium", "high")

TO_SOURCE = {
    "low": "低档",
    "medium": "中档",
    "high": "高档",
}

FROM_SOURCE = {
    "低档": "low",
    "中低档": "low",
    "中档": "medium",
    "中高档": "medium",
    "高档": "high",
    "强劲档": "high",
}


def to_source(mode: str) -> str:
    """Return the existing climate entity's fan mode for a HomeKit choice."""
    return TO_SOURCE[mode]


def from_source(mode: str | None) -> str | None:
    """Describe a source fan mode without writing a different speed back."""
    return FROM_SOURCE.get(mode)
