import asyncio
import json
import os
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

API_ID = 22376342
API_HASH = 'f623dc4ae2b015463cfde7874ab0f270'
BOT_TOKEN = '8428497737:AAFPwtkZHsZKDjvuoaUwnb2E_qTr3rSa3rc'

DB_FILE = 'users_data.json'
bot = AsyncTeleBot(BOT_TOKEN)
user_states = {}
active_tasks = {}

# --- БАЗА ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- КЛАВИАТУРЫ ---
def main_menu(authorized):
    if authorized:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Мои чаты", callback_data='chats_menu')],
            [InlineKeyboardButton("📝 Текст рассылки", callback_data='set_text'),
             InlineKeyboardButton("⏱ Интервал", callback_data='set_delay')],
            [InlineKeyboardButton("▶️ ЗАПУСТИТЬ", callback_data='start_spam'),
             InlineKeyboardButton("⏹ ОСТАНОВИТЬ", callback_data='stop_spam')],
            [InlineKeyboardButton("📊 Статус", callback_data='status')],
            [InlineKeyboardButton("🔄 Перелогиниться", callback_data='relogin')]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 ВОЙТИ В АККАУНТ", callback_data='login')],
            [InlineKeyboardButton("ℹ️ Что это?", callback_data='about')]
        ])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back_main')]])

def chats_menu_keyboard(chats):
    chat_list = '\n'.join([f"• {c}" for c in chats]) if chats else "пусто"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить чат", callback_data='add_chat')],
        [InlineKeyboardButton("🗑 Очистить всё", callback_data='clear_chats')],
        [InlineKeyboardButton("🔙 В меню", callback_data='back_main')]
    ]), chat_list

# --- РАССЫЛКА ---
async def spam_loop(session_str, user_id):
    global active_tasks
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error(f"Сессия {user_id} недействительна")
            return
        
        db = load_db()
        user = db.get(str(user_id), {})
        chats = user.get('chats', [])
        text = user.get('message', 'Привет! ✌️')
        delay = user.get('delay', 300)
        
        await client.send_message('me', f"✅ Рассылка запущена! Сообщение будет отправляться каждые {delay} сек")
        
        iteration = 0
        while True:
            if str(user_id) not in active_tasks:
                break
            
            # Обновляем настройки из базы (могли измениться)
            db = load_db()
            user = db.get(str(user_id), {})
            chats = user.get('chats', chats)
            text = user.get('message', text)
            delay = user.get('delay', delay)
            
            if not chats:
                await asyncio.sleep(30)
                continue
            
            iteration += 1
            logger.info(f"📤 Рассылка #{iteration} для {user_id} | Чатов: {len(chats)}")
            
            for chat in chats:
                try:
                    await client.send_message(chat, text)
                    logger.info(f"  ✅ Отправлено в {chat}")
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.warning(f"  ❌ {chat}: {e}")
                    await asyncio.sleep(1)
            
            await asyncio.sleep(delay)
    except Exception as e:
        logger.error(f"Рассылка {user_id} упала: {e}")
    finally:
        await client.disconnect()
        active_tasks.pop(str(user_id), None)

# --- ОБРАБОТКА ВХОДА ---
async def handle_login_step(msg):
    uid = str(msg.from_user.id)
    state = user_states.get(uid, {})
    step = state.get('step')
    
    if step == 'waiting_phone':
        phone = msg.text.strip()
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            sent = await client.send_code_request(phone)
            state['client'] = client
            state['phone'] = phone
            state['phone_code_hash'] = sent.phone_code_hash
            state['step'] = 'waiting_code'
            user_states[uid] = state
            await bot.send_message(msg.chat.id, "📱 Код отправлен! Введи его:", reply_markup=back_keyboard())
        except Exception as e:
            await bot.send_message(msg.chat.id, f"❌ Ошибка: {e}\nПопробуй ещё раз /login")
            del user_states[uid]
    
    elif step == 'waiting_code':
        code = msg.text.strip()
        client = state['client']
        try:
            await client.sign_in(phone=state['phone'], code=code, phone_code_hash=state['phone_code_hash'])
        except SessionPasswordNeededError:
            state['step'] = 'waiting_2fa'
            user_states[uid] = state
            await bot.send_message(msg.chat.id, "🔒 Введи облачный пароль (2FA):", reply_markup=back_keyboard())
            return
        
        await finish_login(uid, client, msg.chat.id)
    
    elif step == 'waiting_2fa':
        password = msg.text.strip()
        client = state['client']
        try:
            await client.sign_in(password=password)
        except Exception as e:
            await bot.send_message(msg.chat.id, f"❌ Неверный пароль: {e}")
            return
        
        await finish_login(uid, client, msg.chat.id)

