import asyncio
import contextlib
import os
import platform
import random
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, time as time_type
from datetime import timezone as dt_timezone
from typing import Deque, Dict, List, Tuple

import requests
from fastapi import FastAPI, HTTPException, Query
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import FileResponse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def send_log_to_loki(message: str, app_label: str = "app", level: str = "INFO") -> bool:
    """Отправка лога в Loki с label app для фильтра в Grafana."""
    LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100/loki/api/v1/push")

    timestamp_ns = str(int(time.time() * 1_000_000_000))
    payload = {
        "streams": [
            {
                "stream": {
                    "job": "app",
                    "app": app_label,
                    "level": level,
                    "service": "crypto-backend",
                },
                "values": [[timestamp_ns, message]],
            }
        ]
    }

    try:
        response = requests.post(LOKI_URL, json=payload, timeout=5)
        if response.status_code == 204:
            print(f"✓ [{level}] [{app_label}] {message}")
            return True
        print(f"✗ Ошибка отправки: {response.status_code}")
    except Exception as e:
        print(f"✗ Ошибка: {e}")

    return False


app = FastAPI(
    title="Crypto Simulator Time Server API",
    description=(
        "Эмулятор работы реального crypto-бэкенда: торговая активность, "
        "системные события и логи в Loki."
    ),
    version="1.0.0",
)

SYMBOLS: List[str] = ["BTC", "ETH", "SOL", "USDT"]

SYSTEM_EVENTS = [
    "Мониторинг подозрительной активности",
    "Синхронизация котировок с биржей",
    "Проверка балансов пользователей",
    "Обновление кэша ордербука",
    "Health-check внутренних сервисов",
]

USER_EVENTS = [
    "Пользователь user_{id} открыл позицию по {symbol}",
    "Пользователь user_{id} установил stop-loss на {symbol}",
    "Пользователь user_{id} пополнил кошелёк на {amount} USDT",
    "Пользователь user_{id} запросил вывод {amount} USDT",
]

TRADE_EVENTS = [
    "Сделка {side} {qty} {symbol} по цене {price}",
    "Исполнен ордер {side} {qty} {symbol} @ {price}",
    "Арбитражная сделка {symbol}: {price}",
]

AUTH_EVENTS = [
    "Успешная авторизация user_{id}",
    "Попытка входа user_{id} с IP {ip}",
    "Обновлён JWT-токен для user_{id}",
    "Выход пользователя user_{id} из системы",
]

VALIDATION_EVENTS = [
    "Валидация ордера {symbol}: OK",
    "Валидация ордера {symbol}: отклонено (недостаточный баланс)",
    "Проверка лимитов user_{id}: пройдена",
    "Проверка KYC user_{id}: в ожидании",
]

API_EVENTS = [
    "GET /time -> 200 ({ms}ms)",
    "GET /crypto/ticker/{symbol} -> 200 ({ms}ms)",
    "GET /health -> 200 ({ms}ms)",
    "GET /convert -> 200 ({ms}ms)",
]


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
    side: str
    ts: str


class CryptoState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
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


