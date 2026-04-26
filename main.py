import asyncio
import random
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from deep_translator import GoogleTranslator
from app.config.bot_config import (
    BOT_TOKEN,
    DEFINITIONS_FILE,
    STATS_FILE,
    STUDENTS_FILE,
    TRANSLATIONS_FILE,
    VOCAB_FILE,
    logger,
)
from app.resources.bot_resources import ADMIN_IDS, SUCCESS_QUOTES, WRITING_TOPICS
from app.storage.json_store import load_json as load_json_file, save_json as save_json_file
from app.services.lexicon_service import (
    build_distractors as build_distractors_service,
    choose_next_word as choose_next_word_service,
    english_similarity_score as english_similarity_score_service,
    get_definition as get_definition_service,
    get_translation as get_translation_service,
    normalize_english_answer as normalize_english_answer_service,
)
from app.storage.sqlite_store import (
    count_active_writings_for_sender,
    count_writing_tasks_for_user,
    create_writing_task,
    expire_due_writings,
    export_runtime_snapshot_to_json,
    get_writing_task,
    initialize_database,
    list_writing_tasks_for_user,
    load_runtime_state,
    migrate_json_to_database,
    refresh_reference_data_from_json,
    review_writing_task,
    sync_dataset,
)
from app.services.user_data import (
    add_words_to_student as add_words_to_student_data,
    get_level_stats as get_level_stats_data,
    get_user_profile as get_user_profile_data,
    get_word_stats as get_word_stats_data,
    is_admin as is_admin_data,
    mark_user_activity as mark_user_activity_data,
    parse_reminder_time as parse_reminder_time_data,
    refresh_daily_goal as refresh_daily_goal_data,
    replace_word_for_student as replace_word_for_student_data,
    remove_words_from_student as remove_words_from_student_data,
    split_words_input as split_words_input_data,
    update_daily_goal_progress as update_daily_goal_progress_data,
    update_play_streak as update_play_streak_data,
)




bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
translator = GoogleTranslator(source="en", target="ru")
student_words = {}
students = {}
stats_store = {}
translation_cache = {}
definition_cache = {}
definition_miss_words = set()
sessions = {}
definition_service_available = True


# Сохраняет JSON как резервную копию и одновременно синхронизирует
# соответствующий набор данных в SQLite, который теперь является
# основным рабочим хранилищем приложения.
def save_json(path, data) -> None:
    save_json_file(path, data)
    sync_dataset(path, data)


# Загружает JSON только как резервный источник для миграции и служебных сценариев.
TEXTS = {
    "ru": {
        "main_menu_greeting": "Привет, {name}.\n\nЭтот бот помогает тренировать слова из твоего списка.",
        "no_vocab": "Для тебя пока нет словаря.",
        "menu_start": "Начать игру",
        "menu_writing": "Writing Exchange",
        "menu_stats": "Статистика",
        "menu_settings": "Настройки",
        "menu_home": "Главное меню",
        "settings_title": "Настройки\n\nЯзык интерфейса: {language}\nУровень английского: {english_level}\nНапоминания: {reminders}\nВремя напоминания: {time}",
        "settings_language": "Язык: {language}",
        "settings_english_level": "Уровень английского: {english_level}",
        "settings_reminders": "Напоминания: {status}",
        "settings_time": "Время: {time}",
        "settings_enter_time": "Отправь время в формате HH:MM, например 18:30.",
        "settings_time_saved": "Время напоминания сохранено: {time}",
        "settings_time_invalid": "Не удалось распознать время. Используй формат HH:MM, например 09:45.",
        "language_ru": "Русский",
        "language_en": "Английский",
        "status_on": "включены",
        "status_off": "выключены",
        "stats_title": "Статистика для {name}\n\nСыграно игр: {games_played}\nПобед: {wins}\nПоражений: {losses}\nОстановлено вручную: {stopped_games}\nЛучший счёт: {best_score}\nПоследний счёт: {last_score}\nВсего правильных ответов: {total_correct}\nВсего ошибок: {total_wrong}\n\nСамые сложные слова:\n{hardest_words}",
        "hardest_none": "Пока данных по сложным словам нет.",
        "hardest_item": "{word} - ошибок: {wrong}, правильных: {correct}, показов: {shown}",
        "score_header": "Счёт: {score}\nСлово {index} из {total}\n\nВыбери перевод слова:\n{word}",
        "stop_game": "Закончить игру",
        "play_again": "Играть заново",
        "game_stopped": "Игра остановлена.",
        "game_finished": "Игра окончена.",
        "game_won": "Ты прошёл весь список слов.",
        "score_now": "Текущий счёт: {score}",
        "stop_manual": "Ты завершил игру вручную.",
        "no_active_game": "Сейчас активной игры нет.",
        "game_not_started": "Сейчас игра не запущена.",
        "game_already_finished": "Игра уже закончилась. Можешь начать новую.",
        "answer_unavailable": "Этот вариант уже недоступен.",
        "answer_correct": "Верно.\n\n{question}",
        "answer_wrong": "Неправильно.\n\nСлово: {word}\nПравильный ответ: {answer}",
        "round_complete": "Все слова в этом раунде закончились.",
        "prepare_failed": "Не удалось подготовить игру.",
        "home_title": "Главное меню, {name}.",
        "reminder_text": "Сегодня ты ещё не заходил в игру. Загляни потренироваться.",
    },
    "en": {
        "main_menu_greeting": "Hi, {name}.\n\nThis bot trains words from your list.\nEach correct answer increases your score, and the first mistake ends the game.",
        "no_vocab": "There is no vocabulary assigned to you yet.",
        "menu_start": "Start game",
        "menu_writing": "Writing Exchange",
        "menu_stats": "Statistics",
        "menu_settings": "Settings",
        "menu_home": "Main menu",
        "settings_title": "Settings\n\nInterface language: {language}\nEnglish level: {english_level}\nReminders: {reminders}\nReminder time: {time}",
        "settings_language": "Language: {language}",
        "settings_english_level": "English level: {english_level}",
        "settings_reminders": "Reminders: {status}",
        "settings_time": "Time: {time}",
        "settings_enter_time": "Send time in HH:MM format, for example 18:30.",
        "settings_time_saved": "Reminder time saved: {time}",
        "settings_time_invalid": "Could not parse the time. Use HH:MM format, for example 09:45.",
        "language_ru": "Russian",
        "language_en": "English",
        "status_on": "enabled",
        "status_off": "disabled",
        "stats_title": "Statistics for {name}\n\nGames played: {games_played}\nWins: {wins}\nLosses: {losses}\nStopped manually: {stopped_games}\nBest score: {best_score}\nLast score: {last_score}\nTotal correct answers: {total_correct}\nTotal mistakes: {total_wrong}\n\nHardest words:\n{hardest_words}",
        "hardest_none": "There is no difficult-word data yet.",
        "hardest_item": "{word} - mistakes: {wrong}, correct: {correct}, shown: {shown}",
        "score_header": "Score: {score}\nWord {index} of {total}\n\nChoose the translation for:\n{word}",
        "stop_game": "End game",
        "play_again": "Play again",
        "game_stopped": "Game stopped.",
        "game_finished": "Game over.",
        "game_won": "You completed the whole word list.",
        "score_now": "Current score: {score}",
        "stop_manual": "You ended the game manually.",
        "no_active_game": "There is no active game right now.",
        "game_not_started": "No game is currently running.",
        "game_already_finished": "The game is already over. You can start a new one.",
        "answer_unavailable": "This answer is no longer available.",
        "answer_correct": "Correct.\n\n{question}",
        "answer_wrong": "Wrong.\n\nWord: {word}\nCorrect answer: {answer}",
        "round_complete": "All words in this round were completed without mistakes.",
        "prepare_failed": "Could not prepare the game.",
        "home_title": "Main menu, {name}.",
        "reminder_text": "You have not opened the game today yet. Come back and practice.",
    },
}

ENGLISH_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
ENGLISH_LEVEL_ORDER = {level: index for index, level in enumerate(ENGLISH_LEVELS)}
WRITING_PAGE_SIZE = 8
MAX_ACTIVE_WRITING_TASKS = 3
MAX_WRITING_TEXT_LENGTH = 5000
MIN_TOPIC_WORDS = 3


def get_user_profile(user_id: str) -> dict:
    profile = get_user_profile_data(stats_store, user_id)
    refresh_daily_goal_data(profile)
    return profile


# �"ос�,ае�, с�,а�,ис�,ик�f по конк�?е�,ном�f слов�f пол�Oзова�,еля или создае�, п�fс�,�f�Z запис�O.
def get_word_stats(user_id: str, word: str) -> dict:
    return get_word_stats_data(stats_store, user_id, word)


# �'озв�?а�?ае�, накопленн�f�Z с�,а�,ис�,ик�f пол�Oзова�,еля по конк�?е�,ном�f �f�?овн�Z иг�?�<.
def get_level_stats(user_id: str, level: int) -> dict:
    return get_level_stats_data(stats_store, user_id, level)


# �'озв�?а�?ае�, �,ек�f�?ий яз�<к ин�,е�?�"ейса пол�Oзова�,еля.
def get_language(user_id: str) -> str:
    return get_user_profile(user_id).get("language", "ru")


# �Yодс�,авляе�, локализованн�<й �,екс�, по кл�Z�?�f и �"о�?ма�,и�?�fе�, его данн�<ми.
def t(user_id: str, key: str, **kwargs) -> str:
    language = get_language(user_id)
    template = TEXTS.get(language, TEXTS["ru"]).get(key, key)
    return template.format(**kwargs)


# �Y�?еоб�?аз�fе�, код яз�<ка в подпис�O для ин�,е�?�"ейса на в�<б�?анном яз�<ке.
def format_language_label(language: str, ui_language: str) -> str:
    key = "language_ru" if language == "ru" else "language_en"
    return TEXTS.get(ui_language, TEXTS["ru"]).get(key, language)


def get_english_level(user_id: str) -> str:
    return get_user_profile(user_id).get("english_level", "")


def format_english_level_label(level: str, ui_language: str) -> str:
    if level in ENGLISH_LEVELS:
        return level
    return "не выбран" if ui_language == "ru" else "not selected"


def display_user_name(user_id: str) -> str:
    return students.get(user_id, f"User {user_id}")


def required_sentences_for_level(level: str) -> int:
    if level in {"A1", "A2"}:
        return 3
    if level in {"B1", "B2"}:
        return 6
    return 10


def count_sentences(text: str) -> int:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    prepared = normalized.replace("!", ".").replace("?", ".")
    parts = [chunk.strip() for chunk in prepared.split(".")]
    return len([part for part in parts if part])


def writing_text_is_english(text: str) -> bool:
    latin_letters = re.findall(r"[A-Za-z]", text)
    cyrillic_letters = re.findall(r"[А-Яа-яЁё]", text)
    return bool(latin_letters) and not bool(cyrillic_letters)


def writing_level_relation(sender_level: str, receiver_level: str, ui_language: str) -> str:
    sender_order = ENGLISH_LEVEL_ORDER.get(sender_level)
    receiver_order = ENGLISH_LEVEL_ORDER.get(receiver_level)
    if sender_order is None or receiver_order is None:
        return ""
    if sender_order == receiver_order:
        return "same level" if ui_language == "en" else "тот же уровень"
    if receiver_order > sender_order:
        return "higher level" if ui_language == "en" else "уровень выше"
    return "lower level" if ui_language == "en" else "уровень ниже"


def writing_candidates(user_id: str) -> list[str]:
    candidates = []
    for candidate_id in sorted(set(student_words.keys()) | set(stats_store.keys()) | set(students.keys())):
        if candidate_id == user_id:
            continue
        profile = get_user_profile(candidate_id)
        if profile.get("english_level") not in ENGLISH_LEVELS:
            continue
        if not profile.get("chat_id"):
            continue
        candidates.append(candidate_id)
    return candidates


