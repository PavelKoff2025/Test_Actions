# Time Server API

Простой REST API на **FastAPI** для получения текущего времени, даты и конвертации часовых поясов.

**Live:** http://80.78.246.211:8000/docs

## Возможности

- Текущее время, дата и datetime в UTC
- Конвертация времени между часовыми поясами
- Health check для мониторинга
- Swagger-документация из коробки
- CI/CD: сборка Docker-образа и автодеплой на VPS

## Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/` | Приветствие |
| `GET` | `/time` | Текущее время (UTC) |
| `GET` | `/date` | Текущая дата (UTC) |
| `GET` | `/datetime` | Дата и время (UTC) |
| `GET` | `/convert` | Конвертация UTC → часовой пояс |
| `GET` | `/health` | Проверка состояния |
| `GET` | `/docs` | Swagger UI |

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Docker

```bash
docker build -t time-api .
docker run -p 8000:8000 time-api
```

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`):

1. Сборка образа и push в **GitHub Container Registry**
2. Деплой на сервер через **SSH**

Подробнее: [DEPLOYMENT.md](DEPLOYMENT.md)

## Стек

Python · FastAPI · Uvicorn · Docker · GitHub Actions · GHCR

## Лицензия

[MIT](LICENSE)
