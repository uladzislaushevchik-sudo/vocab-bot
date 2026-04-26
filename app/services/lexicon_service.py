import asyncio
import random
from difflib import SequenceMatcher
from urllib.parse import quote

import aiohttp


# Переводит слово на русский язык, кеширует результат и повторно не дёргает переводчик.
def get_translation(word: str, translation_cache: dict, translator, save_json, translations_file, logger) -> str:
    cached = translation_cache.get(word)
    if cached:
        return cached

    try:
        translated = translator.translate(word)
    except Exception as exc:
        logger.warning("Translation failed for %s: %s", word, exc)
        translated = word

    translation_cache[word] = translated
    save_json(translations_file, translation_cache)
    return translated


# Получает английское определение слова из внешнего словаря и кеширует только удачные ответы.
async def get_definition(
    word: str,
    definition_cache: dict,
    definition_miss_words: set,
    definition_service_available: bool,
    save_json,
    definitions_file,
    logger,
) -> tuple[str | None, bool]:
    cached = definition_cache.get(word)
    if isinstance(cached, str) and cached.strip():
        return cached, definition_service_available

    if word in definition_miss_words:
        return None, definition_service_available

    if not definition_service_available:
        return None, definition_service_available

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word)}"
    payload = None
    try:
        timeout = aiohttp.ClientTimeout(total=4)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    definition_miss_words.add(word)
                    logger.info("Definition was not found for %s. HTTP status: %s", word, response.status)
                    return None, definition_service_available
                payload = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        logger.warning("Definition service error for %s: %s", word, exc)
        return None, False

    definition = None
    if isinstance(payload, list):
        for entry in payload:
            for meaning in entry.get("meanings", []):
                for item in meaning.get("definitions", []):
                    text = item.get("definition", "").strip()
                    if text:
                        definition = text
                        break
                if definition:
                    break
            if definition:
                break

    if definition:
        definition_cache[word] = definition
        save_json(definitions_file, definition_cache)
    else:
        definition_miss_words.add(word)
    return definition, definition_service_available


# Упрощает текст для более стабильного сравнения похожести.
def normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum() or ch.isspace()).strip()


# Считает общую похожесть слов по английскому написанию и русскому переводу.
def similarity_score(target_word: str, candidate_word: str, get_translation_func) -> float:
    target_translation = get_translation_func(target_word)
    candidate_translation = get_translation_func(candidate_word)

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
def weighted_word_choice(user_id: str, available_words: list[str], get_word_stats_func) -> str:
    weights = []
    for word in available_words:
        word_stats = get_word_stats_func(user_id, word)
        shown = word_stats["shown"]
        correct = word_stats["correct"]
        wrong = word_stats["wrong"]
        weight = 1.0

        if shown == 0:
            weight += 3.0
        else:
            accuracy = correct / shown
            mastery_gap = 1.0 - accuracy
            weight += wrong * 4.5
            weight += mastery_gap * 4.0
            weight += max(shown - correct, 0) * 1.5
            if shown >= 4 and accuracy >= 0.85:
                weight *= 0.55
            elif shown >= 2 and accuracy >= 0.7:
                weight *= 0.8

        if wrong > correct:
            weight += 2.0
        if correct >= 5 and wrong == 0:
            weight *= 0.45

        weights.append(max(weight, 0.25))

    return random.choices(available_words, weights=weights, k=1)[0]


# Берёт следующее слово для раунда из ещё не использованных слов.
def choose_next_word(user_id: str, session: dict, get_word_stats_func) -> str | None:
    all_words = session["all_words"]
    asked_words = set(session["asked_words"])
    remaining_words = [word for word in all_words if word not in asked_words]
    if not remaining_words:
        return None
    return weighted_word_choice(user_id, remaining_words, get_word_stats_func)


# Подбирает неправильные варианты ответа: сначала похожие, затем при необходимости добавляет более далёкий вариант.
def build_distractors(
    user_id: str,
    target_word: str,
    correct_answer: str,
    student_words: dict,
    get_translation_func,
    options_count: int = 4,
) -> list[str]:
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
        key=lambda candidate: similarity_score(target_word, candidate, get_translation_func),
        reverse=True,
    )

    distractors = []
    used_answers = {correct_answer.casefold()}

    for candidate in ranked:
        translated = get_translation_func(candidate)
        if translated.casefold() in used_answers:
            continue
        distractors.append(translated)
        used_answers.add(translated.casefold())
        if len(distractors) == max(options_count - 1, 0):
            break

    if len(distractors) >= 2 and len(ranked) > len(distractors):
        for candidate in reversed(ranked):
            translated = get_translation_func(candidate)
            if translated.casefold() in used_answers:
                continue
            distractors[-1] = translated
            break

    return distractors[: options_count - 1]


# Нормализует введённое слово: нижний регистр, без знаков препинания и лишних пробелов.
def normalize_english_answer(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(cleaned.split())
