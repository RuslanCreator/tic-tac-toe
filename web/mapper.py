from application.read_models import FinishedSessionInfo, WaitingSessionInfo
from domain.entities.game_session import GameSession
from domain.entities.playing_board import CellState
from web.schema import (
    AvailableSessionsResponse,
    FinishedSessionItem,
    FinishedSessionsResponse,
    GameResponse,
    WaitingSessionItem,
)


class WebGameMapper:
    _STR_TO_ENUM = {
        "X": CellState.SIGN_X,
        "O": CellState.SIGN_O,
        "": CellState.EMPTY,
    }

    _ENUM_TO_STR = {
        CellState.SIGN_X: "X",
        CellState.SIGN_O: "O",
        CellState.EMPTY: "",
    }

    @classmethod
    def to_web_response(cls, domain_game_session: GameSession) -> GameResponse:
        flat_board_strs = [
            cls._ENUM_TO_STR[cell] for cell in domain_game_session.board.grid
        ]

        return GameResponse(
            game_session_id=domain_game_session.id,
            status=domain_game_session.status.name,
            status_text=domain_game_session.status_text,
            board=flat_board_strs,
        )

    @classmethod
    def to_available_sessions_response(
        cls, domain_infos: list[WaitingSessionInfo]
    ) -> AvailableSessionsResponse:
        return AvailableSessionsResponse(
            sessions=[
                WaitingSessionItem(
                    game_session_id=info.game_session_id,
                    creator_login=info.creator_login,
                )
                for info in domain_infos
            ]
        )

    @classmethod
    def to_finished_sessions_response(
        cls, infos: list[FinishedSessionInfo]
    ) -> FinishedSessionsResponse:
        return FinishedSessionsResponse(
            sessions=[
                FinishedSessionItem(
                    game_session_id=info.game_session_id,
                    result=info.result,
                    created_at=info.created_at,
                )
                for info in infos
            ]
        )
