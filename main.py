import asyncio
import json
import random
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from deep_translator import GoogleTranslator

BASE_DIR = Path(__file__).resolve().parent
VOCAB_FILE = BASE_DIR / "vocabularies.json"
STUDENTS_FILE = BASE_DIR / "students.json"
STATS_FILE = BASE_DIR / "game_stats.json"
TRANSLATIONS_FILE = BASE_DIR / "translation_cache.json"

# test_token заканчивается на l4IRWAd2vU
# main_token заканчивается на NutXo
BOT_TOKEN = "8650502659:AAH6lo6vj5PACtkD0AV9tqdKDAeBG_NutXo"


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
translator = GoogleTranslator(source="en", target="ru")
student_words = {}
students = {}
stats_store = {}
translation_cache = {}
sessions = {}
ADMIN_IDS = {"1383902967", "449856263"}

TEXTS = {
    "ru": {
        "main_menu_greeting": "Привет, {name}.\n\nЭтот бот тренирует слова из твоего списка.\nС каждым правильным ответом счет растет, а первая ошибка завершает игру.",
        "no_vocab": "Для тебя пока нет словаря.",
        "menu_start": "Начать игру",
        "menu_stats": "Статистика",
        "menu_settings": "Настройки",
        "menu_home": "Главное меню",
        "settings_title": "Настройки\n\nЯзык интерфейса: {language}\nНапоминания: {reminders}\nВремя напоминания: {time}",
        "settings_language": "Язык: {language}",
        "settings_reminders": "Напоминания: {status}",
        "settings_time": "Время: {time}",
        "settings_enter_time": "Отправь время в формате HH:MM, например 18:30.",
        "settings_time_saved": "Время напоминания сохранено: {time}",
        "settings_time_invalid": "Не удалось распознать время. Используй формат HH:MM, например 09:45.",
        "language_ru": "Русский",
        "language_en": "Английский",
        "status_on": "включены",
        "status_off": "выключены",
        "stats_title": "Статистика для {name}\n\nСыграно игр: {games_played}\nПобед: {wins}\nПоражений: {losses}\nОстановлено вручную: {stopped_games}\nЛучший счет: {best_score}\nПоследний счет: {last_score}\nВсего правильных ответов: {total_correct}\nВсего ошибок: {total_wrong}\n\nСамые сложные слова:\n{hardest_words}",
        "hardest_none": "Пока данных по сложным словам нет.",
        "hardest_item": "{word} - ошибок: {wrong}, правильных: {correct}, показов: {shown}",
        "score_header": "Счет: {score}\nСлово {index} из {total}\n\nВыбери перевод слова:\n{word}",
        "stop_game": "Закончить игру",
        "play_again": "Играть заново",
        "game_stopped": "Игра остановлена.",
        "game_finished": "Игра окончена.",
        "game_won": "Ты прошел весь список слов.",
        "score_now": "Текущий счет: {score}",
        "stop_manual": "Ты завершил игру вручную.",
        "no_active_game": "Сейчас активной игры нет.",
        "game_not_started": "Сейчас игра не запущена.",
        "game_already_finished": "Игра уже закончилась. Можешь начать новую.",
        "answer_unavailable": "Этот вариант уже недоступен.",
        "answer_correct": "Верно.\n\n{question}",
        "answer_wrong": "Неправильно.\n\nСлово: {word}\nПравильный ответ: {answer}",
        "round_complete": "Все слова в этом раунде закончились без ошибок.",
        "prepare_failed": "Не удалось подготовить игру.",
        "home_title": "Главное меню, {name}.",
        "reminder_text": "Сегодня ты еще не заходил в игру. Загляни потренироваться.",
    },
    "en": {
        "main_menu_greeting": "Hi, {name}.\n\nThis bot trains words from your list.\nEach correct answer increases your score, and the first mistake ends the game.",
        "no_vocab": "There is no vocabulary assigned to you yet.",
        "menu_start": "Start game",
        "menu_stats": "Statistics",
        "menu_settings": "Settings",
        "menu_home": "Main menu",
        "settings_title": "Settings\n\nInterface language: {language}\nReminders: {reminders}\nReminder time: {time}",
        "settings_language": "Language: {language}",
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


@dp.message(Command("legacy_disabled_start"))
# Старый тестовый обработчик оставлен отключенным и не участвует в логике бота.
async def start_command(message: Message):
    await message.answer("Привет")
    return
    await message.answer('Привет')


# Загружает данные из JSON-файла и возвращает значение по умолчанию, если файла нет или он битый.
def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


# Сохраняет словари и статистику в JSON-файл в читаемом виде.
def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


# Возвращает профиль пользователя и при первом обращении создает в нем все нужные поля.
def get_user_profile(user_id: str) -> dict:
    profile = stats_store.setdefault(
        user_id,
        {
            "games_played": 0,
            "wins": 0,
            "losses": 0,
            "stopped_games": 0,
            "best_score": 0,
            "last_score": 0,
            "total_correct": 0,
            "total_wrong": 0,
            "language": "ru",
            "reminders_enabled": False,
            "reminder_time": "18:00",
            "last_seen_date": "",
            "last_reminder_date": "",
            "chat_id": None,
            "level_stats": {},
            "word_stats": {},
        },
    )
    profile.setdefault("word_stats", {})
    profile.setdefault("language", "ru")
    profile.setdefault("reminders_enabled", False)
    profile.setdefault("reminder_time", "18:00")
    profile.setdefault("last_seen_date", "")
    profile.setdefault("last_reminder_date", "")
    profile.setdefault("chat_id", None)
    profile.setdefault("level_stats", {})
    return profile


# Достает статистику по конкретному слову пользователя или создает пустую запись.
def get_word_stats(user_id: str, word: str) -> dict:
    profile = get_user_profile(user_id)
    return profile["word_stats"].setdefault(
        word,
        {
            "shown": 0,
            "correct": 0,
            "wrong": 0,
        },
    )


# Возвращает накопленную статистику пользователя по конкретному уровню игры.
def get_level_stats(user_id: str, level: int) -> dict:
    profile = get_user_profile(user_id)
    key = str(level)
    return profile["level_stats"].setdefault(
        key,
        {
            "games_played": 0,
            "wins": 0,
            "losses": 0,
            "stopped_games": 0,
            "correct_answers": 0,
            "wrong_answers": 0,
            "best_score": 0,
        },
    )


# Возвращает текущий язык интерфейса пользователя.
def get_language(user_id: str) -> str:
    return get_user_profile(user_id).get("language", "ru")


# Подставляет локализованный текст по ключу и форматирует его данными.
def t(user_id: str, key: str, **kwargs) -> str:
    language = get_language(user_id)
    template = TEXTS.get(language, TEXTS["ru"]).get(key, key)
    return template.format(**kwargs)


# Преобразует код языка в подпись для интерфейса на выбранном языке.
def format_language_label(language: str, ui_language: str) -> str:
    key = "language_ru" if language == "ru" else "language_en"
    return TEXTS.get(ui_language, TEXTS["ru"]).get(key, language)


# Проверяет, есть ли у пользователя права администратора.
def is_admin(user_id: str) -> bool:
    return user_id in ADMIN_IDS


# Помечает, что пользователь сегодня был активен, и запоминает чат для напоминаний.
def mark_user_activity(user_id: str, chat_id: int | None = None) -> None:
    profile = get_user_profile(user_id)
    profile["last_seen_date"] = datetime.now().strftime("%Y-%m-%d")
    if chat_id is not None:
        profile["chat_id"] = chat_id
    save_json(STATS_FILE, stats_store)


# Проверяет строку времени и приводит ее к формату HH:MM.
def parse_reminder_time(value: str) -> str | None:
    if ":" not in value:
        return None
    hour_text, minute_text = value.split(":", maxsplit=1)
    if not (hour_text.isdigit() and minute_text.isdigit()):
        return None
    hour = int(hour_text)
    minute = int(minute_text)
    if hour not in range(24) or minute not in range(60):
        return None
    return f"{hour:02d}:{minute:02d}"


# Переводит слово на русский язык, кеширует результат и повторно не дергает переводчик.
def get_translation(word: str) -> str:
    cached = translation_cache.get(word)
    if cached:
        return cached

    try:
        translated = translator.translate(word)
    except Exception:
        translated = word

    translation_cache[word] = translated
    save_json(TRANSLATIONS_FILE, translation_cache)
    return translated


# Упрощает текст для более стабильного сравнения похожести.
def normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum() or ch.isspace()).strip()


# Считает общую похожесть слов по английскому написанию и русскому переводу.
def similarity_score(target_word: str, candidate_word: str) -> float:
    target_translation = get_translation(target_word)
    candidate_translation = get_translation(candidate_word)

    english_similarity = SequenceMatcher(None, normalize(target_word), normalize(candidate_word)).ratio()
    russian_similarity = SequenceMatcher(
        None,
        normalize(target_translation),
        normalize(candidate_translation),
    ).ratio()
    return max(english_similarity, russian_similarity)


# Быстро оценивает похожесть только по английскому написанию для предварительного отбора.
def english_similarity_score(target_word: str, candidate_word: str) -> float:
    return SequenceMatcher(None, normalize(target_word), normalize(candidate_word)).ratio()


# Выбирает следующее слово с повышенным шансом для тех слов, где было больше ошибок.
def weighted_word_choice(user_id: str, available_words: list[str]) -> str:
    weights = []
    for word in available_words:
        word_stats = get_word_stats(user_id, word)
        weight = 1.0
        weight += word_stats["wrong"] * 4.0
        weight += max(word_stats["shown"] - word_stats["correct"], 0) * 1.5
        if word_stats["shown"] == 0:
            weight += 2.0
        weight -= min(word_stats["correct"], 4) * 0.35
        weights.append(max(weight, 0.25))

    return random.choices(available_words, weights=weights, k=1)[0]


# Берет следующее слово для раунда из еще не использованных слов.
def choose_next_word(user_id: str, session: dict) -> str | None:
    all_words = session["all_words"]
    asked_words = set(session["asked_words"])
    remaining_words = [word for word in all_words if word not in asked_words]
    if not remaining_words:
        return None
    return weighted_word_choice(user_id, remaining_words)


# Подбирает неправильные варианты ответа: сначала похожие, затем при необходимости добавляет более далекий вариант.
def build_distractors(user_id: str, target_word: str, correct_answer: str, options_count: int = 4) -> list[str]:
    user_pool = student_words.get(user_id, [])
    global_pool = []
    for words in student_words.values():
        global_pool.extend(words)

    unique_candidates = []
    seen_words = {target_word}
    for word in user_pool + global_pool:
        if word in seen_words:
            continue
        seen_words.add(word)
        unique_candidates.append(word)

    english_ranked = sorted(
        unique_candidates,
        key=lambda candidate: english_similarity_score(target_word, candidate),
        reverse=True,
    )
    shortlist = english_ranked[:12]
    if len(english_ranked) > 12:
        shortlist.extend(random.sample(english_ranked[12:], k=min(8, len(english_ranked) - 12)))

    ranked = sorted(
        shortlist,
        key=lambda candidate: similarity_score(target_word, candidate),
        reverse=True,
    )

    distractors = []
    used_answers = {correct_answer.casefold()}

    for candidate in ranked:
        translated = get_translation(candidate)
        if translated.casefold() in used_answers:
            continue
        distractors.append(translated)
        used_answers.add(translated.casefold())
        if len(distractors) == max(options_count - 1, 0):
            break

    if len(distractors) >= 2 and len(ranked) > len(distractors):
        for candidate in reversed(ranked):
            translated = get_translation(candidate)
            if translated.casefold() in used_answers:
                continue
            distractors[-1] = translated
            break

    return distractors[: options_count - 1]


# Пытается обновить текущее сообщение по кнопке, а если не выходит — отправляет новое.
async def respond_to_callback(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


# Собирает главное меню с кнопками запуска игры, статистики и настроек.
def build_main_menu_kb(user_id: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(user_id, "menu_start"), callback_data="menu:start")],
        [InlineKeyboardButton(text=t(user_id, "menu_stats"), callback_data="menu:stats")],
        [InlineKeyboardButton(text=t(user_id, "menu_settings"), callback_data="menu:settings")],
    ]
    if is_admin(user_id):
        admin_label = "Админ-панель" if get_language(user_id) == "ru" else "Admin panel"
        rows.append([InlineKeyboardButton(text=admin_label, callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Собирает меню выбора доступного уровня игры.
def build_levels_kb(user_id: str) -> InlineKeyboardMarkup:
    rows = []
    unlocked = set(available_levels(user_id))
    labels = {
        1: "Уровень 1: English -> Russian" if get_language(user_id) == "ru" else "Level 1: English -> Russian",
        2: "Уровень 2: Russian -> English" if get_language(user_id) == "ru" else "Level 2: Russian -> English",
        3: "Уровень 3: Type English word" if get_language(user_id) == "ru" else "Level 3: Type English word",
    }
    for level in (1, 2, 3):
        if level in unlocked:
            rows.append([InlineKeyboardButton(text=labels[level], callback_data=f"level:{level}")])
        else:
            locked_text = f"{labels[level]} [locked]"
            rows.append([InlineKeyboardButton(text=locked_text, callback_data=f"locked:{level}")])
    rows.append([InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Собирает клавиатуру текущего вопроса с вариантами ответа и кнопкой остановки игры.
def build_in_game_kb(user_id: str, options: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=option, callback_data=f"answer:{index}")]
        for index, option in enumerate(options)
    ]
    rows.append([InlineKeyboardButton(text=t(user_id, "stop_game"), callback_data="game:end")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Показывает действия после завершения игры: перезапуск или возврат в меню.
def build_post_game_kb(user_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(user_id, "play_again"), callback_data="menu:start")],
            [InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")],
        ]
    )


# Формирует экран настроек с языком, напоминаниями и временем уведомлений.
def build_settings_kb(user_id: str) -> InlineKeyboardMarkup:
    profile = get_user_profile(user_id)
    ui_language = get_language(user_id)
    language_label = format_language_label(profile["language"], ui_language)
    reminders_label = t(user_id, "status_on") if profile["reminders_enabled"] else t(user_id, "status_off")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(user_id, "settings_language", language=language_label), callback_data="settings:language")],
            [InlineKeyboardButton(text=t(user_id, "settings_reminders", status=reminders_label), callback_data="settings:reminders")],
            [InlineKeyboardButton(text=t(user_id, "settings_time", time=profile["reminder_time"]), callback_data="settings:time")],
            [InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")],
        ]
    )


