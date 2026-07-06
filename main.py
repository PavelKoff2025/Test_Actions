from datetime import datetime, time
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query

app = FastAPI(
    title="Time Server API",
    description="Простое API для получения текущего времени сервера",
    version="1.0.0",
)

TIMEZONE_ALIASES = {
    "MSK": "Europe/Moscow",
    "UTC": "UTC",
    "EST": "America/New_York",
    "PST": "America/Los_Angeles",
    "CET": "Europe/Paris",
    "GMT": "Europe/London",
}


def parse_utc_time(value: str) -> time:
    normalized = value.strip().replace(".", ":")
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(normalized, fmt).time()
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail="Invalid time format. Use HH:MM or HH.MM, for example 15:00",
    )


def resolve_timezone(name: str) -> tuple[str, ZoneInfo]:
    tz_name = TIMEZONE_ALIASES.get(name.strip().upper(), name.strip())
    try:
        return tz_name, ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=400, detail=f"Unknown timezone: {name}")


@app.get("/", summary="Root")
def root():
    return {
        "message": "Добро пожаловать в Time Server API! Используйте /time для получения текущего времени.",
    }


@app.get("/time", summary="Get Current Time")
def get_current_time():
    now = datetime.now(dt_timezone.utc)
    return {
        "utc": now.isoformat(),
        "timestamp": now.timestamp(),
    }


@app.get("/date", summary="Get Current Date")
def get_current_date():
    today = datetime.now(dt_timezone.utc).date()
    return {
        "utc": today.isoformat(),
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "weekday": today.strftime("%A"),
    }


@app.get("/datetime", summary="Get Current Datetime")
def get_current_datetime():
    now = datetime.now(dt_timezone.utc)
    return {
        "utc": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.time().isoformat(),
        "timestamp": now.timestamp(),
    }


@app.get("/health", summary="Health Check")
def health_check():
    return {"status": "ok"}


@app.get("/convert", summary="Convert UTC Time to Timezone")
def convert_time(
    time_value: str = Query(
        ...,
        alias="time",
        description="Время в UTC, например 15:00 или 15.00",
        examples=["15:00"],
    ),
    timezone: str = Query(
        ...,
        description="Часовой пояс, например Europe/Moscow или MSK",
        examples=["Europe/Moscow"],
    ),
):
    parsed_time = parse_utc_time(time_value)
    tz_name, tz = resolve_timezone(timezone)

    utc_dt = datetime.combine(
        datetime.now(dt_timezone.utc).date(),
        parsed_time,
        tzinfo=dt_timezone.utc,
    )
    converted = utc_dt.astimezone(tz)

    return {
        "input_utc": parsed_time.strftime("%H:%M"),
        "timezone": tz_name,
        "converted": converted.strftime("%H:%M"),
        "converted_iso": converted.isoformat(),
    }
