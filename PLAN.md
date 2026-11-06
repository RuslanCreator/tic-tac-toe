# План правок и уровни валидации

## Что осталось

### Из ТЗ (не сделано)

1. `created_at` в модели игры (сейчас закомментирован в `domain/entities/game_session.py`) + миграция колонки в `infrastructure/model.py` и маппинг в `infrastructure/mappers/game_session.py`.
2. `GET /game/finished` + метод репозитория `get_finished_by_player_id` + use case + схема ответа. Роут ставить **до** `/{game_session_id}`.

Запрос к БД для завершённых игр:

```sql
SELECT gs.*
FROM game_sessions AS gs
WHERE (gs.player_x_id = :player_id OR gs.player_o_id = :player_id)
  AND (
        gs.status = 'DRAW'
     OR (gs.status = 'WON_X' AND gs.player_x_id = :player_id)
     OR (gs.status = 'WON_O' AND gs.player_o_id = :player_id)
  )
ORDER BY gs.created_at DESC;
```

### Реальные баги

3. `player_x_id: Mapped[str]` → в SQLAlchemy это `NOT NULL`, а `ondelete="SET NULL"` с ним несовместим. Вернуть `Mapped[str | None]`.
4. `TRUNCATE` в `lifespan` (`main.py`) — стирает историю при каждом старте. Убрать (или включать только по env-флагу для тестов).
5. `except Exception as e: ... str(e)` в 8 эндпоинтах `web/router.py` — отдаёт внутренности клиенту и превращает всё в 500.
6. Гонка регистрации: `unique` в БД теперь бросит `IntegrityError` → 500 вместо 400.
7. `BOT_PLAYER_ID` + проверка, что сессия действительно PvE (иначе через `/move/pve` можно сходить в PvP и получить ход бота).
8. JWT-секрет в коде (`application/jwt_service.py`).

### Гигиена

9. Тестов нет вообще.
10. README пустой; в `pyproject.toml` нет ruff/pytest.
11. `notifier` in-memory — ограничение (рестарт/несколько воркеров), хотя бы в README.

### Архитектурный долг

12. Порты и DIP: перенести `domain/interfaces.py` в `application/ports/`, вынести `WaitingSessionInfo` в `application/read_models.py`, ввести `PasswordHasherInterface` и `AIPlayerInterface` вместо конкретных сервисов в use case'ах. Детали и порядок работ — в разделе «Порты и границы слоёв (DIP)».

## Уровни проверок

Их пять, и у каждого своя зона ответственности:

| Уровень | Что проверяет | Чем | Ответ |
|---|---|---|---|
| Схема (Pydantic) | форма: типы, `ge=0`, длины, обязательность | `Field(...)` | 422 автоматом |
| Аутентификация | «кто ты» | `get_current_player_id` | 401 |
| Авторизация | «можно ли тебе эту игру» | `is_participant` в роутере | 403 |
| Сценарий (use case) | существует ли ресурс, допустима ли операция сейчас | репозиторий | 404 / 409 |
| Домен | правила игры и инварианты | `GameSession.make_move` | доменное исключение |
| БД | целостность как страховка | PK/FK/unique/NOT NULL | 400/409 |

Три правила, которые убирают 90% сложности:

1. **Один факт — одно место.** Границы доски проверяет `set_cell`; не дублируй их в Pydantic (он не знает `grid_size`) и в use case.
2. **Форма — на границе, смысл — в домене.** Схема не должна знать «сейчас не твой ход». Домен не должен знать про JWT и HTTP-коды.
3. **БД — страховка, а не мессенджер.** `unique(login)` ловит гонку, но пользователю объясняет сценарий, а не `IntegrityError`.

Алгоритм «куда положить новую проверку» — по порядку:

- зависит от формата запроса? → схема;
- зависит от того, кто я? → guard;
- зависит от прав на конкретный объект? → роутер/сценарий;
- зависит от правил игры? → домен;
- не должно случиться никогда? → constraint в БД.

## Что лежит не на своём уровне

- **«Только создатель лобби может удалить»** (`DeleteGameSessionUseCase`) — это авторизация, должно быть 403. Сейчас `ValueError` → 400. Домен тут ни при чём, решение зависит от того, кто ты.
- **`is_participant`** — правило в домене, применение в роутере. Это правильно: домен описывает «кто участник», веб решает «пускать или нет».
- **Верхняя граница `row/col`** — в домене, а не в `MoveRequest`. Тоже правильно: зависит от `grid_size`, которого схема не знает.
- **`max_length=25` в схеме и `String(25)` в БД** — не дублирование, а разные задачи: подсказка пользователю и целостность.

Почему тема кажется сложной: один и тот же факт можно проверить на трёх уровнях, и без правила начинаешь защищаться везде. Правило простое — **проверяет тот, кто владеет знанием; остальные уровни только страхуют и не переизобретают сообщение**.

## Порты и границы слоёв (DIP)

### Решение по `interfaces.py`

Интерфейс (порт) принадлежит слою, который его **потребляет**. Реализация — во внешнем слое. Поэтому контракты репозиториев переносим из `domain/` в `application/ports/`:

```text
application/ports/repositories.py   # GameSessionRepositoryInterface, PlayerRepositoryInterface
application/use_cases.py            # зависит от портов
infrastructure/repositories/*.py        # реализует порты
domain/entities/                    # остаётся чистым: только правила игры
```

