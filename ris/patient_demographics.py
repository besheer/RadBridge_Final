"""Patient demographic normalization shared by registration entry points."""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re


@dataclass(frozen=True)
class DobResolution:
    dob: str
    estimated: bool
    age_value: int | None = None
    age_unit: str = "YEARS"


_AGE_LIMITS = {
    "YEARS": 150,
    "MONTHS": 1800,
    "DAYS": 55000,
}

_AGE_UNITS = {
    "Y": "YEARS",
    "YEAR": "YEARS",
    "YEARS": "YEARS",
    "M": "MONTHS",
    "MONTH": "MONTHS",
    "MONTHS": "MONTHS",
    "D": "DAYS",
    "DAY": "DAYS",
    "DAYS": "DAYS",
}


def _subtract_years(day: date, years: int) -> date:
    target_year = day.year - years
    target_day = min(day.day, calendar.monthrange(target_year, day.month)[1])
    return day.replace(year=target_year, day=target_day)


def _subtract_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    target_year, zero_based_month = divmod(month_index, 12)
    target_month = zero_based_month + 1
    target_day = min(day.day, calendar.monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day)


def resolve_patient_dob(values, *, prefix="new_", today=None):
    """Resolve an exact DOB or derive an explicitly marked approximate DOB.

    Exact dates take precedence. When the browser populated the date from an
    entered age it also sends ``dob_estimated=1``; the server then recomputes
    the date so clinical data does not depend on client-side JavaScript.
    """
    today = today or date.today()
    raw_dob = str(values.get(f"{prefix}dob") or "").strip()
    raw_age = str(values.get(f"{prefix}age_value") or "").strip()
    estimated = str(values.get(f"{prefix}dob_estimated") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if raw_dob and not (raw_age and estimated):
        try:
            parsed = datetime.strptime(raw_dob, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("Invalid patient date of birth.") from exc
        if parsed > today:
            raise ValueError("Patient date of birth cannot be in the future.")
        return DobResolution(parsed.strftime("%Y%m%d"), estimated)

    if not raw_age:
        return DobResolution("", False)
    if not re.fullmatch(r"[0-9]+", raw_age):
        raise ValueError("Patient age must be a whole number.")

    age_value = int(raw_age)
    unit = _AGE_UNITS.get(
        str(values.get(f"{prefix}age_unit") or "YEARS").strip().upper()
    )
    if not unit:
        raise ValueError("Invalid patient age unit.")
    if age_value > _AGE_LIMITS[unit]:
        raise ValueError("Patient age is outside the supported range.")

    if unit == "YEARS":
        parsed = _subtract_years(today, age_value)
    elif unit == "MONTHS":
        parsed = _subtract_months(today, age_value)
    else:
        parsed = today - timedelta(days=age_value)

    return DobResolution(
        parsed.strftime("%Y%m%d"),
        True,
        age_value=age_value,
        age_unit=unit,
    )
