from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="Time API", version="1.0.0")


@app.get("/")
def root():
    return {
        "message": "Time API",
        "docs": "/docs",
        "endpoints": ["/time", "/date", "/date/local"],
    }


@app.get("/time")
def get_server_time():
    now = datetime.now(timezone.utc)
    return {
        "utc": now.isoformat(),
        "timestamp": now.timestamp(),
    }


@app.get("/date")
def get_server_date():
    today = datetime.now(timezone.utc).date()
    return {
        "utc": today.isoformat(),
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "weekday": today.strftime("%A"),
    }


@app.get("/date/local")
def get_local_date():
    today = datetime.now().astimezone().date()
    tz = datetime.now().astimezone().tzinfo
    return {
        "date": today.isoformat(),
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "weekday": today.strftime("%A"),
        "timezone": str(tz),
    }
