import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
VOCAB_FILE = BASE_DIR / "vocabularies.json"
STUDENTS_FILE = BASE_DIR / "students.json"
STATS_FILE = BASE_DIR / "game_stats.json"
TRANSLATIONS_FILE = BASE_DIR / "translation_cache.json"
DEFINITIONS_FILE = BASE_DIR / "definition_cache.json"
DB_FILE = BASE_DIR / ".tmp" / "bot_data.db"
ENV_FILE = BASE_DIR / ".env"
TOKEN_FILE = BASE_DIR / "token.txt"
LOG_FILE = BASE_DIR / "bot.log"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_TARGETS = {
    VOCAB_FILE.name,
    STUDENTS_FILE.name,
    STATS_FILE.name,
    TRANSLATIONS_FILE.name,
    DEFINITIONS_FILE.name,
}


# Настраивает логирование в файл и консоль, чтобы проще было разбирать сбои бота.
def configure_logging() -> None:
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


# Подгружает переменные окружения из .env, если локальный файл уже создан.
def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Читает токен из token.txt как запасной вариант, если .env пока не настроен.
def load_token_from_file(path: Path) -> str | None:
    if not path.exists():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", maxsplit=1)
            if key.strip() in {"BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "MAIN_BOT_TOKEN"}:
                token = value.strip().strip('"').strip("'")
                if token:
                    return token
        elif ":" in line:
            return line
    return None


configure_logging()
logger = logging.getLogger("vocbot")


# Ищет токен в .env или token.txt и не даёт запустить бота без секрета.
def load_bot_token() -> str:
    load_env_file(ENV_FILE)
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
    if token:
        return token

    token = load_token_from_file(TOKEN_FILE)
    if token:
        logger.warning("BOT token loaded from token.txt fallback. Move it to .env when convenient.")
        return token

    raise RuntimeError("Telegram bot token is missing. Add TELEGRAM_BOT_TOKEN to .env or token.txt.")


BOT_TOKEN = load_bot_token()