Текущее `domain/interfaces.py` правило зависимостей не нарушает, но в нём два смешения:

- `get_by_id_for_update` — это `SELECT ... FOR UPDATE`, инфраструктурная блокировка, а не доменное правило;
- `WaitingSessionInfo` — read model для списка лобби, а не сущность домена.

Шаги:

1. Перенести файл `domain/interfaces.py` → `application/ports/repositories.py` (классы не меняются).
2. Обновить импорты — всего три файла:
   - `application/use_cases.py:8`
   - `infrastructure/repositories/player.py:7`
   - `infrastructure/repositories/game_session.py:11`
3. `WaitingSessionInfo` вынести из `domain/entities/game_session.py` в `application/read_models.py`. Обновить импорты в `application/use_cases.py`, `infrastructure/repositories/game_session.py` и в новом `application/ports/repositories.py`.
4. `get_by_id_for_update` пока оставить в порте. Это компромисс: метод описывает блокировку БД. Убирать его правильно вместе с UnitOfWork (транзакция открывается на сценарий, а не через «for update» в интерфейсе). До тех пор фиксируем как известный долг, а не как норму домена.
5. Проверить, что `domain/` не импортирует `application/`, `infrastructure/` или `web/`. Направление зависимостей: `web → application → domain`, а `infrastructure` — внешний слой, он зависит от внутреннего `application`, это разрешено.

Новый файл `application/ports/__init__.py` создавать не обязательно: проект использует namespace packages, импорт `application.ports.repositories` работает и так.

### DIP для сервисов: реальная жёсткая связка

Сейчас use case'ы зависят от конкретных классов, а не от абстракций:

| Use case | Зависимость | Где |
|---|---|---|
| `SignUpUseCase` | `PasswordCryptoService` | `application/use_cases.py:18` |
| `AuthenticatePlayerUseCase` | `PasswordCryptoService` | `application/use_cases.py:40` |
| `MakeMovePvEUseCase` | `MiniMaxService` | `application/use_cases.py:130` |

Из-за этого:

- нельзя подменить хеширование или ИИ в тестах, не патча модуль;
- `application/use_cases.py` знает про конкретную реализацию, а не про контракт;
- `di/composition.py` тоже передаёт конкретные объекты (`context.crypto_service`, `context.ai_engine`), хотя это можно делать через порты.

Порты:

```python
# application/ports/password_hasher.py
from abc import ABC, abstractmethod


class PasswordHasherInterface(ABC):
    @abstractmethod
    def hash_password(self, password: str) -> str: ...

    @abstractmethod
    def verify_password(self, password: str, password_hash: str) -> bool: ...
```

```python
# application/ports/ai_player.py
from abc import ABC, abstractmethod

from domain.entities.playing_board import CellState, PlayingBoard


class AIPlayerInterface(ABC):
    @abstractmethod
    def calculate_best_move(
        self, board: PlayingBoard, ai_sign: CellState
    ) -> tuple[int, int]: ...
```

Шаги:

1. Создать `application/ports/password_hasher.py` и `application/ports/ai_player.py` с ABC выше.
2. В `application/services.py` явно указать наследование:
   - `class PasswordCryptoService(PasswordHasherInterface)`
   - `class MiniMaxService(AIPlayerInterface)`
   Тела методов не меняются.
3. В `application/use_cases.py` заменить типы зависимостей:
   - `crypto_service: PasswordCryptoService` → `crypto_service: PasswordHasherInterface`;
   - `ai_engine: MiniMaxService` → `ai_engine: AIPlayerInterface`.
   Импорты — из `application.ports.*`.
4. В `di/composition.py` ничего структурно не меняется: передаются те же `context.crypto_service` и `context.ai_engine`. Но теперь провайдеры типизированы через порты. Опционально в `AppContext` объявить поля как `crypto_service: PasswordHasherInterface` и `ai_engine: AIPlayerInterface`.
5. Проверить, что `application/use_cases.py` больше не импортирует `application.services` (кроме случаев, где нужна конкретная реализация; сейчас таких быть не должно).
6. В тестах после этого можно подставлять `FakePasswordHasher` и `FakeAIPlayer` через провайдеры или `dependency_overrides`.

Порты нужны не для всего. Оправданы там, где возможна замена или важен контроль: репозитории, хеширование пароля, ИИ-движок, внешние API, время, генерация UUID. Для чистых доменных функций порты не нужны.

### Порядок работ

1. Вынести порты сервисов (`password_hasher.py`, `ai_player.py`) и перевести на них use case'ы — это самый заметный выигрыш.
2. Перенести `interfaces.py` → `application/ports/repositories.py` и обновить три импорта.
3. Вынести `WaitingSessionInfo` в `application/read_models.py`.
4. Вернуться к `get_by_id_for_update` вместе с UnitOfWork.
5. Прогнать проверки: `python -c "import main"`, старт uvicorn, `grep -rn "from domain.interfaces"`.

### Критерии готовности

