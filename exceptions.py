class MissingTokenError(Exception):
    """Отсутствует обязательная переменная окружения."""


class APIConnectionError(Exception):
    """Ошибка подключения к API."""


class APIResponseError(Exception):
    """Некорректный ответ API."""


class HomeworkStatusError(Exception):
    """Неизвестный статус домашней работы."""
