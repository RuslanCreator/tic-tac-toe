from datasource.model import GameSessionDataModel
from domain.entities.game_session import GameSession, GameSessionState
from domain.entities.playing_board import PlayingBoard


class GameSessionMapper:
    @staticmethod
    def to_domain(model: GameSessionDataModel) -> GameSession:
        return GameSession.restore(
            id=model.id,
            board=PlayingBoard.from_int_list(model.grid_cells, model.grid_size),
            player_x_id=model.player_x_id,
            player_o_id=model.player_o_id,
            status=GameSessionState(model.status),
        )

    @staticmethod
    def to_data(entity: GameSession) -> GameSessionDataModel:
        return GameSessionDataModel(
            id=entity.id,
            status=entity.status.value,
            grid_size=entity.board.grid_size,
            player_x_id=entity.player_x_id,
            player_o_id=entity.player_o_id,
            grid_cells=entity.board.to_int_list(),
        )

    @staticmethod
    def update_data_model(
        source_entity: GameSession, target_model: GameSessionDataModel
    ) -> None:
        target_model.status = source_entity.status.value
        target_model.player_x_id = source_entity.player_x_id
        target_model.player_o_id = source_entity.player_o_id
        target_model.grid_cells = source_entity.board.to_int_list()
        target_model.grid_size = source_entity.board.grid_size
