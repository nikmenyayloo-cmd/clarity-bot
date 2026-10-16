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
# Токен берётся из переменной окружения Railway (Variables → BOT_TOKEN).
# НЕ вставляй токен прямо в код и НЕ загружай его на GitHub!
TOKEN = os.environ["BOT_TOKEN"]

# Коды активации — каждый выдаётся одному пользователю.
# Берутся из переменной Railway ACTIVATION_CODES (через запятую), а НЕ из кода:
# так их не видно на GitHub. Список см. в файле activation_codes_SECRET.txt.
CODES = [c.strip() for c in os.environ.get("ACTIVATION_CODES", "").split(",") if c.strip()]
if not CODES:
    raise RuntimeError(
        "Не задана переменная ACTIVATION_CODES (Railway → Variables). "
        "Вставь туда коды через запятую."
    )

# ID администратора — поставь свой (узнать: написать @userinfobot)
ADMIN_IDS = [1285434989]

# Файл для хранения выданных кодов.
# Чтобы данные не пропадали при каждом деплое: в Railway подключи Volume
# (путь /data) и задай переменную DB_FILE=/data/clarity_codes.json
DB_FILE = os.environ.get("DB_FILE", "clarity_codes.json")

# Ссылка на приложение
APP_URL = "https://nikmenyayloo-cmd.github.io/CLARITY_/"

# ── DATABASE ────────────────────────────────────────────────────────
def load_db():
    db = {"issued": {}, "used_codes": []}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            db = json.load(f)
    # Старые коды, которых больше нет в списке ACTIVATION_CODES,
    # сбрасываем — такие пользователи при следующем нажатии получат новый код.
    db["issued"] = {u: c for u, c in db.get("issued", {}).items() if c in CODES}
    db["used_codes"] = [c for c in db.get("used_codes", []) if c in CODES]
    return db

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
        f"Нажми на код чтобы скопировать → введи при первом входе.\n\n"
        f"📲 <b>Как установить на экран:</b>\n\n"
        f"<b>iPhone:</b> открой ссылку в Safari → Поделиться ↑ → «На экран «Домой»»\n\n"
        f"<b>Android:</b> открой в Chrome → три точки ⋮ → «Добавить на главный экран»\n\n"
        f"Удачи! 🚀"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Открыть CLARITY →", url=APP_URL)
    ]])
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def btn_install_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "📲 <b>Как установить CLARITY на экран</b>\n\n"
        "<b>iPhone:</b>\n"
        "1. Скопируй ссылку: <code>https://nikmenyayloo-cmd.github.io/CLARITY_/</code>\n"
        "2. Открой <b>Safari</b> (не Chrome!)\n"
        "3. Вставь ссылку в адресную строку\n"
        "4. Нажми кнопку Поделиться ↑ внизу\n"
        "5. Выбери <b>«На экран «Домой»»</b>\n\n"
        "<b>Android:</b>\n"
        "1. Открой ссылку в Chrome\n"
        "2. Три точки ⋮ → <b>«Добавить на главный экран»</b>\n\n"
        "Готово — CLARITY как обычное приложение 🎉"
    )
    await query.message.reply_text(text, parse_mode="HTML")


async def cmd_install(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Инструкция по установке на экран"""
    text = (
        "📲 <b>Как установить CLARITY на экран телефона</b>\n\n"
        "<b>iPhone:</b>\n"
        "1. Скопируй ссылку: <code>https://nikmenyayloo-cmd.github.io/CLARITY_/</code>\n"
        "2. Открой Safari (не Chrome!)\n"
        "3. Вставь ссылку в адресную строку\n"
        "4. Нажми кнопку Поделиться ↑ внизу экрана\n"
        "5. Выбери <b>«На экран «Домой»»</b>\n"
        "6. Нажми <b>Добавить</b>\n\n"
        "<b>Android:</b>\n"
        "1. Открой ссылку в Chrome\n"
        "2. Нажми три точки ⋮ в правом верхнем углу\n"
        "3. Выбери <b>«Добавить на главный экран»</b>\n"
        "4. Нажми <b>Добавить</b>\n\n"
        "Готово — CLARITY появится как обычное приложение 🎉"
    )
    await update.message.reply_text(text, parse_mode="HTML")


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
    app.add_handler(CommandHandler("install", cmd_install))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("code", cmd_code))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(btn_get_code, pattern="^get_code$"))
    app.add_handler(CallbackQueryHandler(btn_install_help, pattern="^install_help$"))

    print("✅ CLARITY Bot запущен. Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