class LokiAPILogMiddleware(BaseHTTPMiddleware):
    """Логирует реальные HTTP-запросы в категорию api."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path not in {"/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"}:
            message = f"{request.method} {request.url.path} -> {response.status_code}"
            asyncio.create_task(asyncio.to_thread(send_log_to_loki, message, "api", "INFO"))
        return response


app.add_middleware(LokiAPILogMiddleware)


def _levels_around_price(
    price: float, spread: float, levels: int = 5
) -> Tuple[List[List[float]], List[List[float]]]:
    bid = price - spread / 2
    ask = price + spread / 2
    bids: List[List[float]] = []
    asks: List[List[float]] = []

    for i in range(levels):
        bid_price = bid * (1 - (i + 1) * random.uniform(0.00005, 0.001))
        ask_price = ask * (1 + (i + 1) * random.uniform(0.00005, 0.001))
        bid_qty = random.uniform(0.01, 2.5) * (levels - i) / levels
        ask_qty = random.uniform(0.01, 2.5) * (levels - i) / levels
        bids.append([round(bid_price, 8), round(bid_qty, 6)])
        asks.append([round(ask_price, 8), round(ask_qty, 6)])

    return bids, asks


def _random_event_message(state: CryptoState) -> tuple[str, str, str]:
    """Генерирует случайное событие, уровень лога и категорию app."""
    category = random.choices(
        ["system", "user_activity", "trading", "auth", "validation", "api"],
        weights=[2, 2, 3, 1, 1, 1],
        k=1,
    )[0]
    symbol = random.choice([s for s in SYMBOLS if s != "USDT"])
    ticker = state.tickers[symbol]
    user_id = random.randint(1000, 9999)

    if category == "system":
        level = random.choice(["INFO", "DEBUG", "WARNING"])
        return f"Система: {random.choice(SYSTEM_EVENTS)}", level, "system"

    if category == "user_activity":
        template = random.choice(USER_EVENTS)
        return template.format(
            id=user_id,
            symbol=symbol,
            amount=round(random.uniform(50, 5000), 2),
        ), "INFO", "user_activity"

    if category == "auth":
        template = random.choice(AUTH_EVENTS)
        return template.format(
            id=user_id,
            ip=f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}",
        ), "INFO", "auth"

    if category == "validation":
        template = random.choice(VALIDATION_EVENTS)
        return template.format(symbol=symbol, id=user_id), "INFO", "validation"

    if category == "api":
        template = random.choice(API_EVENTS)
        return template.format(
            symbol=symbol,
            ms=random.randint(5, 120),
        ), "INFO", "api"

    side = random.choice(["buy", "sell"])
    qty = round(random.uniform(0.01, 1.5), 4)
    price = ticker.price
    template = random.choice(TRADE_EVENTS)
    return template.format(side=side, qty=qty, symbol=symbol, price=price), "INFO", "trading"


async def main() -> None:
    """
    Эмуляция реального crypto-бэкенда:
    события каждые 2-8 секунд + отправка логов в Loki.
    """
    state: CryptoState = app.state.crypto_state

    send_log_to_loki("Криптовалютный бэкенд запущен", "app", "INFO")
    print("🚀 Запуск криптовалютного бэкенда...")
    print("📊 Эмуляция торговой активности, пользовательских действий и системных событий")
    print("⏱️  Генерация событий каждые 2-8 секунд")

    while True:
        await asyncio.sleep(random.uniform(2, 8))
        now_iso = datetime.now(dt_timezone.utc).isoformat()

        async with state.lock:
            sym = random.choice(SYMBOLS)
            prev = state.tickers[sym].price
            step_pct = random.gauss(0.0, 0.002)
            new_price = max(0.0001, float(prev) * (1.0 + step_pct))
            spread = new_price * random.uniform(0.0002, 0.003)
            change = (new_price / state.base_price[sym] - 1.0) * 100.0

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

            bids, asks = _levels_around_price(new_price, spread)
            state.orderbook[sym] = {
                "bid": round(new_price - spread / 2, 8),
                "ask": round(new_price + spread / 2, 8),
                "spread": round(spread, 8),
                "bids": bids,
                "asks": asks,
                "updated_at": now_iso,
            }

            if random.random() < 0.7:
                state.trade_seq += 1
                side = "buy" if random.random() < 0.5 else "sell"
                qty_max = 2.0 if sym != "USDT" else 500.0
                qty = random.uniform(0.001, qty_max)
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

            message, level, app_label = _random_event_message(state)

        await asyncio.to_thread(send_log_to_loki, message, app_label, level)


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
        result = asdict(state.tickers[symbol])

    send_log_to_loki(f"Запрошен тикер {symbol}", "api", "INFO")
    return result


@app.get("/crypto/orderbook/{symbol}", summary="Crypto orderbook (simulated)")
async def crypto_orderbook(symbol: str) -> dict:
    symbol = symbol.strip().upper()
    state: CryptoState = app.state.crypto_state
    if symbol not in state.orderbook:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    async with state.lock:
        result = state.orderbook[symbol]

    send_log_to_loki(f"Запрошен ордербук {symbol}", "api", "INFO")
    return result


@app.get("/crypto/trades/{symbol}", summary="Recent trades (simulated)")
async def crypto_trades(symbol: str, limit: int = Query(10, ge=1, le=50)) -> dict:
    symbol = symbol.strip().upper()
    state: CryptoState = app.state.crypto_state
    if symbol not in state.trades:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    async with state.lock:
        trades = list(state.trades[symbol])[-limit:]
        result = {
            "symbol": symbol,
            "limit": limit,
            "trades": [asdict(t) for t in trades],
        }

    send_log_to_loki(f"Запрошены сделки {symbol} (limit={limit})", "api", "INFO")
    return result


TIMEZONE_ALIASES = {
    "MSK": "Europe/Moscow",
    "UTC": "UTC",
    "EST": "America/New_York",
    "PST": "America/Los_Angeles",
    "CET": "Europe/Paris",
    "GMT": "Europe/London",
}


def parse_utc_time(value: str) -> time_type:
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
    send_log_to_loki("Был запрошен главный экран", "app", "INFO")
    return {
        "message": "Приложение успешно запущено в Docker контейнере!",
        "timestamp": datetime.now(dt_timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "container_id": os.environ.get("HOSTNAME", "unknown"),
        "environment": dict(os.environ),
    }


@app.get("/ui", summary="Frontend UI")
def frontend_ui():
    send_log_to_loki("Открыт UI интерфейс", "app", "INFO")
    return FileResponse("frontend/index.html")


@app.get("/time", summary="Get Current Time")
def get_current_time():
    now = datetime.now(dt_timezone.utc)
    send_log_to_loki("Запрошено текущее время UTC", "api", "INFO")
    return {"utc": now.isoformat(), "timestamp": now.timestamp()}


@app.get("/date", summary="Get Current Date")
def get_current_date():
    today = datetime.now(dt_timezone.utc).date()
    send_log_to_loki("Запрошена текущая дата UTC", "api", "INFO")
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
    send_log_to_loki("Запрошены дата и время UTC", "api", "INFO")
    return {
        "utc": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.time().isoformat(),
        "timestamp": now.timestamp(),
    }


@app.get("/health", summary="Health Check")
def health_check():
    send_log_to_loki("Выполнен health-check", "api", "INFO")
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

    send_log_to_loki(
        f"Конвертация времени {parsed_time.strftime('%H:%M')} UTC в {tz_name}",
        "api",
        "INFO",
    )
    return {
        "input_utc": parsed_time.strftime("%H:%M"),
        "timezone": tz_name,
        "converted": converted.strftime("%H:%M"),
        "converted_iso": converted.isoformat(),
    }


@app.get("/math/add", summary="Add two numbers")
def math_add(
    a: float = Query(..., description="First number"),
    b: float = Query(..., description="Second number"),
):
    result = a + b
    send_log_to_loki(f"Сложение {a} + {b} = {result}", "api", "INFO")
    return {"a": a, "b": b, "operation": "add", "result": result}


@app.get("/math/multiply", summary="Multiply two numbers")
def math_multiply(
    a: float = Query(..., description="First number"),
    b: float = Query(..., description="Second number"),
):
    result = a * b
    send_log_to_loki(f"Умножение {a} × {b} = {result}", "api", "INFO")
    return {"a": a, "b": b, "operation": "multiply", "result": result}
