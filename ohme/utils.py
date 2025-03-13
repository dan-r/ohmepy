"""Utility functions for ohmepy."""

from dataclasses import dataclass
import datetime
from zoneinfo import ZoneInfo


def time_next_occurs(hour, minute):
    """Find when this time next occurs."""
    current = datetime.datetime.now()
    target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= datetime.datetime.now():
        target = target + datetime.timedelta(days=1)

    return target


@dataclass
class ChargeSlot:
    """Dataclass for reporting an individual charge slot."""

    start: datetime.datetime
    end: datetime.datetime
    energy: float

    def __str__(self):
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"


def slot_list(data):
    """Get list of charge slots with energy delta summed for merged slots."""
    session_slots = data.get("allSessionSlots", [])
    if not session_slots:
        return []

    slots = []

    for slot in session_slots:
        start_time = (
            datetime.datetime.fromtimestamp(slot["startTimeMs"] / 1000)
            .replace(tzinfo=ZoneInfo("UTC"), microsecond=0)
            .astimezone()
        )
        end_time = (
            datetime.datetime.fromtimestamp(slot["endTimeMs"] / 1000)
            .replace(tzinfo=ZoneInfo("UTC"), microsecond=0)
            .astimezone()
        )

        hours = (end_time - start_time).total_seconds() / 3600
        energy = round((slot["watts"] * hours) / 1000, 2)

        slots.append(ChargeSlot(start_time, end_time, energy))

    # Merge adjacent slots
    merged_slots = []
    for slot in slots:
        if merged_slots and merged_slots[-1].end == slot.start:
            # Merge slot by extending the end time and summing energy
            merged_slots[-1] = ChargeSlot(
                merged_slots[-1].start,
                slot.end,
                merged_slots[-1].energy + slot.energy,
            )
        else:
            merged_slots.append(slot)

    return merged_slots

def vehicle_to_name(vehicle):
    """Translate vehicle object to human readable name."""
    if vehicle.get("name") is not None:
        return vehicle.get("name")

    model = vehicle.get("model") or {}
    brand = model.get("brand") or {}

    brand_name = brand.get("name") or model.get("make") or "Unknown"
    model_name = model.get("modelName") or "Unknown"
    year_from = model.get("availableFromYear")
    year_to = model.get("availableToYear") or ""

    if year_from is None:
        return f"{brand_name} {model_name}"

    return f"{brand_name} {model_name} ({year_from}-{year_to})"
