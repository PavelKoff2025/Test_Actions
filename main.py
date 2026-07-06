from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="Time API", version="1.0.0")


@app.get("/")
def root():
    return {"message": "Time API", "docs": "/docs"}


@app.get("/time")
def get_server_time():
    now = datetime.now(timezone.utc)
    return {
        "utc": now.isoformat(),
        "timestamp": now.timestamp(),
    }