- `domain/` не импортирует `application/`, `infrastructure/`, `web/`;
- `application/` не импортирует `infrastructure/` и `web/`;
- `infrastructure/` реализует порты из `application/`, а не наоборот;
- use case'ы зависят только от портов, а не от конкретных сервисов;
- `grep -rn "domain.interfaces"` не находит ничего;
- циклических импортов нет: `di/composition.py` — единственное место, где слои соединяются.


я думаю у меня может неправильно сотсавленны поинты move/pve, move/pvp, думаю можно их написать лучше, из за чего не понадобится проверка какой поинт запустил use_case, догадка
НАДО сгенерить нормальный фронт и тесты и может докер(если успею)

---

# Реализация: разграничение PvE/PvP ходов

## 1. В чём была проблема старой схемы

Изначально ход был разрезан на два HTTP-маршрута:

```text
POST /game/{game_session_id}/move/pve  -> MakeMovePvEUseCase
POST /game/{game_session_id}/move/pvp  -> MakeMovePvPUseCase
```

На первый взгляд это удобно: клиент явно говорит, какой сценарий ему нужен.
Но у такого решения есть системная ошибка: **режим игры — это свойство
конкретной партии, а не свойство HTTP-запроса**. Игра уже знает, что она PvE
или PvP (`player_o_id == "bot"`). Если режим дополнительно передаётся через
URL, появляются два источника истины, которые могут разойтись.

Практические последствия:

1. **Неправильный endpoint может запустить неправильный сценарий.** Клиент
   может отправить `/move/pve` для PvP-игры. Если use case не проверяет режим
   внутри сессии, в PvP-партии неожиданно сходит бот.
2. **Дублирование кода.** Оба use case'а делают одно и то же: загружают игру с
   блокировкой, проверяют участие, вызывают `make_move`, сохраняют состояние.
   Отличается только один шаг — ответ бота.
3. **Дублирование маршрутов и DI.** На каждый режим нужны свой роут, свой
   use case, свой провайдер в `di/composition.py` и своя ветка в тестах.
4. **Клиент знает слишком много.** Фронтенд обязан помнить, в какой игре он
   находится, и выбирать URL. Это знание уже есть в ответе сервера.
5. **Добавление нового режима** (например, PvE с уровнем сложности) требует
   нового маршрута, а не новой стратегии.
6. **HTTP-маршрут превращается в `switch` по режиму игры.** Маршрут должен
   отвечать на вопрос «какое действие выполняется» (ход), а не «в каком режиме
   работает домен».

Итоговое правило: **действие одно — ход. Режим определяет домен по состоянию
игры, а не клиент по URL.**

## 2. Принятое решение

Остался один эндпоинт:

```text
POST /game/{game_session_id}/move
```

Он не содержит `mode` ни в path, ни в query, ни в body. Тело осталось
минимальным:

```python
class MoveRequest(BaseModel):
    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)
```

Последовательность обработки:

```text
POST /game/{id}/move
  |
  +-- get_current_player_id        # JWT -> player_id, иначе 401
  |
  +-- MakeMoveUseCase.execute()
        |
        +-- repo.get_by_id_for_update(id)     # блокировка строки
        +-- проверка участия                  # иначе 403
        +-- session.make_move(row, col, player_id)
        |     +-- проверка очереди хода
        |     +-- проверка клетки
        |     +-- проверка победы/ничьей
        |
        +-- registry.get(session.mode).respond(session)
        |     +-- PVP: ничего не делает
        |     +-- PVE: считает ход ИИ и делает его за бота
        |
        +-- repo.update(session)
  |
  +-- WebGameMapper.to_web_response(session)
  +-- notifier.broadcast(...)       # обновление для WebSocket-клиентов
  +-- return GameResponse           # 200
```

Ключевая идея: **use case не спрашивает «какой endpoint меня вызвал»**. Он
смотрит на загруженную сущность и выбирает поведение по её режиму. Никакой
флаг `is_pve` из запроса не принимается — иначе клиент мог бы попросить
выполнить PvE-логику в PvP-игре.

## 3. Где хранится режим игры

Отдельной колонки `game_mode` в БД нет. Режим выводится из состава игроков:

```python
BOT_PLAYER_ID = "bot"


@property
def mode(self) -> GameMode:
    if self.player_o_id == BOT_PLAYER_ID:
        return GameMode.PVE
    return GameMode.PVP


@property
def is_pve(self) -> bool:
    return self.mode == GameMode.PVE
```

Почему так:

- не нужна миграция существующей таблицы;
- невозможно получить рассогласование «колонка говорит PvP, а за O сидит бот»;
- правило определения режима находится в одном месте — в доменной сущности;
- `GameMode` — `StrEnum`, поэтому он одинаково хорошо работает в Python-коде
  и в JSON-ответах Pydantic (`"PVE"` / `"PVP"`).

Компромисс: режим неявный, и его нужно знать при чтении кода. Поэтому инвариант
зафиксирован константой `BOT_PLAYER_ID`, фабриками `create_pve` / `create_pvp`
и тестами.

## 4. Стратегии ответа после хода

Для различия поведения используется паттерн **Strategy** и небольшой реестр.
Файл `application/strategies.py`:

