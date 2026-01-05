# main.py — Ведьмак 3.0: Визитка + Курьеры + Казино + Игры
import os
import re
import asyncio
import json
import random
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import InviteToChannelRequest
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler, ConversationHandler
)

# === 🔐 КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8299876582:AAEkQUUa-8PQS2f9snMdEze8wg-OXFpWo4I"
API_ID = 26544586
API_HASH = "df66008b91f7f30e9d59fa279c0963a7"
MANAGER_ID = 7200996688
TARGET_CHANNEL = "https://t.me/+qqy_UijRlqtkZWIx"
CHANNEL_USERNAME = "qqy_UijRlqtkZWIx"

# === 🗃️ ФАЙЛЫ ===
USERS_FILE = "users.json"
FORMS_FILE = "forms.json"
BALANCES_FILE = "balances.json"

# === 🎰 КАЗИНО ===
WIN_PROBABILITY = 0.05  # 5% шанс выигрыша
HOUSE_EDGE = 0.95       # Казино всегда в плюсе

# === FSM СОСТОЯНИЯ ===
FORM_NAME, FORM_CITY, FORM_PHONE = range(3)
CASINO_BET = range(1)

def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_balance(user_id):
    balances = load_json(BALANCES_FILE)
    return balances.get(str(user_id), 0.0)

def set_balance(user_id, amount):
    balances = load_json(BALANCES_FILE)
    balances[str(user_id)] = round(amount, 2)
    save_json(BALANCES_FILE, balances)

# === 🧙‍♂️ TELETHON ===
telethon_client = None

async def get_telethon_client():
    global telethon_client
    if telethon_client is None:
        telethon_client = Telegram Office('session', API_ID, API_HASH)
        await telethon_client.start()
    return telethon_client

# === 🖼️ ВИЗИТКА (красивая, цифровая) ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nickname = f"@{user.username}" if user.username else f"ID{user.id}"
    
    # Сохраняем пользователя
    users = load_json(USERS_FILE)
    if str(user.id) not in users:
        users[str(user.id)] = {
            "nickname": nickname,
            "joined": datetime.now().isoformat()
        }
        save_json(USERS_FILE, users)
        
        # Уведомляем менеджера
        try:
            await context.bot.send_message(
                chat_id=MANAGER_ID,
                text=f"🔔 Новый контакт!\n{nickname} нажал /start"
            )
        except:
            pass
    
    # Красивая визитка
    await update.message.reply_text(
        "🧙‍♂️ <b>ДОБРО ПОЖАЛОВАТЬ В CHAPODAY!</b>\n\n"
        "✨ <b>Мы — цифровая платформа будущего:</b>\n"
        "✅ <b>Работа:</b> Только курьеры (до 1500₽/день)\n"
        "🎰 <b>Игры:</b> Казино, рулетка, лотерея\n"
        "💼 <b>Товары:</b> Быстро и анонимно\n\n"
        "👇 Выбери действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💼 Курьер", callback_data='courier')],
            [InlineKeyboardButton("🎰 Казино", callback_data='casino')],
            [InlineKeyboardButton("🎮 Игры", callback_data='games')],
            [InlineKeyboardButton("📞 Контакты", callback_data='contacts')]
        ])
    )

# === 💼 ВАКАНСИИ (только курьер) ===
async def courier_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📦 <b>ВАКАНСИЯ: КУРЬЕР</b>\n\n"
        "💰 <b>Доход:</b> до 1500₽/день\n"
        "🕒 <b>График:</b> гибкий (2-6 часов/день)\n"
        "📍 <b>Требования:</b>\n"
        "• Возраст от 18 лет\n"
        "• Смартфон с Telegram\n"
        "• Ответственность\n\n"
        "📝 Чтобы подать заявку — нажми 'Подать заявку'",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Подать заявку", callback_data='apply_courier')],
            [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
        ])
    )

async def apply_courier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✍️ Как тебя зовут?")
    context.user_data['applying'] = True
    return FORM_NAME

# === 🎰 КАЗИНО (5% шанс, всегда в плюсе) ===
async def casino_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    balance = get_balance(query.from_user.id)
    await query.edit_message_text(
        f"💰 <b>Твой баланс:</b> {balance}₽\n\n"
        "🎰 <b>Сделай ставку:</b>\n"
        "• Минимум: 10₽\n"
        "• Шанс выигрыша: 5%\n"
        "• Выигрыш: x20 от ставки\n\n"
        "👇 Введи сумму ставки:",
        parse_mode="HTML"
    )
    context.user_data['awaiting_bet'] = True

