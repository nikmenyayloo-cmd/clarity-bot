#!/usr/bin/env python3
"""
CLARITY Telegram Bot
Команды: /start, /test, /code, /broadcast, /stats, /grant (+ оплата Robokassa)
"""

import os
import json
import logging
import time
import hmac
import hashlib
from urllib.parse import urlencode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
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

# ── ОПЛАТА (ручной режим, для самозанятого) ───────────────────────
# Пока PAID_MODE не равен 1, бот работает как раньше (код бесплатно по кнопке).
# PAID_MODE=1 → код выдаётся только после подтверждения оплаты админом.
# Реквизиты НЕ в коде, а в переменной Railway PAY_DETAILS (например:
# "СБП / Сбербанк: +7 900 000-00-00, Имя Ф.") — так их не видно на GitHub.
# ── Автоматическая оплата через Robokassa (самозанятый) ──
# Задай в Railway: ROBOKASSA_LOGIN, ROBOKASSA_PASS1, ROBOKASSA_PASS2.
# ROBOKASSA_TEST=1 — тестовый режим (тогда нужны ТЕСТОВЫЕ пароли из кабинета).
# ROBOKASSA_HASH — алгоритм подписи из кабинета (md5 по умолчанию; или sha256).
RK_LOGIN = os.environ.get("ROBOKASSA_LOGIN", "").strip()
RK_PASS1 = os.environ.get("ROBOKASSA_PASS1", "").strip()
RK_PASS2 = os.environ.get("ROBOKASSA_PASS2", "").strip()
RK_TEST = os.environ.get("ROBOKASSA_TEST", "0").strip() == "1"
RK_HASH = os.environ.get("ROBOKASSA_HASH", "md5").strip().lower()
RK = bool(RK_LOGIN)
if RK and not (RK_PASS1 and RK_PASS2):
    raise RuntimeError("Задан ROBOKASSA_LOGIN, но нет ROBOKASSA_PASS1 / ROBOKASSA_PASS2.")
if RK_HASH not in ("md5", "sha256", "sha1", "sha512"):
    raise RuntimeError("ROBOKASSA_HASH должен быть md5, sha256, sha1 или sha512.")

PAID = RK or os.environ.get("PAID_MODE", "0").strip() == "1"
PRICE = os.environ.get("PRICE", "399").strip()
PAY_DETAILS = os.environ.get("PAY_DETAILS", "").strip()
if PAID and not RK and not PAY_DETAILS:
    raise RuntimeError("PAID_MODE=1 без Robokassa: не задана переменная PAY_DETAILS (реквизиты для оплаты).")
PENDING_TTL = 600  # сек: повторная заявка от одного человека не чаще, чем раз в 10 минут

# Ссылка на приложение
APP_URL = "https://nikmenyayloo-cmd.github.io/CLARITY_/"

def app_link(code):
    """Ссылка на приложение со входом по коду (#k=КОД): код не придётся вводить заново,
    даже если телефон или встроенный браузер Telegram «забыли» вход."""
    return f"{APP_URL}#k={code}" if code else APP_URL


# ── DATABASE ────────────────────────────────────────────────────────
def load_db():
    db = {"issued": {}, "used_codes": [], "pending": {}, "orders": {}, "next_inv": 1000}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            db = json.load(f)
    db.setdefault("issued", {}); db.setdefault("used_codes", []); db.setdefault("pending", {})
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
            InlineKeyboardButton("Открыть CLARITY →", url=app_link(code))
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
        InlineKeyboardButton(("💳 Купить за %s ₽" % PRICE) if PAID else "🔑 Получить код", callback_data="get_code")
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
            InlineKeyboardButton("Открыть CLARITY →", url=app_link(code))
        ]])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    if PAID:
        await send_buy_prompt(update.message)
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
        InlineKeyboardButton("Открыть CLARITY →", url=app_link(code))
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
        InlineKeyboardButton(("Купить за %s ₽ →" % PRICE) if PAID else "Получить код →", callback_data="get_code"),
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
            InlineKeyboardButton("Открыть CLARITY →", url=app_link(code))
        ]])
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    if PAID:
        await send_buy_prompt(query.message)
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
        InlineKeyboardButton("Открыть CLARITY →", url=app_link(code))
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


# ── ОПЛАТА: ручное подтверждение ────────────────────────────────────
INSTALL_TEXT = (
    "📲 <b>Как установить на экран:</b>\n\n"
    "<b>iPhone:</b> открой ссылку в Safari → Поделиться ↑ → «На экран «Домой»»\n\n"
    "<b>Android:</b> открой в Chrome → три точки ⋮ → «Добавить на главный экран»\n\n"
    "💡 Если приложение снова просит код — нажми «Открыть CLARITY →» в этом чате: вход произойдёт автоматически."
)