```python
class PvpMoveResponder:
    """В PvP после хода человека ничего не происходит."""

    def respond(self, session: GameSession) -> None:
        pass


class PveMoveResponder:
    """В PvE после хода человека отвечает бот."""

    def __init__(self, ai_engine: AIPlayerInterface) -> None:
        self._ai_engine = ai_engine

    def respond(self, session: GameSession) -> None:
        if session.is_finished():
            return

        row, col = self._ai_engine.calculate_best_move(
            board=session.board,
            ai_sign=session.get_current_turn_sign(),
        )
        session.make_move(row, col, BOT_PLAYER_ID)


class MoveResponderRegistry:
    def __init__(self, responders: Mapping[GameMode, MoveResponder]) -> None:
        missing = set(GameMode) - set(responders)
        if missing:
            modes = ", ".join(mode.value for mode in missing)
            raise ValueError(f"Нет стратегии ответа для режимов: {modes}")

        self._responders = dict(responders)

    def get(self, mode: GameMode) -> MoveResponder:
        return self._responders[mode]
```

Что это даёт:

- **PvP-стратегия — явный no-op.** Отсутствие ответа бота — это тоже поведение,
  а не забытая ветка `if`.
- **PvE-стратегия изолирована.** Вся работа с ИИ находится в одном классе;
  домен и роутер про MiniMax не знают.
- **Проверка полноты реестра.** Если появится новый `GameMode` и для него не
  добавят стратегию, приложение упадёт при сборке реестра, а не в рантайме у
  игрока.
- **Тестируемость.** В `PveMoveResponder` передаётся порт `AIPlayerInterface`,
  поэтому в тестах используется `FakeAIPlayer`, а не настоящий MiniMax.
- **Расширяемость.** Новый режим — это новая запись в словаре, а не новый
  маршрут и не второй use case.

Почему не `if session.is_pve: ... else: ...` прямо в use case? Для двух режимов
это сработало бы. Но тогда:

- use case начинает знать про конкретный AI-сервис;
- тест PvP обязан проверять, что AI не вызван, через monkeypatch;
- добавление режима меняет центральный сценарий, а не добавляет независимый
  компонент;
- нарушается Open/Closed Principle.

Почему не наследование `PvpGameSession` / `PveGameSession`? Потому что режим —
это не разная структура состояния, а один и тот же агрегат с разным
пост-ходовым действием. Наследование усложнило бы маппинг из БД и восстановление
сущности, не дав выигрыша.

Почему не `match session.mode`? Это допустимый простой вариант, но он снова
собирает все режимы в одном методе. Реестр выбран как более явная точка
расширения; при двух режимах разница невелика, но контракт стратегии уже
зафиксирован.

## 5. Единый use case

`MakeMoveUseCase` больше не знает, PvE это или PvP:

```python
class MakeMoveUseCase:
    def __init__(
        self,
        game_session_repository: GameSessionRepositoryInterface,
        responders: MoveResponderRegistry,
    ):
        self._game_session_repository = game_session_repository
        self._responders = responders

    async def execute(
        self,
        game_session_id: str,
        row: int,
        col: int,
        player_id: str,
    ) -> GameSession:
        game_session = await self._game_session_repository.get_by_id_for_update(
            game_session_id
        )
        if not game_session:
            raise NotFoundError(...)

        if not game_session.is_participant(player_id):
            raise ForbiddenError("Нет доступа к этой игре")

        game_session.make_move(row, col, player_id)
        self._responders.get(game_session.mode).respond(game_session)

        await self._game_session_repository.update(game_session)
        return game_session
```

Порядок важен:

1. Сначала загружается игра с `FOR UPDATE`, чтобы два одновременных хода не
   прочитали одно и то же состояние.
2. Проверка участия стоит до доменного хода: посторонний получает 403, а не
   сообщение о занятой клетке.
3. Доменный `make_move` проверяет очередь, границы и завершённость.
4. Только после успешного хода человека вызывается стратегия ответа.
5. `PveMoveResponder` сам проверяет `is_finished()`: если человек выиграл
   последним ходом, бот не должен ходить в завершённую игру.
6. Сохранение выполняется один раз после обоих ходов — человеческого и
   ответа бота. Это важно: клиент не увидит промежуточное состояние, где бот
   ещё не ответил.

## 6. Сборка зависимостей

Реестр собирается в composition root, а не внутри use case:

```python
def get_move_responders(
    context: AppContext = Depends(get_context),
) -> MoveResponderRegistry:
    return MoveResponderRegistry(
        {
            GameMode.PVP: PvpMoveResponder(),
            GameMode.PVE: PveMoveResponder(context.ai_engine),
        }
    )


def get_make_move_use_case(
    repository: GameSessionRepository = Depends(get_game_session_repository),
    responders: MoveResponderRegistry = Depends(get_move_responders),
) -> MakeMoveUseCase:
    return MakeMoveUseCase(
        game_session_repository=repository,
        responders=responders,
    )
```

`AppContext` хранит `ai_engine: AIPlayerInterface`, то есть конкретный
`MiniMaxService` скрыт за портом. Use case получает готовый реестр и не создаёт
зависимости сам. Это и есть Dependency Injection в терминах FastAPI:
`Depends` — механизм, `di/composition.py` — место сборки графа объектов.

## 7. Роутер

В `web/router.py` остался один обработчик хода:

