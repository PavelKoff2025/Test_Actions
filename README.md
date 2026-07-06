# Time API

Простой тестовый бэкенд на FastAPI, возвращающий текущее время сервера.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск

```bash
uvicorn main:app --reload
```

Сервер будет доступен на http://127.0.0.1:8000

## Эндпоинты

- `GET /` — информация об API
- `GET /time` — текущее время сервера (UTC)
- `GET /docs` — интерактивная документация Swagger