async def handle_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_bet'):
        return
    
    try:
        bet = float(update.message.text)
        user_id = update.effective_user.id
        balance = get_balance(user_id)
        
        if bet < 10:
            await update.message.reply_text("❌ Минимальная ставка — 10₽")
            return
        if bet > balance:
            await update.message.reply_text("❌ Недостаточно средств")
            return
        
        # Снимаем ставку
        set_balance(user_id, balance - bet)
        
        # 5% шанс выигрыша
        if random.random() < WIN_PROBABILITY:
            win = bet * 20 * HOUSE_EDGE
            set_balance(user_id, get_balance(user_id) + win)
            await update.message.reply_text(
                f"🎉 <b>ПОБЕДА!</b>\n"
                f"Ты выиграл {win:.2f}₽!",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                "💀 <b>Проигрыш</b>\n"
                "Повезёт в следующий раз!",
                parse_mode="HTML"
            )
    except ValueError:
        await update.message.reply_text("❌ Введи число")
    
    context.user_data['awaiting_bet'] = False

# === 🎮 ИГРЫ ===
async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎮 <b>Игры</b>\n\n"
        "• <b>Рулетка:</b> Угадай цвет (красный/чёрный)\n"
        "• <b>Лотерея:</b> Купон на товар\n"
        "• <b>Кости:</b> Угадай сумму",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Рулетка", callback_data='roulette')],
            [InlineKeyboardButton("🎫 Лотерея", callback_data='lottery')],
            [InlineKeyboardButton("🎲 Кости", callback_data='dice')],
            [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
        ])
    )

# === 📞 КОНТАКТЫ ===
async def contacts_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📞 <b>КОНТАКТЫ</b>\n\n"
        "• <b>Поддержка:</b> @chapoday_support\n"
        "• <b>Работа:</b> @chapoday_hr\n"
        "• <b>Email:</b> hr@chapoday.ru",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
        ])
    )

# === ГЛАВНОЕ МЕНЮ ===
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "🧙‍♂️ <b>ДОБРО ПОЖАЛОВАТЬ В CHAPODAY!</b>\n\n"
            "👇 Выбери действие:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💼 Курьер", callback_data='courier')],
                [InlineKeyboardButton("🎰 Казино", callback_data='casino')],
                [InlineKeyboardButton("🎮 Игры", callback_data='games')],
                [InlineKeyboardButton("📞 Контакты", callback_data='contacts')]
            ])
        )

# === ОБРАБОТКА КНОПОК ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'courier':
        await courier_info(update, context)
    elif query.data == 'apply_courier':
        await apply_courier(update, context)
    elif query.data == 'casino':
        await casino_menu(update, context)
    elif query.data == 'games':
        await games_menu(update, context)
    elif query.data == 'contacts':
        await contacts_info(update, context)
    elif query.data == 'main_menu':
        await main_menu(update, context)
    elif query.data == 'roulette':
        await query.edit_message_text("🎲 Рулетка пока недоступна")
    elif query.data == 'lottery':
        await query.edit_message_text("🎫 Лотерея скоро будет")
    elif query.data == 'dice':
        await query.edit_message_text("🎲 Кости в разработке")

# === ОБРАБОТКА СООБЩЕНИЙ ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработка ставок
    if context.user_data.get('awaiting_bet'):
        await handle_bet(update, context)
        return
    
    # Обработка анкеты
    if context.user_data.get('applying'):
        # Здесь можно добавить полную анкету
        await update.message.reply_text("✅ Заявка принята! Ожидай ответа.")
        context.user_data['applying'] = False
        return
    
    # Пересылка менеджеру
    if update.effective_user.id != MANAGER_ID:
        try:
            await context.bot.send_message(
                chat_id=MANAGER_ID,
                text=f"От {update.effective_user.username or update.effective_user.id}:\n{update.message.text}"
            )
        except:
            pass
        await update.message.reply_text("✅ Сообщение отправлено!")

# === 🚀 ЗАПУСК ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Визитка
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Обычные сообщения
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    print("✅ Ведьмак 3.0 запущен!")
    print("🔹 Визитка: /start")
    print("🔸 Казино: 5% шанс, всегда в плюсе")
    app.run_polling()

if __name__ == '__main__':
    main()