def _rk_hash(*parts):
    return getattr(hashlib, RK_HASH)(":".join(parts).encode("utf-8")).hexdigest()


def rk_link(inv: int) -> str:
    out = f"{float(PRICE):.2f}"
    q = {
        "MerchantLogin": RK_LOGIN,
        "OutSum": out,
        "InvId": inv,
        "Description": "CLARITY - доступ к приложению",
        "SignatureValue": _rk_hash(RK_LOGIN, out, str(inv), RK_PASS1),
        "Culture": "ru",
    }
    if RK_TEST:
        q["IsTest"] = 1
    return "https://auth.robokassa.ru/Merchant/Index.aspx?" + urlencode(q)


async def send_robokassa_prompt(msg):
    uid = str(msg.chat.id)
    db = load_db()
    now = time.time()
    inv = None
    for i, o in db["orders"].items():  # переиспользуем свежий неоплаченный счёт
        if o["uid"] == uid and o["status"] == "new" and now - o["ts"] < 3600:
            inv = int(i)
            break
    if inv is None:
        inv = db["next_inv"]
        db["next_inv"] = inv + 1
        db["orders"][str(inv)] = {"uid": uid, "ts": now, "status": "new"}
        save_db(db)
    text = (
        f"💳 <b>CLARITY — {PRICE} ₽, один раз и навсегда</b>\n\n"
        f"Нажми «Оплатить», выбери удобный способ (карта, СБП). "
        f"Как только платёж пройдёт, код придёт сюда автоматически.\n\n"
        f"Если за пару минут код не пришёл — напиши @clarityapp."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"Оплатить {PRICE} ₽", url=rk_link(inv))]])
    await msg.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def rk_result(request):
    """Уведомление Robokassa об оплате (Result URL). Выдаёт код после проверки подписи."""
    from aiohttp import web
    data = await request.post() if request.method == "POST" else request.query
    out, inv, sig = data.get("OutSum", ""), data.get("InvId", ""), data.get("SignatureValue", "")
    # Если в Result URL добавлены Shp_ параметры, их надо включить в подпись (по алфавиту).
    shp = sorted((k, v) for k, v in data.items() if k.lower().startswith("shp_"))
    expect = _rk_hash(out, inv, RK_PASS2, *[f"{k}={v}" for k, v in shp])
    if not hmac.compare_digest(sig.lower(), expect.lower()):
        logging.warning("Robokassa: неверная подпись, InvId=%s", inv)
        return web.Response(status=400, text="bad signature")
    db = load_db()
    order = db["orders"].get(inv)
    if not order:
        logging.warning("Robokassa: неизвестный счёт %s", inv)
        return web.Response(status=404, text="unknown order")
    try:
        if abs(float(out) - float(PRICE)) > 0.01:
            logging.warning("Robokassa: сумма %s не совпадает с ценой", out)
            return web.Response(status=400, text="bad amount")
    except ValueError:
        return web.Response(status=400, text="bad amount")
    bot = request.app["bot"]
    uid = order["uid"]
    order["status"] = "paid"
    save_db(db)
    try:
        code = await give_code(bot, uid)
        note = f"✅ Код выдан: {code}" if code else "⚠️ ОПЛАЧЕНО, но коды закончились! Добавь коды и отправь /grant " + uid
    except Exception as e:
        note = f"⚠️ Оплачено, но код не доставлен ({e}). Отправь /grant {uid}"
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin, text=f"💰 Оплата {out} ₽ · счёт {inv} · пользователь {uid}\n{note}")
        except Exception:
            pass
    return web.Response(text=f"OK{inv}")


