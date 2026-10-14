#!/usr/bin/env python3
"""
CLARITY Telegram Bot
Команды: /start, /test, /code, /broadcast
"""

import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ── CONFIG ──────────────────────────────────────────────────────────
TOKEN = "8710520052:AAFgSbd5h3wGrB7humwiKzUAJltHSvklwDY"

# Коды активации — каждый выдаётся одному пользователю
CODES = [
    "CLARITY-001", "CLARITY-002", "CLARITY-003", "CLARITY-004", "CLARITY-005",
    "CLARITY-006", "CLARITY-007", "CLARITY-008", "CLARITY-009", "CLARITY-010",
]

# ID администратора — поставь свой (узнать: написать @userinfobot)
ADMIN_IDS = [1285434989]

# Файл для хранения выданных кодов
DB_FILE = "clarity_codes.json"

# Ссылка на приложение
APP_URL = "https://nikmenyayloo-cmd.github.io/CLARITY_/"

# ── DATABASE ────────────────────────────────────────────────────────
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"issued": {}, "used_codes": []}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_free_code(db):
    for code in CODES:
        if code not in db["used_codes"]:
            return code
    return None

# ── HANDLERS ────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = load_db()
    uid = str(user.id)

    # Если у пользователя уже есть код — напомним
    if uid in db["issued"]:
        code = db["issued"][uid]
        text = (
            f"👋 С возвращением, {user.first_name}!\n\n"
            f"Твой код активации:\n"
            f"<code>{code}</code>\n\n"
            f"Нажми на код чтобы скопировать, потом открой приложение."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Открыть CLARITY →", url=APP_URL)
        ]])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    # Новый пользователь — приветствие с кнопкой
    text = (
        f"Привет, {user.first_name} 👋\n\n"
        f"Ещё одно приложение для продуктивности? Да.\n"
        f"Только это реально работает — проверено на людях с вечно незакрытыми вкладками и списком дел из 2019 года.\n\n"
        f"<b>CLARITY</b> помогает не сойти с ума от задач и тревоги. Просто. Без 47 настроек и туториала на 20 минут.\n\n"
        f"Ты попал в закрытый тест. Таких как ты — много. Не облажайся 😄\n\n"
        f"Жми кнопку 👇"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔑 Получить код", callback_data="get_code")
    ]])
    VIDEO_ID = "BAACAgIAAxkBAAMmas_483NiPc9fuydJo15Rs7LcxAcAAvqmAAJjaYBKJqupYZhBOwM9BA"
    await update.message.reply_video(VIDEO_ID, caption=text, parse_mode="HTML", reply_markup=kb)


async def issue_code(update: Update, user):
    """Выдать код пользователю"""
    db = load_db()
    uid = str(user.id)

    if uid in db["issued"]:
        code = db["issued"][uid]
        text = (
            f"Твой код активации:\n"
            f"<code>{code}</code>\n\n"
            f"Нажми на код чтобы скопировать, потом открой приложение."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Открыть CLARITY →", url=APP_URL)
        ]])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    code = get_free_code(db)
    if not code:
        await update.message.reply_text(
            "😔 Все коды уже разобраны. Напиши нам — добавим ещё.\n@clarityapp"
        )
        return

    db["issued"][uid] = code
    db["used_codes"].append(code)
    save_db(db)

    text = (
        f"✅ Держи свой код:\n\n"
        f"<code>{code}</code>\n\n"
        f"Нажми на код чтобы скопировать → открой приложение → введи код при первом входе.\n\n"
        f"Удачи! 🚀"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Открыть CLARITY →", url=APP_URL)
    ]])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_test(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Команда /test — сообщение о тесте с описанием"""
    text = (
        "🚀 <b>CLARITY — закрытое бета-тестирование</b>\n\n"
        "Это приложение для тех кто хочет:\n"
        "• Отслеживать задачи по категориям\n"
        "• Видеть прогресс дня через кольцо\n"
        "• Работать с тревогой по простой системе\n\n"
        "Ты получишь <b>персональный код</b> — он вводится один раз при первом входе.\n\n"
        "Нажми <b>Получить код</b> чтобы начать 👇"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Получить код →", callback_data="get_code"),
        InlineKeyboardButton("Открыть приложение", url=APP_URL)
    ]])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Команда /code — получить или напомнить код"""
    await issue_code(update, update.effective_user)


async def btn_get_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Кнопка 'Получить код'"""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db = load_db()
    uid = str(user.id)

    if uid in db["issued"]:
        code = db["issued"][uid]
        text = (
            f"Твой код активации:\n"
            f"<code>{code}</code>\n\n"
            f"Нажми на код чтобы скопировать, потом открой приложение."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Открыть CLARITY →", url=APP_URL)
        ]])
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    code = get_free_code(db)
    if not code:
        await query.message.reply_text("😔 Все коды уже разобраны. Напиши нам — добавим ещё.\n@clarityapp")
        return

    db["issued"][uid] = code
    db["used_codes"].append(code)
    save_db(db)

    text = (
        f"✅ Держи свой код:\n\n"
        f"<code>{code}</code>\n\n"
        f"Нажми на код чтобы скопировать → открой приложение → введи код при первом входе.\n\n"
        f"Удачи! 🚀"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Открыть CLARITY →", url=APP_URL)
    ]])
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def cmd_getid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Команда /getid"""
    await update.message.reply_text("Теперь отправь видео отдельным сообщением — без команды")


async def handle_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Любое видео или файл — возвращаем file_id"""
    msg = update.message
    if msg.video:
        await msg.reply_text(f"✅ Video file_id:\n<code>{msg.video.file_id}</code>", parse_mode="HTML")
    elif msg.document:
        await msg.reply_text(f"✅ Document file_id:\n<code>{msg.document.file_id}</code>", parse_mode="HTML")


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /broadcast <текст> — рассылка всем кто получил код (только для админов)
    Пример: /broadcast Привет! Вышло обновление.
    """
    user = update.effective_user
    if ADMIN_IDS and user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа.")
        return

    if not ctx.args:
        await update.message.reply_text(
            "Использование: /broadcast <текст>\n\nПример:\n/broadcast Привет! Вышло обновление CLARITY 1.1 🎉"
        )
        return

    db = load_db()
    msg = " ".join(ctx.args)
    sent = 0
    failed = 0

    for uid in db["issued"]:
        try:
            await ctx.bot.send_message(
                chat_id=int(uid),
                text=msg,
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ Отправлено: {sent}\n❌ Не доставлено: {failed}"
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /stats — статистика выданных кодов (только для админов)
    """
    user = update.effective_user
    if ADMIN_IDS and user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа.")
        return

    db = load_db()
    total = len(CODES)
    used = len(db["used_codes"])
    free = total - used

    await update.message.reply_text(
        f"📊 <b>Статистика CLARITY</b>\n\n"
        f"Всего кодов: {total}\n"
        f"Выдано: {used}\n"
        f"Свободно: {free}\n\n"
        f"Пользователей: {len(db['issued'])}",
        parse_mode="HTML"
    )


# ── MAIN ────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.INFO
    )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("getid", cmd_getid))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("code", cmd_code))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(btn_get_code, pattern="^get_code$"))

    print("✅ CLARITY Bot запущен. Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