```python
@game_router.post("/{game_session_id}/move", response_model=GameResponse)
async def make_move(
    request: MoveRequest,
    game_session_id: uuid.UUID = Path(...),
    use_case: MakeMoveUseCase = Depends(get_make_move_use_case),
    current_player_id: str = Depends(get_current_player_id),
):
    updated_game_session = await use_case.execute(
        game_session_id=str(game_session_id),
        player_id=current_player_id,
        row=request.row,
        col=request.col,
    )
    await notifier.broadcast(
        game_session_id=str(game_session_id),
        message=WebGameMapper.to_web_response(updated_game_session).model_dump(
            mode="json"
        ),
    )

    return WebGameMapper.to_web_response(domain_game_session=updated_game_session)
```

Роутер не содержит `if mode == ...`. Он делает только транспортную работу:
валидирует путь и тело, достаёт игрока из JWT, вызывает сценарий, отправляет
обновление в WebSocket и возвращает DTO.

`GameResponse` теперь содержит всё, что нужно фронтенду, чтобы не делать
дополнительных запросов:

```text
game_session_id, mode, status, status_text, board, grid_size,
player_x_id, player_o_id, current_player_id, is_finished
```

Это же представление используется и для `POST /game/{id}/join` — после
присоединения клиент сразу получает полное состояние партии.

## 8. Что удалено

- `POST /game/{id}/move/pve`;
- `POST /game/{id}/move/pvp`;
- `MakeMovePvEUseCase`;
- `MakeMovePvPUseCase`;
- соответствующие провайдеры в `di/composition.py`;
- отдельный `POST /game/{id}/del` заменён на `POST /game/{id}/leave`.

Старые URL теперь возвращают 404. Это зафиксировано API-тестом
`test_old_move_endpoints_are_gone`: случайно оставленный старый маршрут не
должен продолжать работать.

## 9. Поведение ошибок

| Ситуация | Ответ |
|---|---|
| Нет или просрочен JWT | `401` |
| Игра не найдена | `404` |
| Игрок не участник партии | `403` |
| Игра ждёт второго игрока | `400` (доменная ошибка) |
| Сейчас ход другого игрока | `400` |
| Клетка занята | `400` |
| Координаты вне поля | `400` |
| Попытка хода после завершения | `400` |
| Ошибка БД / constraint | `409` или `500` по типу ошибки |

Доменные ошибки не просачиваются наружу как `ValueError` с внутренним текстом:
они преобразуются в `DomainError` и централизованно маппятся в HTTP в
`web/errors.py`.

## 10. Как это проверено тестами

| Тест | Что доказывает |
|---|---|
| `test_pvp_move_does_not_call_ai` | В PvP стратегия не обращается к ИИ |
| `test_pve_move_calls_ai_and_applies_bot_move` | В PvE после хода человека бот отвечает, и оба хода сохраняются |
| `test_pve_does_not_call_ai_after_human_win` | Бот не ходит в завершённой игре |
| `test_move_missing_game_raises_not_found` | Несуществующая игра — 404 |
| `test_move_by_non_participant_is_forbidden` | Посторонний не может ходить |
| `test_move_out_of_turn_is_rejected` | Очередь хода проверяется доменом |
| `test_move_after_finish_is_rejected` | Завершённая партия не меняется |
| `test_registry_rejects_incomplete_modes` | Реестр падает при отсутствии стратегии |
| `test_unified_pve_move_applies_bot_answer` | API-тест единого PvE-эндпоинта |
| `test_pvp_join_and_moves` | API-тест PvP: join, два хода, смена игрока |
| `test_old_move_endpoints_are_gone` | Старые `/move/pve` и `/move/pvp` недоступны |
| `test_non_participant_cannot_move` | HTTP-слой отдаёт 403 |

Тесты стратегий используют `FakeAIPlayer`, поэтому не зависят от глубины
MiniMax и работают быстро.

## 11. Известные ограничения решения

1. `PveMoveResponder` делает **один** ответный ход. Для крестиков-ноликов этого
   достаточно: после хода бота снова ход человека. Если появится режим, где
   бот должен ходить несколько раз подряд, понадобится цикл или отдельный
   сценарий.
2. Режим выводится из `player_o_id == "bot"`. Если когда-нибудь появится
   «бот за X» или несколько ботов, одного условия станет мало — тогда лучше
   ввести явный `GameMode` в модели, но уже осознанно, с миграцией.
3. WebSocket-уведомление отправляется в роутере до завершения транзакции
   зависимости. При ошибке commit клиенты теоретически могут увидеть состояние,
   которое не сохранилось. Для учебного проекта это приемлемо; строгий вариант —
   отправлять событие после commit (Unit of Work / outbox / background task).
4. In-memory `ConnectionManager` не переживает рестарт и не синхронизирует
   несколько воркеров. Для продакшена нужен Redis Pub/Sub или аналогичный
   брокер.

---

# Теоретическая сводка: архитектура и инструменты Python

## 1. Архитектурный стиль

Проект построен по принципам **слоистой архитектуры** с элементами
**Ports & Adapters (гексагональной архитектуры)**.

Главное правило — **направление зависимостей**:

```text
web  ->  application  ->  domain
              ^
              |
       infrastructure
```

