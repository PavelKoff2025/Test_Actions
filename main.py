from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(
    title="Time Server API",
    description="Простое API для получения текущего времени сервера",
    version="1.0.0",
)


@app.get("/", summary="Root")
def root():
    return {
        "message": "Добро пожаловать в Time Server API! Используйте /time для получения текущего времени.",
    }


@app.get("/time", summary="Get Current Time")
def get_current_time():
    now = datetime.now(timezone.utc)
    return {
        "utc": now.isoformat(),
        "timestamp": now.timestamp(),
    }


@app.get("/date", summary="Get Current Date")
def get_current_date():
    today = datetime.now(timezone.utc).date()
    return {
        "utc": today.isoformat(),
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "weekday": today.strftime("%A"),
    }


@app.get("/datetime", summary="Get Current Datetime")
def get_current_datetime():
    now = datetime.now(timezone.utc)
    return {
        "utc": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.time().isoformat(),
        "timestamp": now.timestamp(),
    }


@app.get("/health", summary="Health Check")
def health_check():
    return {"status": "ok"}
