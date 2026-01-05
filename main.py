# main.py — Ведьмак v12.0: Визитка + Управление + Анкета + 24/7
import os
import re
import asyncio
import json
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError
from telethon.tl.functions.channels import InviteToChannelRequest
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler, ConversationHandler
)

# === 🔐 КОНФИГУРАЦИЯ (ЗАМЕНИ ТОЛЬКО ЭТИ СТРОКИ) ===
BOT_TOKEN = "8299876582:AAEkQUUa-8PQS2f9snMdEze8wg-OXFpWo4I"  # ← ТОКЕН БОТА-ВИЗИТКИ
API_ID = 26544586          # ← Твой API_ID с my.telegram.org
API_HASH = "df66008b91f7f30e9d59fa279c0963a7"  # ← Твой API_HASH
MANAGER_ID = 7200996688    # ← Твой ID (узнай в @userinfobot)
TARGET_CHANNEL = "https://t.me/+qqy_UijRlqtkZWIx"  # ← Ссылка на твой канал
CHANNEL_USERNAME = "qqy_UijRlqtkZWIx"  # ← Часть после + (без +)

# === 🗃️ ФАЙЛЫ ===
USERS_FILE = "users.json"
PARSED_FILE = "parsed.json"
FORMS_FILE = "forms.json"

# === 🛡️ БЕЗОПАСНОСТЬ ===
ANTI_SPAM_DELAY = 3
MAX_INVITES_PER_HOUR = 15

# FSM СОСТОЯНИЯ
FORM_NAME, FORM_AGE, FORM_CITY, FORM_EXPERIENCE = range(4)

def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# === 🧙‍♂️ TELETHON ===
telethon_client = None

async def get_telethon_client():
    global telethon_client
    if telethon_client is None:
        telethon_client = TelegramClient('session', API_ID, API_HASH)
        await telethon_client.start()
    return telethon_client

# === 🔐 УПРАВЛЕНИЕ (только для менеджера) ===
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MANAGER_ID:
        return
    keyboard = [
        [InlineKeyboardButton("📊 Статус", callback_data='status')],
        [InlineKeyboardButton("🔍 Парсинг", callback_data='parse_prompt')],
        [InlineKeyboardButton("📥 Добавить в канал", callback_data='invite_start')],
        [InlineKeyboardButton("🔄 Уведомить", callback_data='notify_prompt')],
        [InlineKeyboardButton("📋 Анкеты", callback_data='forms_list')],
        [InlineKeyboardButton("👥 База", callback_data='users_list')]
    ]
    await update.message.reply_text(
        "🧙‍♂️ Меню управления Ведьмаком",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != MANAGER_ID:
        return

    if query.data == 'status':
        users = load_json(USERS_FILE)
        parsed = load_json(PARSED_FILE)
        forms = load_json(FORMS_FILE)
        await query.edit_message_text(
            f"📊 Статус системы:\n"
            f"👥 Контактов: {len(users)}\n"
            f"🔍 В базе парсинга: {len(parsed)}\n"
            f"📋 Анкет: {len(forms)}"
        )
    elif query.data == 'parse_prompt':
        await query.edit_message_text("Введите @username чата для парсинга:")
        context.user_data['awaiting_parse'] = True
    elif query.data == 'invite_start':
        parsed = load_json(PARSED_FILE)
        if not parsed:
            await query.edit_message_text("❌ База пуста. Сначала запустите парсинг.")
            return
        await query.edit_message_text(f"Добавить {min(len(parsed), MAX_INVITES_PER_HOUR)} юзеров в канал?")
        keyboard = [
            [InlineKeyboardButton("✅ Да", callback_data='invite_confirm')],
            [InlineKeyboardButton("❌ Нет", callback_data='admin_menu')]
        ]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
    elif query.data == 'notify_prompt':
        await query.edit_message_text("Введите текст для рассылки:")
        context.user_data['awaiting_notify'] = True
    elif query.data == 'forms_list':
        forms = load_json(FORMS_FILE)
        text = "📋 Анкеты:\n"
        for user_id, data in list(forms.items())[:10]:
            text += f"• {data['name']} - {data['city']}\n"
        await query.edit_message_text(text or "Нет анкет")
    elif query.data == 'users_list':
        users = load_json(USERS_FILE)
        await query.edit_message_text(f"👥 Всего контактов: {len(users)}")

# === ✅ ВИЗИТКА (для всех) ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else f"ID{user.id}"

    # Сохраняем пользователя
    users = load_json(USERS_FILE)
    if str(user.id) not in users:
        users[str(user.id)] = {
            "username": username,
            "joined": datetime.now().isoformat()
        }
        save_json(USERS_FILE, users)

        # Уведомляем менеджера
        try:
            await context.bot.send_message(
                chat_id=MANAGER_ID,
                text=f"🔔 Новый контакт!\n{username} нажал /start"
            )
        except:
            pass

    # Отвечаем клиенту
    await update.message.reply_text(
        "🧙‍♂️ Привет! Я — ассистент магазина CHAPODAY.\n\n"
        "✨ Мы снова работаем!\n"
        "🤝 Присоединяйся к нам: https://t.me/+qqy_UijRlqtkZWIx\n\n"
        "💬 Есть вопросы? Напиши их здесь — ответим в течение часа!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💼 Работа", callback_data='job_info')],
            [InlineKeyboardButton("📲 Контакты", callback_data='contact_info')]
        ])
    )