- `domain` не знает ни про FastAPI, ни про SQLAlchemy, ни про JSON.
- `application` знает про домен и про свои порты, но не про конкретную БД.
- `infrastructure` реализует порты `application` с помощью SQLAlchemy.
- `web` знает про `application`, принимает HTTP/WebSocket и преобразует
  доменные объекты в Pydantic-схемы.
- `di` — единственное место, где слои собираются вместе.

Проверка этого правила простая:

```bash
grep -rn "from application\|from infrastructure\|from web" domain
```

Команда не должна находить импортов. Именно поэтому `domain/errors.py`
содержит только доменную ошибку, а не HTTP-коды.

### Слои и их ответственность

| Слой | Что лежит | Чего там быть не должно |
|---|---|---|
| `domain/` | сущности, value objects, правила игры, доменные ошибки | HTTP, SQL, JWT, Pydantic |
| `application/` | use cases, порты, read-модели, стратегии | FastAPI, SQLAlchemy, конкретные репозитории |
| `infrastructure/` | ORM-модели, репозитории, мапперы, инициализация БД | бизнес-правила |
| `web/` | роутеры, схемы, guard'ы, мапперы, обработчики ошибок, статика | прямые SQL-запросы |
| `di/` | настройки, AppContext, провайдеры `Depends` | бизнес-логика |
| `tests/` | unit-, API- и инфраструктурные тесты, фейки | доступ к реальной БД |

### Домен

Домен — это центр приложения. В нём находятся:

- `Player` — сущность игрока;
- `PlayingBoard` — неизменяемое игровое поле;
- `GameSession` — агрегат партии;
- `GameRules` — проверка победных линий;
- `GameSessionState`, `GameMode`, `CellState` — перечисления состояний;
- `DomainError` — нарушение правил игры.

`PlayingBoard` и `Player` объявлены как `@dataclass(frozen=True)`: значение
нельзя изменить после создания. Ход возвращает **новую** доску, а не мутирует
старую. Это упрощает тесты и исключает случайные изменения состояния.

`GameSession` — изменяемый агрегат: у него есть жизненный цикл (ожидание,
ход X, ход O, победа, ничья). Все переходы собраны в его методах, а не в
роутерах. Это называется **rich domain model**: сущность сама защищает свои
инварианты.

### Application layer

Здесь находятся сценарии, которые отвечают на вопрос «что делает система»:

- `SignUpUseCase`, `AuthenticatePlayerUseCase`;
- `CreatePvEGameUseCase`, `CreatePvPGameUseCase`;
- `JoinPvPGameUseCase`, `MakeMoveUseCase`, `LeaveGameUseCase`;
- `GetGameSessionUseCase`, `GetWaitingSessionsUseCase`,
  `GetFinishedSessionsUseCase`, `GetPlayerByUuidUseCase`.

Use case не знает, откуда его вызвали — из HTTP, CLI или теста. Он принимает
простые аргументы, работает с портами и возвращает доменный объект или
read-модель.

**Порты** — это интерфейсы, которые нужны внутреннему слою:

- `application/ports/repositories.py` — работа с игроками и партиями;
- `application/ports/password_hasher.py` — хеширование паролей;
- `application/ports/ai_player.py` — расчёт хода ИИ;
- `application/ports/move_responder.py` — реакция на ход человека.

Для репозиториев и сервисов используется `ABC` + `@abstractmethod`, для
стратегии ответа — `typing.Protocol`. `Protocol` удобен, когда нужен
структурный контракт без явного наследования: классу достаточно иметь метод
`respond`.

**Read-модели** (`WaitingSessionInfo`, `FinishedSessionInfo`) — это не сущности
домена, а лёгкие DTO для списков. Они лежат в `application/read_models.py`,
потому что описывают потребность сценария, а не правило игры.

### Infrastructure layer

Здесь находятся адаптеры к внешнему миру:

- `infrastructure/model.py` — SQLAlchemy-модели `PlayerDataModel` и
  `GameSessionDataModel`;
- `infrastructure/mappers/` — преобразование ORM-моделей в доменные сущности и
  обратно;
- `infrastructure/repositories/` — реализация портов;
- `infrastructure/init.py` — создание таблиц и служебного игрока-бота.

Репозиторий не возвращает ORM-модель наружу: он маппит её в домен. Это защищает
домен от знания о таблицах и позволяет менять схему БД, не меняя use case.

### Web layer

FastAPI-роутеры выполняют только транспортные обязанности:

1. принять и провалидировать запрос;
2. достать `player_id` из JWT;
3. вызвать use case;
4. преобразовать результат в Pydantic-схему;
5. вернуть HTTP-статус и, где нужно, разослать WebSocket-событие.

Pydantic-схемы (`web/schema.py`) — это **контракт API**, а не доменные модели.
Они проверяют форму данных: типы, `ge=0`, длины строк, обязательность полей.
Смысловые проверки («сейчас не твой ход») остаются в домене.

`web/mapper.py` переводит доменные объекты и read-модели в ответы API. Это
позволяет не отдавать наружу внутренние поля и не привязывать JSON к структуре
сущности.

### DI и composition root

`di/composition.py` — единственное место, где создаются конкретные реализации:

- `JWTService`;
- `PasswordCryptoService`;
- `MiniMaxService`;
- SQLAlchemy engine и session factory;
- репозитории;
- use cases;
- реестр стратегий.

