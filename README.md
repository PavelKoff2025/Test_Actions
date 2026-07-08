# Crypto Simulator Time Server API

FastAPI-приложение: Time Server API + эмулятор crypto-бэкенда с отправкой логов в **Loki** и визуализацией в **Grafana**.

**Live:** http://80.78.246.211:8000/docs  
**UI:** http://80.78.246.211:8000/ui

## Возможности

- Time API: время, дата, datetime, конвертация часовых поясов
- Crypto-симулятор: тикеры, ордербук, сделки, фоновые события
- Логирование в Loki (`send_log_to_loki`) с метками `job`, `app`, `level`
- Веб-интерфейс для тестирования API (`/ui`)
- Docker Compose для локального запуска
- CI/CD: сборка образа и автодеплой на VPS через GitHub Actions

## Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/` | Информация о контейнере |
| `GET` | `/ui` | Веб-интерфейс |
| `GET` | `/time` | Текущее время (UTC) |
| `GET` | `/date` | Текущая дата (UTC) |
| `GET` | `/datetime` | Дата и время (UTC) |
| `GET` | `/convert` | Конвертация UTC → часовой пояс |
| `GET` | `/health` | Health check |
| `GET` | `/crypto/ticker/{symbol}` | Тикер криптовалюты |
| `GET` | `/crypto/orderbook/{symbol}` | Ордербук |
| `GET` | `/crypto/trades/{symbol}` | Последние сделки |
| `GET` | `/math/add` | Сложение чисел |
| `GET` | `/math/multiply` | Умножение чисел |
| `GET` | `/docs` | Swagger UI |

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Docker

```bash
docker compose up -d --build
```

Мониторинг (Loki + Grafana):

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

- Grafana: http://localhost:3000 (`admin` / `admin`)
- Loki: http://localhost:3100

## Структура проекта

```
app.py                          # FastAPI-приложение, Loki-логирование
main.py                         # Точка входа (uvicorn)
frontend/index.html             # Веб-интерфейс
docker-compose.yml              # Приложение
docker-compose.monitoring.yml   # Loki + Grafana
.github/workflows/deploy.yml    # CI/CD
```

## Grafana

- Data source: Loki (`http://loki:3100`)
- Dashboard: **Logs / App** — логи + pie chart по уровням
- Фильтр: `{job="app", app=~"$app"}`

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`):

1. Сборка образа и push в **GitHub Container Registry**
2. Деплой на сервер через **SSH**

Подробнее: [DEPLOYMENT.md](DEPLOYMENT.md)

## Стек

Python · FastAPI · Uvicorn · Loki · Grafana · Docker · GitHub Actions · GHCR

## Лицензия

[MIT](LICENSE)