# Собирает клавиатуру админ-панели с доступными административными действиями.
def build_admin_kb(user_id: str) -> InlineKeyboardMarkup:
    users_label = "Статистика по юзерам" if get_language(user_id) == "ru" else "User statistics"
    add_words_label = "Добавить слова студенту" if get_language(user_id) == "ru" else "Add words to student"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=users_label, callback_data="admin:user_stats")],
            [InlineKeyboardButton(text=add_words_label, callback_data="admin:add_words")],
            [InlineKeyboardButton(text=t(user_id, "menu_home"), callback_data="menu:home")],
        ]
    )


# Генерирует текст текущих настроек пользователя.
def settings_text(user_id: str) -> str:
    profile = get_user_profile(user_id)
    ui_language = get_language(user_id)
    language_label = format_language_label(profile["language"], ui_language)
    reminders_label = t(user_id, "status_on") if profile["reminders_enabled"] else t(user_id, "status_off")
    return t(
        user_id,
        "settings_title",
        language=language_label,
        reminders=reminders_label,
        time=profile["reminder_time"],
    )


# Собирает сравнительную статистику по всем пользователям для админ-панели.
def admin_users_stats_text(user_id: str) -> str:
    rows = []
    all_user_ids = sorted(set(student_words.keys()) | set(stats_store.keys()))

    ranked_users = []
    for candidate_id in all_user_ids:
        profile = get_user_profile(candidate_id)
        ranked_users.append(
            (
                profile["best_score"],
                profile["wins"],
                profile["total_correct"],
                -profile["total_wrong"],
                candidate_id,
            )
        )

    ranked_users.sort(reverse=True)

    for place, (_, _, _, _, candidate_id) in enumerate(ranked_users, start=1):
        profile = get_user_profile(candidate_id)
        name = students.get(candidate_id, f"User {candidate_id}")
        if get_language(user_id) == "ru":
            row = (
                f"{place}. {name}\n"
                f"ID: {candidate_id}\n"
                f"Игр: {profile['games_played']} | Побед: {profile['wins']} | "
                f"Ошибок: {profile['total_wrong']} | Лучший счет: {profile['best_score']}"
            )
        else:
            row = (
                f"{place}. {name}\n"
                f"ID: {candidate_id}\n"
                f"Games: {profile['games_played']} | Wins: {profile['wins']} | "
                f"Mistakes: {profile['total_wrong']} | Best score: {profile['best_score']}"
            )
        rows.append(row)

    if not rows:
        return "Пока нет данных по пользователям." if get_language(user_id) == "ru" else "There is no user data yet."

    title = "Сравнительная статистика по всем юзерам" if get_language(user_id) == "ru" else "Comparison statistics for all users"
    return title + "\n\n" + "\n\n".join(rows[:15])