FastAPI `Depends` — это DI-контейнер уровня запроса. Зависимости с `yield`
создают и закрывают ресурсы (например, сессию БД) вокруг обработки запроса.
`app.state.context` хранит долгоживущие объекты, созданные в `lifespan`.

Паттерн **Composition Root** важен тем, что бизнес-код не занимается
самосборкой. Если завтра нужно заменить `MiniMaxService` на другую реализацию,
меняется одна строчка в `di`, а не все use case'ы.

### Использованные паттерны

| Паттерн | Где |
|---|---|
| Repository | `GameSessionRepository`, `PlayerRepository` |
| Ports & Adapters | `application/ports/*` + `infrastructure/repositories/*` |
| Strategy | `PvpMoveResponder`, `PveMoveResponder`, `MoveResponderRegistry` |
| Mapper / DTO | `infrastructure/mappers/*`, `web/mapper.py`, Pydantic-схемы |
| Dependency Injection | `Depends`, `di/composition.py` |
| Composition Root | `AppContext` + провайдеры |
| Unit of Work (частично) | сессия БД и commit/rollback в `get_db_session` |
| Guard | `get_current_player_id` |

## 2. Поток HTTP-запроса

На примере хода:

```text
клиент
  -> FastAPI router
  -> Pydantic валидация тела
  -> get_current_player_id (JWT)
  -> MakeMoveUseCase
  -> GameSessionRepository (SQLAlchemy)
  -> PostgreSQL
  -> GameSession.make_move (домен)
  -> MoveResponderRegistry -> PveMoveResponder -> MiniMax
  -> repository.update
  -> WebGameMapper -> GameResponse
  -> notifier.broadcast (WebSocket)
  -> HTTP 200 + JSON
```

Важно, что каждый слой видит только соседний внутренний слой. Роутер не делает
SQL, репозиторий не проверяет очередь хода, а домен не знает, что существует
HTTP-статус 403.

## 3. Асинхронность

Проект полностью асинхронный:

- FastAPI-обработчики объявлены через `async def`;
- SQLAlchemy работает в async-режиме;
- драйвер PostgreSQL — `asyncpg`;
- WebSocket-обработчик тоже асинхронный;
- сессия БД создаётся через `async_sessionmaker`.

`AsyncGenerator` используется в зависимости `get_db_session`:

