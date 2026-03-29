# VERSION: vocab_bot_v7.2 SCHOOL SYSTEM

import random
import json
import csv
from datetime import datetime
import nest_asyncio
import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from deep_translator import GoogleTranslator

nest_asyncio.apply()  # позволяет запускать внутри уже работающего цикла

# Функция для удаления всех сообщений, сохранённых в context.user_data["msg_ids"]
async def clear_messages(context):
    chat_id = context.user_data.get("chat_id")
    if not chat_id:
        return
    msg_ids = context.user_data.get("msg_ids", [])
    for msg_id in msg_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass  # Игнорируем ошибки удаления (например, если сообщение уже удалено)
    context.user_data["msg_ids"] = []  # очищаем список


TOKEN = "8381588510:AAFwlVCdX3uFq0Wc7lKY8MDSdurGDel_TtY"

translator = GoogleTranslator(source="en", target="ru")
cache = {}

RESULTS_FILE = "results.csv"
MISTAKES_FILE = "mistakes.json"
STUDENTS_FILE = "students.json"
VOCAB_FILE = "vocabularies.json"

# Загружаем студентов
with open(STUDENTS_FILE, "r", encoding="utf-8") as f:
    students = json.load(f)

# Загружаем словари
with open(VOCAB_FILE, "r", encoding="utf-8") as f:
    student_words = json.load(f)

# Загружаем ошибки
try:
    with open(MISTAKES_FILE, "r", encoding="utf-8") as f:
        mistakes = json.load(f)
except:
    mistakes = {}

# Переводчик с кешем
def tr(word):
    if word in cache:
        return cache[word]
    try:
        t = translator.translate(word)
    except:
        t = word
    cache[word] = t
    return t

# Сохранение результатов
def save_result(user_id, level, correct, wrong, total):
    name = students.get(user_id, "Unknown")
    percent = int(correct / total * 100) if total else 0
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([name, user_id, level, correct, wrong, total, percent, date])

# Добавление ошибок
def add_mistake(user_id, word):
    if user_id not in mistakes:
        mistakes[user_id] = []
    if word not in mistakes[user_id]:
        mistakes[user_id].append(word)
    with open(MISTAKES_FILE, "w", encoding="utf-8") as f:
        json.dump(mistakes, f, ensure_ascii=False, indent=2)

# Функция для удаления всех сообщений
async def clear_previous_messages(context):
    """Удаляет все предыдущие сообщения, которые бот сохранил"""
    chat_id = context.user_data.get("chat_id")
    if not chat_id:
        return
    msg_ids = context.user_data.get("msg_ids", [])
    for msg_id in msg_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass
    context.user_data["msg_ids"] = []

# Команда restart
async def restart(update, context):
    user_id = str(update.effective_user.id)
    context.user_data["chat_id"] = update.effective_chat.id

    # Удаляем все предыдущие сообщения
    await clear_previous_messages(context)

    # Запускаем игру заново
    words = student_words.get(user_id, []).copy()
    if not words:
        msg = await update.message.reply_text("Нет словаря для вас")
        context.user_data["msg_ids"].append(msg.message_id)
        return

    random.shuffle(words)
    context.user_data.update({
        "words": words,
        "i": 0,
        "correct": 0,
        "wrong": 0,
        "level": 1,
        "msg_ids": []
    })

    msg = await update.message.reply_text(f"LEVEL 1")
    context.user_data["msg_ids"].append(msg.message_id)

    await send_q(update, context)

async def start(update, context):
    user_id = str(update.effective_user.id)
    context.user_data["chat_id"] = update.effective_chat.id
    context.user_data["msg_ids"] = context.user_data.get("msg_ids", [])

    # Удаляем все предыдущие сообщения
    await clear_messages(update, context)

    if user_id not in student_words:
        msg = await update.message.reply_text("Нет словаря для вас")
        context.user_data["msg_ids"].append(msg.message_id)
        return

    words = student_words[user_id].copy()
    random.shuffle(words)

    context.user_data.update({
        "words": words,
        "i": 0,
        "correct": 0,
        "wrong": 0,
        "level": 1
    })

    msg = await update.message.reply_text(f"LEVEL 1")
    context.user_data["msg_ids"].append(msg.message_id)

    await send_q(update, context)

async def start(update, context):
    user_id = str(update.effective_user.id)
    context.user_data["chat_id"] = update.effective_chat.id

    # /start не удаляет предыдущие сообщения
    context.user_data["msg_ids"] = []

    if user_id not in student_words or not student_words[user_id]:
        msg = await update.message.reply_text("Нет словаря для вас")
        context.user_data["msg_ids"].append(msg.message_id)
        return

    words = student_words[user_id].copy()
    random.shuffle(words)

    context.user_data.update({
        "words": words,
        "i": 0,
        "correct": 0,
        "wrong": 0,
        "level": 1
    })

    msg = await update.message.reply_text(f"LEVEL 1")
    context.user_data["msg_ids"].append(msg.message_id)

    await send_q(update, context)