# Собирает список самых проблемных слов на основе накопленной статистики.
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


# Считает процент правильных ответов по выбранному уровню на основе накопленной статистики.
def level_accuracy_percent(user_id: str, level: int) -> int:
    level_stats = get_level_stats(user_id, level)
    total_answers = level_stats["correct_answers"] + level_stats["wrong_answers"]
    if total_answers == 0:
        return 0
    return int((level_stats["correct_answers"] / total_answers) * 100)


# Проверяет, какие уровни сейчас доступны пользователю по правилам открытия.
def available_levels(user_id: str) -> list[int]:
    words_count = len(student_words.get(user_id, []))
    levels = [1]
    if words_count >= 50 and level_accuracy_percent(user_id, 1) >= 30:
        levels.append(2)
    if words_count >= 50 and level_accuracy_percent(user_id, 2) >= 80:
        levels.append(3)
    return levels


# Собирает полную статистику пользователя для экрана статистики.
def stats_text(user_id: str) -> str:
    profile = get_user_profile(user_id)
    student_name = students.get(user_id, "Student")
    learned_percent, learned_count, total_words = learned_words_percent(user_id)
    learned_line = (
        f"\nПроцент изучения слов: {learned_percent}% ({learned_count}/{total_words})"
        if get_language(user_id) == "ru"
        else f"\nLearned words progress: {learned_percent}% ({learned_count}/{total_words})"
    )
    return t(
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
    ) + learned_line


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
            f"Уровень 3: нужно минимум 50 слов и 80% правильных ответов в уровне 2. Сейчас: слов {words_count}, точность {level2}%."
        )
    return (
        "Choose a game level.\n\n"
        "Level 1 is available immediately.\n"
        f"Level 2: requires at least 50 words and 30% correct answers in level 1. Now: words {words_count}, accuracy {level1}%.\n"
        f"Level 3: requires at least 50 words and 80% correct answers in level 2. Now: words {words_count}, accuracy {level2}%."
    )