async def client_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'job_info':
        await query.edit_message_text(
            "💼 У нас есть вакансии:\n"
            "• Менеджер по продажам\n"
            "• Курьер\n"
            "• Оператор чата\n\n"
            "📝 Чтобы подать заявку, напиши «Хочу работать»"
        )
    elif query.data == 'contact_info':
        await query.edit_message_text(
            "📬 Наши контакты:\n"
            "• Telegram: @your_manager\n"
            "• Email: hr@chapoday.ru"
        )

# === 📋 АНКЕТИРОВАНИЕ ===
async def form_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "хочу работать" in text or update.message.text == "📝 Подать заявку":
        await update.message.reply_text("✍️ Как тебя зовут?")
        return FORM_NAME
    return ConversationHandler.END

async def form_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("📅 Сколько тебе лет?")
    return FORM_AGE

async def form_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    await update.message.reply_text("🏙️ Из какого ты города?")
    return FORM_CITY

async def form_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['city'] = update.message.text
    await update.message.reply_text("💼 Расскажи о своём опыте работы:")
    return FORM_EXPERIENCE

async def form_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['experience'] = update.message.text
    user = update.effective_user

    # Сохраняем анкету
    forms = load_json(FORMS_FILE)
    forms[str(user.id)] = {
        "name": context.user_data['name'],
        "age": context.user_data['age'],
        "city": context.user_data['city'],
        "experience": context.user_data['experience'],
        "username": f"@{user.username}" if user.username else f"ID{user.id}",
        "submitted": datetime.now().isoformat()
    }
    save_json(FORMS_FILE, forms)

    # Уведомляем менеджера
    try:
        await context.bot.send_message(
            chat_id=MANAGER_ID,
            text=f"📋 Новая анкета!\n"
                 f"Имя: {context.user_data['name']}\n"
                 f"Город: {context.user_data['city']}\n"
                 f"Опыт: {context.user_data['experience'][:50]}..."
        )
    except:
        pass

    await update.message.reply_text("✅ Анкета отправлена! Мы свяжемся с тобой.")
    return ConversationHandler.END

# === ОБРАБОТКА СООБЩЕНИЙ ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Управление для менеджера
    if user_id == MANAGER_ID:
        if context.user_data.get('awaiting_parse'):
            context.user_data['awaiting_parse'] = False
            await parse_chat_manual(update, context, text.lstrip('@'))
            return
        elif context.user_data.get('awaiting_notify'):
            context.user_data['awaiting_notify'] = False
            await notify_manual(update, context, text)
            return
        elif text == "/admin":
            await admin_menu(update, context)
            return

    # Обработка анкеты от клиента
    if "хочу работать" in text.lower():
        await update.message.reply_text("✍️ Как тебя зовут?")
        return FORM_NAME

    # Пересылка менеджеру
    if user_id != MANAGER_ID:
        try:
            await context.bot.send_message(
                chat_id=MANAGER_ID,
                text=f"От {update.effective_user.username or user_id}:\n{text}"
            )
        except:
            pass
        await update.message.reply_text("✅ Сообщение отправлено! Ответим в ближайшее время.")

# === ФУНКЦИИ УПРАВЛЕНИЯ ===
async def parse_chat_manual(update, context, chat):
    await update.message.reply_text(f"🔍 Парсинг @{chat}...")
    try:
        client = await get_telethon_client()
        entity = await client.get_entity(chat)
        users = []
        async for user in client.iter_participants(entity, limit=200):
            if user.username and not user.bot:
                users.append(f"@{user.username}")

        parsed = load_json(PARSED_FILE)
        for u in users:
            parsed[u] = {"parsed_at": datetime.now().isoformat()}
        save_json(PARSED_FILE, parsed)

        await update.message.reply_text(f"✅ Найдено: {len(users)} юзеров")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def notify_manual(update, context, message):
    users = load_json(USERS_FILE)
    client = await get_telethon_client()
    sent = 0
    for user_data in users.values():
        username = user_data.get("username")
        if username and username.startswith("@"):
            try:
                await client.send_message(username, message)
                sent += 1
                await asyncio.sleep(ANTI_SPAM_DELAY)
            except:
                pass
    await update.message.reply_text(f"✅ Рассылка завершена! Отправлено: {sent}")

# === 🚀 ЗАПУСК ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Визитка
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(client_button_handler, pattern='job_info|contact_info'))

    # Управление (только для менеджера)
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Анкета
    form_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, form_start)],
        states={
            FORM_NAME: [MessageHandler(filters.TEXT, form_name)],
            FORM_AGE: [MessageHandler(filters.TEXT, form_age)],
            FORM_CITY: [MessageHandler(filters.TEXT, form_city)],
            FORM_EXPERIENCE: [MessageHandler(filters.TEXT, form_experience)]
        },
        fallbacks=[]
    )
    app.add_handler(form_handler)

    # Обычные сообщения
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("✅ Ведьмак v12.0 запущен!")
    print("🔹 Клиенты: /start")
    print("🔸 Менеджер: /admin")
    app.run_polling()

if __name__ == '__main__':
    main()