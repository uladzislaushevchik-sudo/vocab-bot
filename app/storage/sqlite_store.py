import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.config.bot_config import (
    DB_FILE,
    DEFINITIONS_FILE,
    STATS_FILE,
    STUDENTS_FILE,
    TRANSLATIONS_FILE,
    VOCAB_FILE,
    logger,
)


PATH_TO_DATASET = {
    VOCAB_FILE.name: "vocab",
    STUDENTS_FILE.name: "students",
    STATS_FILE.name: "stats",
    TRANSLATIONS_FILE.name: "translations",
    DEFINITIONS_FILE.name: "definitions",
}


def connect_db(db_path: Path = DB_FILE) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: Path = DB_FILE) -> None:
    with connect_db(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vocab_words (
                user_id TEXT NOT NULL,
                word TEXT NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY (user_id, position)
            );

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                games_played INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                stopped_games INTEGER NOT NULL DEFAULT 0,
                best_score INTEGER NOT NULL DEFAULT 0,
                last_score INTEGER NOT NULL DEFAULT 0,
                total_correct INTEGER NOT NULL DEFAULT 0,
                total_wrong INTEGER NOT NULL DEFAULT 0,
                language TEXT NOT NULL DEFAULT 'ru',
                english_level TEXT NOT NULL DEFAULT '',
                reminders_enabled INTEGER NOT NULL DEFAULT 0,
                reminder_time TEXT NOT NULL DEFAULT '18:00',
                last_seen_date TEXT NOT NULL DEFAULT '',
                last_reminder_date TEXT NOT NULL DEFAULT '',
                chat_id INTEGER,
                current_streak INTEGER NOT NULL DEFAULT 0,
                best_streak INTEGER NOT NULL DEFAULT 0,
                last_round_date TEXT NOT NULL DEFAULT '',
                daily_goal_target INTEGER NOT NULL DEFAULT 20,
                daily_goal_progress INTEGER NOT NULL DEFAULT 0,
                daily_goal_date TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS level_stats (
                user_id TEXT NOT NULL,
                level INTEGER NOT NULL,
                games_played INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                stopped_games INTEGER NOT NULL DEFAULT 0,
                correct_answers INTEGER NOT NULL DEFAULT 0,
                wrong_answers INTEGER NOT NULL DEFAULT 0,
                best_score INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, level)
            );

            CREATE TABLE IF NOT EXISTS word_stats (
                user_id TEXT NOT NULL,
                word TEXT NOT NULL,
                shown INTEGER NOT NULL DEFAULT 0,
                correct INTEGER NOT NULL DEFAULT 0,
                wrong INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, word)
            );

            CREATE TABLE IF NOT EXISTS translation_cache (
                word TEXT PRIMARY KEY,
                translation TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS definition_cache (
                word TEXT PRIMARY KEY,
                definition TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS writings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                sender_level TEXT NOT NULL,
                receiver_level TEXT NOT NULL,
                topic TEXT NOT NULL,
                text_original TEXT NOT NULL,
                text_corrected TEXT,
                reviewer_comment TEXT NOT NULL DEFAULT '',
                reviewer_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reviewed_at TEXT NOT NULL DEFAULT ''
            );
            """
        )
        _ensure_column(conn, "user_profiles", "english_level", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "user_profiles", "current_streak", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "user_profiles", "best_streak", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "user_profiles", "last_round_date", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "user_profiles", "daily_goal_target", "INTEGER NOT NULL DEFAULT 20")
        _ensure_column(conn, "user_profiles", "daily_goal_progress", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "user_profiles", "daily_goal_date", "TEXT NOT NULL DEFAULT ''")


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_definition: str) -> None:
    existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in existing_columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def database_has_runtime_data(db_path: Path = DB_FILE) -> bool:
    with connect_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM students) +
                (SELECT COUNT(*) FROM vocab_words) +
                (SELECT COUNT(*) FROM user_profiles) +
                (SELECT COUNT(*) FROM translation_cache) +
                (SELECT COUNT(*) FROM definition_cache) AS total_count
            """
        ).fetchone()
        return bool(row["total_count"])