def writing_selection_text(user_id: str, page: int = 0) -> str:
    candidates = writing_candidates(user_id)
    if not candidates:
        return (
            "Пока нет доступных собеседников с выбранным уровнем языка."
            if get_language(user_id) == "ru"
            else "There are no available partners with a selected language level yet."
        )
    total_pages = max(1, (len(candidates) + WRITING_PAGE_SIZE - 1) // WRITING_PAGE_SIZE)
    safe_page = max(0, min(page, total_pages - 1))
    if get_language(user_id) == "ru":
        return (
            "Writing Exchange\n\n"
            "Выбери собеседника. В списке показан его уровень языка.\n"
            f"Страница {safe_page + 1} из {total_pages}"
        )
    return (
        "Writing Exchange\n\n"
        "Choose a partner. Their language level is shown in the list.\n"
        f"Page {safe_page + 1} of {total_pages}"
    )


def writing_menu_text(user_id: str) -> str:
    incoming_total = count_writing_tasks_for_user(user_id, "receiver")
    outgoing_total = count_writing_tasks_for_user(user_id, "sender")
    if get_language(user_id) == "ru":
        return (
            "Writing Exchange\n\n"
            "Здесь можно отправлять письменные задания, смотреть входящие и отслеживать свои отправленные тексты.\n\n"
            f"Входящих: {incoming_total}\n"
            f"Исходящих: {outgoing_total}"
        )
    return (
        "Writing Exchange\n\n"
        "Here you can send writing tasks, check incoming ones, and track the texts you have sent.\n\n"
        f"Incoming: {incoming_total}\n"
        f"Outgoing: {outgoing_total}"
    )


def writing_selected_text(user_id: str, target_user_id: str) -> str:
    target_level = get_english_level(target_user_id)
    target_name = display_user_name(target_user_id)
    relation = writing_level_relation(get_english_level(user_id), target_level, get_language(user_id))
    relation_line = f"\n{relation}" if relation else ""
    if get_language(user_id) == "ru":
        return f"Выбран пользователь: {target_name} ({target_level}){relation_line}"
    return f"Selected user: {target_name} ({target_level}){relation_line}"


def writing_task_status_label(status: str, ui_language: str) -> str:
    labels = {
        "sent": "sent" if ui_language == "en" else "отправлено",
        "reviewed": "reviewed" if ui_language == "en" else "проверено",
        "expired": "expired" if ui_language == "en" else "истекло",
    }
    return labels.get(status, status)


def writing_tasks_list_text(user_id: str, role: str, page: int = 0) -> str:
    total = count_writing_tasks_for_user(user_id, role)
    if total == 0:
        if get_language(user_id) == "ru":
            return "Здесь пока нет заданий." if role == "receiver" else "Ты пока ничего не отправлял."
        return "There are no tasks here yet." if role == "receiver" else "You have not sent any tasks yet."

    total_pages = max(1, (total + WRITING_PAGE_SIZE - 1) // WRITING_PAGE_SIZE)
    safe_page = max(0, min(page, total_pages - 1))
    tasks = list_writing_tasks_for_user(user_id, role, limit=WRITING_PAGE_SIZE, offset=safe_page * WRITING_PAGE_SIZE)
    title = (
        "Входящие задания" if role == "receiver" and get_language(user_id) == "ru"
        else "Исходящие задания" if role == "sender" and get_language(user_id) == "ru"
        else "Incoming tasks" if role == "receiver"
        else "Outgoing tasks"
    )
    lines = [title, ""]
    for task in tasks:
        other_user_id = task["sender_id"] if role == "receiver" else task["receiver_id"]
        other_name = display_user_name(other_user_id)
        status_label = writing_task_status_label(task["status"], get_language(user_id))
        if get_language(user_id) == "ru":
            lines.append(f"#{task['id']} • {other_name} • {task['topic']} • {status_label}")
        else:
            lines.append(f"#{task['id']} • {other_name} • {task['topic']} • {status_label}")
    lines.append("")
    lines.append(
        f"Страница {safe_page + 1} из {total_pages}" if get_language(user_id) == "ru" else f"Page {safe_page + 1} of {total_pages}"
    )
    return "\n".join(lines)


def writing_topic_prompt_text(user_id: str, target_user_id: str) -> str:
    target_name = display_user_name(target_user_id)
    if get_language(user_id) == "ru":
        return (
            f"Собеседник: {target_name} ({get_english_level(target_user_id)})\n\n"
            "Теперь отправь тему задания.\n"
            "Минимум 3 слова."
        )
    return (
        f"Partner: {target_name} ({get_english_level(target_user_id)})\n\n"
        "Now send the topic.\n"
        "Use at least 3 words."
    )


def writing_text_prompt_text(user_id: str, topic: str) -> str:
    level = get_english_level(user_id)
    min_sentences = required_sentences_for_level(level)
    if get_language(user_id) == "ru":
        return (
            f"Тема: {topic}\n\n"
            f"Теперь напиши текст на английском.\n"
            f"Для уровня {level} нужно минимум {min_sentences} предложений."
        )
    return (
        f"Topic: {topic}\n\n"
        f"Now write your text in English.\n"
        f"For level {level} you need at least {min_sentences} sentences."
    )


def writing_topic_mode_text(user_id: str, target_user_id: str) -> str:
    target_name = display_user_name(target_user_id)
    if get_language(user_id) == "ru":
        return (
            f"Собеседник: {target_name} ({get_english_level(target_user_id)})\n\n"
            "Теперь выбери, как задать тему."
        )
    return (
        f"Partner: {target_name} ({get_english_level(target_user_id)})\n\n"
        "Now choose how you want to set the topic."
    )


def writing_topic_level_text(user_id: str) -> str:
    if get_language(user_id) == "ru":
        return "Выбери уровень темы."
    return "Choose the topic level."


def writing_topic_band_label(band: str, ui_language: str) -> str:
    mapping = {
        "a": "A1-A2",
        "b": "B1-B2",
        "c": "C1-C2",
    }
    return mapping.get(band, band.upper())


def writing_topic_suggestions_text(user_id: str, band: str, topics: list[str]) -> str:
    band_label = writing_topic_band_label(band, get_language(user_id))
    lines = [f"Topics {band_label}" if get_language(user_id) == "en" else f"Темы {band_label}", ""]
    for index, topic in enumerate(topics, start=1):
        lines.append(f"{index}. {topic}")
    lines.append("")
    lines.append("Выбери тему кнопкой ниже или попроси ещё 5." if get_language(user_id) == "ru" else "Choose a topic below or request 5 more.")
    return "\n".join(lines)


def writing_task_text(viewer_id: str, task: dict) -> str:
    sender_name = display_user_name(task["sender_id"])
    if get_language(viewer_id) == "ru":
        return (
            "Новое письменное задание\n\n"
            f"Отправитель: {sender_name}\n"
            f"Уровень отправителя: {task['sender_level']}\n"
            f"Тема: {task['topic']}\n\n"
            f"{task['text_original']}"
        )
    return (
        "New writing task\n\n"
        f"Sender: {sender_name}\n"
        f"Sender level: {task['sender_level']}\n"
        f"Topic: {task['topic']}\n\n"
        f"{task['text_original']}"
    )


def writing_review_result_text(sender_id: str, task: dict) -> str:
    reviewer_name = display_user_name(task["reviewer_id"]) if task.get("reviewer_id") else "Reviewer"
    if task.get("text_corrected"):
        if get_language(sender_id) == "ru":
            return (
                "Твоё письменное задание проверено.\n\n"
                f"Проверил: {reviewer_name}\n"
                f"Тема: {task['topic']}\n\n"
                f"Оригинальный текст:\n{task['text_original']}\n\n"
                f"Исправленный текст:\n{task['text_corrected']}"
            )
        return (
            "Your writing task has been reviewed.\n\n"
            f"Reviewed by: {reviewer_name}\n"
            f"Topic: {task['topic']}\n\n"
            f"Original text:\n{task['text_original']}\n\n"
            f"Corrected text:\n{task['text_corrected']}"
        )

    comment = task.get("reviewer_comment") or ("Ошибок не найдено." if get_language(sender_id) == "ru" else "No mistakes were found.")
    if get_language(sender_id) == "ru":
        return (
            "Твоё письменное задание проверено.\n\n"
            f"Проверил: {reviewer_name}\n"
            f"Тема: {task['topic']}\n\n"
            f"Текст:\n{task['text_original']}\n\n"
            f"Комментарий:\n{comment}"
        )
    return (
        "Your writing task has been reviewed.\n\n"
        f"Reviewed by: {reviewer_name}\n"
        f"Topic: {task['topic']}\n\n"
        f"Text:\n{task['text_original']}\n\n"
        f"Comment:\n{comment}"
    )


def writing_task_details_text(user_id: str, task: dict) -> str:
    sender_name = display_user_name(task["sender_id"])
    receiver_name = display_user_name(task["receiver_id"])
    status_label = writing_task_status_label(task["status"], get_language(user_id))
    lines = []
    if get_language(user_id) == "ru":
        lines.extend(
            [
                f"Writing task #{task['id']}",
                "",
                f"Отправитель: {sender_name} ({task['sender_level']})",
                f"Получатель: {receiver_name} ({task['receiver_level']})",
                f"Тема: {task['topic']}",
                f"Статус: {status_label}",
                "",
                f"Оригинальный текст:\n{task['text_original']}",
            ]
        )
        if task.get("text_corrected"):
            lines.extend(["", f"Исправленный текст:\n{task['text_corrected']}"])
        if task.get("reviewer_comment"):
            lines.extend(["", f"Комментарий:\n{task['reviewer_comment']}"])
    else:
        lines.extend(
            [
                f"Writing task #{task['id']}",
                "",
                f"Sender: {sender_name} ({task['sender_level']})",
                f"Receiver: {receiver_name} ({task['receiver_level']})",
                f"Topic: {task['topic']}",
                f"Status: {status_label}",
                "",
                f"Original text:\n{task['text_original']}",
            ]
        )
        if task.get("text_corrected"):
            lines.extend(["", f"Corrected text:\n{task['text_corrected']}"])
        if task.get("reviewer_comment"):
            lines.extend(["", f"Comment:\n{task['reviewer_comment']}"])
    return "\n".join(lines)


def generate_writing_topic_choices(band: str, count: int = 5, exclude: list[str] | None = None) -> list[str]:
    topics = WRITING_TOPICS.get(band, [])
    exclude_set = set(exclude or [])
    available = [topic for topic in topics if topic not in exclude_set]
    if len(available) >= count:
        return random.sample(available, count)
    if len(topics) <= count:
        return list(topics)
    return random.sample(topics, count)


# �Y�?ове�?яе�,, ес�,�O ли �f пол�Oзова�,еля п�?ава админис�,�?а�,о�?а.
def is_admin(user_id: str) -> bool:
    return is_admin_data(ADMIN_IDS, user_id)


# �Yоме�?ае�,, �?�,о пол�Oзова�,ел�O сегодня б�<л ак�,ивен, и запоминае�, �?а�, для напоминаний.
def mark_user_activity(user_id: str, chat_id: int | None = None) -> None:
    mark_user_activity_data(stats_store, save_json, STATS_FILE, user_id, chat_id)


# �Y�?ове�?яе�, с�,�?ок�f в�?емени и п�?иводи�, ее к �"о�?ма�,�f HH:MM.
def parse_reminder_time(value: str) -> str | None:
    return parse_reminder_time_data(value)


def update_daily_goal_progress(user_id: str, correct_delta: int = 0) -> None:
    profile = get_user_profile(user_id)
    update_daily_goal_progress_data(profile, correct_delta)


def update_play_streak(user_id: str) -> None:
    profile = get_user_profile(user_id)
    update_play_streak_data(profile)


# �Yе�?еводи�, слово на �?�fсский яз�<к, ке�^и�?�fе�, �?ез�fл�O�,а�, и пов�,о�?но не де�?гае�, пе�?евод�?ик.
def get_translation(word: str) -> str:
    return get_translation_service(word, translation_cache, translator, save_json, TRANSLATIONS_FILE, logger)


# �Yол�f�?ае�, английское оп�?еделение слова из вне�^него слова�?я и ке�^и�?�fе�, �,ол�Oко �fда�?н�<е о�,ве�,�<.
async def get_definition(word: str) -> str | None:
    global definition_service_available
    definition, definition_service_available = await get_definition_service(
        word,
        definition_cache,
        definition_miss_words,
        definition_service_available,
        save_json,
        DEFINITIONS_FILE,
        logger,
    )
    return definition


# Уп�?о�?ае�, �,екс�, для более с�,абил�Oного с�?авнения по�.ожес�,и.
# С�?и�,ае�, об�?�f�Z по�.ожес�,�O слов по английском�f написани�Z и �?�fсском�f пе�?евод�f.
# �'�<с�,�?о о�?енивае�, по�.ожес�,�O �,ол�Oко по английском�f написани�Z для п�?едва�?и�,ел�Oного о�,бо�?а.
def english_similarity_score(target_word: str, candidate_word: str) -> float:
    return english_similarity_score_service(target_word, candidate_word)


# �'�<би�?ае�, след�f�Z�?ее слово с пов�<�^енн�<м �^ансом для �,е�. слов, где б�<ло бол�O�^е о�^ибок.
# �'е�?е�, след�f�Z�?ее слово для �?а�fнда из е�?е не испол�Oзованн�<�. слов.
def choose_next_word(user_id: str, session: dict) -> str | None:
    return choose_next_word_service(user_id, session, get_word_stats)


# �Yодби�?ае�, неп�?авил�Oн�<е ва�?иан�,�< о�,ве�,а: сна�?ала по�.ожие, за�,ем п�?и необ�.одимос�,и добавляе�, более далекий ва�?иан�,.
def build_distractors(user_id: str, target_word: str, correct_answer: str, options_count: int = 4) -> list[str]:
    return build_distractors_service(user_id, target_word, correct_answer, student_words, get_translation, options_count)


# �Y�<�,ае�,ся обнови�,�O �,ек�f�?ее сооб�?ение по кнопке, а если не в�<�.оди�, �?" о�,п�?авляе�, новое.
async def respond_to_callback(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as exc:
        logger.info("Falling back to a new message after edit_text failure: %s", exc)
        await callback.message.answer(text, reply_markup=reply_markup)


# Соби�?ае�, главное мен�Z с кнопками зап�fска иг�?�<, с�,а�,ис�,ики и нас�,�?оек.
def build_main_menu_kb(user_id: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(user_id, "menu_start"), callback_data="menu:start")],
        [InlineKeyboardButton(text=t(user_id, "menu_writing"), callback_data="menu:writing")],
        [InlineKeyboardButton(text=t(user_id, "menu_stats"), callback_data="menu:stats")],
        [InlineKeyboardButton(text=t(user_id, "menu_settings"), callback_data="menu:settings")],
    ]
    if is_admin(user_id):
        admin_label = "Админ-панель" if get_language(user_id) == "ru" else "Admin panel"
        rows.append([InlineKeyboardButton(text=admin_label, callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Соби�?ае�, мен�Z в�<бо�?а дос�,�fпного �f�?овня иг�?�<.
def build_levels_kb(user_id: str) -> InlineKeyboardMarkup:
    rows = []
    unlocked = set(available_levels(user_id))
    labels = {
        1: "Уровень 1: English -> Russian" if get_language(user_id) == "ru" else "Level 1: English -> Russian",
        2: "Уровень 2: Russian -> English" if get_language(user_id) == "ru" else "Level 2: Russian -> English",
        3: "Уровень 3: Type English word" if get_language(user_id) == "ru" else "Level 3: Type English word",
        4: "Уровень 4: Definition -> English" if get_language(user_id) == "ru" else "Level 4: Definition -> English",
    }
    for level in (1, 2, 3, 4):
        if level in unlocked:
            rows.append([InlineKeyboardButton(text=labels[level], callback_data=f"level:{level}")])
        else:
            locked_text = f"{labels[level]} [locked]"
            rows.append([InlineKeyboardButton(text=locked_text, callback_data=f"locked:{level}")])
    rows.append([InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Соби�?ае�, клавиа�,�f�?�f �,ек�f�?его воп�?оса с ва�?иан�,ами о�,ве�,а и кнопкой ос�,ановки иг�?�<.
def build_in_game_kb(user_id: str, options: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=option, callback_data=f"answer:{index}")]
        for index, option in enumerate(options)
    ]
    rows.append([InlineKeyboardButton(text=t(user_id, "stop_game"), callback_data="game:end")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_question_kb(user_id: str, session: dict) -> InlineKeyboardMarkup | None:
    if session["question_type"] == "choice":
        return build_in_game_kb(user_id, session["options"])
    if session["question_type"] == "definition_typing":
        return build_in_game_kb(user_id, [])
    return None


# �Yоказ�<вае�, дейс�,вия после заве�?�^ения иг�?�<: пе�?езап�fск или возв�?а�, в мен�Z.
def build_post_game_kb(user_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(user_id, "play_again"), callback_data="menu:start")],
            [InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")],
        ]
    )


# Фо�?ми�?�fе�, эк�?ан нас�,�?оек с яз�<ком, напоминаниями и в�?еменем �fведомлений.
def build_settings_kb(user_id: str) -> InlineKeyboardMarkup:
    profile = get_user_profile(user_id)
    ui_language = get_language(user_id)
    language_label = format_language_label(profile["language"], ui_language)
    english_level_label = format_english_level_label(profile.get("english_level", ""), ui_language)
    reminders_label = t(user_id, "status_on") if profile["reminders_enabled"] else t(user_id, "status_off")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(user_id, "settings_language", language=language_label), callback_data="settings:language")],
            [InlineKeyboardButton(text=t(user_id, "settings_english_level", english_level=english_level_label), callback_data="settings:english_level")],
            [InlineKeyboardButton(text=t(user_id, "settings_reminders", status=reminders_label), callback_data="settings:reminders")],
            [InlineKeyboardButton(text=t(user_id, "settings_time", time=profile["reminder_time"]), callback_data="settings:time")],
            [InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")],
        ]
    )


def build_english_level_kb(user_id: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=level, callback_data=f"settings:english_level:{level}")] for level in ENGLISH_LEVELS]
    rows.append([InlineKeyboardButton(text=t(user_id, "menu_settings"), callback_data="menu:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Собирает клавиатуру админ-панели с доступными административными действиями.
def build_admin_kb(user_id: str) -> InlineKeyboardMarkup:
    users_label = "Статистика по юзерам" if get_language(user_id) == "ru" else "User statistics"
    find_student_label = "Найти ученика" if get_language(user_id) == "ru" else "Find student"
    add_words_label = "Добавить слова студенту" if get_language(user_id) == "ru" else "Add words to student"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=users_label, callback_data="admin:user_stats")],
            [InlineKeyboardButton(text=find_student_label, callback_data="admin:find_student")],
            [InlineKeyboardButton(text=add_words_label, callback_data="admin:add_words")],
            [InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")],
        ]
    )


