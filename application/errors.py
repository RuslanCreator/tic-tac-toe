class AppError(Exception):
    """Базовая ошибка прикладного слоя."""


class ValidationError(AppError):
    """Некорректные входные данные сценария."""


class AuthenticationError(AppError):
    """Игрок не аутентифицирован."""


class ForbiddenError(AppError):
    """У игрока нет прав на действие с ресурсом."""


class NotFoundError(AppError):
    """Запрошенный ресурс не найден."""


class ConflictError(AppError):
    """Действие конфликтует с текущим состоянием ресурса."""