# Меню
async def show_menu(update, context):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Показать ошибки", callback_data="show_mistakes")],
        [InlineKeyboardButton("Статистика", callback_data="show_stats")]
    ])
    msg = await update.message.reply_text("Меню:", reply_markup=kb)
    if "msg_ids" not in context.user_data:
        context.user_data["msg_ids"] = []
    context.user_data["msg_ids"].append(msg.message_id)

async def menu_handler(update, context):
    q = update.callback_query
    await q.answer()
    user_id = str(q.from_user.id)
    if q.data == "show_mistakes":
        words = mistakes.get(user_id, [])
        text = "\n".join(words) if words else "Ошибок нет"
        await q.edit_message_text(f"Ваши ошибки:\n{text}")
    elif q.data == "show_stats":
        await q.edit_message_text("Статистика пока недоступна (реализация позже)")

# Команда /start
async def start(update, context):
    user_id = str(update.effective_user.id)
    context.user_data["chat_id"] = update.effective_chat.id
    context.user_data["msg_ids"] = context.user_data.get("msg_ids", [])

    # очищаем предыдущие сообщения
    await clear_messages(context)

    if user_id not in student_words:
        msg = await update.message.reply_text("Нет словаря для вас")
        context.user_data["msg_ids"].append(msg.message_id)
        return

    words = student_words[user_id].copy()
    random.shuffle(words)

    context.user_data.update({
        "words": words,
        "i": 0,
        "correct": 0,
        "wrong": 0,
        "level": 1
    })

    msg = await update.message.reply_text(f"LEVEL 1")
    context.user_data["msg_ids"].append(msg.message_id)

    await send_q(update, context)

# Отправка вопроса
async def send_q(update, context):
    words = context.user_data["words"]
    i = context.user_data["i"]
    if i >= len(words):
        c = context.user_data["correct"]
        w = context.user_data["wrong"]
        total = len(words)
        save_result(str(update.effective_user.id), context.user_data["level"], c, w, total)
        msg = await update.message.reply_text(
            f"LEVEL {context.user_data['level']} FINISHED\n"
            f"Correct: {c}\nWrong: {w}\nTotal: {total}\n"
            f"Success: {int(c/total*100)}%\n"
            f"Нажмите /level2 для следующего уровня"
        )
        context.user_data["msg_ids"].append(msg.message_id)
        return

    word = words[i]
    correct = tr(word)
    options = [correct]
    while len(options) < 4:
        fake = tr(random.choice(words))
        if fake not in options:
            options.append(fake)
    random.shuffle(options)
    context.user_data.update({"correct_answer": correct, "current_word": word})

    kb = [[InlineKeyboardButton(o, callback_data=o)] for o in options]
    msg = await update.message.reply_text(word, reply_markup=InlineKeyboardMarkup(kb))
    context.user_data["msg_ids"].append(msg.message_id)

# Обработка ответа
async def answer(update, context):
    q = update.callback_query
    await q.answer()
    user_id = str(q.from_user.id)
    sel = q.data
    correct = context.user_data["correct_answer"]
    word = context.user_data["current_word"]

    if sel == correct:
        context.user_data["correct"] += 1
        text = f"✅ {sel}"
    else:
        context.user_data["wrong"] += 1
        add_mistake(user_id, word)
        text = f"❌ {sel}\n✅ {correct}"

    await q.edit_message_text(text)
    context.user_data["i"] += 1
    await asyncio.sleep(1)
    await send_q(q, context)

# Уровень 2
async def level2(update, context):
    user_id = str(update.effective_user.id)
    context.user_data["chat_id"] = update.effective_chat.id
    context.user_data["msg_ids"] = context.user_data.get("msg_ids", [])

    await clear_messages(context)

    if user_id not in student_words:
        msg = await update.message.reply_text("Нет словаря для второго уровня")
        context.user_data["msg_ids"].append(msg.message_id)
        return

    words = student_words[user_id].copy()
    random.shuffle(words)

    context.user_data.update({
        "words": words,
        "i": 0,
        "correct": 0,
        "wrong": 0,
        "level": 2
    })

    msg = await update.message.reply_text(f"LEVEL 2")
    context.user_data["msg_ids"].append(msg.message_id)
    await send_q(update, context)

# MAIN
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("level2", level2))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CallbackQueryHandler(answer, pattern=".*"))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="show_"))

    print("SCHOOL SYSTEM STARTED")
    await app.run_polling()

#if __name__ == "__main__":
 #   asyncio.run(main())