# Подсказка для админа перед выбором ученика, которому нужно добавить слова.
def admin_student_id_prompt(user_id: str) -> str:
    if get_language(user_id) == "ru":
        return "Введи ID студента, которому нужно добавить слова."
    return "Send the student ID you want to add words to."


# Подсказка для админа перед вводом новых слов через запятую.
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


# Добавляет студенту новые слова без дубликатов и сохраняет обновленный словарь на диск.
def add_words_to_student(student_id: str, words: list[str]) -> tuple[int, int]:
    existing_words = student_words.setdefault(student_id, [])
    existing_lower = {word.casefold() for word in existing_words}
    added = 0
    skipped = 0
    for word in words:
        if word.casefold() in existing_lower:
            skipped += 1
            continue
        existing_words.append(word)
        existing_lower.add(word.casefold())
        added += 1
    save_json(VOCAB_FILE, student_words)
    return added, skipped


# Возвращает причину, по которой выбранный уровень пока заблокирован.
def locked_level_text(user_id: str, level: int) -> str:
    words_count = len(student_words.get(user_id, []))
    if level == 2:
        accuracy = level_accuracy_percent(user_id, 1)
        if get_language(user_id) == "ru":
            return f"Уровень 2 пока закрыт.\nНужно 50 слов и 30% правильных ответов в уровне 1.\nСейчас: слов {words_count}, точность {accuracy}%."
        return f"Level 2 is still locked.\nIt requires 50 words and 30% correct answers in level 1.\nNow: words {words_count}, accuracy {accuracy}%."
    accuracy = level_accuracy_percent(user_id, 2)
    if get_language(user_id) == "ru":
        return f"Уровень 3 пока закрыт.\nНужно 50 слов и 80% правильных ответов в уровне 2.\nСейчас: слов {words_count}, точность {accuracy}%."
    return f"Level 3 is still locked.\nIt requires 50 words and 80% correct answers in level 2.\nNow: words {words_count}, accuracy {accuracy}%."


