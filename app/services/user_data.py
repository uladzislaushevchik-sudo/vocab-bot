from datetime import datetime, timedelta


# Возвращает профиль пользователя и при первом обращении создаёт в нём все нужные поля.
def get_user_profile(stats_store: dict, user_id: str) -> dict:
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
            "english_level": "",
            "reminders_enabled": False,
            "reminder_time": "18:00",
            "last_seen_date": "",
            "last_reminder_date": "",
            "chat_id": None,
            "current_streak": 0,
            "best_streak": 0,
            "last_round_date": "",
            "daily_goal_target": 20,
            "daily_goal_progress": 0,
            "daily_goal_date": "",
            "level_stats": {},
            "word_stats": {},
        },
    )
    profile.setdefault("word_stats", {})
    profile.setdefault("language", "ru")
    profile.setdefault("english_level", "")
    profile.setdefault("reminders_enabled", False)
    profile.setdefault("reminder_time", "18:00")
    profile.setdefault("last_seen_date", "")
    profile.setdefault("last_reminder_date", "")
    profile.setdefault("chat_id", None)
    profile.setdefault("current_streak", 0)
    profile.setdefault("best_streak", 0)
    profile.setdefault("last_round_date", "")
    profile.setdefault("daily_goal_target", 20)
    profile.setdefault("daily_goal_progress", 0)
    profile.setdefault("daily_goal_date", "")
    profile.setdefault("level_stats", {})
    return profile


def refresh_daily_goal(profile: dict, today: str | None = None) -> None:
    today = today or datetime.now().strftime("%Y-%m-%d")
    if profile.get("daily_goal_date") != today:
        profile["daily_goal_date"] = today
        profile["daily_goal_progress"] = 0


def update_daily_goal_progress(profile: dict, correct_delta: int = 0, today: str | None = None) -> None:
    refresh_daily_goal(profile, today)
    if correct_delta > 0:
        profile["daily_goal_progress"] += correct_delta


def update_play_streak(profile: dict, today: str | None = None) -> None:
    today = today or datetime.now().strftime("%Y-%m-%d")
    last_round_date = profile.get("last_round_date", "")
    if last_round_date == today:
        return

    if last_round_date:
        try:
            previous_day = datetime.strptime(last_round_date, "%Y-%m-%d").date()
            current_day = datetime.strptime(today, "%Y-%m-%d").date()
        except ValueError:
            profile["current_streak"] = 1
        else:
            if previous_day + timedelta(days=1) == current_day:
                profile["current_streak"] = profile.get("current_streak", 0) + 1
            else:
                profile["current_streak"] = 1
    else:
        profile["current_streak"] = 1

    profile["last_round_date"] = today
    profile["best_streak"] = max(profile.get("best_streak", 0), profile.get("current_streak", 0))


# Достаёт статистику по конкретному слову пользователя или создаёт пустую запись.
def get_word_stats(stats_store: dict, user_id: str, word: str) -> dict:
    profile = get_user_profile(stats_store, user_id)
    return profile["word_stats"].setdefault(
        word,
        {
            "shown": 0,
            "correct": 0,
            "wrong": 0,
        },
    )


# Возвращает накопленную статистику пользователя по конкретному уровню игры.
def get_level_stats(stats_store: dict, user_id: str, level: int) -> dict:
    profile = get_user_profile(stats_store, user_id)
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


# Проверяет, есть ли у пользователя права администратора.
def is_admin(admin_ids: set[str], user_id: str) -> bool:
    return user_id in admin_ids


# Помечает, что пользователь сегодня был активен, и запоминает чат для напоминаний.
def mark_user_activity(stats_store: dict, save_json, stats_file, user_id: str, chat_id: int | None = None) -> None:
    profile = get_user_profile(stats_store, user_id)
    profile["last_seen_date"] = datetime.now().strftime("%Y-%m-%d")
    if chat_id is not None:
        profile["chat_id"] = chat_id
    save_json(stats_file, stats_store)


# Проверяет строку времени и приводит её к формату HH:MM.
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


# Добавляет студенту новые слова без дублей и сохраняет обновлённый словарь.
def add_words_to_student(student_words: dict, save_json, vocab_file, student_id: str, words: list[str]) -> tuple[int, int]:
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
    save_json(vocab_file, student_words)
    return added, skipped


# Разбивает введённый текст на слова по запятым и переводам строки.
# Удаляет слова из словаря студента без учета регистра и сохраняет обновленный список.
def remove_words_from_student(student_words: dict, save_json, vocab_file, student_id: str, words: list[str]) -> tuple[int, int]:
    existing_words = student_words.get(student_id, [])
    if not existing_words:
        return 0, len(words)

    targets = {word.casefold() for word in words}
    updated_words = []
    removed = 0

    for existing_word in existing_words:
        if existing_word.casefold() in targets:
            removed += 1
            targets.discard(existing_word.casefold())
            continue
        updated_words.append(existing_word)

    student_words[student_id] = updated_words
    save_json(vocab_file, student_words)
    not_found = len(targets)
    return removed, not_found


def replace_word_for_student(student_words: dict, save_json, vocab_file, student_id: str, old_word: str, new_word: str) -> tuple[bool, str]:
    existing_words = student_words.get(student_id, [])
    if not existing_words:
        return False, "student_has_no_words"

    old_key = old_word.casefold()
    new_key = new_word.casefold()

    if old_key == new_key:
        return False, "same_word"

    if any(word.casefold() == new_key for word in existing_words):
        return False, "new_word_exists"

    for index, existing_word in enumerate(existing_words):
        if existing_word.casefold() == old_key:
            existing_words[index] = new_word
            save_json(vocab_file, student_words)
            return True, "replaced"

    return False, "old_word_not_found"


def split_words_input(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for line in normalized.split("\n"):
        parts.extend(chunk.strip() for chunk in line.split(","))
    return [part for part in parts if part]