async def finish_login(uid, client, chat_id):
    session_str = client.session.save()
    me = await client.get_me()
    
    db = load_db()
    db[uid] = {'session': session_str, 'chats': [], 'message': 'Привет! ✌️', 'delay': 300}
    save_db(db)
    
    del user_states[uid]
    await client.disconnect()
    
    await bot.send_message(chat_id, 
        f"✅ Успешный вход как @{me.username or me.first_name}!\n"
        "Теперь настрой рассылку:",
        reply_markup=main_menu(True))

# --- ОБРАБОТЧИКИ КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
async def handle_callback(call):
    uid = str(call.from_user.id)
    db = load_db()
    user = db.get(uid, {})
    is_auth = 'session' in user
    
    data = call.data
    
    if data == 'login':
        user_states[uid] = {'step': 'waiting_phone'}
        await bot.edit_message_text(
            "📱 Введи номер телефона (с +):\nПример: +79991234567",
            call.message.chat.id, call.message.message_id,
            reply_markup=back_keyboard())
    
    elif data == 'relogin':
        user_states[uid] = {'step': 'waiting_phone'}
        await bot.edit_message_text(
            "📱 Введи номер телефона заново:",
            call.message.chat.id, call.message.message_id,
            reply_markup=back_keyboard())
    
    elif data == 'about':
        await bot.edit_message_text(
            "🤖 Этот бот позволяет запустить рассылку от твоего лица.\n"
            "Ты входишь в аккаунт — бот сохраняет сессию и шлёт сообщения куда скажешь.\n\n"
            "🚫 Твой номер и пароль никуда не передаются кроме серверов Telegram.",
            call.message.chat.id, call.message.message_id,
            reply_markup=back_keyboard())
    
    elif data == 'chats_menu':
        if not is_auth:
            await bot.answer_callback_query(call.id, "❌ Сначала войди!")
            return
        chats = user.get('chats', [])
        kb, chat_list = chats_menu_keyboard(chats)
        await bot.edit_message_text(
            f"💬 Твои чаты:\n{chat_list}",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb)
    
    elif data == 'add_chat':
        user_states[uid] = {'step': 'adding_chat'}
        await bot.edit_message_text(
            "➕ Отправь @username или ссылку на чат:",
            call.message.chat.id, call.message.message_id,
            reply_markup=back_keyboard())
    
    elif data == 'clear_chats':
        if is_auth:
            db[uid]['chats'] = []
            save_db(db)
            await bot.answer_callback_query(call.id, "✅ Чаты очищены!")
            await bot.edit_message_text(
                "💬 Твои чаты:\nпусто",
                call.message.chat.id, call.message.message_id,
                reply_markup=chats_menu_keyboard([])[0])
    
    elif data == 'set_text':
        user_states[uid] = {'step': 'setting_text'}
        await bot.edit_message_text(
            "📝 Отправь текст для рассылки:",
            call.message.chat.id, call.message.message_id,
            reply_markup=back_keyboard())
    
    elif data == 'set_delay':
        user_states[uid] = {'step': 'setting_delay'}
        await bot.edit_message_text(
            "⏱ Отправь интервал в секундах (30-3600):",
            call.message.chat.id, call.message.message_id,
            reply_markup=back_keyboard())
    
    elif data == 'start_spam':
        if not is_auth:
            await bot.answer_callback_query(call.id, "❌ Сначала войди!")
            return
        if not user.get('chats'):
            await bot.answer_callback_query(call.id, "❌ Добавь чаты!")
            return
        
        active_tasks[str(uid)] = True
        asyncio.create_task(spam_loop(user['session'], uid))
        await bot.edit_message_text(
            f"🚀 Рассылка запущена!\nЧатов: {len(user['chats'])}\nИнтервал: {user['delay']}с",
            call.message.chat.id, call.message.message_id,
            reply_markup=main_menu(True))
    
    elif data == 'stop_spam':
        active_tasks.pop(str(uid), None)
        await bot.edit_message_text(
            "⏹ Рассылка остановлена",
            call.message.chat.id, call.message.message_id,
            reply_markup=main_menu(True))
    
    elif data == 'status':
        if not is_auth:
            await bot.answer_callback_query(call.id, "❌ Сначала войди!")
            return
        is_active = str(uid) in active_tasks
        await bot.edit_message_text(
            f"📊 СТАТУС\n"
            f"• Аккаунт: привязан ✅\n"
            f"• Рассылка: {'🟢 Активна' if is_active else '🔴 Остановлена'}\n"
            f"• Чатов: {len(user.get('chats', []))}\n"
            f"• Текст: {user.get('message', 'не задан')}\n"
            f"• Интервал: {user.get('delay', 300)}с",
            call.message.chat.id, call.message.message_id,
            reply_markup=main_menu(True))
    
    elif data == 'back_main':
        await bot.edit_message_text(
            "🏠 Главное меню\nЧто делаем?",
            call.message.chat.id, call.message.message_id,
            reply_markup=main_menu(is_auth))

