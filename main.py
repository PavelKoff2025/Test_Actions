import asyncio
import contextlib
import random
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, time
from datetime import timezone as dt_timezone
from typing import Deque, Dict, List, Tuple

from fastapi import FastAPI, HTTPException, Query
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


app = FastAPI(
    title="Crypto Simulator Time Server API",
    description=(
        "Эмулятор работы реального crypto-бэкенда: постоянно обновляемые котировки и сделки "
        "(рандомные значения), плюс эндпоинты для текущего времени сервера."
    ),
    version="1.0.0",
)

# -------------------- Crypto simulator --------------------

SYMBOLS: List[str] = ["BTC", "ETH", "SOL", "USDT"]


@dataclass
class CryptoTicker:
    symbol: str
    price: float
    spread: float
    change_24h_pct: float
    volume_24h: float
    updated_at: str


@dataclass
class CryptoTrade:
    trade_id: int
    symbol: str
    price: float
    qty: float
    side: str  # buy/sell
    ts: str


class CryptoState:
    def __init__(self) -> None:
        # Lock нужен, чтобы эндпоинты читали консистентный снапшот.
        self.lock = asyncio.Lock()

        # "База" для расчёта change_24h_pct.
        self.base_price: Dict[str, float] = {
            "BTC": 65000.0,
            "ETH": 3200.0,
            "SOL": 150.0,
            "USDT": 1.0,
        }

        self._volume_24h: Dict[str, float] = {
            sym: random.uniform(50_000, 300_000) for sym in SYMBOLS if sym != "USDT"
        }
        self._volume_24h["USDT"] = random.uniform(1_000_000, 5_000_000)

        self.tickers: Dict[str, CryptoTicker] = {}
        self.orderbook: Dict[str, dict] = {}
        self.trades: Dict[str, Deque[CryptoTrade]] = {
            sym: deque(maxlen=200) for sym in SYMBOLS
        }
        self.trade_seq = 0

        self._init_all()

    def _init_all(self) -> None:
        now = datetime.now(dt_timezone.utc).isoformat()
        for sym in SYMBOLS:
            price = self.base_price[sym] * random.uniform(0.98, 1.02)
            spread = price * random.uniform(0.0002, 0.003)
            change = (price / self.base_price[sym] - 1.0) * 100.0
            self.tickers[sym] = CryptoTicker(
                symbol=sym,
                price=round(price, 8 if sym != "USDT" else 4),
                spread=round(spread, 8),
                change_24h_pct=round(change, 4),
                volume_24h=round(self._volume_24h[sym], 2),
                updated_at=now,
            )
            self.orderbook[sym] = {
                "bid": round(price - spread / 2, 8),
                "ask": round(price + spread / 2, 8),
                "spread": round(spread, 8),
                "bids": [],
                "asks": [],
                "updated_at": now,
            }


def _levels_around_price(price: float, spread: float, levels: int = 5) -> Tuple[List[List[float]], List[List[float]]]:
    bid = price - spread / 2
    ask = price + spread / 2

    bids: List[List[float]] = []
    asks: List[List[float]] = []

    for i in range(levels):
        bid_price = bid * (1 - (i + 1) * random.uniform(0.00005, 0.001))
        ask_price = ask * (1 + (i + 1) * random.uniform(0.00005, 0.001))

        # "Глубина" книги обычно разная по уровням.
        bid_qty = random.uniform(0.01, 2.5) * (levels - i) / levels
        ask_qty = random.uniform(0.01, 2.5) * (levels - i) / levels

        bids.append([round(bid_price, 8), round(bid_qty, 6)])
        asks.append([round(ask_price, 8), round(ask_qty, 6)])

    return bids, asks


