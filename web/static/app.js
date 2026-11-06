"use strict";

const TOKEN_KEY = "tictactoe.token";
const LOGIN_KEY = "tictactoe.login";
const PLAYER_ID_KEY = "tictactoe.playerId";

const state = {
    token: localStorage.getItem(TOKEN_KEY),
    login: localStorage.getItem(LOGIN_KEY),
    playerId: localStorage.getItem(PLAYER_ID_KEY),
    game: null,
    gameId: null,
    socket: null,
    socketGameId: null,
    reconnectTimer: null,
    reconnectAttempts: 0,
    moving: false,
    authMode: "login",
    userCache: new Map(),
};

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}

const dom = {
    screens: Array.from(document.querySelectorAll(".screen")),
    userArea: document.getElementById("user-area"),
    menuUser: document.getElementById("menu-user"),
    authModal: document.getElementById("auth-modal"),
    authTitle: document.getElementById("auth-title"),
    authForm: document.getElementById("auth-form"),
    authLogin: document.getElementById("auth-login"),
    authPassword: document.getElementById("auth-password"),
    authError: document.getElementById("auth-error"),
    authSubmit: document.getElementById("auth-submit"),
    tabLogin: document.getElementById("tab-login"),
    tabRegister: document.getElementById("tab-register"),
    board: document.getElementById("board"),
    gameStatus: document.getElementById("game-status"),
    gameMode: document.getElementById("game-mode"),
    gameTitle: document.getElementById("game-title"),
    playerSelf: document.getElementById("player-self"),
    playerOpponent: document.getElementById("player-opponent"),
    connection: document.getElementById("connection-state"),
    lobbiesList: document.getElementById("lobbies-list"),
    historyList: document.getElementById("history-list"),
    toasts: document.getElementById("toasts"),
};