# Собирает обновленную админскую сводку с процентом изучения слов по каждому пользователю.
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
                f"Игр: {profile['games_played']} | Побед: {profile['wins']} | "
                f"Ошибок: {profile['total_wrong']} | Лучший счет: {profile['best_score']}\n"
                f"Изучено слов: {learned_percent}% ({learned_count}/{total_words})\n"
                f"Последний день в игре: {last_seen}"
            )
        else:
            row = (
                f"{place}. {name}\n"
                f"ID: {candidate_id}\n"
                f"Games: {profile['games_played']} | Wins: {profile['wins']} | "
                f"Mistakes: {profile['total_wrong']} | Best score: {profile['best_score']}\n"
                f"Learned words: {learned_percent}% ({learned_count}/{total_words})\n"
                f"Last day in game: {last_seen}"
            )
        rows.append(row)

    if not rows:
        return "Пока нет данных по пользователям." if get_language(user_id) == "ru" else "There is no user data yet."

    title = "Сравнительная статистика по всем юзерам" if get_language(user_id) == "ru" else "Comparison statistics for all users"
    return title + "\n\n" + "\n\n".join(rows[:15])


# Возвращает текущую игровую сессию пользователя и создает ее при первом обращении.
def ensure_session(user_id: str) -> dict:
    return sessions.setdefault(
        user_id,
        {
            "user_id": user_id,
            "active": False,
            "level": 1,
            "score": 0,
            "correct_answers": 0,
            "wrong_answers": 0,
            "asked_words": [],
            "all_words": [],
            "current_word": None,
            "current_answer": None,
            "options": [],
            "awaiting_reminder_time": False,
            "awaiting_admin_student_id": False,
            "awaiting_admin_words": False,
            "admin_target_student_id": None,
        },
    )