# Собирает клавиатуру карточки ученика с быстрыми действиями над словарём.
def build_admin_student_kb(user_id: str, student_id: str) -> InlineKeyboardMarkup:
    if get_language(user_id) == "ru":
        add_label = "Добавить слова"
        remove_label = "Удалить слова"
        edit_label = "Редактировать слово"
        vocab_label = "Открыть словарь"
        search_label = "Найти другого"
        back_label = "К админ-панели"
    else:
        add_label = "Add words"
        remove_label = "Delete words"
        edit_label = "Edit word"
        vocab_label = "Open vocabulary"
        search_label = "Find another"
        back_label = "Back to admin panel"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=add_label, callback_data=f"admin:student_add:{student_id}")],
            [InlineKeyboardButton(text=remove_label, callback_data=f"admin:student_remove:{student_id}")],
            [InlineKeyboardButton(text=edit_label, callback_data=f"admin:student_edit:{student_id}")],
            [InlineKeyboardButton(text=vocab_label, callback_data=f"admin:student_vocab:{student_id}:0")],
            [InlineKeyboardButton(text=search_label, callback_data="admin:find_student")],
            [InlineKeyboardButton(text=back_label, callback_data="menu:admin")],
        ]
    )


# Формирует клавиатуру с найденными учениками, чтобы админ мог открыть нужную карточку.
def build_admin_search_results_kb(user_id: str, candidate_ids: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for candidate_id in candidate_ids[:10]:
        name = students.get(candidate_id, f"User {candidate_id}")
        rows.append([InlineKeyboardButton(text=f"{name} ({candidate_id})", callback_data=f"admin:student:{candidate_id}")])
    rows.append([InlineKeyboardButton(text="К админ-панели" if get_language(user_id) == "ru" else "Back to admin panel", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_vocab_kb(user_id: str, student_id: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    if get_language(user_id) == "ru":
        prev_label = "Назад"
        next_label = "Вперед"
        card_label = "К карточке"
    else:
        prev_label = "Previous"
        next_label = "Next"
        card_label = "Back to card"

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text=prev_label, callback_data=f"admin:student_vocab:{student_id}:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text=next_label, callback_data=f"admin:student_vocab:{student_id}:{page + 1}"))

    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton(text=card_label, callback_data=f"admin:student:{student_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_writing_candidates_kb(user_id: str, page: int = 0) -> InlineKeyboardMarkup:
    candidates = writing_candidates(user_id)
    total_pages = max(1, (len(candidates) + WRITING_PAGE_SIZE - 1) // WRITING_PAGE_SIZE)
    safe_page = max(0, min(page, total_pages - 1))
    start = safe_page * WRITING_PAGE_SIZE
    page_candidates = candidates[start:start + WRITING_PAGE_SIZE]
    rows = []
    for candidate_id in page_candidates:
        candidate_level = get_english_level(candidate_id)
        candidate_name = display_user_name(candidate_id)
        relation = writing_level_relation(get_english_level(user_id), candidate_level, get_language(user_id))
        suffix = f" • {relation}" if relation else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{candidate_name} ({candidate_level}){suffix}",
                    callback_data=f"writing:select:{candidate_id}",
                )
            ]
        )

    nav_row = []
    if safe_page > 0:
        nav_row.append(InlineKeyboardButton(text="Назад" if get_language(user_id) == "ru" else "Previous", callback_data=f"writing:users:{safe_page - 1}"))
    if safe_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Вперед" if get_language(user_id) == "ru" else "Next", callback_data=f"writing:users:{safe_page + 1}"))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="К Writing Exchange" if get_language(user_id) == "ru" else "Back to Writing Exchange", callback_data="menu:writing")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_writing_menu_kb(user_id: str) -> InlineKeyboardMarkup:
    if get_language(user_id) == "ru":
        new_task_label = "Новое задание"
        incoming_label = "Входящие"
        outgoing_label = "Исходящие"
    else:
        new_task_label = "New task"
        incoming_label = "Incoming"
        outgoing_label = "Outgoing"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=new_task_label, callback_data="writing:new")],
            [InlineKeyboardButton(text=incoming_label, callback_data="writing:list:receiver:0")],
            [InlineKeyboardButton(text=outgoing_label, callback_data="writing:list:sender:0")],
            [InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")],
        ]
    )


def build_writing_confirm_kb(user_id: str) -> InlineKeyboardMarkup:
    if get_language(user_id) == "ru":
        confirm_label = "Подтвердить"
        change_label = "Выбрать другого"
    else:
        confirm_label = "Confirm"
        change_label = "Change user"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=confirm_label, callback_data="writing:confirm")],
            [InlineKeyboardButton(text=change_label, callback_data="writing:change")],
            [InlineKeyboardButton(text="К Writing Exchange" if get_language(user_id) == "ru" else "Back to Writing Exchange", callback_data="menu:writing")],
        ]
    )


def build_writing_topic_mode_kb(user_id: str) -> InlineKeyboardMarkup:
    if get_language(user_id) == "ru":
        own_label = "Написать свою тему"
        suggested_label = "Выбрать из предложенных"
    else:
        own_label = "Write my own topic"
        suggested_label = "Choose from suggested topics"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=own_label, callback_data="writing:topic_mode:own")],
            [InlineKeyboardButton(text=suggested_label, callback_data="writing:topic_mode:suggested")],
            [InlineKeyboardButton(text="К Writing Exchange" if get_language(user_id) == "ru" else "Back to Writing Exchange", callback_data="menu:writing")],
        ]
    )


def build_writing_topic_level_kb(user_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="A1-A2", callback_data="writing:topic_level:a")],
            [InlineKeyboardButton(text="B1-B2", callback_data="writing:topic_level:b")],
            [InlineKeyboardButton(text="C1-C2", callback_data="writing:topic_level:c")],
            [InlineKeyboardButton(text="К Writing Exchange" if get_language(user_id) == "ru" else "Back to Writing Exchange", callback_data="menu:writing")],
        ]
    )


def build_writing_topic_suggestions_kb(user_id: str, band: str, topics: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for index, topic in enumerate(topics):
        rows.append([InlineKeyboardButton(text=topic, callback_data=f"writing:topic_pick:{index}")])
    if get_language(user_id) == "ru":
        more_label = "Ещё 5 тем"
        change_level_label = "Сменить уровень темы"
    else:
        more_label = "Show 5 more"
        change_level_label = "Change topic level"
    rows.append([InlineKeyboardButton(text=more_label, callback_data=f"writing:topic_refresh:{band}")])
    rows.append([InlineKeyboardButton(text=change_level_label, callback_data="writing:topic_mode:suggested")])
    rows.append([InlineKeyboardButton(text="К Writing Exchange" if get_language(user_id) == "ru" else "Back to Writing Exchange", callback_data="menu:writing")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_writing_task_kb(user_id: str, task_id: int) -> InlineKeyboardMarkup:
    if get_language(user_id) == "ru":
        correct_label = "Исправить текст"
        no_mistakes_label = "Без ошибок"
    else:
        correct_label = "Correct text"
        no_mistakes_label = "No mistakes"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=correct_label, callback_data=f"writing:correct:{task_id}")],
            [InlineKeyboardButton(text=no_mistakes_label, callback_data=f"writing:no_mistakes:{task_id}")],
            [InlineKeyboardButton(text="К Writing Exchange" if get_language(user_id) == "ru" else "Back to Writing Exchange", callback_data="menu:writing")],
        ]
    )


def build_writing_tasks_list_kb(user_id: str, role: str, page: int = 0) -> InlineKeyboardMarkup:
    total = count_writing_tasks_for_user(user_id, role)
    total_pages = max(1, (total + WRITING_PAGE_SIZE - 1) // WRITING_PAGE_SIZE)
    safe_page = max(0, min(page, total_pages - 1))
    tasks = list_writing_tasks_for_user(user_id, role, limit=WRITING_PAGE_SIZE, offset=safe_page * WRITING_PAGE_SIZE)
    rows = []
    for task in tasks:
        other_user_id = task["sender_id"] if role == "receiver" else task["receiver_id"]
        other_name = display_user_name(other_user_id)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"#{task['id']} {other_name}",
                    callback_data=f"writing:view:{task['id']}",
                )
            ]
        )

    nav_row = []
    if safe_page > 0:
        nav_row.append(InlineKeyboardButton(text="Назад" if get_language(user_id) == "ru" else "Previous", callback_data=f"writing:list:{role}:{safe_page - 1}"))
    if safe_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Вперед" if get_language(user_id) == "ru" else "Next", callback_data=f"writing:list:{role}:{safe_page + 1}"))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="К Writing Exchange" if get_language(user_id) == "ru" else "Back to Writing Exchange", callback_data="menu:writing")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Генерирует текст текущих настроек пользователя.
def settings_text(user_id: str) -> str:
    profile = get_user_profile(user_id)
    ui_language = get_language(user_id)
    language_label = format_language_label(profile["language"], ui_language)
    english_level_label = format_english_level_label(profile.get("english_level", ""), ui_language)
    reminders_label = t(user_id, "status_on") if profile["reminders_enabled"] else t(user_id, "status_off")
    return t(
        user_id,
        "settings_title",
        language=language_label,
        english_level=english_level_label,
        reminders=reminders_label,
        time=profile["reminder_time"],
    )


# Собирает текст с самыми сложными словами пользователя.
def hardest_words_text(user_id: str, limit: int = 5) -> str:
    word_stats = get_user_profile(user_id)["word_stats"]
    scored_words = []

    for word, info in word_stats.items():
        difficulty = info["wrong"] * 3 + max(info["shown"] - info["correct"], 0)
        if difficulty <= 0:
            continue
        scored_words.append((difficulty, word, info))

    if not scored_words:
        return t(user_id, "hardest_none")

    scored_words.sort(reverse=True)
    lines = []
    for _, word, info in scored_words[:limit]:
        lines.append(t(user_id, "hardest_item", word=word, wrong=info["wrong"], correct=info["correct"], shown=info["shown"]))
    return "\n".join(lines)


# Считает процент выученных слов по правилу: слово считается выученным при точности ответов выше 80%.
def learned_words_percent(user_id: str) -> tuple[int, int, int]:
    words = student_words.get(user_id, [])
    total_words = len(words)
    if total_words == 0:
        return 0, 0, 0

    learned_count = 0
    for word in words:
        info = get_word_stats(user_id, word)
        shown = info["shown"]
        if shown == 0:
            continue
        accuracy = info["correct"] / shown
        if accuracy > 0.8:
            learned_count += 1

    percent = int((learned_count / total_words) * 100)
    return percent, learned_count, total_words


# Считает процент правильных ответов по выбранному уровню.
def level_accuracy_percent(user_id: str, level: int) -> int:
    level_stats = get_level_stats(user_id, level)
    total_answers = level_stats["correct_answers"] + level_stats["wrong_answers"]
    if total_answers == 0:
        return 0
    return int((level_stats["correct_answers"] / total_answers) * 100)


