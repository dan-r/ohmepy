from datetime import datetime, timedelta


def time_next_occurs(hour, minute):
    """Find when this time next occurs."""
    current = datetime.now()
    target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= datetime.now():
        target = target + timedelta(days=1)

    return target