# Сохраняет итог раунда: победу, поражение или ручную остановку, а также счет.
def register_round_result(user_id: str, outcome: str, score: int, level: int, correct_answers: int, wrong_answers: int) -> None:
    profile = get_user_profile(user_id)
    level_stats = get_level_stats(user_id, level)
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


# Обновляет статистику конкретного слова и общий счетчик правильных или ошибочных ответов.
def register_answer(user_id: str, word: str, is_correct: bool) -> None:
    profile = get_user_profile(user_id)
    word_info = get_word_stats(user_id, word)
    word_info["shown"] += 1

    if is_correct:
        word_info["correct"] += 1
        profile["total_correct"] += 1
    else:
        word_info["wrong"] += 1
        profile["total_wrong"] += 1

    save_json(STATS_FILE, stats_store)


# Готовит текст вопроса с текущим счетом и номером слова в раунде.
def render_question_text(session: dict) -> str:
    asked = len(session["asked_words"]) + 1
    total = len(session["all_words"])
    prompt_word = session["prompt_word"]
    return t(
        session["user_id"],
        "score_header",
        score=session["score"],
        index=asked,
        total=total,
        word=prompt_word,
    )


# Выбирает новое слово, находит правильный перевод и собирает варианты ответа.
def prepare_question(user_id: str, session: dict) -> bool:
    next_word = choose_next_word(user_id, session)
    if not next_word:
        return False

    level = session["level"]
    prompt_word = next_word
    options = []

    if level == 1:
        correct_answer = get_translation(next_word)
        distractors = build_distractors(user_id, next_word, correct_answer)
        options = distractors + [correct_answer]
        random.shuffle(options)
        prompt_word = next_word
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
    else:
        correct_answer = next_word
        prompt_word = get_translation(next_word)
        options = []

    session["current_word"] = next_word
    session["prompt_word"] = prompt_word
    session["current_answer"] = correct_answer
    session["options"] = options
    return True