def sync_students(students: dict, db_path: Path = DB_FILE) -> None:
    with connect_db(db_path) as conn:
        conn.execute("DELETE FROM students")
        conn.executemany(
            "INSERT INTO students (user_id, name) VALUES (?, ?)",
            [(user_id, name) for user_id, name in students.items()],
        )


def sync_vocab(student_words: dict, db_path: Path = DB_FILE) -> None:
    rows = []
    for user_id, words in student_words.items():
        for position, word in enumerate(words):
            rows.append((user_id, word, position))
    with connect_db(db_path) as conn:
        conn.execute("DELETE FROM vocab_words")
        conn.executemany(
            "INSERT INTO vocab_words (user_id, word, position) VALUES (?, ?, ?)",
            rows,
        )


def sync_stats(stats_store: dict, db_path: Path = DB_FILE) -> None:
    with connect_db(db_path) as conn:
        conn.execute("DELETE FROM user_profiles")
        conn.execute("DELETE FROM level_stats")
        conn.execute("DELETE FROM word_stats")

        profile_rows = []
        level_rows = []
        word_rows = []
        for user_id, profile in stats_store.items():
            profile_rows.append(
                (
                    user_id,
                    profile.get("games_played", 0),
                    profile.get("wins", 0),
                    profile.get("losses", 0),
                    profile.get("stopped_games", 0),
                    profile.get("best_score", 0),
                    profile.get("last_score", 0),
                    profile.get("total_correct", 0),
                    profile.get("total_wrong", 0),
                    profile.get("language", "ru"),
                    profile.get("english_level", ""),
                    int(bool(profile.get("reminders_enabled", False))),
                    profile.get("reminder_time", "18:00"),
                    profile.get("last_seen_date", ""),
                    profile.get("last_reminder_date", ""),
                    profile.get("chat_id"),
                    profile.get("current_streak", 0),
                    profile.get("best_streak", 0),
                    profile.get("last_round_date", ""),
                    profile.get("daily_goal_target", 20),
                    profile.get("daily_goal_progress", 0),
                    profile.get("daily_goal_date", ""),
                )
            )

            for level, level_info in profile.get("level_stats", {}).items():
                level_rows.append(
                    (
                        user_id,
                        int(level),
                        level_info.get("games_played", 0),
                        level_info.get("wins", 0),
                        level_info.get("losses", 0),
                        level_info.get("stopped_games", 0),
                        level_info.get("correct_answers", 0),
                        level_info.get("wrong_answers", 0),
                        level_info.get("best_score", 0),
                    )
                )

            for word, word_info in profile.get("word_stats", {}).items():
                word_rows.append(
                    (
                        user_id,
                        word,
                        word_info.get("shown", 0),
                        word_info.get("correct", 0),
                        word_info.get("wrong", 0),
                    )
                )

        conn.executemany(
            """
            INSERT INTO user_profiles (
                user_id, games_played, wins, losses, stopped_games, best_score, last_score,
                total_correct, total_wrong, language, english_level, reminders_enabled, reminder_time,
                last_seen_date, last_reminder_date, chat_id, current_streak, best_streak,
                last_round_date, daily_goal_target, daily_goal_progress, daily_goal_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            profile_rows,
        )
        conn.executemany(
            """
            INSERT INTO level_stats (
                user_id, level, games_played, wins, losses, stopped_games,
                correct_answers, wrong_answers, best_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            level_rows,
        )
        conn.executemany(
            "INSERT INTO word_stats (user_id, word, shown, correct, wrong) VALUES (?, ?, ?, ?, ?)",
            word_rows,
        )


def sync_translation_cache(translation_cache: dict, db_path: Path = DB_FILE) -> None:
    with connect_db(db_path) as conn:
        conn.execute("DELETE FROM translation_cache")
        conn.executemany(
            "INSERT INTO translation_cache (word, translation) VALUES (?, ?)",
            [(word, translation) for word, translation in translation_cache.items()],
        )


def sync_definition_cache(definition_cache: dict, db_path: Path = DB_FILE) -> None:
    with connect_db(db_path) as conn:
        conn.execute("DELETE FROM definition_cache")
        conn.executemany(
            "INSERT INTO definition_cache (word, definition) VALUES (?, ?)",
            [(word, definition) for word, definition in definition_cache.items()],
        )


def sync_dataset(path: Path, data, db_path: Path = DB_FILE) -> None:
    dataset = PATH_TO_DATASET.get(path.name)
    if dataset == "students":
        sync_students(data, db_path)
    elif dataset == "vocab":
        sync_vocab(data, db_path)
    elif dataset == "stats":
        sync_stats(data, db_path)
    elif dataset == "translations":
        sync_translation_cache(data, db_path)
    elif dataset == "definitions":
        sync_definition_cache(data, db_path)


def load_students(db_path: Path = DB_FILE) -> dict:
    with connect_db(db_path) as conn:
        rows = conn.execute("SELECT user_id, name FROM students ORDER BY user_id").fetchall()
    return {row["user_id"]: row["name"] for row in rows}


def load_vocab(db_path: Path = DB_FILE) -> dict:
    with connect_db(db_path) as conn:
        rows = conn.execute("SELECT user_id, word FROM vocab_words ORDER BY user_id, position").fetchall()
    result = {}
    for row in rows:
        result.setdefault(row["user_id"], []).append(row["word"])
    return result


def load_stats(db_path: Path = DB_FILE) -> dict:
    result = {}
    with connect_db(db_path) as conn:
        profile_rows = conn.execute("SELECT * FROM user_profiles").fetchall()
        level_rows = conn.execute("SELECT * FROM level_stats").fetchall()
        word_rows = conn.execute("SELECT * FROM word_stats").fetchall()

    for row in profile_rows:
        result[row["user_id"]] = {
            "games_played": row["games_played"],
            "wins": row["wins"],
            "losses": row["losses"],
            "stopped_games": row["stopped_games"],
            "best_score": row["best_score"],
            "last_score": row["last_score"],
            "total_correct": row["total_correct"],
            "total_wrong": row["total_wrong"],
            "language": row["language"],
            "english_level": row["english_level"],
            "reminders_enabled": bool(row["reminders_enabled"]),
            "reminder_time": row["reminder_time"],
            "last_seen_date": row["last_seen_date"],
            "last_reminder_date": row["last_reminder_date"],
            "chat_id": row["chat_id"],
            "current_streak": row["current_streak"],
            "best_streak": row["best_streak"],
            "last_round_date": row["last_round_date"],
            "daily_goal_target": row["daily_goal_target"],
            "daily_goal_progress": row["daily_goal_progress"],
            "daily_goal_date": row["daily_goal_date"],
            "level_stats": {},
            "word_stats": {},
        }

    for row in level_rows:
        profile = result.setdefault(
            row["user_id"],
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
        profile["level_stats"][str(row["level"])] = {
            "games_played": row["games_played"],
            "wins": row["wins"],
            "losses": row["losses"],
            "stopped_games": row["stopped_games"],
            "correct_answers": row["correct_answers"],
            "wrong_answers": row["wrong_answers"],
            "best_score": row["best_score"],
        }

    for row in word_rows:
        profile = result.setdefault(
            row["user_id"],
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
        profile["word_stats"][row["word"]] = {
            "shown": row["shown"],
            "correct": row["correct"],
            "wrong": row["wrong"],
        }

    return result


def load_translation_cache(db_path: Path = DB_FILE) -> dict:
    with connect_db(db_path) as conn:
        rows = conn.execute("SELECT word, translation FROM translation_cache ORDER BY word").fetchall()
    return {row["word"]: row["translation"] for row in rows}


def load_definition_cache(db_path: Path = DB_FILE) -> dict:
    with connect_db(db_path) as conn:
        rows = conn.execute("SELECT word, definition FROM definition_cache ORDER BY word").fetchall()
    return {row["word"]: row["definition"] for row in rows}


def migrate_json_to_database(load_json_func, db_path: Path = DB_FILE) -> None:
    if database_has_runtime_data(db_path):
        return

    logger.info("SQLite database is empty. Migrating data from JSON files.")
    sync_students(load_json_func(STUDENTS_FILE, {}), db_path)
    sync_vocab(load_json_func(VOCAB_FILE, {}), db_path)
    sync_stats(load_json_func(STATS_FILE, {}), db_path)
    sync_translation_cache(load_json_func(TRANSLATIONS_FILE, {}), db_path)
    definition_cache = {
        word: definition
        for word, definition in load_json_func(DEFINITIONS_FILE, {}).items()
        if isinstance(definition, str) and definition.strip()
    }
    sync_definition_cache(definition_cache, db_path)


def refresh_reference_data_from_json(load_json_func, db_path: Path = DB_FILE) -> None:
    logger.info("Refreshing students and vocabulary from JSON into SQLite without touching progress data.")
    sync_students(load_json_func(STUDENTS_FILE, {}), db_path)
    sync_vocab(load_json_func(VOCAB_FILE, {}), db_path)


def export_runtime_snapshot_to_json(save_json_func, db_path: Path = DB_FILE) -> None:
    logger.info("Exporting player stats from SQLite into tracked JSON snapshot file.")
    _, _, stats_store, _, _ = load_runtime_state(db_path)
    save_json_func(STATS_FILE, stats_store)


def load_runtime_state(db_path: Path = DB_FILE) -> tuple[dict, dict, dict, dict, dict]:
    return (
        load_vocab(db_path),
        load_students(db_path),
        load_stats(db_path),
        load_translation_cache(db_path),
        load_definition_cache(db_path),
    )


def expire_due_writings(db_path: Path = DB_FILE, hours: int = 72) -> int:
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    with connect_db(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE writings
            SET status = 'expired'
            WHERE status = 'sent' AND created_at < ?
            """,
            (cutoff,),
        )
        return cursor.rowcount or 0


def create_writing_task(
    sender_id: str,
    receiver_id: str,
    sender_level: str,
    receiver_level: str,
    topic: str,
    text_original: str,
    db_path: Path = DB_FILE,
) -> int:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO writings (
                sender_id, receiver_id, sender_level, receiver_level,
                topic, text_original, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'sent', ?)
            """,
            (sender_id, receiver_id, sender_level, receiver_level, topic, text_original, created_at),
        )
        return int(cursor.lastrowid)


def get_writing_task(task_id: int, db_path: Path = DB_FILE) -> dict | None:
    expire_due_writings(db_path)
    with connect_db(db_path) as conn:
        row = conn.execute("SELECT * FROM writings WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def count_active_writings_for_sender(sender_id: str, db_path: Path = DB_FILE) -> int:
    expire_due_writings(db_path)
    with connect_db(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM writings WHERE sender_id = ? AND status = 'sent'",
            (sender_id,),
        ).fetchone()
    return int(row["count"])


def review_writing_task(
    task_id: int,
    reviewer_id: str,
    text_corrected: str | None,
    reviewer_comment: str,
    db_path: Path = DB_FILE,
) -> bool:
    reviewed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect_db(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE writings
            SET text_corrected = ?, reviewer_comment = ?, reviewer_id = ?,
                status = 'reviewed', reviewed_at = ?
            WHERE id = ? AND status = 'sent'
            """,
            (text_corrected, reviewer_comment, reviewer_id, reviewed_at, task_id),
        )
        return bool(cursor.rowcount)


def list_writing_tasks_for_user(
    user_id: str,
    role: str,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db_path: Path = DB_FILE,
) -> list[dict]:
    expire_due_writings(db_path)
    if role not in {"sender", "receiver"}:
        raise ValueError("role must be 'sender' or 'receiver'")

    query = f"SELECT * FROM writings WHERE {role}_id = ?"
    params: list[object] = [user_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with connect_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def count_writing_tasks_for_user(
    user_id: str,
    role: str,
    status: str | None = None,
    db_path: Path = DB_FILE,
) -> int:
    expire_due_writings(db_path)
    if role not in {"sender", "receiver"}:
        raise ValueError("role must be 'sender' or 'receiver'")

    query = f"SELECT COUNT(*) AS count FROM writings WHERE {role}_id = ?"
    params: list[object] = [user_id]
    if status:
        query += " AND status = ?"
        params.append(status)

    with connect_db(db_path) as conn:
        row = conn.execute(query, params).fetchone()
    return int(row["count"])
