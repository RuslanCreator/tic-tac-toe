# Крестики-нолики

Онлайн-игра «Крестики-нолики» на FastAPI с PvE (против бота), PvP-лобби,
обновлениями по WebSocket и JWT-авторизацией.

Проект разложен по слоям:

```text
domain/          сущности и правила игры (без FastAPI и SQLAlchemy)
application/     сценарии использования, порты и стратегии ответа
infrastructure/  SQLAlchemy-модели, репозитории, инициализация БД
web/             HTTP/WebSocket-роутеры, схемы, статика
di/              composition root и настройки из переменных окружения
tests/           unit- и API-тесты на фейковых репозиториях
```

## Быстрый старт

Требования: Python 3.12+, [uv](https://docs.astral.sh/uv/), PostgreSQL.

1. Установите зависимости:

   ```bash
   uv sync
   ```

2. Создайте базу данных:

   ```bash
   createdb tictactoe
   ```

3. Задайте переменные окружения. Минимально нужны `DB_USER`, `DB_NAME` и
   `JWT_SECRET` (не короче 32 символов):

   ```bash
   export DB_USER=postgres
   export DB_PASSWORD=postgres
   export DB_NAME=tictactoe
   export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
   ```

4. Запустите приложение:

   ```bash
   uv run uvicorn main:app --reload
   ```

Приложение доступно на <http://127.0.0.1:8000>. При старте создаются таблицы
(если их нет) и служебный игрок-бот с id `bot`.

## Переменные окружения

| Переменная | Обязательна | Значение по умолчанию |
| --- | --- | --- |
| `DB_USER` | да | — |
| `DB_NAME` | да | — |
| `DB_PASSWORD` | нет | пусто |
| `DB_HOST` | нет | `localhost` |
| `DB_PORT` | нет | `5432` |
| `JWT_SECRET` | да | — (минимум 32 символа) |
| `JWT_ALGORITHM` | нет | `HS256` |
| `JWT_EXPIRE_MINUTES` | нет | `60` |

## API

Авторизация — `Authorization: Bearer <token>`.

| Метод | Путь | Описание |
| --- | --- | --- |
| `POST` | `/auth/signup` | Регистрация |
| `POST` | `/auth/login` | Вход, возвращает JWT |
| `GET` | `/auth/me` | Текущий игрок |
| `GET` | `/health` | Проверка приложения и БД |
| `POST` | `/game/new/pve` | Новая игра против бота |
| `POST` | `/game/new/pvp` | Новое PvP-лобби |
| `GET` | `/game/open_lobby` | Открытые лобби |
| `POST` | `/game/{id}/join` | Присоединиться к лобби |
| `POST` | `/game/{id}/move` | Ход (PvE и PvP) |
| `POST` | `/game/{id}/leave` | Выйти из игры |
| `GET` | `/game/finished` | История завершённых игр |
| `GET` | `/game/{id}` | Состояние игры |
| `GET` | `/game/user/{uuid}` | Публичный профиль игрока |
| `WS` | `/game/{id}/ws` | Обновления состояния игры |

### Ходы и выход

- `POST /game/{id}/move` принимает `{"row": 0, "col": 0}`. В PvE после хода
  человека бот отвечает автоматически, ответ уже содержит итоговое поле.
- `POST /game/{id}/leave` возвращает `204`. Незавершённое лобби или PvE-игра
  удаляются, а в активной PvP-игре игрок сдаётся — соперник получает победу.
- Режим игры не хранится отдельной колонкой: PvE определяется по
  `player_o_id == "bot"`.

### WebSocket

Токен передаётся первым значением в `Sec-WebSocket-Protocol`:

```js
new WebSocket(url, ["access_token", token]);
```

Параметр `?token=` поддерживается как устаревший fallback. Сразу после
подключения сервер присылает текущее состояние игры, затем — обновления после
ходов и присоединения соперника. Если лобби удалено, приходит
`{"type": "GAME_DELETED"}`.

## Разработка

```bash
make test      # pytest
make lint      # ruff check
make format    # ruff format
make cov       # покрытие domain/application/web/infrastructure
make check     # lint + test
```

Тесты не требуют PostgreSQL: API-тесты собирают приложение через
`create_app(init_db=False, context=FakeAppContext(...))` и подменяют
репозитории на in-memory реализации.

## Структура фронтенда

Фронтенд — три статических файла без сборки:

- `web/static/index.html`
- `web/static/styles.css`
- `web/static/app.js`

Они раздаются FastAPI через `StaticFiles`, а `/` отдаёт `index.html`.