# Показывает пользователю разбор ответа со значками правильного и ошибочного вариантов.
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


# Нормализует введенное слово: нижний регистр, без знаков препинания и лишних пробелов.
def normalize_english_answer(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(cleaned.split())


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


# Собирает итоговую статистику раунда после прохождения всех слов.
def round_results_text(user_id: str, session: dict) -> str:
    correct = session["correct_answers"]
    wrong = session["wrong_answers"]
    total = correct + wrong
    percent = int((correct / total) * 100) if total else 0
    if get_language(user_id) == "ru":
        return (
            f"Раунд завершен.\n\n"
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


# Отправляет пользователю главное меню на выбранном языке.
async def send_main_menu(message: Message, user_id: str) -> None:
    if user_id not in student_words or not student_words[user_id]:
        await message.answer(t(user_id, "no_vocab"))
        return

    student_name = students.get(user_id, "Student")
    await message.answer(
        t(user_id, "main_menu_greeting", name=student_name),
        reply_markup=build_main_menu_kb(user_id),
    )


# Запускает новый раунд: сбрасывает сессию, выбирает первое слово и показывает вопрос.
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

    if not prepare_question(user_id, session):
        session["active"] = False
        text = t(user_id, "prepare_failed")
        if isinstance(target, Message):
            await target.answer(text)
        else:
            await respond_to_callback(target, text)
        return

    text = render_question_text(session)
    keyboard = None if level == 3 else build_in_game_kb(user_id, session["options"])
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await respond_to_callback(target, text, reply_markup=keyboard)


# Завершает игру, сохраняет результат и показывает экран после окончания раунда.
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
# Открывает главное меню по команде /start.
async def main_start_command(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    await send_main_menu(message, user_id)


@dp.message(Command("menu"))
# Открывает главное меню по текстовой команде /menu.
async def menu_command(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    await send_main_menu(message, user_id)


@dp.message(Command("stats"))
# Показывает статистику пользователя по команде /stats.
async def stats_command(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    await message.answer(stats_text(user_id), reply_markup=build_main_menu_kb(user_id))


@dp.message(Command("stop"))
# Останавливает активную игру по команде /stop.
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
# Запускает игру из главного меню по нажатию кнопки.
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
# Запускает выбранный пользователем доступный уровень.
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
# Показывает условия открытия закрытого уровня.
async def locked_level(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    level = int(callback.data.split(":", maxsplit=1)[1])
    await respond_to_callback(callback, locked_level_text(user_id, level), reply_markup=build_levels_kb(user_id))


@dp.callback_query(F.data == "menu:stats")
# Открывает экран статистики из главного меню.
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
# Открывает экран настроек из главного меню.
async def menu_settings(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    await respond_to_callback(
        callback,
        settings_text(user_id),
        reply_markup=build_settings_kb(user_id),
    )


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
    session["awaiting_admin_student_id"] = True
    session["awaiting_admin_words"] = False
    session["admin_target_student_id"] = None
    await callback.message.answer(admin_student_id_prompt(user_id), reply_markup=build_admin_kb(user_id))


@dp.callback_query(F.data == "menu:home")
# Возвращает пользователя в главное меню из других экранов.
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
# Переключает язык интерфейса между русским и английским.
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
# Включает или выключает ежедневные напоминания.
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
# Переводит бота в режим ожидания времени напоминания от пользователя.
async def settings_time(callback: CallbackQuery):
    await callback.answer()
    user_id = str(callback.from_user.id)
    mark_user_activity(user_id, callback.message.chat.id)
    session = ensure_session(user_id)
    session["awaiting_reminder_time"] = True
    await callback.message.answer(t(user_id, "settings_enter_time"))


@dp.callback_query(F.data == "game:end")
# Завершает текущую игру по кнопке во время раунда.
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
# Проверяет выбранный вариант, обновляет статистику и либо продолжает игру, либо завершает ее.
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

        if not prepare_question(user_id, session):
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
            reply_markup=build_in_game_kb(user_id, session["options"]) if session["level"] != 3 else None,
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

    if not prepare_question(user_id, session):
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
        reply_markup=build_in_game_kb(user_id, session["options"]) if session["level"] != 3 else None,
    )


@dp.message(F.text)
# Обрабатывает текстовый ввод пользователя, когда бот ждет новое время напоминания.
async def text_input_handler(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    session = ensure_session(user_id)

    if session.get("awaiting_admin_student_id"):
        if not is_admin(user_id):
            session["awaiting_admin_student_id"] = False
            await message.answer("Нет доступа." if get_language(user_id) == "ru" else "Access denied.")
            return

        student_id = message.text.strip()
        if not student_id.isdigit():
            if get_language(user_id) == "ru":
                await message.answer("ID студента должен состоять только из цифр.")
            else:
                await message.answer("Student ID must contain digits only.")
            return

        session["awaiting_admin_student_id"] = False
        session["awaiting_admin_words"] = True
        session["admin_target_student_id"] = student_id
        if student_id not in student_words:
            student_words[student_id] = []
            save_json(VOCAB_FILE, student_words)
        await message.answer(admin_words_prompt(user_id, student_id), reply_markup=build_admin_kb(user_id))
        return

    if session.get("awaiting_admin_words"):
        if not is_admin(user_id):
            session["awaiting_admin_words"] = False
            session["admin_target_student_id"] = None
            await message.answer("Нет доступа." if get_language(user_id) == "ru" else "Access denied.")
            return

        student_id = session.get("admin_target_student_id")
        raw_words = [word.strip() for word in message.text.split(",")]
        words = [word for word in raw_words if word]
        if not words:
            if get_language(user_id) == "ru":
                await message.answer("Не удалось найти слова. Отправь одно или несколько слов через запятую.")
            else:
                await message.answer("Could not find any words. Send one or more words separated by commas.")
            return

        added, skipped = add_words_to_student(student_id, words)
        session["awaiting_admin_words"] = False
        session["admin_target_student_id"] = None

        if get_language(user_id) == "ru":
            await message.answer(
                f"Готово.\nID студента: {student_id}\nДобавлено слов: {added}\nПропущено дублей: {skipped}",
                reply_markup=build_admin_kb(user_id),
            )
        else:
            await message.answer(
                f"Done.\nStudent ID: {student_id}\nWords added: {added}\nDuplicates skipped: {skipped}",
                reply_markup=build_admin_kb(user_id),
            )
        return

    if not session.get("awaiting_reminder_time"):
        if not session["active"] or session.get("level") != 3 or session["current_word"] is None:
            return

        typed_answer = normalize_english_answer(message.text.strip())
        correct_answer = normalize_english_answer(session["current_answer"])
        current_word = session["current_word"]
        prompt_word = session["prompt_word"]

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

        if not prepare_question(user_id, session):
            class TempCallback:
                def __init__(self, msg):
                    self.message = msg
            await finish_game(TempCallback(message), user_id, "win", round_results_text(user_id, session))
            return

        await message.answer(render_question_text(session))
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


# Фоновый цикл раз в минуту проверяет, кому пора отправить ежедневное напоминание.
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
            except Exception:
                continue

        await asyncio.sleep(60)


# Загружает данные и запускает polling вместе с фоновым циклом напоминаний.
async def main():
    global student_words, students, stats_store, translation_cache

    student_words = load_json(VOCAB_FILE, {})
    students = load_json(STUDENTS_FILE, {})
    stats_store = load_json(STATS_FILE, {})
    translation_cache = load_json(TRANSLATIONS_FILE, {})
    reminder_task = asyncio.create_task(reminder_loop())
    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
