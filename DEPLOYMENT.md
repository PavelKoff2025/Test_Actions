# Деплой Time API

Инструкция по сборке Docker-образа и автоматическому деплою на удалённый сервер через GitHub Actions.

## Архитектура

```
push в main
    │
    ▼
GitHub Actions (build-and-push)
    │  сборка Docker-образа
    │  push в GHCR
    ▼
GitHub Container Registry
    │  ghcr.io/pavelkoff2025/test_actions:latest
    ▼
GitHub Actions (deploy)
    │  SSH на сервер
    │  docker pull + docker run
    ▼
Удалённый сервер (порт 8000)
```

## Требования

### Локально

- Python 3.11+
- Docker Desktop
- Git

### На сервере

- Ubuntu (или другой Linux)
- Docker
- Открытый порт `8000`
- SSH-доступ

## Локальная сборка Docker

```bash
docker build -t time-api .
docker run -p 8000:8000 time-api
```

Проверка: http://127.0.0.1:8000/time

## CI/CD (GitHub Actions)

Workflow: `.github/workflows/deploy.yml`

| Джоба | Описание |
|-------|----------|
| `build-and-push` | Собирает образ и пушит в GHCR |
| `deploy` | Подключается по SSH, скачивает образ и запускает контейнер |

**Триггеры:**

- push в ветку `main`
- ручной запуск: Actions → Build and Deploy → Run workflow

## Секреты GitHub

Settings → Secrets and variables → Actions:

| Секрет | Описание |
|--------|----------|
| `SSH_HOST` | IP или домен сервера |
| `SSH_USER` | Пользователь SSH (`root`, `ubuntu` и т.д.) |
| `SSH_PRIVATE_KEY` | Приватный SSH-ключ для деплоя |
| `SSH_PORT` | Порт SSH (опционально, по умолчанию `22`) |
| `GHCR_TOKEN` | GitHub PAT с правом `read:packages` |

`GITHUB_TOKEN` для push в GHCR используется автоматически.

## Настройка SSH-ключа

На Mac:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy
```

- Приватный ключ (`~/.ssh/github_actions_deploy`) → секрет `SSH_PRIVATE_KEY`
- Публичный ключ → на сервер в `~/.ssh/authorized_keys`

```bash
cat ~/.ssh/github_actions_deploy.pub
```

На сервере:

```bash
mkdir -p ~/.ssh
echo "ВАШ_ПУБЛИЧНЫЙ_КЛЮЧ" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

Проверка с Mac (вход без пароля):

```bash
ssh -i ~/.ssh/github_actions_deploy USER@SERVER_IP
```

## Установка Docker на сервере

```bash
apt update
apt install -y docker.io
systemctl enable --now docker
docker --version
```

## GHCR_TOKEN

1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Отметить `read:packages`
4. Сохранить токен в секрет `GHCR_TOKEN`

## Проверка деплоя

После успешного workflow:

```bash
curl http://SERVER_IP:8000/time
curl http://SERVER_IP:8000/date
```

Swagger: http://SERVER_IP:8000/docs

На сервере:

```bash
docker ps
```

Контейнер `time-api` должен быть в статусе `Up`.

## Образ в реестре

```
ghcr.io/pavelkoff2025/test_actions:latest
ghcr.io/pavelkoff2025/test_actions:<commit-sha>
```

Имя образа приводится к нижнему регистру — требование GHCR.

## Ручной перезапуск

Actions → Build and Deploy → Run workflow → branch `main`

## Устранение неполадок

| Ошибка | Решение |
|--------|---------|
| `repository name must be lowercase` | Имя образа должно быть в нижнем регистре (уже исправлено в workflow) |
| `missing server host` | Не задан секрет `SSH_HOST` |
| `ssh: no key found` | Неверно вставлен `SSH_PRIVATE_KEY` — скопировать целиком через `pbcopy` |
| `unable to authenticate` | Публичный ключ не добавлен на сервер |
| `port is already allocated` | Порт 8000 занят — остановить старый контейнер |