# --- ОБРАБОТЧИК ТЕКСТА ---
@bot.message_handler(func=lambda m: True)
async def handle_text(msg):
    uid = str(msg.from_user.id)
    state = user_states.get(uid, {})
    step = state.get('step')
    
    if step in ['waiting_phone', 'waiting_code', 'waiting_2fa']:
        await handle_login_step(msg)
        return
    
    elif step == 'adding_chat':
        chat = msg.text.strip()
        db = load_db()
        if uid in db:
            if chat not in db[uid].get('chats', []):
                db[uid]['chats'] = db[uid].get('chats', []) + [chat]
                save_db(db)
                await bot.send_message(msg.chat.id, f"✅ {chat} добавлен!", reply_markup=main_menu(True))
            else:
                await bot.send_message(msg.chat.id, "⚠️ Уже в списке", reply_markup=main_menu(True))
        del user_states[uid]
        return
    
    elif step == 'setting_text':
        text = msg.text.strip()
        db = load_db()
        if uid in db:
            db[uid]['message'] = text
            save_db(db)
            await bot.send_message(msg.chat.id, f"✅ Текст сохранён: {text}", reply_markup=main_menu(True))
        del user_states[uid]
        return
    
    elif step == 'setting_delay':
        try:
            delay = int(msg.text.strip())
            if 30 <= delay <= 3600:
                db = load_db()
                if uid in db:
                    db[uid]['delay'] = delay
                    save_db(db)
                    await bot.send_message(msg.chat.id, f"✅ Интервал: {delay}с", reply_markup=main_menu(True))
            else:
                await bot.send_message(msg.chat.id, "❌ От 30 до 3600!", reply_markup=back_keyboard())
                return
        except:
            await bot.send_message(msg.chat.id, "❌ Число отправь!", reply_markup=back_keyboard())
            return
        del user_states[uid]
        return
    
    # Если нет активного шага — показываем меню
    db = load_db()
    is_auth = 'session' in db.get(uid, {})
    await bot.send_message(msg.chat.id, "🏠 Главное меню", reply_markup=main_menu(is_auth))

# --- СТАРТ ---
@bot.message_handler(commands=['start'])
async def start_cmd(msg):
    uid = str(msg.from_user.id)
    db = load_db()
    is_auth = 'session' in db.get(uid, {})
    
    await bot.send_message(msg.chat.id,
        "👋 Привет! Я бот для авторассылки.\n"
        "Войди в аккаунт и настрой spam по любым чатам.",
        reply_markup=main_menu(is_auth))

# --- ВОССТАНОВЛЕНИЕ РАССЫЛОК ПРИ ЗАПУСКЕ ---
async def restore_spam():
    db = load_db()
    for uid, user in db.items():
        if 'session' in user and user.get('chats'):
            active_tasks[uid] = True
            asyncio.create_task(spam_loop(user['session'], uid))
            logger.info(f"♻ Восстановлена рассылка для {uid}")

async def main():
    logger.info("🤖 Бот стартует...")
    
    # Восстанавливаем все активные рассылки
    await restore_spam()
    
    await bot.polling(non_stop=True)

if __name__ == '__main__':
    asyncio.run(main())
