from sqlalchemy import ARRAY, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PlayerDataModel(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    login: Mapped[str] = mapped_column(String(25), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)


class GameSessionDataModel(Base):
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    grid_size: Mapped[int] = mapped_column(Integer, default=3)
    grid_cells: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    player_x_id: Mapped[str] = mapped_column(
        String, ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    player_o_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )

    # SQLAlchemy автоматически за один микрозапрос подтянет и данные игроков,
    # чтобы нам не пришлось делать это вручную.
    player_x: Mapped[PlayerDataModel] = relationship(
        "PlayerDataModel",
        foreign_keys=[player_x_id],
    )
    player_o: Mapped[PlayerDataModel | None] = relationship(
        "PlayerDataModel",
        foreign_keys=[player_o_id],
    )
