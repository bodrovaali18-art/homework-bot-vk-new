import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import vk_api
from dotenv import load_dotenv

from exceptions import (
    APIConnectionError,
    APIResponseError,
    HomeworkStatusError,
)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
VK_TOKEN = os.getenv('VK_TOKEN')
VK_USER_ID = os.getenv('VK_USER_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'VK_TOKEN': VK_TOKEN,
        'VK_USER_ID': VK_USER_ID
    }

    missing_tokens = [
        token_name
        for token_name, token_value in tokens.items()
        if not token_value
    ]

    if missing_tokens:
        logger.critical(
            'Отсутствуют обязательные переменные окружения: %s',
            ', '.join(missing_tokens)
        )
        return False

    return True


def send_message(vk, message):
    """Отправляет сообщение в VK."""
    vk.messages.send(
        user_id=VK_USER_ID,
        message=message,
        random_id=0
    )
    logger.debug('Бот отправил сообщение "%s"', message)


def get_api_answer(timestamp):
    """Делает запрос к API Практикум Домашка."""
    payload = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except requests.RequestException as error:
        logger.error('Ошибка при запросе к API: %s', error)
        raise APIConnectionError(
            f'Эндпоинт {ENDPOINT} недоступен.'
        ) from error

    if response.status_code != HTTPStatus.OK:
        error_message = (
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
        logger.error(error_message)
        raise APIResponseError(error_message)

    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as error:
        logger.error('Не удалось декодировать JSON: %s', error)
        raise APIResponseError(
            'Ответ API не удалось преобразовать в JSON.'
        ) from error


def check_response(response):
    """Проверяет корректность ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём.')

    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ homeworks.')

    if 'current_date' not in response:
        raise KeyError('В ответе API отсутствует ключ current_date.')

    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение homeworks должно быть списком.')

    if not isinstance(response['current_date'], int):
        raise TypeError('Значение current_date должно быть числом.')

    return response['homeworks']


def parse_status(homework):
    """Извлекает статус домашней работы и формирует сообщение."""
    if 'homework_name' not in homework:
        raise KeyError(
            'В ответе API отсутствует ключ homework_name.'
        )

    if 'status' not in homework:
        raise KeyError(
            'В ответе API отсутствует ключ status.'
        )

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        logger.error(
            'Обнаружен неожиданный статус домашней работы: %s',
            status
        )
        raise HomeworkStatusError(
            f'Неизвестный статус домашней работы: {status}'
        )

    verdict = HOMEWORK_VERDICTS[status]

    return (
        'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    if not check_tokens():
        raise SystemExit('Программа остановлена.')

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()

    timestamp = int(time.time())
    error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response['current_date']

            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(vk, message)
            else:
                logger.debug('В ответе API нет новых статусов.')

            error_message = None

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)

            if message != error_message:
                try:
                    send_message(vk, message)
                    error_message = message
                except Exception as send_error:
                    logger.error(
                        'Не удалось отправить сообщение об ошибке '
                        'в VK: %s',
                        send_error
                    )

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
