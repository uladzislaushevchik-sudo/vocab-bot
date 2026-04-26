import json
import shutil
from datetime import datetime
from pathlib import Path

from app.config.bot_config import BACKUP_DIR, BACKUP_TARGETS, logger


# Делает ежедневную резервную копию важных JSON-файлов и оставляет только свежие копии.
def backup_file_if_needed(path: Path, keep_days: int = 14) -> None:
    if path.name not in BACKUP_TARGETS or not path.exists():
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_name = f"{path.stem}-{datetime.now().strftime('%Y%m%d')}{path.suffix}"
    backup_path = BACKUP_DIR / backup_name
    if not backup_path.exists():
        shutil.copy2(path, backup_path)

    old_backups = sorted(BACKUP_DIR.glob(f"{path.stem}-*{path.suffix}"))
    for outdated_backup in old_backups[:-keep_days]:
        outdated_backup.unlink(missing_ok=True)


# Загружает данные из JSON-файла и возвращает значение по умолчанию, если файла нет или он поврежден.
def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("Could not load %s. Using default value.", path.name)
        return default


def _write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


# Сохраняет JSON атомарно: сначала пишет во временный файл, потом подменяет основной.
def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_file_if_needed(path)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        _write_json(temp_path, data)
        try:
            temp_path.replace(path)
        except PermissionError:
            logger.warning(
                "Atomic replace failed for %s. Falling back to direct write, likely due to a file lock.",
                path.name,
            )
            _write_json(path, data)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
            except PermissionError:
                logger.warning("Could not remove temporary file %s because it is locked.", temp_path.name)