function showScreen(id) {
    for (const screen of dom.screens) {
        screen.classList.toggle("active", screen.id === id);
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function toast(message, kind = "info") {
    const node = document.createElement("div");
    node.className = `toast ${kind}`;
    node.textContent = message;
    dom.toasts.append(node);
    window.setTimeout(() => node.remove(), 4200);
}

async function api(path, options = {}) {
    const { method = "GET", body, auth = true } = options;
    const headers = {};
    if (body !== undefined) {
        headers["Content-Type"] = "application/json";
    }
    if (auth && state.token) {
        headers.Authorization = `Bearer ${state.token}`;
    }

    const response = await fetch(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (response.status === 204) {
        return null;
    }

    let data = null;
    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {
        if (response.status === 401 && auth) {
            clearSession();
            closeGame();
            renderHeader();
            showScreen("welcome-screen");
        }
        const detail = data && data.detail;
        const message =
            typeof detail === "string"
                ? detail
                : detail
                  ? "Некорректные данные запроса"
                  : `Ошибка ${response.status}`;
        throw new ApiError(message, response.status);
    }

    return data;
}

function saveSession(payload) {
    state.token = payload.access_token;
    state.login = payload.login;
    state.playerId = payload.player_id;
    localStorage.setItem(TOKEN_KEY, state.token);
    localStorage.setItem(LOGIN_KEY, state.login);
    localStorage.setItem(PLAYER_ID_KEY, state.playerId);
    state.userCache.clear();
}

function clearSession() {
    state.token = null;
    state.login = null;
    state.playerId = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LOGIN_KEY);
    localStorage.removeItem(PLAYER_ID_KEY);
}

function renderHeader() {
    dom.userArea.replaceChildren();
    if (!state.token) {
        return;
    }

    const chip = document.createElement("span");
    chip.className = "user-chip";
    const label = document.createElement("strong");
    label.textContent = state.login || "Игрок";
    chip.append("Вы вошли как ", label);

    const logout = document.createElement("button");
    logout.type = "button";
    logout.className = "btn btn-ghost";
    logout.textContent = "Выйти";
    logout.addEventListener("click", () => {
        closeGame();
        clearSession();
        renderHeader();
        showScreen("welcome-screen");
    });

    dom.userArea.append(chip, logout);
    dom.menuUser.textContent = state.login || "";
}

function openAuth(mode) {
    state.authMode = mode;
    dom.authError.hidden = true;
    dom.authError.textContent = "";
    dom.authLogin.value = "";
    dom.authPassword.value = "";
    setAuthMode(mode);
    dom.authModal.hidden = false;
    window.setTimeout(() => dom.authLogin.focus(), 30);
}

function closeAuth() {
    dom.authModal.hidden = true;
}

function setAuthMode(mode) {
    state.authMode = mode;
    const isLogin = mode === "login";
    dom.tabLogin.classList.toggle("active", isLogin);
    dom.tabRegister.classList.toggle("active", !isLogin);
    dom.tabLogin.setAttribute("aria-selected", String(isLogin));
    dom.tabRegister.setAttribute("aria-selected", String(!isLogin));
    dom.authTitle.textContent = isLogin ? "Вход" : "Регистрация";
    dom.authSubmit.textContent = isLogin ? "Войти" : "Создать аккаунт";
    dom.authPassword.autocomplete = isLogin ? "current-password" : "new-password";
}

async function submitAuth(event) {
    event.preventDefault();
    const login = dom.authLogin.value.trim();
    const password = dom.authPassword.value;
    dom.authError.hidden = true;

    if (login.length < 3 || password.length < 6) {
        dom.authError.textContent =
            "Логин — минимум 3 символа, пароль — минимум 6 символов.";
        dom.authError.hidden = false;
        return;
    }

    dom.authSubmit.disabled = true;
    try {
        if (state.authMode === "register") {
            await api("/auth/signup", {
                method: "POST",
                body: { login, password },
                auth: false,
            });
        }

        const payload = await api("/auth/login", {
            method: "POST",
            body: { login, password },
            auth: false,
        });
        saveSession(payload);
        renderHeader();
        closeAuth();
        showScreen("menu-screen");
        toast(`Добро пожаловать, ${payload.login}!`, "success");
    } catch (error) {
        dom.authError.textContent = error.message;
        dom.authError.hidden = false;
    } finally {
        dom.authSubmit.disabled = false;
    }
}

async function restoreSession() {
    renderHeader();
    if (!state.token) {
        showScreen("welcome-screen");
        return;
    }

    try {
        const me = await api("/auth/me");
        state.login = me.login;
        state.playerId = me.id;
        localStorage.setItem(LOGIN_KEY, state.login);
        localStorage.setItem(PLAYER_ID_KEY, state.playerId);
        renderHeader();
        showScreen("menu-screen");
    } catch {
        clearSession();
        renderHeader();
        showScreen("welcome-screen");
    }
}

async function resolveLogin(playerId) {
    if (!playerId) {
        return null;
    }
    if (playerId === "bot") {
        return "Компьютер";
    }
    if (playerId === state.playerId) {
        return state.login;
    }
    if (state.userCache.has(playerId)) {
        return state.userCache.get(playerId);
    }

    try {
        const user = await api(`/game/user/${playerId}`);
        state.userCache.set(playerId, user.login);
        return user.login;
    } catch {
        return null;
    }
}

function mySign(game) {
    if (game.player_x_id === state.playerId) {
        return "X";
    }
    if (game.player_o_id === state.playerId) {
        return "O";
    }
    return null;
}

function winningCells(game) {
    const size = game.grid_size;
    const board = game.board;
    const lines = [];

    for (let row = 0; row < size; row += 1) {
        lines.push(Array.from({ length: size }, (_, col) => row * size + col));
    }
    for (let col = 0; col < size; col += 1) {
        lines.push(Array.from({ length: size }, (_, row) => row * size + col));
    }
    lines.push(Array.from({ length: size }, (_, index) => index * size + index));
    lines.push(
        Array.from({ length: size }, (_, index) => index * size + (size - 1 - index)),
    );

    for (const line of lines) {
        const first = board[line[0]];
        if (first && line.every((index) => board[index] === first)) {
            return new Set(line);
        }
    }
    return new Set();
}

function statusLabel(game) {
    const sign = mySign(game);
    switch (game.status) {
        case "WAITING":
            return "Ожидание соперника…";
        case "DRAW":
            return "Ничья. Поле заполнено.";
        case "WON_X":
        case "WON_O": {
            const winner = game.status === "WON_X" ? "X" : "O";
            if (sign === winner) {
                return "Вы победили! 🎉";
            }
            if (sign) {
                return "Вы проиграли.";
            }
            return `Победил игрок ${winner}.`;
        }
        case "TURN_X":
        case "TURN_O": {
            const turn = game.status === "TURN_X" ? "X" : "O";
            if (!sign) {
                return `Ход игрока ${turn}.`;
            }
            return sign === turn ? "Ваш ход" : "Ход соперника…";
        }
        default:
            return game.status_text || "Игра";
    }
}

function renderBoard(game) {
    dom.board.replaceChildren();
    dom.board.style.gridTemplateColumns = `repeat(${game.grid_size}, 1fr)`;
    dom.board.setAttribute("role", "grid");

    const wins = winningCells(game);
    const sign = mySign(game);
    const myTurn =
        !state.moving &&
        !game.is_finished &&
        sign !== null &&
        game.current_player_id === state.playerId;

    game.board.forEach((value, index) => {
        const cell = document.createElement("button");
        cell.type = "button";
        cell.className = "cell";
        cell.setAttribute("role", "gridcell");
        cell.setAttribute("aria-label", `Клетка ${index + 1}`);
        cell.textContent = value;

        if (value === "X") {
            cell.classList.add("x");
        } else if (value === "O") {
            cell.classList.add("o");
        }
        if (wins.has(index)) {
            cell.classList.add("win");
        }

        const playable = myTurn && value === "";
        if (playable) {
            cell.classList.add("playable");
            cell.addEventListener("click", () => makeMove(game, index));
        } else {
            cell.disabled = true;
        }

        dom.board.append(cell);
    });
}

async function makeMove(game, index) {
    if (state.moving || !state.gameId) {
        return;
    }

    const size = game.grid_size;
    const row = Math.floor(index / size);
    const col = index % size;
    state.moving = true;
    renderGame(state.game);

    try {
        const updated = await api(`/game/${state.gameId}/move`, {
            method: "POST",
            body: { row, col },
        });
        applyGame(updated);
    } catch (error) {
        toast(error.message, "error");
    } finally {
        state.moving = false;
        if (state.game) {
            renderGame(state.game);
        }
    }
}

function renderGame(game) {
    if (!game) {
        return;
    }

    const sign = mySign(game);
    const isPve = game.mode === "PVE";

    dom.gameMode.textContent = isPve ? "Игра против бота" : "PvP матч";
    dom.gameTitle.textContent = isPve ? "PvE" : "PvP";

    const selfLabel = sign ? `${state.login || "Вы"} · ${sign}` : state.login || "Вы";
    dom.playerSelf.textContent = selfLabel;

    if (isPve) {
        dom.playerOpponent.textContent = "Компьютер · O";
    } else if (game.player_o_id) {
        const opponentId =
            game.player_x_id === state.playerId ? game.player_o_id : game.player_x_id;
        dom.playerOpponent.textContent = "Соперник";
        resolveLogin(opponentId).then((name) => {
            if (state.game === game && name) {
                const opponentSign = game.player_x_id === state.playerId ? "O" : "X";
                dom.playerOpponent.textContent = `${name} · ${opponentSign}`;
            }
        });
    } else {
        dom.playerOpponent.textContent = "Ожидание соперника…";
    }

    dom.playerSelf.classList.toggle(
        "active",
        !game.is_finished && game.current_player_id === state.playerId,
    );
    dom.playerOpponent.classList.toggle(
        "active",
        !game.is_finished &&
            game.current_player_id !== null &&
            game.current_player_id !== state.playerId,
    );

    dom.gameStatus.textContent = statusLabel(game);
    renderBoard(game);
}

function setConnection(online) {
    dom.connection.hidden = false;
    dom.connection.textContent = online ? "Онлайн" : "Переподключение…";
    dom.connection.classList.toggle("online", online);
    dom.connection.classList.toggle("offline", !online);
}

function closeSocket() {
    if (state.reconnectTimer) {
        window.clearTimeout(state.reconnectTimer);
        state.reconnectTimer = null;
    }
    if (state.socket) {
        const socket = state.socket;
        state.socket = null;
        socket.onclose = null;
        socket.onerror = null;
        socket.onmessage = null;
        socket.close();
    }
    state.socketGameId = null;
    dom.connection.hidden = true;
}

function connectSocket(gameId) {
    if (!state.token) {
        return;
    }

    closeSocket();
    state.socketGameId = gameId;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/game/${gameId}/ws`;
    const socket = new WebSocket(url, ["access_token", state.token]);
    state.socket = socket;

    socket.onopen = () => {
        state.reconnectAttempts = 0;
        setConnection(true);
    };

    socket.onmessage = (event) => {
        if (state.gameId !== gameId) {
            return;
        }
        try {
            const message = JSON.parse(event.data);
            if (message && message.type === "GAME_DELETED") {
                toast("Игра была закрыта.", "info");
                closeGame();
                showScreen("menu-screen");
                return;
            }
            applyGame(message);
        } catch {
            // Игнорируем повреждённое сообщение, сервер пришлёт актуальное.
        }
    };

    socket.onclose = () => {
        if (state.socket === socket) {
            state.socket = null;
        }
        if (state.gameId !== gameId || !state.token) {
            return;
        }
        if (state.game && state.game.is_finished) {
            setConnection(false);
            dom.connection.textContent = "Игра завершена";
            return;
        }

        setConnection(false);
        if (state.reconnectAttempts >= 5) {
            dom.connection.textContent = "Нет связи";
            return;
        }
        state.reconnectAttempts += 1;
        state.reconnectTimer = window.setTimeout(() => {
            if (state.gameId === gameId) {
                connectSocket(gameId);
            }
        }, 2000 * state.reconnectAttempts);
    };
}

function applyGame(game) {
    if (!game || !game.game_session_id) {
        return;
    }
    state.game = game;
    if (state.gameId === game.game_session_id) {
        renderGame(game);
    }
}

function openGame(game) {
    state.game = game;
    state.gameId = game.game_session_id;
    state.moving = false;
    renderGame(game);
    showScreen("game-screen");
    connectSocket(game.game_session_id);
}

function closeGame() {
    closeSocket();
    state.game = null;
    state.gameId = null;
    state.moving = false;
}

async function startGame(path) {
    try {
        const game = await api(path, { method: "POST" });
        openGame(game);
    } catch (error) {
        toast(error.message, "error");
    }
}

async function leaveGame() {
    if (!state.gameId) {
        closeGame();
        showScreen("menu-screen");
        return;
    }

    const gameId = state.gameId;
    const wasWaiting = state.game && state.game.status === "WAITING";
    closeGame();

    try {
        await api(`/game/${gameId}/leave`, { method: "POST" });
    } catch (error) {
        toast(error.message, "error");
    }

    showScreen("menu-screen");
    if (wasWaiting) {
        toast("Лобби закрыто.", "info");
    }
}

function renderLobbies(sessions) {
    dom.lobbiesList.replaceChildren();
    if (!sessions.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent =
            "Сейчас нет открытых лобби. Создайте своё и подождите соперника.";
        dom.lobbiesList.append(empty);
        return;
    }

    for (const session of sessions) {
        const item = document.createElement("div");
        item.className = "list-item";

        const main = document.createElement("div");
        main.className = "list-item-main";
        const title = document.createElement("span");
        title.className = "list-item-title";
        title.textContent = `Лобби ${session.creator_login}`;
        const subtitle = document.createElement("span");
        subtitle.className = "list-item-subtitle";
        subtitle.textContent = `ID: ${session.game_session_id}`;
        main.append(title, subtitle);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-primary";
        button.textContent =
            session.creator_login === state.login ? "Открыть" : "Присоединиться";
        button.addEventListener("click", () => joinLobby(session.game_session_id));

        item.append(main, button);
        dom.lobbiesList.append(item);
    }
}

async function loadLobbies() {
    dom.lobbiesList.replaceChildren();
    const loading = document.createElement("div");
    loading.className = "empty-state";
    loading.textContent = "Загрузка…";
    dom.lobbiesList.append(loading);

    try {
        const data = await api("/game/open_lobby");
        renderLobbies(data.sessions || []);
    } catch (error) {
        dom.lobbiesList.replaceChildren();
        toast(error.message, "error");
    }
}

async function openLobbies() {
    showScreen("lobbies-screen");
    await loadLobbies();
}

async function joinLobby(gameId) {
    try {
        const game = await api(`/game/${gameId}/join`, { method: "POST" });
        openGame(game);
    } catch (error) {
        toast(error.message, "error");
        await loadLobbies();
    }
}

function resultLabel(result) {
    if (result === "WIN") {
        return "Победа";
    }
    if (result === "LOSE") {
        return "Поражение";
    }
    return "Ничья";
}

function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    return date.toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

async function loadHistory() {
    dom.historyList.replaceChildren();
    const loading = document.createElement("div");
    loading.className = "empty-state";
    loading.textContent = "Загрузка…";
    dom.historyList.append(loading);

    try {
        const data = await api("/game/finished");
        const sessions = data.sessions || [];
        dom.historyList.replaceChildren();

        if (!sessions.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "Вы ещё не завершили ни одной игры.";
            dom.historyList.append(empty);
            return;
        }

        for (const session of sessions) {
            const item = document.createElement("div");
            item.className = "list-item";

            const main = document.createElement("div");
            main.className = "list-item-main";
            const title = document.createElement("span");
            title.className = "list-item-title";
            title.textContent = formatDate(session.created_at) || "Завершённая игра";
            const subtitle = document.createElement("span");
            subtitle.className = "list-item-subtitle";
            subtitle.textContent = `ID: ${session.game_session_id}`;
            main.append(title, subtitle);

            const result = document.createElement("span");
            result.className = `result ${session.result.toLowerCase()}`;
            result.textContent = resultLabel(session.result);

            item.append(main, result);
            dom.historyList.append(item);
        }
    } catch (error) {
        dom.historyList.replaceChildren();
        toast(error.message, "error");
    }
}

async function openHistory() {
    showScreen("history-screen");
    await loadHistory();
}

function bindEvents() {
    document
        .getElementById("welcome-login")
        .addEventListener("click", () => openAuth("login"));
    document
        .getElementById("welcome-register")
        .addEventListener("click", () => openAuth("register"));
    document.getElementById("auth-close").addEventListener("click", closeAuth);
    dom.authModal.addEventListener("click", (event) => {
        if (event.target === dom.authModal) {
            closeAuth();
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !dom.authModal.hidden) {
            closeAuth();
        }
    });

    dom.tabLogin.addEventListener("click", () => setAuthMode("login"));
    dom.tabRegister.addEventListener("click", () => setAuthMode("register"));
    dom.authForm.addEventListener("submit", submitAuth);

    document
        .getElementById("play-bot")
        .addEventListener("click", () => startGame("/game/new/pve"));
    document
        .getElementById("create-pvp")
        .addEventListener("click", () => startGame("/game/new/pvp"));
    document.getElementById("open-lobbies").addEventListener("click", openLobbies);
    document.getElementById("open-history").addEventListener("click", openHistory);

    document.getElementById("refresh-lobbies").addEventListener("click", loadLobbies);
    document
        .getElementById("lobbies-back")
        .addEventListener("click", () => showScreen("menu-screen"));
    document
        .getElementById("history-back")
        .addEventListener("click", () => showScreen("menu-screen"));
    document.getElementById("leave-game").addEventListener("click", leaveGame);

    document.getElementById("logo-button").addEventListener("click", () => {
        if (state.token) {
            closeGame();
            showScreen("menu-screen");
        } else {
            showScreen("welcome-screen");
        }
    });

    window.addEventListener("beforeunload", closeSocket);
}

bindEvents();
restoreSession();