async def main() -> None:
    """
    Функция `main` имитирует постоянную работу crypto-бэкенда:
    периодически "получаем" новые котировки/сделки (рандомно) и обновляем in-memory state.
    """
    state: CryptoState = app.state.crypto_state

    # Маленькая задержка между обновлениями — чтобы было похоже на реальный стриминг.
    while True:
        await asyncio.sleep(random.uniform(0.25, 0.55))
        now_iso = datetime.now(dt_timezone.utc).isoformat()

        async with state.lock:
            for sym in state.tickers.keys():
                prev = state.tickers[sym].price
                # Рандомное "движение цены" (random walk).
                step_pct = random.gauss(0.0, 0.002)  # ~0.2% типично
                new_price = max(0.0001, float(prev) * (1.0 + step_pct))
                spread = new_price * random.uniform(0.0002, 0.003)

                # change_24h_pct относительно base_price.
                change = (new_price / state.base_price[sym] - 1.0) * 100.0

                # volume_24h тоже "дергаем" рандомно.
                state._volume_24h[sym] = max(
                    0.0,
                    state._volume_24h[sym] * (1.0 + random.gauss(0.0, 0.01)),
                )

                state.tickers[sym] = CryptoTicker(
                    symbol=sym,
                    price=round(new_price, 8 if sym != "USDT" else 4),
                    spread=round(spread, 8),
                    change_24h_pct=round(change, 4),
                    volume_24h=round(state._volume_24h[sym], 2),
                    updated_at=now_iso,
                )

                bids, asks = _levels_around_price(new_price, spread, levels=5)
                state.orderbook[sym] = {
                    "bid": round(new_price - spread / 2, 8),
                    "ask": round(new_price + spread / 2, 8),
                    "spread": round(spread, 8),
                    "bids": bids,
                    "asks": asks,
                    "updated_at": now_iso,
                }

                # Иногда создаём "сделку", как будто это пришло из стрима.
                if random.random() < 0.65:
                    state.trade_seq += 1
                    side = "buy" if random.random() < 0.5 else "sell"
                    qty_max = 2.0 if sym != "USDT" else 500.0
                    qty = random.uniform(0.001, qty_max)

                    # Цена сделки где-то между bid и ask.
                    trade_price = (new_price - spread / 2) + (spread * random.random())
                    state.trades[sym].append(
                        CryptoTrade(
                            trade_id=state.trade_seq,
                            symbol=sym,
                            price=round(trade_price, 8 if sym != "USDT" else 4),
                            qty=round(qty, 6),
                            side=side,
                            ts=now_iso,
                        )
                    )


@app.on_event("startup")
async def _startup() -> None:
    app.state.crypto_state = CryptoState()
    app.state.crypto_task = asyncio.create_task(main())


@app.on_event("shutdown")
async def _shutdown() -> None:
    task = getattr(app.state, "crypto_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/crypto/ticker/{symbol}", summary="Crypto ticker (simulated)")
async def crypto_ticker(symbol: str) -> dict:
    symbol = symbol.strip().upper()
    state: CryptoState = app.state.crypto_state
    if symbol not in state.tickers:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    async with state.lock:
        return asdict(state.tickers[symbol])


@app.get("/crypto/orderbook/{symbol}", summary="Crypto orderbook (simulated)")
async def crypto_orderbook(symbol: str) -> dict:
    symbol = symbol.strip().upper()
    state: CryptoState = app.state.crypto_state
    if symbol not in state.orderbook:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    async with state.lock:
        return state.orderbook[symbol]


@app.get("/crypto/trades/{symbol}", summary="Recent trades (simulated)")
async def crypto_trades(symbol: str, limit: int = Query(10, ge=1, le=50)) -> dict:
    symbol = symbol.strip().upper()
    state: CryptoState = app.state.crypto_state
    if symbol not in state.trades:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    async with state.lock:
        trades = list(state.trades[symbol])[-limit:]
        # отдаём в хронологическом порядке
        return {
            "symbol": symbol,
            "limit": limit,
            "trades": [asdict(t) for t in trades],
        }


# -------------------- Time API (keep from your earlier tasks) --------------------

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
