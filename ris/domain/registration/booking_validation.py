"""Local appointment datetime policy without request or database dependencies."""
from datetime import datetime


def local_appointment_time(value):
    scheduled=datetime.fromisoformat(value)
    if scheduled.tzinfo is not None:
        raise ValueError('Use the local appointment date and time.')
    return scheduled
