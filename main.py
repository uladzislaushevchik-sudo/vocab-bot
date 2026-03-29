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


BOT_TOKEN = "8650502659:AAH6lo6vj5PACtkD0AV9tqdKDAeBG_NutXo"


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
translator = GoogleTranslator(source="en", target="ru")
student_words = {}
students = {}
stats_store = {}
translation_cache = {}
sessions = {}

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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(user_id, "menu_start"), callback_data="menu:start")],
            [InlineKeyboardButton(text=t(user_id, "menu_stats"), callback_data="menu:stats")],
            [InlineKeyboardButton(text=t(user_id, "menu_settings"), callback_data="menu:settings")],
        ]
    )


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


# Собирает полную статистику пользователя для экрана статистики.
def stats_text(user_id: str) -> str:
    profile = get_user_profile(user_id)
    student_name = students.get(user_id, "Student")
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
    )


# Возвращает текущую игровую сессию пользователя и создает ее при первом обращении.
def ensure_session(user_id: str) -> dict:
    return sessions.setdefault(
        user_id,
        {
            "user_id": user_id,
            "active": False,
            "score": 0,
            "asked_words": [],
            "all_words": [],
            "current_word": None,
            "current_answer": None,
            "options": [],
            "awaiting_reminder_time": False,
        },
    )


# Сохраняет итог раунда: победу, поражение или ручную остановку, а также счет.
def register_round_result(user_id: str, outcome: str, score: int) -> None:
    profile = get_user_profile(user_id)
    profile["games_played"] += 1
    profile["last_score"] = score
    profile["best_score"] = max(profile["best_score"], score)

    if outcome == "win":
        profile["wins"] += 1
    elif outcome == "loss":
        profile["losses"] += 1
    elif outcome == "stopped":
        profile["stopped_games"] += 1

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
    return t(
        session["user_id"],
        "score_header",
        score=session["score"],
        index=asked,
        total=total,
        word=session["current_word"],
    )


# Выбирает новое слово, находит правильный перевод и собирает варианты ответа.
def prepare_question(user_id: str, session: dict) -> bool:
    next_word = choose_next_word(user_id, session)
    if not next_word:
        return False

    correct_answer = get_translation(next_word)
    distractors = build_distractors(user_id, next_word, correct_answer)
    options = distractors + [correct_answer]
    random.shuffle(options)

    session["current_word"] = next_word
    session["current_answer"] = correct_answer
    session["options"] = options
    return True


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
async def start_game(target, user_id: str) -> None:
    if user_id not in student_words or not student_words[user_id]:
        text = t(user_id, "no_vocab")
        if isinstance(target, Message):
            await target.answer(text)
        else:
            await respond_to_callback(target, text)
        return

    session = ensure_session(user_id)
    session["active"] = True
    session["score"] = 0
    session["asked_words"] = []
    session["all_words"] = list(student_words[user_id])
    session["user_id"] = user_id
    session["current_word"] = None
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
    keyboard = build_in_game_kb(user_id, session["options"])
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await respond_to_callback(target, text, reply_markup=keyboard)


# Завершает игру, сохраняет результат и показывает экран после окончания раунда.
async def finish_game(callback: CallbackQuery, user_id: str, reason: str, extra_text: str) -> None:
    session = ensure_session(user_id)
    score = session["score"]
    session["active"] = False

    if reason == "win":
        title = t(user_id, "game_won")
    elif reason == "loss":
        title = t(user_id, "game_finished")
    else:
        title = t(user_id, "game_stopped")

    register_round_result(user_id, reason, score)
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
    register_round_result(user_id, "stopped", session["score"])
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
    await start_game(callback, user_id)


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
        session["asked_words"].append(current_word)

        if not prepare_question(user_id, session):
            await finish_game(
                callback,
                user_id,
                "win",
                t(user_id, "round_complete"),
            )
            return

        await respond_to_callback(
            callback,
            t(user_id, "answer_correct", question=render_question_text(session)),
            reply_markup=build_in_game_kb(user_id, session["options"]),
        )
        return

    register_answer(user_id, current_word, False)
    session["asked_words"].append(current_word)
    await finish_game(
        callback,
        user_id,
        "loss",
        t(user_id, "answer_wrong", word=current_word, answer=correct_answer),
    )


@dp.message(F.text)
# Обрабатывает текстовый ввод пользователя, когда бот ждет новое время напоминания.
async def text_input_handler(message: Message):
    user_id = str(message.from_user.id)
    mark_user_activity(user_id, message.chat.id)
    session = ensure_session(user_id)

    if not session.get("awaiting_reminder_time"):
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