async def start_web(app):
    """Запускает маленький веб-сервер для уведомлений Robokassa рядом с ботом."""
    from aiohttp import web
    w = web.Application()
    w["bot"] = app.bot
    w.router.add_route("*", "/robokassa/result", rk_result)
    w.router.add_get("/", lambda r: web.Response(text="CLARITY bot OK"))
    runner = web.AppRunner(w)
    await runner.setup()
    port = int(os.environ.get("PORT", "8080"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info("Веб-сервер для Robokassa запущен на порту %s", port)


async def send_buy_prompt(msg):
    if RK:
        await send_robokassa_prompt(msg)
        return
    uid = msg.chat.id
    text = (
        f"💳 <b>CLARITY — {PRICE} ₽, один раз и навсегда</b>\n\n"
        f"Переведи {PRICE} ₽ по реквизитам:\n<code>{PAY_DETAILS}</code>\n\n"
        f"В комментарии к переводу напиши: <code>CL{str(uid)[-5:]}</code>\n\n"
        f"После оплаты нажми кнопку ниже и пришли скриншот или чек. "
        f"Я проверю платёж и сразу пришлю твой код."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid")]])
    await msg.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def btn_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📸 Пришли сюда скриншот или чек оплаты (фото или файл) одним сообщением.")


async def handle_proof(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Фото/файл от пользователя → админу с кнопками «Выдать код / Отклонить»."""
    if not PAID or RK:
        return
    user = update.effective_user
    msg = update.message
    if user.id in ADMIN_IDS:
        return
    db = load_db()
    uid = str(user.id)
    if uid in db["issued"]:
        await msg.reply_text("У тебя уже есть код — отправь /code, я пришлю его снова.")
        return
    last = db["pending"].get(uid, 0)
    if time.time() - last < PENDING_TTL:
        await msg.reply_text("⏳ Заявка уже отправлена, я проверяю платёж. Обычно это быстро.")
        return
    db["pending"][uid] = time.time()
    save_db(db)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Выдать код", callback_data=f"ok:{uid}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"no:{uid}"),
    ]])
    who = f"{user.full_name} @{user.username}" if user.username else user.full_name
    cap = f"💰 Оплата {PRICE} ₽?\nОт: {who}\nID: {uid}\nКомментарий должен быть: CL{uid[-5:]}"
    sent = 0
    for admin in ADMIN_IDS:
        try:
            await ctx.bot.copy_message(chat_id=admin, from_chat_id=msg.chat_id,
                                       message_id=msg.message_id, caption=cap, reply_markup=kb)
            sent += 1
        except Exception:
            logging.exception("не удалось отправить заявку админу")
    if sent:
        await msg.reply_text("📨 Принято! Проверю платёж и пришлю код в этом чате.")
    else:
        await msg.reply_text("Не удалось передать заявку. Напиши @clarityapp.")


async def give_code(bot, uid: str):
    """Выдать (или повторно прислать) код пользователю. Возвращает (код|None)."""
    db = load_db()
    code = db["issued"].get(uid)
    if not code:
        code = get_free_code(db)
        if not code:
            return None
        db["issued"][uid] = code
        db["used_codes"].append(code)
    db["pending"].pop(uid, None)
    save_db(db)
    text = (
        f"✅ Оплата подтверждена. Спасибо!\n\nТвой код:\n<code>{code}</code>\n\n"
        f"Нажми на код чтобы скопировать → открой приложение → введи код при первом входе.\n\n"
        + INSTALL_TEXT
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Открыть CLARITY →", url=app_link(code))]])
    await bot.send_message(chat_id=int(uid), text=text, parse_mode="HTML", reply_markup=kb)
    return code


async def btn_admin_decision(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Нет доступа", show_alert=True)
        return
    await query.answer()
    action, uid = query.data.split(":", 1)
    if action == "ok":
        try:
            code = await give_code(ctx.bot, uid)
        except Exception as e:
            await query.edit_message_caption(caption=(query.message.caption or "") + f"\n\n⚠️ Не доставлено: {e}")
            return
        if code is None:
            await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n⚠️ Коды закончились!")
            return
        await query.edit_message_caption(caption=(query.message.caption or "") + f"\n\n✅ Код выдан: {code}")
    else:
        db = load_db()
        db["pending"].pop(uid, None)
        save_db(db)
        try:
            await ctx.bot.send_message(chat_id=int(uid), text=(
                "Не смог подтвердить платёж. Проверь сумму и комментарий и пришли скриншот ещё раз, "
                "или напиши @clarityapp."))
        except Exception:
            pass
        await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n❌ Отклонено")


async def cmd_grant(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/grant <id пользователя> — выдать код вручную (только админ)."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа.")
        return
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Использование: /grant <ID пользователя>")
        return
    try:
        code = await give_code(ctx.bot, ctx.args[0])
    except Exception as e:
        await update.message.reply_text(f"⚠️ Не доставлено: {e}")
        return
    await update.message.reply_text(f"✅ Выдан: {code}" if code else "⚠️ Коды закончились.")


# ── MAIN ────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.INFO
    )

    builder = Application.builder().token(TOKEN)
    if RK:
        builder = builder.post_init(start_web)
    app = builder.build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("install", cmd_install))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("code", cmd_code))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(btn_get_code, pattern="^get_code$"))
    app.add_handler(CallbackQueryHandler(btn_install_help, pattern="^install_help$"))
    app.add_handler(CommandHandler("grant", cmd_grant))
    app.add_handler(CallbackQueryHandler(btn_paid, pattern="^paid$"))
    app.add_handler(CallbackQueryHandler(btn_admin_decision, pattern="^(ok|no):\\d+$"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_proof))

    print("✅ CLARITY Bot запущен. Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
