from domain.entities.player import Player
from infrastructure.model import PlayerDataModel


class PlayerMapper:
    @staticmethod
    def to_domain(model: PlayerDataModel) -> Player:
        return Player(id=model.id, login=model.login)

    @staticmethod
    def to_data(entity: Player) -> PlayerDataModel:
        return PlayerDataModel(id=entity.id, login=entity.login)