def daily_goal_text(user_id: str) -> str:
    profile = get_user_profile(user_id)
    progress = min(profile.get("daily_goal_progress", 0), profile.get("daily_goal_target", 20))
    target = profile.get("daily_goal_target", 20)
    if get_language(user_id) == "ru":
        return f"Дневная цель: {progress}/{target} правильных ответов"
    return f"Daily goal: {progress}/{target} correct answers"


def streak_text(user_id: str) -> str:
    profile = get_user_profile(user_id)
    if get_language(user_id) == "ru":
        return f"Серия дней: {profile.get('current_streak', 0)} | Лучшая серия: {profile.get('best_streak', 0)}"
    return f"Day streak: {profile.get('current_streak', 0)} | Best streak: {profile.get('best_streak', 0)}"


def level_breakdown_text(user_id: str) -> str:
    lines = []
    for level in range(1, 5):
        level_stats = get_level_stats(user_id, level)
        total_answers = level_stats["correct_answers"] + level_stats["wrong_answers"]
        accuracy = level_accuracy_percent(user_id, level)
        if get_language(user_id) == "ru":
            lines.append(
                f"L{level}: игр {level_stats['games_played']}, точность {accuracy}%, "
                f"ответов {total_answers}, лучший счёт {level_stats['best_score']}"
            )
        else:
            lines.append(
                f"L{level}: games {level_stats['games_played']}, accuracy {accuracy}%, "
                f"answers {total_answers}, best score {level_stats['best_score']}"
            )
    return "\n".join(lines)


def weakest_level_text(user_id: str) -> str:
    scored_levels = []
    for level in range(1, 5):
        level_stats = get_level_stats(user_id, level)
        total_answers = level_stats["correct_answers"] + level_stats["wrong_answers"]
        if total_answers == 0:
            continue
        scored_levels.append((level_accuracy_percent(user_id, level), total_answers, level))

    if not scored_levels:
        return "Пока нет данных по уровням." if get_language(user_id) == "ru" else "There is no level data yet."

    accuracy, total_answers, level = min(scored_levels, key=lambda item: (item[0], -item[1], item[2]))
    if get_language(user_id) == "ru":
        return f"Сейчас слабее всего идёт уровень {level}: точность {accuracy}% при {total_answers} ответах."
    return f"Your weakest level right now is level {level}: accuracy {accuracy}% over {total_answers} answers"


# Проверяет, какие уровни сейчас доступны пользователю по правилам открытия.
def available_levels(user_id: str) -> list[int]:
    words_count = len(student_words.get(user_id, []))
    levels = [1]
    if words_count >= 50 and level_accuracy_percent(user_id, 1) >= 30:
        levels.append(2)
    if words_count >= 50 and level_accuracy_percent(user_id, 2) >= 80:
        levels.append(3)
    if words_count > 0:
        levels.append(4)
    return levels


# Собирает полную статистику пользователя для экрана статистики.
def stats_text(user_id: str) -> str:
    profile = get_user_profile(user_id)
    student_name = students.get(user_id, "Student")
    learned_percent, learned_count, total_words = learned_words_percent(user_id)
    if get_language(user_id) == "ru":
        learned_line = f"\nПроцент изучения слов: {learned_percent}% ({learned_count}/{total_words})"
    else:
        learned_line = f"\nLearned words progress: {learned_percent}% ({learned_count}/{total_words})"

    base_text = t(
        user_id,
        "stats_title",
        name=student_name,
        games_played=profile["games_played"],
        wins=profile["wins"],
        losses=profile["losses"],
        stopped_games=profile["stopped_games"],
        best_score=profile["best_score"],
        last_score=profile["last_score"],
        total_correct=profile["total_correct"],
        total_wrong=profile["total_wrong"],
        hardest_words=hardest_words_text(user_id),
    )
    return (
        f"{base_text}{learned_line}\n"
        f"{streak_text(user_id)}\n"
        f"{daily_goal_text(user_id)}\n\n"
        f"{weakest_level_text(user_id)}\n\n"
        f"{level_breakdown_text(user_id)}"
    )


# Формирует текст экрана выбора уровней и условий их открытия.
def levels_text(user_id: str) -> str:
    words_count = len(student_words.get(user_id, []))
    level1 = level_accuracy_percent(user_id, 1)
    level2 = level_accuracy_percent(user_id, 2)
    if get_language(user_id) == "ru":
        return (
            "Выбери уровень игры.\n\n"
            "Уровень 1 доступен сразу.\n"
            f"Уровень 2: нужно минимум 50 слов и 30% правильных ответов в уровне 1. Сейчас: слов {words_count}, точность {level1}%.\n"
            f"Уровень 3: нужно минимум 50 слов и 80% правильных ответов в уровне 2. Сейчас: слов {words_count}, точность {level2}%.\n"
            "Уровень 4: описание слова -> английское слово, доступен сразу."
        )
    return (
        "Choose a game level.\n\n"
        "Level 1 is available immediately.\n"
        f"Level 2: requires at least 50 words and 30% correct answers in level 1. Now: words {words_count}, accuracy {level1}%.\n"
        f"Level 3: requires at least 50 words and 80% correct answers in level 2. Now: words {words_count}, accuracy {level2}%.\n"
        "Level 4: definition -> English word, available immediately."
    )


# Подсказка для админа перед выбором ученика, которому нужно добавить слова.
def admin_student_id_prompt(user_id: str) -> str:
    if get_language(user_id) == "ru":
        return "Введи ID студента, которому нужно добавить слова."
    return "Send the student ID you want to add words to."


# Подсказка для админа перед вводом новых слов.
def admin_words_prompt(user_id: str, student_id: str) -> str:
    if get_language(user_id) == "ru":
        return (
            f"Студент ID: {student_id}\n"
            f"Теперь отправь новые слова.\n\n"
            f"⚠️ Если добавляешь несколько слов за раз, обязательно разделяй их запятой."
        )
    return (
        f"Student ID: {student_id}\n"
        f"Now send the new words.\n\n"
        f"⚠️ If you send multiple words at once, you must separate them with commas."
    )


# Добавляет студенту новые слова без дублей и сохраняет обновлённый словарь на диск.
def add_words_to_student(student_id: str, words: list[str]) -> tuple[int, int]:
    return add_words_to_student_data(student_words, save_json, VOCAB_FILE, student_id, words)


# Разбивает введённый текст на слова по запятым и переводам строки.
def admin_search_prompt(user_id: str) -> str:
    if get_language(user_id) == "ru":
        return "Введи имя ученика или его ID, чтобы открыть карточку."
    return "Send the student name or ID to open the student card."


def admin_remove_words_prompt(user_id: str, student_id: str) -> str:
    if get_language(user_id) == "ru":
        return (
            f"Студент ID: {student_id}\n"
            f"Отправь слова, которые нужно удалить.\n\n"
            f"⚠️ Можно отправлять несколько слов через запятую или с новой строки."
        )
    return (
        f"Student ID: {student_id}\n"
        f"Now send the words you want to delete.\n\n"
        f"⚠️ You can send multiple words separated by commas or new lines."
    )


def admin_edit_word_prompt(user_id: str, student_id: str) -> str:
    if get_language(user_id) == "ru":
        return (
            f"Студент ID: {student_id}\n"
            f"Отправь замену в формате:\n"
            f"старое слово => новое слово"
        )
    return (
        f"Student ID: {student_id}\n"
        f"Send the replacement in this format:\n"
        f"old word => new word"
    )


def remove_words_from_student(student_id: str, words: list[str]) -> tuple[int, int]:
    return remove_words_from_student_data(student_words, save_json, VOCAB_FILE, student_id, words)


def replace_word_for_student(student_id: str, old_word: str, new_word: str) -> tuple[bool, str]:
    return replace_word_for_student_data(student_words, save_json, VOCAB_FILE, student_id, old_word, new_word)


def parse_replace_words_input(text: str) -> tuple[str, str] | None:
    for separator in ("=>", "->", "→"):
        if separator in text:
            old_word, new_word = text.split(separator, maxsplit=1)
            old_word = old_word.strip()
            new_word = new_word.strip()
            if old_word and new_word:
                return old_word, new_word
    return None


def split_words_input(text: str) -> list[str]:
    return split_words_input_data(text)


def find_students(query: str) -> list[str]:
    query = query.strip().casefold()
    if not query:
        return []

    candidate_ids = sorted(set(student_words.keys()) | set(stats_store.keys()) | set(students.keys()))
    direct_matches = []
    fuzzy_matches = []

    for candidate_id in candidate_ids:
        candidate_name = students.get(candidate_id, "").casefold()
        if candidate_id == query:
            direct_matches.append(candidate_id)
            continue
        if query in candidate_id.casefold() or (candidate_name and query in candidate_name):
            fuzzy_matches.append(candidate_id)

    return direct_matches + sorted(
        fuzzy_matches,
        key=lambda candidate_id: (
            students.get(candidate_id, f"User {candidate_id}").casefold(),
            candidate_id,
        ),
    )


def hardest_words_for_target(viewer_id: str, target_user_id: str, limit: int = 5) -> str:
    word_stats = get_user_profile(target_user_id)["word_stats"]
    scored_words = []

    for word, info in word_stats.items():
        difficulty = info["wrong"] * 3 + max(info["shown"] - info["correct"], 0)
        if difficulty <= 0:
            continue
        scored_words.append((difficulty, word, info))

    if not scored_words:
        return "Пока нет накопленных ошибок." if get_language(viewer_id) == "ru" else "There are no accumulated mistakes yet."

    scored_words.sort(reverse=True)
    lines = []
    for _, word, info in scored_words[:limit]:
        if get_language(viewer_id) == "ru":
            lines.append(f"{word} - ошибок: {info['wrong']}, правильных: {info['correct']}, показов: {info['shown']}")
        else:
            lines.append(f"{word} - mistakes: {info['wrong']}, correct: {info['correct']}, shown: {info['shown']}")
    return "\n".join(lines)


def admin_student_card_text(viewer_id: str, target_user_id: str) -> str:
    profile = get_user_profile(target_user_id)
    student_name = students.get(target_user_id, f"User {target_user_id}")
    words = student_words.get(target_user_id, [])
    learned_percent, learned_count, total_words = learned_words_percent(target_user_id)
    level1 = level_accuracy_percent(target_user_id, 1)
    level2 = level_accuracy_percent(target_user_id, 2)
    level3 = level_accuracy_percent(target_user_id, 3)
    level4 = level_accuracy_percent(target_user_id, 4)
    last_seen = profile.get("last_seen_date") or ("никогда" if get_language(viewer_id) == "ru" else "never")
    preview_words = ", ".join(words[:10]) if words else ("словарь пуст" if get_language(viewer_id) == "ru" else "vocabulary is empty")

    if get_language(viewer_id) == "ru":
        return (
            f"Карточка ученика\n\n"
            f"Имя: {student_name}\n"
            f"ID: {target_user_id}\n"
            f"Слов в словаре: {len(words)}\n"
            f"Последний день в игре: {last_seen}\n\n"
            f"Серия дней: {profile.get('current_streak', 0)} | Лучшая серия: {profile.get('best_streak', 0)}\n"
            f"Дневная цель: {min(profile.get('daily_goal_progress', 0), profile.get('daily_goal_target', 20))}/{profile.get('daily_goal_target', 20)}\n\n"
            f"Игры: {profile['games_played']} | Победы: {profile['wins']} | Поражения: {profile['losses']}\n"
            f"Лучший счёт: {profile['best_score']} | Последний счёт: {profile['last_score']}\n"
            f"Всего правильных: {profile['total_correct']} | Всего ошибок: {profile['total_wrong']}\n"
            f"Изучено слов: {learned_percent}% ({learned_count}/{total_words})\n\n"
            f"Точность по уровням: L1 {level1}% | L2 {level2}% | L3 {level3}% | L4 {level4}%\n\n"
            f"Сложные слова:\n{hardest_words_for_target(viewer_id, target_user_id)}\n\n"
            f"Первые слова в словаре:\n{preview_words}"
        )

    return (
        f"Student card\n\n"
        f"Name: {student_name}\n"
        f"ID: {target_user_id}\n"
        f"Words in vocabulary: {len(words)}\n"
        f"Last day in game: {last_seen}\n\n"
        f"Day streak: {profile.get('current_streak', 0)} | Best streak: {profile.get('best_streak', 0)}\n"
        f"Daily goal: {min(profile.get('daily_goal_progress', 0), profile.get('daily_goal_target', 20))}/{profile.get('daily_goal_target', 20)}\n\n"
        f"Games: {profile['games_played']} | Wins: {profile['wins']} | Losses: {profile['losses']}\n"
        f"Best score: {profile['best_score']} | Last score: {profile['last_score']}\n"
        f"Total correct: {profile['total_correct']} | Total mistakes: {profile['total_wrong']}\n"
        f"Learned words: {learned_percent}% ({learned_count}/{total_words})\n\n"
        f"Accuracy by levels: L1 {level1}% | L2 {level2}% | L3 {level3}% | L4 {level4}%\n\n"
        f"Hard words:\n{hardest_words_for_target(viewer_id, target_user_id)}\n\n"
        f"First words in vocabulary:\n{preview_words}"
    )