```python
async def get_db_session(...) -> AsyncGenerator[AsyncSession, None]:
    async with context.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

`async with` гарантирует закрытие сессии, а `try/except` — откат при ошибке.
`await` не блокирует event loop и позволяет одному процессу обслуживать много
соединений.

Особенность FastAPI: код после `yield` в зависимости выполняется на этапе
завершения запроса. В текущей версии это происходит после отправки ответа,
поэтому для строгой гарантии «commit до ответа» в будущем стоит вынести
транзакцию в Unit of Work или явный сценарий. Это отмечено в ограничениях выше.

## 4. Инструменты Python

### Версия и синтаксис

Проект использует Python 3.12. Из современных возможностей языка применены:

- **PEP 604**: `str | None` вместо `Optional[str]`;
- **встроенные generics**: `list[str]`, `dict[str, int]`, `tuple[int, ...]`;
- **`enum.StrEnum`** для строковых перечислений;
- **`datetime.UTC`** вместо `timezone.utc`;
- **`match/case`** в `status_text`;
- **`dataclasses`** с `frozen=True`, `kw_only=True`, `field(default_factory=...)`;
- **`pathlib.Path`** для путей к статике;
- **`contextlib.asynccontextmanager`** для `lifespan`;
- **`typing.Protocol`**, `Literal`, `Mapping`, `Sequence`, `AsyncGenerator`;
- **`secrets`**, `hashlib`, `hmac` для безопасности паролей.

### Управление зависимостями: uv

`uv` — быстрый менеджер пакетов и виртуальных окружений:

```bash
uv sync                 # установить runtime + dev зависимости
uv add <package>        # добавить runtime-зависимость
uv add --dev <package>  # добавить dev-зависимость
uv run <command>        # выполнить команду в окружении проекта
```

Зависимости описаны в `pyproject.toml`, точные версии зафиксированы в
`uv.lock`. Dev-группа (`pytest`, `pytest-asyncio`, `httpx`, `ruff`,
`pytest-cov`) не попадает в production-установку.

### Веб-стек

- **FastAPI** — маршрутизация, DI через `Depends`, валидация, OpenAPI,
  WebSocket, `lifespan`.
- **Starlette** — ASGI-основа FastAPI: `Request`, `Response`, `StaticFiles`,
  `WebSocket`.
- **Pydantic v2** — схемы запросов/ответов, `Field`, `ConfigDict`,
  `from_attributes`, сериализация enum'ов.
- **Uvicorn** — ASGI-сервер для запуска приложения.
- **aiofiles** — асинхронная работа со статическими файлами (подключается
  StaticFiles).

### База данных

- **PostgreSQL** — основное хранилище.
- **SQLAlchemy 2.x async** — ORM и query builder:
  - `select`, `insert`, `delete`, `or_`;
  - `with_for_update()` для блокировки строки на время хода;
  - `async_sessionmaker` и `AsyncSession`;
  - `ARRAY(Integer)` для плоского хранения поля;
  - `begin_nested()` (savepoint) для безопасной обработки `IntegrityError`.
- **asyncpg** — асинхронный драйвер PostgreSQL.
- **`Base.metadata.create_all`** — создание таблиц при старте. Это удобно для
  учебного проекта, но не заменяет миграции; для продакшена нужен Alembic.

### Безопасность

- **PyJWT** — создание и проверка JWT (`sub`, `exp`).
- **PBKDF2-HMAC-SHA256** (`hashlib.pbkdf2_hmac`) — хеширование паролей.
- **`secrets.token_bytes`** — случайная соль на каждый пароль.
- **`hmac.compare_digest`** — сравнение хешей за постоянное время.
- **`HTTPBearer`** — извлечение токена из заголовка `Authorization`.
- **WebSocket subprotocol** — передача токена без query-строки, которая
  попадает в логи.
- **`textContent`** на фронтенде — безопасный вывод пользовательских данных
  без интерпретации HTML.

### Тестирование

- **pytest** — основной фреймворк.
- **pytest-asyncio** — запуск async-тестов; в `pyproject.toml` включён
  `asyncio_mode = "auto"`, поэтому `@pytest.mark.asyncio` не нужен.
- **fixtures** — общие объекты (`client`, `app`, репозитории).
- **`pytest.mark.parametrize`** — табличные проверки границ и ошибок.
- **FastAPI TestClient** (на базе httpx) — синхронные API-тесты.
- **`dependency_overrides`** — подмена зависимостей FastAPI без monkeypatch.
- **fakes** — `InMemoryPlayerRepository`, `InMemoryGameSessionRepository`,
  `FakeAIPlayer`, `FakePasswordHasher`, `FakeAppContext`.
- **pytest-cov** — покрытие; цель — проверять домен и сценарии, а не гоняться
  за 100% в адаптерах БД.

Тестовая пирамида проекта:

```text
unit-тесты домена и use case   — много, быстрые, без I/O
API-smoke-тесты                — меньше, проверяют контракт HTTP/WS
интеграционные тесты с БД      — пока отсутствуют (известный долг)
```

### Качество кода

- **ruff** — одновременно линтер и форматтер.
- Выбранные правила: `E`, `F` (ошибки и импорты), `I` (сортировка импортов),
  `UP` (современный синтаксис), `B` (баги), `C4` (comprehensions),
  `SIM` (упрощения).
- `line-length = 88`, `target-version = "py312"`.
- **Makefile** — короткие команды `make test`, `make lint`, `make format`,
  `make cov`, `make check`.

### Фронтенд

Фронтенд не использует Node.js и сборку:

- `web/static/index.html` — разметка;
- `web/static/styles.css` — стили;
- `web/static/app.js` — логика на нативном JavaScript.

Используются:

- `fetch` для HTTP-запросов;
- `WebSocket` с токеном в subprotocol;
- `localStorage` для JWT;
- DOM API (`createElement`, `textContent`, `replaceChildren`) вместо
  `innerHTML` — это исключает XSS;
- `StaticFiles` FastAPI для раздачи файлов;
- `FileResponse` для отдачи `index.html` по `/`.

## 5. Итоговая карта проекта

```text
main.py                          точка входа uvicorn

domain/
  entities/player.py             Player, BOT_PLAYER_ID
  entities/playing_board.py      PlayingBoard, CellState
  entities/game_session.py       GameSession, GameRules, GameMode, состояния
  errors.py                      DomainError

application/
  ports/                         контракты репозиториев, AI, хешера, стратегии
  use_cases.py                   сценарии
  strategies.py                  PvP/PvE-стратегии и реестр
  services.py                    MiniMax, PBKDF2
  read_models.py                 DTO для списков
  jwt_service.py                 JWT
  errors.py                      прикладные ошибки

infrastructure/
  model.py                       SQLAlchemy-модели
  mappers/                       ORM <-> domain
  repositories/                  реализации портов
  init.py                        create_all + бот

web/
  app.py                         create_app, lifespan, health, статика
  router.py                      игровые HTTP-маршруты
  auth/                          signup/login/me и guard
  ws/                            WebSocket-роутер и менеджер соединений
  schema.py                      Pydantic-схемы
  mapper.py                      domain -> API
  errors.py                      маппинг ошибок в HTTP
  static/                        фронтенд

di/
  settings.py                    настройки из env
  composition.py                 AppContext и провайдеры Depends

tests/
  domain/                        правила игры
  application/                   use cases и сервисы
  infrastructure/                мапперы
  web/                           WS, статика, мапперы
  api/                           HTTP/WebSocket smoke-тесты
  fakes.py                       in-memory реализации
```

## 6. Что стоит сделать дальше

1. **Alembic** вместо `create_all` — управляемые миграции.
2. **Unit of Work** — явная транзакция на сценарий и commit до ответа.
3. **Интеграционные тесты с PostgreSQL** — проверить `with_for_update`,
   маппинг ARRAY и constraint'ы.
4. **Redis Pub/Sub** для WebSocket-уведомлений между воркерами.
5. **Docker / docker-compose** — воспроизводимый запуск приложения и БД.
6. **Rate limiting** для `/auth/login` и `/auth/signup`.
7. **Обновление legacy-хешей** при успешном входе пользователя.
8. **Структурированное логирование** и метрики.