def admin_student_vocab_text(viewer_id: str, target_user_id: str, page: int, page_size: int = 20) -> tuple[str, int]:
    words = student_words.get(target_user_id, [])
    student_name = students.get(target_user_id, f"User {target_user_id}")

    if not words:
        if get_language(viewer_id) == "ru":
            return f"Словарь ученика {student_name} пока пуст.", 1
        return f"The vocabulary of {student_name} is still empty.", 1

    total_pages = max(1, (len(words) + page_size - 1) // page_size)
    safe_page = max(0, min(page, total_pages - 1))
    start = safe_page * page_size
    end = start + page_size
    page_words = words[start:end]
    numbered_words = [f"{start + index}. {word}" for index, word in enumerate(page_words, start=1)]

    if get_language(viewer_id) == "ru":
        title = (
            f"Словарь ученика {student_name}\n"
            f"ID: {target_user_id}\n"
            f"Страница {safe_page + 1} из {total_pages}\n"
            f"Всего слов: {len(words)}\n\n"
        )
    else:
        title = (
            f"Vocabulary of {student_name}\n"
            f"ID: {target_user_id}\n"
            f"Page {safe_page + 1} of {total_pages}\n"
            f"Total words: {len(words)}\n\n"
        )

    return title + "\n".join(numbered_words), total_pages


# Возвращает причину, по которой выбранный уровень пока заблокирован.
def locked_level_text(user_id: str, level: int) -> str:
    words_count = len(student_words.get(user_id, []))
    if level == 2:
        accuracy = level_accuracy_percent(user_id, 1)
        if get_language(user_id) == "ru":
            return f"Уровень 2 пока закрыт.\nНужно 50 слов и 30% правильных ответов в уровне 1.\nСейчас: слов {words_count}, точность {accuracy}%."
        return f"Level 2 is still locked.\nIt requires 50 words and 30% correct answers in level 1.\nNow: words {words_count}, accuracy {accuracy}%."
    if level == 4:
        if get_language(user_id) == "ru":
            return "Уровень 4 пока недоступен, потому что в словаре нет слов."
        return "Level 4 is unavailable because the vocabulary is empty."
    accuracy = level_accuracy_percent(user_id, 2)
    if get_language(user_id) == "ru":
        return f"Уровень 3 пока закрыт.\nНужно 50 слов и 80% правильных ответов в уровне 2.\nСейчас: слов {words_count}, точность {accuracy}%."
    return f"Level 3 is still locked.\nIt requires 50 words and 80% correct answers in level 2.\nNow: words {words_count}, accuracy {accuracy}%."


# Собирает админскую сводку с прогрессом по каждому пользователю.
def admin_users_stats_text_v2(user_id: str) -> str:
    rows = []
    all_user_ids = sorted(set(student_words.keys()) | set(stats_store.keys()))

    ranked_users = []
    for candidate_id in all_user_ids:
        profile = get_user_profile(candidate_id)
        learned_percent, learned_count, total_words = learned_words_percent(candidate_id)
        ranked_users.append(
            (
                profile["best_score"],
                profile["wins"],
                learned_percent,
                profile["total_correct"],
                -profile["total_wrong"],
                candidate_id,
                learned_count,
                total_words,
            )
        )

    ranked_users.sort(reverse=True)

    for place, (_, _, learned_percent, _, _, candidate_id, learned_count, total_words) in enumerate(ranked_users, start=1):
        profile = get_user_profile(candidate_id)
        name = students.get(candidate_id, f"User {candidate_id}")
        last_seen = profile.get("last_seen_date") or ("никогда" if get_language(user_id) == "ru" else "never")
        if get_language(user_id) == "ru":
            row = (
                f"{place}. {name}\n"
                f"ID: {candidate_id}\n"
                f"Игры: {profile['games_played']} | Побед: {profile['wins']} | "
                f"Ошибок: {profile['total_wrong']} | Лучший счёт: {profile['best_score']}\n"
                f"Серия: {profile.get('current_streak', 0)} | Дневная цель: {min(profile.get('daily_goal_progress', 0), profile.get('daily_goal_target', 20))}/{profile.get('daily_goal_target', 20)}\n"
                f"Изучено слов: {learned_percent}% ({learned_count}/{total_words})\n"
                f"Последний день в игре: {last_seen}"
            )
        else:
            row = (
                f"{place}. {name}\n"
                f"ID: {candidate_id}\n"
                f"Games: {profile['games_played']} | Wins: {profile['wins']} | "
                f"Mistakes: {profile['total_wrong']} | Best score: {profile['best_score']}\n"
                f"Streak: {profile.get('current_streak', 0)} | Daily goal: {min(profile.get('daily_goal_progress', 0), profile.get('daily_goal_target', 20))}/{profile.get('daily_goal_target', 20)}\n"
                f"Learned words: {learned_percent}% ({learned_count}/{total_words})\n"
                f"Last day in game: {last_seen}"
            )
        rows.append(row)

    if not rows:
        return "Пока нет данных по пользователям." if get_language(user_id) == "ru" else "There is no user data yet."

    title = "Сравнительная статистика по всем юзерам" if get_language(user_id) == "ru" else "Comparison statistics for all users"
    return title + "\n\n" + "\n\n".join(rows[:15])


# �'озв�?а�?ае�, �,ек�f�?�f�Z иг�?ов�f�Z сесси�Z пол�Oзова�,еля и создае�, ее п�?и пе�?вом об�?а�?ении.
def ensure_session(user_id: str) -> dict:
    return sessions.setdefault(
        user_id,
        {
            "user_id": user_id,
            "active": False,
            "level": 1,
            "question_type": "choice",
            "score": 0,
            "correct_answers": 0,
            "wrong_answers": 0,
            "asked_words": [],
            "all_words": [],
            "current_word": None,
            "prompt_word": None,
            "current_answer": None,
            "definition_text": None,
            "attempts_left": 0,
            "options": [],
            "awaiting_reminder_time": False,
            "awaiting_admin_student_id": False,
            "awaiting_admin_search_query": False,
            "awaiting_admin_words": False,
            "awaiting_admin_delete_words": False,
            "awaiting_admin_edit_word": False,
            "admin_target_student_id": None,
            "awaiting_writing_topic": False,
            "awaiting_writing_text": False,
            "awaiting_writing_correction": False,
            "awaiting_writing_no_mistakes_comment": False,
            "writing_target_user_id": None,
            "writing_topic": "",
            "writing_task_id": None,
            "writing_topic_band": None,
            "writing_topic_choices": [],
        },
    )


def reset_admin_flow(session: dict) -> None:
    session["awaiting_admin_student_id"] = False
    session["awaiting_admin_search_query"] = False
    session["awaiting_admin_words"] = False
    session["awaiting_admin_delete_words"] = False
    session["awaiting_admin_edit_word"] = False


def reset_writing_flow(session: dict) -> None:
    session["awaiting_writing_topic"] = False
    session["awaiting_writing_text"] = False
    session["awaiting_writing_correction"] = False
    session["awaiting_writing_no_mistakes_comment"] = False
    session["writing_target_user_id"] = None
    session["writing_topic"] = ""
    session["writing_task_id"] = None
    session["writing_topic_band"] = None
    session["writing_topic_choices"] = []


# Со�.�?аняе�, и�,ог �?а�fнда: побед�f, по�?ажение или �?�f�?н�f�Z ос�,ановк�f, а �,акже с�?е�,.
def register_round_result(user_id: str, outcome: str, score: int, level: int, correct_answers: int, wrong_answers: int) -> None:
    profile = get_user_profile(user_id)
    level_stats = get_level_stats(user_id, level)
    update_play_streak(user_id)
    profile["games_played"] += 1
    profile["last_score"] = score
    profile["best_score"] = max(profile["best_score"], score)
    level_stats["games_played"] += 1
    level_stats["best_score"] = max(level_stats["best_score"], score)
    level_stats["correct_answers"] += correct_answers
    level_stats["wrong_answers"] += wrong_answers

    if outcome == "win":
        profile["wins"] += 1
        level_stats["wins"] += 1
    elif outcome == "loss":
        profile["losses"] += 1
        level_stats["losses"] += 1
    elif outcome == "stopped":
        profile["stopped_games"] += 1
        level_stats["stopped_games"] += 1

    save_json(STATS_FILE, stats_store)


# �zбновляе�, с�,а�,ис�,ик�f конк�?е�,ного слова и об�?ий с�?е�,�?ик п�?авил�Oн�<�. или о�^ибо�?н�<�. о�,ве�,ов.
def register_answer(user_id: str, word: str, is_correct: bool) -> None:
    profile = get_user_profile(user_id)
    word_info = get_word_stats(user_id, word)
    word_info["shown"] += 1

    if is_correct:
        word_info["correct"] += 1
        profile["total_correct"] += 1
        update_daily_goal_progress(user_id, 1)
    else:
        word_info["wrong"] += 1
        profile["total_wrong"] += 1

    save_json(STATS_FILE, stats_store)


# Готовит текст вопроса с текущим счётом и номером слова в раунде.
def render_question_text(session: dict) -> str:
    asked = len(session["asked_words"]) + 1
    total = len(session["all_words"])
    prompt_word = session["prompt_word"]
    user_id = session["user_id"]
    if session["question_type"] == "definition_typing":
        if get_language(user_id) == "ru":
            return (
                f"Счёт: {session['score']}\n"
                f"Слово {asked} из {total}\n"
                f"Попыток осталось: {session['attempts_left']}\n\n"
                f"Прочитай описание и напиши английское слово:\n{prompt_word}"
            )
        return (
            f"Score: {session['score']}\n"
            f"Word {asked} of {total}\n"
            f"Attempts left: {session['attempts_left']}\n\n"
            f"Read the definition and type the English word:\n{prompt_word}"
        )
    if session["question_type"] == "typing_translation":
        if get_language(user_id) == "ru":
            return (
                f"Счёт: {session['score']}\n"
                f"Слово {asked} из {total}\n\n"
                f"Напиши английское слово:\n{prompt_word}"
            )
        return (
            f"Score: {session['score']}\n"
            f"Word {asked} of {total}\n\n"
            f"Type the English word:\n{prompt_word}"
        )
    return t(
        user_id,
        "score_header",
        score=session["score"],
        index=asked,
        total=total,
        word=prompt_word,
    )


# Выбирает новое слово, находит правильный перевод и собирает варианты ответа.
async def prepare_question(user_id: str, session: dict) -> bool:
    next_word = choose_next_word(user_id, session)
    if not next_word:
        return False

    level = session["level"]
    prompt_word = next_word
    options = []
    session["definition_text"] = None
    session["attempts_left"] = 0

    if level == 4:
        remaining_words = [word for word in session["all_words"] if word not in set(session["asked_words"])]
        random.shuffle(remaining_words)
        for candidate_word in remaining_words:
            definition = await get_definition(candidate_word)
            if not definition:
                continue
            session["current_word"] = candidate_word
            session["prompt_word"] = definition
            session["current_answer"] = candidate_word
            session["definition_text"] = definition
            session["attempts_left"] = 3
            session["question_type"] = "definition_typing"
            session["options"] = []
            return True
        return False

    if level == 1:
        correct_answer = get_translation(next_word)
        distractors = build_distractors(user_id, next_word, correct_answer)
        options = distractors + [correct_answer]
        random.shuffle(options)
        prompt_word = next_word
        session["question_type"] = "choice"
    elif level == 2:
        correct_answer = next_word
        prompt_word = get_translation(next_word)
        candidate_words = [word for word in student_words.get(user_id, []) if word != next_word]
        ranked = sorted(candidate_words, key=lambda candidate: english_similarity_score(next_word, candidate), reverse=True)
        distractors = ranked[:3]
        while len(distractors) < 3 and len(candidate_words) > len(distractors):
            candidate = random.choice(candidate_words)
            if candidate not in distractors:
                distractors.append(candidate)
        options = distractors + [correct_answer]
        random.shuffle(options)
        session["question_type"] = "choice"
    else:
        correct_answer = next_word
        prompt_word = get_translation(next_word)
        options = []
        session["question_type"] = "typing_translation"

    session["current_word"] = next_word
    session["prompt_word"] = prompt_word
    session["current_answer"] = correct_answer
    session["options"] = options
    return True


# Показывает пользователю разбор ответа со знаками правильного и ошибочного вариантов.
def render_answer_feedback(user_id: str, word: str, options: list[str], selected_answer: str, correct_answer: str) -> str:
    title = f"Слово: {word}" if get_language(user_id) == "ru" else f"Word: {word}"
    lines = [title, ""]
    for option in options:
        if option == correct_answer:
            lines.append(f"✅ {option}")
        elif option == selected_answer:
            lines.append(f"❌ {option}")
        else:
            lines.append(option)
    return "\n".join(lines)


# Нормализует введённое слово: нижний регистр, без знаков препинания и лишних пробелов.
def normalize_english_answer(text: str) -> str:
    return normalize_english_answer_service(text)


# Показывает результат текстового ответа в третьем уровне.
def render_typed_feedback(user_id: str, prompt_word: str, typed_answer: str, correct_answer: str) -> str:
    if get_language(user_id) == "ru":
        return (
            f"Слово: {prompt_word}\n\n"
            f"Твой ответ: {typed_answer}\n"
            f"Правильный ответ: {correct_answer}"
        )
    return (
        f"Word: {prompt_word}\n\n"
        f"Your answer: {typed_answer}\n"
        f"Correct answer: {correct_answer}"
    )


# Возвращает случайную фразу, которая показывается после правильного ответа на вопрос по определению.
def random_success_quote() -> str:
    return random.choice(SUCCESS_QUOTES)


# Показывает результат задания по определению после успешного ответа.
def definition_success_text(user_id: str) -> str:
    prefix = "Правильно.\n\n" if get_language(user_id) == "ru" else "Correct.\n\n"
    return prefix + random_success_quote()


# Показывает правильный ответ, если все попытки в задании по определению закончились.
def definition_failure_text(user_id: str, prompt_word: str, correct_answer: str) -> str:
    if get_language(user_id) == "ru":
        return (
            f"Попытки закончились.\n\n"
            f"Описание:\n{prompt_word}\n\n"
            f"Правильный ответ: {correct_answer}"
        )
    return (
        f"No attempts left.\n\n"
        f"Definition:\n{prompt_word}\n\n"
        f"Correct answer: {correct_answer}"
    )


# Собирает итоговую статистику раунда после прохождения всех слов.
def round_results_text(user_id: str, session: dict) -> str:
    correct = session["correct_answers"]
    wrong = session["wrong_answers"]
    total = correct + wrong
    percent = int((correct / total) * 100) if total else 0
    if get_language(user_id) == "ru":
        return (
            f"Раунд завершён.\n\n"
            f"Правильных ответов: {correct}\n"
            f"Неправильных ответов: {wrong}\n"
            f"Процент правильных ответов: {percent}%"
        )
    return (
        f"Round completed.\n\n"
        f"Correct answers: {correct}\n"
        f"Wrong answers: {wrong}\n"
        f"Correct answer rate: {percent}%"
    )


# �z�,п�?авляе�, пол�Oзова�,ел�Z главное мен�Z на в�<б�?анном яз�<ке.
async def send_main_menu(message: Message, user_id: str) -> None:
    if user_id not in student_words or not student_words[user_id]:
        await message.answer(t(user_id, "no_vocab"))
        return

    student_name = students.get(user_id, "Student")
    await message.answer(
        t(user_id, "main_menu_greeting", name=student_name),
        reply_markup=build_main_menu_kb(user_id),
    )


# �-ап�fскае�, нов�<й �?а�fнд: сб�?ас�<вае�, сесси�Z, в�<би�?ае�, пе�?вое слово и показ�<вае�, воп�?ос.
async def start_game(target, user_id: str, level: int) -> None:
    if user_id not in student_words or not student_words[user_id]:
        text = t(user_id, "no_vocab")
        if isinstance(target, Message):
            await target.answer(text)
        else:
            await respond_to_callback(target, text)
        return

    session = ensure_session(user_id)
    session["active"] = True
    session["level"] = level
    session["score"] = 0
    session["correct_answers"] = 0
    session["wrong_answers"] = 0
    session["asked_words"] = []
    session["all_words"] = list(student_words[user_id])
    session["user_id"] = user_id
    session["current_word"] = None
    session["prompt_word"] = None
    session["current_answer"] = None
    session["options"] = []
    session["awaiting_reminder_time"] = False

    if not await prepare_question(user_id, session):
        session["active"] = False
        text = t(user_id, "prepare_failed")
        if isinstance(target, Message):
            await target.answer(text)
        else:
            await respond_to_callback(target, text)
        return

    text = render_question_text(session)
    keyboard = build_question_kb(user_id, session)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await respond_to_callback(target, text, reply_markup=keyboard)


# �-аве�?�^ае�, иг�?�f, со�.�?аняе�, �?ез�fл�O�,а�, и показ�<вае�, эк�?ан после окон�?ания �?а�fнда.
async def finish_game(callback: CallbackQuery, user_id: str, reason: str, extra_text: str) -> None:
    session = ensure_session(user_id)
    score = session["score"]
    level = session["level"]
    session["active"] = False

    if reason == "win":
        title = t(user_id, "game_won")
    elif reason == "loss":
        title = t(user_id, "game_finished")
    else:
        title = t(user_id, "game_stopped")

    register_round_result(
        user_id,
        reason,
        score,
        level,
        session["correct_answers"],
        session["wrong_answers"],
    )
    await respond_to_callback(
        callback,
        f"{title}\n\n{extra_text}\n\n{t(user_id, 'score_now', score=score)}",
        reply_markup=build_post_game_kb(user_id),
    )


@dp.message(CommandStart())
# �z�,к�?�<вае�, главное мен�Z по команде /start.
async def main_start_command(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    await send_main_menu(message, user_id)


@dp.message(Command("menu"))
# �z�,к�?�<вае�, главное мен�Z по �,екс�,овой команде /menu.
async def menu_command(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    await send_main_menu(message, user_id)


@dp.message(Command("stats"))
# �Yоказ�<вае�, с�,а�,ис�,ик�f пол�Oзова�,еля по команде /stats.
async def stats_command(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    await message.answer(stats_text(user_id), reply_markup=build_main_menu_kb(user_id))


@dp.message(Command("stop"))
# �zс�,анавливае�, ак�,ивн�f�Z иг�?�f по команде /stop.
async def stop_command(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    session = ensure_session(user_id)
    if not session["active"]:
        await message.answer(t(user_id, "game_not_started"), reply_markup=build_main_menu_kb(user_id))
        return

    session["active"] = False
    register_round_result(
        user_id,
        "stopped",
        session["score"],
        session["level"],
        session["correct_answers"],
        session["wrong_answers"],
    )
    await message.answer(
        f"{t(user_id, 'game_stopped')}\n{t(user_id, 'score_now', score=session['score'])}",
        reply_markup=build_post_game_kb(user_id),
    )


@dp.callback_query(F.data == "menu:start")
# �-ап�fскае�, иг�?�f из главного мен�Z по нажа�,и�Z кнопки.
async def menu_start(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    await respond_to_callback(
        callback,
        levels_text(user_id),
        reply_markup=build_levels_kb(user_id),
    )


@dp.callback_query(F.data.startswith("level:"))
# �-ап�fскае�, в�<б�?анн�<й пол�Oзова�,елем дос�,�fпн�<й �f�?овен�O.
async def level_start(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    level = int(callback.data.split(":", maxsplit=1)[1])
    if level not in available_levels(user_id):
        await respond_to_callback(callback, locked_level_text(user_id, level), reply_markup=build_levels_kb(user_id))
        return
    await start_game(callback, user_id, level)


@dp.callback_query(F.data.startswith("locked:"))
# �Yоказ�<вае�, �fсловия о�,к�?�<�,ия зак�?�<�,ого �f�?овня.
async def locked_level(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    level = int(callback.data.split(":", maxsplit=1)[1])
    await respond_to_callback(callback, locked_level_text(user_id, level), reply_markup=build_levels_kb(user_id))


@dp.callback_query(F.data == "menu:stats")
# �z�,к�?�<вае�, эк�?ан с�,а�,ис�,ики из главного мен�Z.
async def menu_stats(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    await respond_to_callback(
        callback,
        stats_text(user_id),
        reply_markup=build_main_menu_kb(user_id),
    )


@dp.callback_query(F.data == "menu:settings")
# �z�,к�?�<вае�, эк�?ан нас�,�?оек из главного мен�Z.
async def menu_settings(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    await respond_to_callback(
        callback,
        settings_text(user_id),
        reply_markup=build_settings_kb(user_id),
    )


@dp.callback_query(F.data == "menu:writing")
async def menu_writing_exchange(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    profile = get_user_profile(user_id)
    if profile.get("english_level") not in ENGLISH_LEVELS:
        text = (
            "Сначала выбери уровень английского в Settings → Language Level."
            if get_language(user_id) == "ru"
            else "Please choose your English level in Settings → Language Level first."
        )
        await respond_to_callback(callback, text, reply_markup=build_english_level_kb(user_id))
        return

    session = ensure_session(user_id)
    reset_writing_flow(session)
    await respond_to_callback(
        callback,
        writing_menu_text(user_id),
        reply_markup=build_writing_menu_kb(user_id),
    )


@dp.callback_query(F.data == "writing:new")
async def writing_new_task(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    expire_due_writings()
    if count_active_writings_for_sender(user_id) >= MAX_ACTIVE_WRITING_TASKS:
        text = (
            f"У тебя уже {MAX_ACTIVE_WRITING_TASKS} активных письменных заданий. Дождись проверки хотя бы одного."
            if get_language(user_id) == "ru"
            else f"You already have {MAX_ACTIVE_WRITING_TASKS} active writing tasks. Wait until at least one is reviewed."
        )
        await respond_to_callback(callback, text, reply_markup=build_writing_menu_kb(user_id))
        return
    session = ensure_session(user_id)
    reset_writing_flow(session)
    await respond_to_callback(
        callback,
        writing_selection_text(user_id, 0),
        reply_markup=build_writing_candidates_kb(user_id, 0),
    )


@dp.callback_query(F.data == "settings:english_level")
async def settings_english_level(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    text = "Выбери свой уровень английского." if get_language(user_id) == "ru" else "Choose your English level."
    await respond_to_callback(callback, text, reply_markup=build_english_level_kb(user_id))


@dp.callback_query(F.data.startswith("settings:english_level:"))
async def settings_english_level_set(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    chosen_level = callback.data.rsplit(":", maxsplit=1)[1]
    if chosen_level in ENGLISH_LEVELS:
        profile = get_user_profile(user_id)
        profile["english_level"] = chosen_level
        save_json(STATS_FILE, stats_store)
    await respond_to_callback(callback, settings_text(user_id), reply_markup=build_settings_kb(user_id))


@dp.callback_query(F.data.startswith("writing:users:"))
async def writing_users_page(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    page = int(callback.data.rsplit(":", maxsplit=1)[1])
    await respond_to_callback(
        callback,
        writing_selection_text(user_id, page),
        reply_markup=build_writing_candidates_kb(user_id, page),
    )


@dp.callback_query(F.data.startswith("writing:list:"))
async def writing_list_tasks(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    _, _, role, page_text = callback.data.split(":", maxsplit=3)
    page = int(page_text)
    await respond_to_callback(
        callback,
        writing_tasks_list_text(user_id, role, page),
        reply_markup=build_writing_tasks_list_kb(user_id, role, page),
    )


@dp.callback_query(F.data.startswith("writing:select:"))
async def writing_select_user(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    target_user_id = callback.data.rsplit(":", maxsplit=1)[1]
    session = ensure_session(user_id)
    reset_writing_flow(session)
    session["writing_target_user_id"] = target_user_id
    await respond_to_callback(
        callback,
        writing_selected_text(user_id, target_user_id),
        reply_markup=build_writing_confirm_kb(user_id),
    )


@dp.callback_query(F.data == "writing:change")
async def writing_change_user(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    session = ensure_session(user_id)
    reset_writing_flow(session)
    await respond_to_callback(
        callback,
        writing_selection_text(user_id, 0),
        reply_markup=build_writing_candidates_kb(user_id, 0),
    )


@dp.callback_query(F.data == "writing:confirm")
async def writing_confirm_user(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    session = ensure_session(user_id)
    target_user_id = session.get("writing_target_user_id")
    if not target_user_id:
        await respond_to_callback(
            callback,
            writing_selection_text(user_id, 0),
            reply_markup=build_writing_candidates_kb(user_id, 0),
        )
        return
    await respond_to_callback(
        callback,
        writing_topic_mode_text(user_id, target_user_id),
        reply_markup=build_writing_topic_mode_kb(user_id),
    )


@dp.callback_query(F.data == "writing:topic_mode:own")
async def writing_topic_mode_own(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    session = ensure_session(user_id)
    target_user_id = session.get("writing_target_user_id")
    if not target_user_id:
        await respond_to_callback(callback, writing_menu_text(user_id), reply_markup=build_writing_menu_kb(user_id))
        return
    session["awaiting_writing_topic"] = True
    session["writing_topic_band"] = None
    session["writing_topic_choices"] = []
    await callback.message.answer(writing_topic_prompt_text(user_id, target_user_id))


@dp.callback_query(F.data == "writing:topic_mode:suggested")
async def writing_topic_mode_suggested(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    session = ensure_session(user_id)
    session["awaiting_writing_topic"] = False
    await respond_to_callback(
        callback,
        writing_topic_level_text(user_id),
        reply_markup=build_writing_topic_level_kb(user_id),
    )


@dp.callback_query(F.data.startswith("writing:topic_level:"))
async def writing_topic_level_pick(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    band = callback.data.rsplit(":", maxsplit=1)[1]
    session = ensure_session(user_id)
    choices = generate_writing_topic_choices(band)
    session["writing_topic_band"] = band
    session["writing_topic_choices"] = choices
    await respond_to_callback(
        callback,
        writing_topic_suggestions_text(user_id, band, choices),
        reply_markup=build_writing_topic_suggestions_kb(user_id, band, choices),
    )


@dp.callback_query(F.data.startswith("writing:topic_refresh:"))
async def writing_topic_refresh(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    band = callback.data.rsplit(":", maxsplit=1)[1]
    session = ensure_session(user_id)
    choices = generate_writing_topic_choices(band, exclude=session.get("writing_topic_choices", []))
    session["writing_topic_band"] = band
    session["writing_topic_choices"] = choices
    await respond_to_callback(
        callback,
        writing_topic_suggestions_text(user_id, band, choices),
        reply_markup=build_writing_topic_suggestions_kb(user_id, band, choices),
    )


@dp.callback_query(F.data.startswith("writing:topic_pick:"))
async def writing_topic_pick(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    index = int(callback.data.rsplit(":", maxsplit=1)[1])
    session = ensure_session(user_id)
    choices = session.get("writing_topic_choices", [])
    if index < 0 or index >= len(choices):
        await respond_to_callback(callback, writing_menu_text(user_id), reply_markup=build_writing_menu_kb(user_id))
        return
    topic = choices[index]
    session["writing_topic"] = topic
    session["awaiting_writing_topic"] = False
    session["awaiting_writing_text"] = True
    await callback.message.answer(writing_text_prompt_text(user_id, topic))


@dp.callback_query(F.data.startswith("writing:view:"))
async def writing_view_task(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    task_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    task = get_writing_task(task_id)
    if not task:
        text = "Задание не найдено." if get_language(user_id) == "ru" else "Task not found."
        await respond_to_callback(callback, text, reply_markup=build_writing_menu_kb(user_id))
        return
    if user_id not in {task["sender_id"], task["receiver_id"]}:
        text = "Это не твоё задание." if get_language(user_id) == "ru" else "This is not your task."
        await respond_to_callback(callback, text, reply_markup=build_writing_menu_kb(user_id))
        return
    if task["receiver_id"] == user_id and task["status"] == "sent":
        reply_markup = build_writing_task_kb(user_id, task_id)
    else:
        reply_markup = build_writing_menu_kb(user_id)
    await respond_to_callback(callback, writing_task_details_text(user_id, task), reply_markup=reply_markup)


@dp.callback_query(F.data.startswith("writing:open:"))
async def writing_open_task(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    task_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    task = get_writing_task(task_id)
    if not task:
        text = "Задание не найдено." if get_language(user_id) == "ru" else "Task not found."
        await respond_to_callback(callback, text, reply_markup=build_main_menu_kb(user_id))
        return
    if task["receiver_id"] != user_id:
        text = "Это не твоё задание." if get_language(user_id) == "ru" else "This is not your task."
        await respond_to_callback(callback, text, reply_markup=build_writing_menu_kb(user_id))
        return
    if task["status"] == "expired":
        text = "Срок ответа по этому заданию уже истёк." if get_language(user_id) == "ru" else "This task has already expired."
        await respond_to_callback(callback, text, reply_markup=build_writing_menu_kb(user_id))
        return
    if task["status"] == "reviewed":
        await respond_to_callback(callback, writing_task_details_text(user_id, task), reply_markup=build_writing_menu_kb(user_id))
        return
    await respond_to_callback(callback, writing_task_text(user_id, task), reply_markup=build_writing_task_kb(user_id, task_id))


@dp.callback_query(F.data.startswith("writing:correct:"))
async def writing_correct_task(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    task_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    task = get_writing_task(task_id)
    if not task or task["receiver_id"] != user_id or task["status"] != "sent":
        text = "Это задание уже недоступно." if get_language(user_id) == "ru" else "This task is no longer available."
        await respond_to_callback(callback, text, reply_markup=build_main_menu_kb(user_id))
        return
    session = ensure_session(user_id)
    reset_writing_flow(session)
    session["awaiting_writing_correction"] = True
    session["writing_task_id"] = task_id
    prompt = "Отправь исправленную версию текста полностью." if get_language(user_id) == "ru" else "Send the fully corrected version of the text."
    await callback.message.answer(prompt)


@dp.callback_query(F.data.startswith("writing:no_mistakes:"))
async def writing_no_mistakes_task(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    task_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    task = get_writing_task(task_id)
    if not task or task["receiver_id"] != user_id or task["status"] != "sent":
        text = "Это задание уже недоступно." if get_language(user_id) == "ru" else "This task is no longer available."
        await respond_to_callback(callback, text, reply_markup=build_main_menu_kb(user_id))
        return
    session = ensure_session(user_id)
    reset_writing_flow(session)
    session["awaiting_writing_no_mistakes_comment"] = True
    session["writing_task_id"] = task_id
    prompt = (
        "Отправь комментарий для автора или напиши `-`, чтобы использовать шаблон."
        if get_language(user_id) == "ru"
        else "Send a comment for the author or type `-` to use the default template."
    )
    await callback.message.answer(prompt, parse_mode=None)

@dp.callback_query(F.data == "menu:admin")
# Открывает админ-панель только для администраторов.
async def menu_admin(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    title = "Админ-панель" if get_language(user_id) == "ru" else "Admin panel"
    await respond_to_callback(callback, title, reply_markup=build_admin_kb(user_id))


@dp.callback_query(F.data == "admin:user_stats")
# Показывает администратору сравнительную статистику между всеми пользователями.
async def admin_user_stats(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    await respond_to_callback(
        callback,
        admin_users_stats_text_v2(user_id),
        reply_markup=build_admin_kb(user_id),
    )


@dp.callback_query(F.data == "admin:add_words")
# Запускает для админа сценарий добавления новых слов студенту.
async def admin_add_words(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    session = ensure_session(user_id)
    reset_admin_flow(session)
    session["awaiting_admin_student_id"] = True
    session["admin_target_student_id"] = None
    await callback.message.answer(admin_student_id_prompt(user_id), reply_markup=build_admin_kb(user_id))


@dp.callback_query(F.data == "admin:find_student")
async def admin_find_student(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    session = ensure_session(user_id)
    reset_admin_flow(session)
    session["awaiting_admin_search_query"] = True
    await callback.message.answer(admin_search_prompt(user_id), reply_markup=build_admin_kb(user_id))


@dp.callback_query(F.data.startswith("admin:student:"))
async def admin_student_card(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    student_id = callback.data.rsplit(":", maxsplit=1)[1]
    session = ensure_session(user_id)
    reset_admin_flow(session)
    session["admin_target_student_id"] = student_id
    await respond_to_callback(
        callback,
        admin_student_card_text(user_id, student_id),
        reply_markup=build_admin_student_kb(user_id, student_id),
    )


@dp.callback_query(F.data.startswith("admin:student_vocab:"))
async def admin_student_vocab(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    _, _, student_id, page_text = callback.data.split(":", maxsplit=3)
    page = int(page_text)
    session = ensure_session(user_id)
    reset_admin_flow(session)
    session["admin_target_student_id"] = student_id
    text, total_pages = admin_student_vocab_text(user_id, student_id, page)
    safe_page = max(0, min(page, total_pages - 1))
    await respond_to_callback(
        callback,
        text,
        reply_markup=build_admin_vocab_kb(user_id, student_id, safe_page, total_pages),
    )


@dp.callback_query(F.data.startswith("admin:student_add:"))
async def admin_student_add_words(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    student_id = callback.data.rsplit(":", maxsplit=1)[1]
    session = ensure_session(user_id)
    reset_admin_flow(session)
    session["awaiting_admin_words"] = True
    session["admin_target_student_id"] = student_id
    await callback.message.answer(admin_words_prompt(user_id, student_id), reply_markup=build_admin_student_kb(user_id, student_id))


@dp.callback_query(F.data.startswith("admin:student_remove:"))
async def admin_student_remove_words(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    student_id = callback.data.rsplit(":", maxsplit=1)[1]
    session = ensure_session(user_id)
    reset_admin_flow(session)
    session["awaiting_admin_delete_words"] = True
    session["admin_target_student_id"] = student_id
    await callback.message.answer(admin_remove_words_prompt(user_id, student_id), reply_markup=build_admin_student_kb(user_id, student_id))


@dp.callback_query(F.data.startswith("admin:student_edit:"))
async def admin_student_edit_word(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    if not is_admin(user_id):
        denied = "У тебя нет доступа к админ-панели." if get_language(user_id) == "ru" else "You do not have access to the admin panel."
        await respond_to_callback(callback, denied, reply_markup=build_main_menu_kb(user_id))
        return

    student_id = callback.data.rsplit(":", maxsplit=1)[1]
    session = ensure_session(user_id)
    reset_admin_flow(session)
    session["awaiting_admin_edit_word"] = True
    session["admin_target_student_id"] = student_id
    await callback.message.answer(admin_edit_word_prompt(user_id, student_id), reply_markup=build_admin_student_kb(user_id, student_id))


@dp.callback_query(F.data == "menu:home")
# �'озв�?а�?ае�, пол�Oзова�,еля в главное мен�Z из д�?�fги�. эк�?анов.
async def menu_home(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    student_name = students.get(user_id, "Student")
    await respond_to_callback(
        callback,
        t(user_id, "home_title", name=student_name),
        reply_markup=build_main_menu_kb(user_id),
    )


@dp.callback_query(F.data == "settings:language")
# �Yе�?екл�Z�?ае�, яз�<к ин�,е�?�"ейса межд�f �?�fсским и английским.
async def settings_language(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    profile = get_user_profile(user_id)
    profile["language"] = "en" if profile["language"] == "ru" else "ru"
    mark_user_activity(user_id, callback.message.chat.id)
    save_json(STATS_FILE, stats_store)
    await respond_to_callback(
        callback,
        settings_text(user_id),
        reply_markup=build_settings_kb(user_id),
    )


@dp.callback_query(F.data == "settings:reminders")
# �'кл�Z�?ае�, или в�<кл�Z�?ае�, ежедневн�<е напоминания.
async def settings_reminders(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    profile = get_user_profile(user_id)
    profile["reminders_enabled"] = not profile["reminders_enabled"]
    mark_user_activity(user_id, callback.message.chat.id)
    save_json(STATS_FILE, stats_store)
    await respond_to_callback(
        callback,
        settings_text(user_id),
        reply_markup=build_settings_kb(user_id),
    )


@dp.callback_query(F.data == "settings:time")
# �Yе�?еводи�, бо�,а в �?ежим ожидания в�?емени напоминания о�, пол�Oзова�,еля.
async def settings_time(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    session = ensure_session(user_id)
    session["awaiting_reminder_time"] = True
    await callback.message.answer(t(user_id, "settings_enter_time"))


@dp.callback_query(F.data == "game:end")
# �-аве�?�^ае�, �,ек�f�?�f�Z иг�?�f по кнопке во в�?емя �?а�fнда.
async def end_game(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    session = ensure_session(user_id)
    if not session["active"]:
        await respond_to_callback(
            callback,
            t(user_id, "no_active_game"),
            reply_markup=build_main_menu_kb(user_id),
        )
        return

    await finish_game(callback, user_id, "stopped", t(user_id, "stop_manual"))


@dp.callback_query(F.data.startswith("answer:"))
# �Y�?ове�?яе�, в�<б�?анн�<й ва�?иан�,, обновляе�, с�,а�,ис�,ик�f и либо п�?одолжае�, иг�?�f, либо заве�?�^ае�, ее.
async def answer_handler(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    session = ensure_session(user_id)

    if not session["active"] or session["current_word"] is None:
        await respond_to_callback(
            callback,
            t(user_id, "game_already_finished"),
            reply_markup=build_post_game_kb(user_id),
        )
        return

    selected_index = int(callback.data.split(":", maxsplit=1)[1])
    if selected_index >= len(session["options"]):
        await callback.answer(t(user_id, "answer_unavailable"), show_alert=True)
        return

    selected_answer = session["options"][selected_index]
    current_word = session["current_word"]
    correct_answer = session["current_answer"]

    if selected_answer == correct_answer:
        register_answer(user_id, current_word, True)
        session["score"] += 1
        session["correct_answers"] += 1
        session["asked_words"].append(current_word)

        await respond_to_callback(
            callback,
            render_answer_feedback(user_id, current_word, session["options"], selected_answer, correct_answer),
        )
        await asyncio.sleep(1)

        if not await prepare_question(user_id, session):
            await finish_game(
                callback,
                user_id,
                "win",
                round_results_text(user_id, session),
            )
            return

        await respond_to_callback(
            callback,
            render_question_text(session),
            reply_markup=build_question_kb(user_id, session),
        )
        return

    register_answer(user_id, current_word, False)
    session["wrong_answers"] += 1
    session["asked_words"].append(current_word)
    await respond_to_callback(
        callback,
        render_answer_feedback(user_id, current_word, session["options"], selected_answer, correct_answer),
    )
    await asyncio.sleep(1)

    if not await prepare_question(user_id, session):
        await finish_game(
            callback,
            user_id,
            "win",
            round_results_text(user_id, session),
        )
        return

    await respond_to_callback(
        callback,
        render_question_text(session),
        reply_markup=build_question_kb(user_id, session),
    )


@dp.message(F.text)
# �zб�?аба�,�<вае�, �,екс�,ов�<й ввод пол�Oзова�,еля, когда бо�, жде�, новое в�?емя напоминания.
async def text_input_handler(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    session = ensure_session(user_id)

    if session.get("awaiting_admin_search_query"):
        if not is_admin(user_id):
            reset_admin_flow(session)
            await message.answer("Нет доступа." if get_language(user_id) == "ru" else "Access denied.")
            return

        matches = find_students(message.text)
        if not matches:
            if get_language(user_id) == "ru":
                await message.answer("Никого не нашёл. Попробуй часть имени или точный ID.", reply_markup=build_admin_kb(user_id))
            else:
                await message.answer("No students found. Try a name fragment or the exact ID.", reply_markup=build_admin_kb(user_id))
            return

        reset_admin_flow(session)
        if len(matches) == 1:
            student_id = matches[0]
            session["admin_target_student_id"] = student_id
            await message.answer(
                admin_student_card_text(user_id, student_id),
                reply_markup=build_admin_student_kb(user_id, student_id),
            )
            return

        if get_language(user_id) == "ru":
            await message.answer("Нашёл несколько учеников. Выбери нужного:", reply_markup=build_admin_search_results_kb(user_id, matches))
        else:
            await message.answer("I found several students. Choose the right one:", reply_markup=build_admin_search_results_kb(user_id, matches))
        return

    if session.get("awaiting_admin_student_id"):
        if not is_admin(user_id):
            reset_admin_flow(session)
            await message.answer("Нет доступа." if get_language(user_id) == "ru" else "Access denied.")
            return

        student_id = message.text.strip()
        if not student_id.isdigit():
            if get_language(user_id) == "ru":
                await message.answer("ID студента должен состоять только из цифр.")
            else:
                await message.answer("Student ID must contain digits only.")
            return

        reset_admin_flow(session)
        session["awaiting_admin_words"] = True
        session["admin_target_student_id"] = student_id
        if student_id not in student_words:
            student_words[student_id] = []
            save_json(VOCAB_FILE, student_words)
        await message.answer(admin_words_prompt(user_id, student_id), reply_markup=build_admin_kb(user_id))
        return

    if session.get("awaiting_admin_words"):
        if not is_admin(user_id):
            reset_admin_flow(session)
            session["admin_target_student_id"] = None
            await message.answer("Нет доступа." if get_language(user_id) == "ru" else "Access denied.")
            return

        student_id = session.get("admin_target_student_id")
        words = split_words_input(message.text)
        if not words:
            if get_language(user_id) == "ru":
                await message.answer("Не удалось найти слова. Отправь одно или несколько слов через запятую или с новой строки.")
            else:
                await message.answer("Could not find any words. Send one or more words separated by commas or new lines.")
            return

        added, skipped = add_words_to_student(student_id, words)
        reset_admin_flow(session)
        session["admin_target_student_id"] = None

        if get_language(user_id) == "ru":
            await message.answer(
                f"Готово.\nID студента: {student_id}\nДобавлено слов: {added}\nПропущено дублей: {skipped}",
                reply_markup=build_admin_student_kb(user_id, student_id),
            )
        else:
            await message.answer(
                f"Done.\nStudent ID: {student_id}\nWords added: {added}\nDuplicates skipped: {skipped}",
                reply_markup=build_admin_student_kb(user_id, student_id),
            )
        return

    if session.get("awaiting_admin_delete_words"):
        if not is_admin(user_id):
            reset_admin_flow(session)
            session["admin_target_student_id"] = None
            await message.answer("Нет доступа." if get_language(user_id) == "ru" else "Access denied.")
            return

        student_id = session.get("admin_target_student_id")
        words = split_words_input(message.text)
        if not words:
            if get_language(user_id) == "ru":
                await message.answer("Не удалось найти слова для удаления. Отправь одно или несколько слов через запятую или с новой строки.")
            else:
                await message.answer("Could not find any words to delete. Send one or more words separated by commas or new lines.")
            return

        removed, not_found = remove_words_from_student(student_id, words)
        reset_admin_flow(session)
        session["admin_target_student_id"] = student_id

        if get_language(user_id) == "ru":
            await message.answer(
                f"Готово.\nID студента: {student_id}\nУдалено слов: {removed}\nНе найдено: {not_found}",
                reply_markup=build_admin_student_kb(user_id, student_id),
            )
        else:
            await message.answer(
                f"Done.\nStudent ID: {student_id}\nWords removed: {removed}\nNot found: {not_found}",
                reply_markup=build_admin_student_kb(user_id, student_id),
            )
        return

    if session.get("awaiting_admin_edit_word"):
        if not is_admin(user_id):
            reset_admin_flow(session)
            session["admin_target_student_id"] = None
            await message.answer("Нет доступа." if get_language(user_id) == "ru" else "Access denied.")
            return

        student_id = session.get("admin_target_student_id")
        parsed = parse_replace_words_input(message.text)
        if not parsed:
            if get_language(user_id) == "ru":
                await message.answer("Не удалось распознать замену. Используй формат: старое слово => новое слово.")
            else:
                await message.answer("Could not parse the replacement. Use the format: old word => new word.")
            return

        old_word, new_word = parsed
        replaced, reason = replace_word_for_student(student_id, old_word, new_word)
        reset_admin_flow(session)
        session["admin_target_student_id"] = student_id

        if get_language(user_id) == "ru":
            if replaced:
                text = f"Готово.\nID студента: {student_id}\nЗаменено: {old_word} -> {new_word}"
            elif reason == "old_word_not_found":
                text = f"Не нашёл слово `{old_word}` в словаре ученика."
            elif reason == "new_word_exists":
                text = f"Слово `{new_word}` уже есть в словаре ученика."
            elif reason == "same_word":
                text = "Старое и новое слово совпадают."
            else:
                text = "Не удалось изменить слово."
        else:
            if replaced:
                text = f"Done.\nStudent ID: {student_id}\nReplaced: {old_word} -> {new_word}"
            elif reason == "old_word_not_found":
                text = f"I could not find `{old_word}` in the student's vocabulary."
            elif reason == "new_word_exists":
                text = f"`{new_word}` is already in the student's vocabulary."
            elif reason == "same_word":
                text = "The old and new words are the same."
            else:
                text = "Could not edit the word."

        await message.answer(text, reply_markup=build_admin_student_kb(user_id, student_id), parse_mode=None)
        return

    if session.get("awaiting_writing_topic"):
        topic = " ".join(message.text.strip().split())
        if len([word for word in topic.split(" ") if word]) < MIN_TOPIC_WORDS:
            text = (
                f"Тема слишком короткая. Напиши минимум {MIN_TOPIC_WORDS} слова."
                if get_language(user_id) == "ru"
                else f"The topic is too short. Please use at least {MIN_TOPIC_WORDS} words."
            )
            await message.answer(text)
            return

        session["writing_topic"] = topic
        session["awaiting_writing_topic"] = False
        session["awaiting_writing_text"] = True
        await message.answer(writing_text_prompt_text(user_id, topic))
        return

    if session.get("awaiting_writing_text"):
        target_user_id = session.get("writing_target_user_id")
        topic = session.get("writing_topic", "")
        text_original = message.text.strip()
        level = get_english_level(user_id)
        min_sentences = required_sentences_for_level(level)
        if len(text_original) > MAX_WRITING_TEXT_LENGTH:
            text = (
                "Текст слишком длинный. Сократи его и отправь снова."
                if get_language(user_id) == "ru"
                else "The text is too long. Please shorten it and send it again."
            )
            await message.answer(text)
            return
        if not writing_text_is_english(text_original):
            text = (
                "Письмо должно быть написано на английском языке. Текст с русскими буквами отправить нельзя."
                if get_language(user_id) == "ru"
                else "The writing must be in English. Text with Cyrillic letters cannot be sent."
            )
            await message.answer(text)
            return
        if count_sentences(text_original) < min_sentences:
            text = (
                f"Текст слишком короткий для твоего уровня. Напиши минимум {min_sentences} предложений."
                if get_language(user_id) == "ru"
                else f"Text is too short for your level. Please write at least {min_sentences} sentences."
            )
            await message.answer(text)
            return
        if not target_user_id or target_user_id == user_id:
            reset_writing_flow(session)
            await message.answer(
                "Не удалось определить получателя. Выбери собеседника заново."
                if get_language(user_id) == "ru"
                else "Could not determine the receiver. Please choose a partner again.",
                reply_markup=build_main_menu_kb(user_id),
            )
            return

        target_profile = get_user_profile(target_user_id)
        if target_profile.get("english_level") not in ENGLISH_LEVELS or not target_profile.get("chat_id"):
            reset_writing_flow(session)
            await message.answer(
                "Этот собеседник сейчас недоступен. Выбери другого."
                if get_language(user_id) == "ru"
                else "This partner is unavailable right now. Please choose another one.",
                reply_markup=build_main_menu_kb(user_id),
            )
            return

        task_id = create_writing_task(
            user_id,
            target_user_id,
            level,
            target_profile["english_level"],
            topic,
            text_original,
        )
        task = get_writing_task(task_id)
        reset_writing_flow(session)
        await message.answer(
            "Задание отправлено."
            if get_language(user_id) == "ru"
            else "The task has been sent.",
            reply_markup=build_main_menu_kb(user_id),
        )
        try:
            receiver_text = (
                f"Ты получил новое письменное задание.\n\nУровень отправителя: {task['sender_level']}\nТема: {task['topic']}"
                if get_language(target_user_id) == "ru"
                else f"You received a new writing task.\n\nSender level: {task['sender_level']}\nTopic: {task['topic']}"
            )
            await bot.send_message(
                target_profile["chat_id"],
                receiver_text,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Открыть задание" if get_language(target_user_id) == "ru" else "Open task", callback_data=f"writing:open:{task_id}")]]
                ),
            )
        except Exception as exc:
            logger.warning("Could not notify writing receiver %s: %s", target_user_id, exc)
        return

    if session.get("awaiting_writing_correction"):
        task_id = session.get("writing_task_id")
        task = get_writing_task(task_id) if task_id else None
        if not task or task["receiver_id"] != user_id or task["status"] != "sent":
            reset_writing_flow(session)
            await message.answer(
                "Это задание уже недоступно."
                if get_language(user_id) == "ru"
                else "This task is no longer available.",
                reply_markup=build_main_menu_kb(user_id),
            )
            return

        corrected_text = message.text.strip()
        if not corrected_text:
            await message.answer("Отправь исправленный текст целиком." if get_language(user_id) == "ru" else "Send the full corrected text.")
            return

        review_writing_task(task_id, user_id, corrected_text, "")
        updated_task = get_writing_task(task_id)
        reset_writing_flow(session)
        await message.answer(
            "Исправление отправлено автору."
            if get_language(user_id) == "ru"
            else "The correction has been sent to the author.",
            reply_markup=build_main_menu_kb(user_id),
        )
        sender_profile = get_user_profile(updated_task["sender_id"])
        if sender_profile.get("chat_id"):
            try:
                await bot.send_message(sender_profile["chat_id"], writing_review_result_text(updated_task["sender_id"], updated_task))
            except Exception as exc:
                logger.warning("Could not notify writing sender %s: %s", updated_task["sender_id"], exc)
        return

    if session.get("awaiting_writing_no_mistakes_comment"):
        task_id = session.get("writing_task_id")
        task = get_writing_task(task_id) if task_id else None
        if not task or task["receiver_id"] != user_id or task["status"] != "sent":
            reset_writing_flow(session)
            await message.answer(
                "Это задание уже недоступно."
                if get_language(user_id) == "ru"
                else "This task is no longer available.",
                reply_markup=build_main_menu_kb(user_id),
            )
            return

        raw_comment = message.text.strip()
        if raw_comment == "-" or not raw_comment:
            raw_comment = "Ошибок не найдено." if get_language(task["sender_id"]) == "ru" else "No mistakes were found."

        review_writing_task(task_id, user_id, None, raw_comment)
        updated_task = get_writing_task(task_id)
        reset_writing_flow(session)
        await message.answer(
            "Комментарий отправлен автору."
            if get_language(user_id) == "ru"
            else "The comment has been sent to the author.",
            reply_markup=build_main_menu_kb(user_id),
        )
        sender_profile = get_user_profile(updated_task["sender_id"])
        if sender_profile.get("chat_id"):
            try:
                await bot.send_message(sender_profile["chat_id"], writing_review_result_text(updated_task["sender_id"], updated_task))
            except Exception as exc:
                logger.warning("Could not notify writing sender %s: %s", updated_task["sender_id"], exc)
        return

    if not session.get("awaiting_reminder_time"):
        if not session["active"] or session["current_word"] is None:
            return

        if session["question_type"] not in {"typing_translation", "definition_typing"}:
            return

        typed_answer = normalize_english_answer(message.text.strip())
        correct_answer = normalize_english_answer(session["current_answer"])
        current_word = session["current_word"]
        prompt_word = session["prompt_word"]

        if session["question_type"] == "definition_typing":
            if typed_answer == correct_answer:
                register_answer(user_id, current_word, True)
                session["score"] += 1
                session["correct_answers"] += 1
                session["asked_words"].append(current_word)
                await message.answer(definition_success_text(user_id))
                await asyncio.sleep(1)
            else:
                session["attempts_left"] -= 1
                if session["attempts_left"] > 0:
                    await message.answer(
                        render_question_text(session),
                        reply_markup=build_question_kb(user_id, session),
                    )
                    return
                register_answer(user_id, current_word, False)
                session["wrong_answers"] += 1
                session["asked_words"].append(current_word)
                await message.answer(definition_failure_text(user_id, prompt_word, session["current_answer"]))
                await asyncio.sleep(1)
        else:
            if typed_answer == correct_answer:
                register_answer(user_id, current_word, True)
                session["score"] += 1
                session["correct_answers"] += 1
                session["asked_words"].append(current_word)
                await message.answer(render_typed_feedback(user_id, prompt_word, typed_answer or "-", session["current_answer"]))
                await asyncio.sleep(1)
            else:
                register_answer(user_id, current_word, False)
                session["wrong_answers"] += 1
                session["asked_words"].append(current_word)
                await message.answer(render_typed_feedback(user_id, prompt_word, typed_answer or "-", session["current_answer"]))
                await asyncio.sleep(1)

        if not await prepare_question(user_id, session):
            class TempCallback:
                def __init__(self, msg):
                    self.message = msg
            await finish_game(TempCallback(message), user_id, "win", round_results_text(user_id, session))
            return

        await message.answer(
            render_question_text(session),
            reply_markup=build_question_kb(user_id, session),
        )
        return

    parsed_time = parse_reminder_time(message.text.strip())
    if not parsed_time:
        await message.answer(t(user_id, "settings_time_invalid"))
        return

    profile = get_user_profile(user_id)
    profile["reminder_time"] = parsed_time
    session["awaiting_reminder_time"] = False
    save_json(STATS_FILE, stats_store)
    await message.answer(
        t(user_id, "settings_time_saved", time=parsed_time),
        reply_markup=build_settings_kb(user_id),
    )



async def reminder_loop():
    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        for user_id in list(stats_store.keys()):
            profile = get_user_profile(user_id)
            if not profile.get("reminders_enabled"):
                continue
            if not profile.get("chat_id"):
                continue
            if profile.get("last_seen_date") == today:
                continue
            if profile.get("last_reminder_date") == today:
                continue
            if current_time < profile.get("reminder_time", "18:00"):
                continue

            try:
                await bot.send_message(
                    chat_id=profile["chat_id"],
                    text=t(user_id, "reminder_text"),
                    reply_markup=build_main_menu_kb(user_id),
                )
                profile["last_reminder_date"] = today
                save_json(STATS_FILE, stats_store)
            except Exception as exc:
                logger.warning("Failed to send reminder to %s: %s", user_id, exc)
                continue

        await asyncio.sleep(60)


# �-аг�?�fжае�, данн�<е и зап�fскае�, polling вмес�,е с �"онов�<м �?иклом напоминаний.
async def main():
    global student_words, students, stats_store, translation_cache, definition_cache, definition_service_available

    initialize_database()
    migrate_json_to_database(load_json_file)
    refresh_reference_data_from_json(load_json_file)
    student_words, students, stats_store, translation_cache, definition_cache = load_runtime_state()
    raw_definition_cache = dict(definition_cache)
    definition_cache = {
        word: definition
        for word, definition in raw_definition_cache.items()
        if isinstance(definition, str) and definition.strip()
    }
    if definition_cache != raw_definition_cache:
        save_json(DEFINITIONS_FILE, definition_cache)
    export_runtime_snapshot_to_json(save_json_file)
    definition_service_available = True
    logger.info(
        "Bot startup completed from SQLite. vocab_users=%s students=%s stats_profiles=%s cached_translations=%s cached_definitions=%s",
        len(student_words),
        len(students),
        len(stats_store),
        len(translation_cache),
        len(definition_cache),
    )
    reminder_task = asyncio.create_task(reminder_loop())
    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
