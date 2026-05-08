import asyncio, json, os, threading, logging, io
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
import qrcode

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

API_ID = 22376342
API_HASH = 'f623dc4ae2b015463cfde7874ab0f270'
BOT_TOKEN = '8428497737:AAFPwtkZHsZKDjvuoaUwnb2E_qTr3rSa3rc'
DB_FILE = 'users_data.json'

bot = AsyncTeleBot(BOT_TOKEN)
user_states = {}
active_tasks = {}

# --- Веб-сервер для Render ---
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

def run_web():
    port = int(os.environ.get('PORT', 8080))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# --- База ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f: return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=2, ensure_ascii=False)

# --- Приветственное сообщение ---
START_TEXT = """
✏️ 👋 Добро пожаловать в нашу систему!

Приветствуем тебя, дорогой пользователь! Ты попал в официальный бот-рассыльщик, созданный для тех, кто ценит эффективность и безопасность своей работы в Telegram. 🚀

📚 🛡 Почему нам можно доверять?
Мы знаем, как важна конфиденциальность в наше время. Именно поэтому наш инструмент:
⦁ Абсолютно прозрачен: Мы работаем на базе открытого исходного кода.
⦁ Безопасен: Бот НЕ ворует сессии и не хранит ваши личные данные в корыстных целях.
⦁ Open Source: Ты лично можешь убедиться в честности алгоритмов, заглянув в наш репозиторий на GitHub:
🔗 [Посмотреть код на GitHub](https://github.com/dlyapleeroka123-cyber/telegram-bot) 📁
————————

📚 👨‍💻 Наша команда
Над проектом трудились люди, которые горят своим делом:
⦁ Главный разработчик: За техническую магию и архитектуру бота отвечает @cf_mz — человек, воплотивший эту идею в жизнь. 🛠️
⦁ Поддержка и продвижение: Огромный вклад в развитие, тестирование и PR внес @ilialg. Благодаря ему о боте узнает всё больше профи! 📢
————————

📚 ✨ Начинаем?
Мы постарались сделать интерфейс максимально интуитивным, чтобы твои рассылки летели точно в цель. 🎯
Удачного пользования! Пусть этот инструмент станет твоим верным помощником в достижении крутых результатов. Если возникнут вопросы — мы всегда на связи! 🌟
"""

# --- Клавиатуры ---
def main_menu(authorized, accounts_count=0):
    kb = []
    if authorized:
        kb.append([InlineKeyboardButton("💬 Мои чаты", callback_data='chats_menu')])
        kb.append([InlineKeyboardButton("📝 Текст", callback_data='set_text'), InlineKeyboardButton("⏱ Интервал", callback_data='set_delay')])
        kb.append([InlineKeyboardButton("▶️ ЗАПУСТИТЬ", callback_data='start_spam'), InlineKeyboardButton("⏹ ОСТАНОВИТЬ", callback_data='stop_spam')])
        kb.append([InlineKeyboardButton("📊 Статус", callback_data='status')])
        kb.append([InlineKeyboardButton(f"👤 Аккаунты ({accounts_count}/3)", callback_data='accounts_list')])
    else:
        if accounts_count < 3:
            kb.append([InlineKeyboardButton("🔐 ВОЙТИ ЧЕРЕЗ QR", callback_data='login_qr')])
        if accounts_count > 0:
            kb.append([InlineKeyboardButton(f"👤 Аккаунты ({accounts_count}/3)", callback_data='accounts_list')])
    return InlineKeyboardMarkup(kb)

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back_main')]])

def chats_menu_keyboard(chats):
    cl = '\n'.join([f"• {c}" for c in chats]) if chats else "пусто"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить чат", callback_data='add_chat')],
        [InlineKeyboardButton("🗑 Очистить всё", callback_data='clear_chats')],
        [InlineKeyboardButton("🔙 В меню", callback_data='back_main')]
    ]), cl

# --- Логика рассылки ---
async def spam_loop(session_str, user_id, account_name):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    try:
        await client.connect()
        db = load_db()
        user = db.get(str(user_id), {}).get('accounts', {}).get(account_name, {})
        chats = user.get('chats', [])
        text = user.get('message', 'Привет!')
        delay = user.get('delay', 300)
        task_id = f"{user_id}_{account_name}"
        logger.info(f"Рассылка {task_id} | чатов: {len(chats)} | интервал: {delay}с")
        while task_id in active_tasks:
            db = load_db()
            user = db.get(str(user_id), {}).get('accounts', {}).get(account_name, {})
            chats = user.get('chats', chats)
            text = user.get('message', text)
            delay = user.get('delay', delay)
            for chat in chats:
                try:
                    await client.send_message(chat, text)
                    logger.info(f"✅ {chat}")
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.warning(f"❌ {chat}: {e}")
                    await asyncio.sleep(1)
            await asyncio.sleep(delay)
    except Exception as e:
        logger.error(f"Крах {user_id}_{account_name}: {e}")
    finally:
        await client.disconnect()
        active_tasks.pop(f"{user_id}_{account_name}", None)

def get_accounts(uid):
    db = load_db()
    return db.get(str(uid), {}).get('accounts', {})

# --- QR-вход ---
async def qr_login(uid, chat_id, acc_num):
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    qr_login = await client.qr_login()
    qr_url = qr_login.url
    
    qr = qrcode.QRCode()
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    await bot.send_photo(chat_id, buf, caption="📱 Отсканируй QR-код в приложении Telegram:\nНастройки → Устройства → Подключить устройство\n\nОжидаю вход...")
    
    try:
        await qr_login.wait(timeout=120)
        session_str = client.session.save()
        me = await client.get_me()
        
        db = load_db()
        if str(uid) not in db:
            db[str(uid)] = {'accounts': {}}
        acc_name = f"account_{acc_num}"
        db[str(uid)]['accounts'][acc_name] = {
            'session': session_str,
            'username': me.username or me.first_name,
            'chats': [],
            'message': 'Привет!',
            'delay': 300
        }
        save_db(db)
        await client.disconnect()
        await bot.send_message(chat_id, f"✅ Вошёл как @{me.username or me.first_name}!", 
            reply_markup=main_menu(True, len(get_accounts(uid))))
    except Exception as e:
        await client.disconnect()
        await bot.send_message(chat_id, f"❌ Время вышло или ошибка: {e}", reply_markup=main_menu(False, len(get_accounts(uid))))

# --- Обработка кнопок ---
@bot.callback_query_handler(func=lambda call: True)
async def handle_callback(call):
    uid = str(call.from_user.id)
    db = load_db()
    accounts = get_accounts(uid)
    acc_count = len(accounts)
    data = call.data

    try:
        if data == 'login_qr':
            if acc_count >= 3:
                await bot.answer_callback_query(call.id, "Максимум 3 аккаунта!")
                return
            await bot.edit_message_text("🔐 Генерирую QR-код...", call.message.chat.id, call.message.message_id)
            asyncio.create_task(qr_login(uid, call.message.chat.id, acc_count + 1))

        elif data == 'accounts_list':
            if acc_count == 0:
                await bot.answer_callback_query(call.id, "Нет привязанных аккаунтов")
                return
            kb = []
            for name, acc in accounts.items():
                kb.append([InlineKeyboardButton(f"👤 @{acc.get('username', name)}", callback_data=f"acc_{name}")])
            kb.append([InlineKeyboardButton("🗑 Удалить аккаунт", callback_data='delete_account')])
            kb.append([InlineKeyboardButton("🔙 В меню", callback_data='back_main')])
            await bot.edit_message_text("👤 Твои аккаунты:", call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith('acc_'):
            acc_name = data[4:]
            user_states[uid] = {'current_account': acc_name}
            kb = [
                [InlineKeyboardButton("💬 Чаты", callback_data='chats_menu')],
                [InlineKeyboardButton("📝 Текст", callback_data='set_text'), InlineKeyboardButton("⏱ Интервал", callback_data='set_delay')],
                [InlineKeyboardButton("▶️ Запустить этот", callback_data='start_spam'), InlineKeyboardButton("⏹ Стоп", callback_data='stop_spam')],
                [InlineKeyboardButton("📊 Статус", callback_data='status')],
                [InlineKeyboardButton("🔙 К списку", callback_data='accounts_list')]
            ]
            await bot.edit_message_text(f"👤 Аккаунт @{accounts[acc_name].get('username', acc_name)}", call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup(kb))

        elif data == 'delete_account':
            if acc_count == 0: await bot.answer_callback_query(call.id, "Нечего удалять"); return
            kb = [[InlineKeyboardButton(f"❌ @{acc.get('username', name)}", callback_data=f"del_{name}")] for name, acc in accounts.items()]
            kb.append([InlineKeyboardButton("🔙 Назад", callback_data='accounts_list')])
            await bot.edit_message_text("Выбери для удаления:", call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith('del_'):
            acc_name = data[4:]
            if acc_name in accounts:
                active_tasks.pop(f"{uid}_{acc_name}", None)
                del db[str(uid)]['accounts'][acc_name]
                save_db(db)
                await bot.answer_callback_query(call.id, "Удалён!")
                await bot.edit_message_text("👤 Обновлено", call.message.chat.id, call.message.message_id, reply_markup=main_menu(len(get_accounts(uid))>0, len(get_accounts(uid))))

        elif data == 'chats_menu':
            acc_name = user_states.get(uid, {}).get('current_account')
            if not acc_name: await bot.answer_callback_query(call.id, "Выбери аккаунт!"); return
            chats = accounts.get(acc_name, {}).get('chats', [])
            kb, cl = chats_menu_keyboard(chats)
            await bot.edit_message_text(f"💬 Чаты (@{accounts[acc_name].get('username', acc_name)}):\n{cl}", call.message.chat.id, call.message.message_id, reply_markup=kb)

        elif data == 'add_chat':
            user_states[uid] = {**user_states.get(uid, {}), 'step': 'adding_chat'}
            await bot.edit_message_text("➕ Пришли @username или ссылку:", call.message.chat.id, call.message.message_id, reply_markup=back_keyboard())

        elif data == 'clear_chats':
            acc_name = user_states.get(uid, {}).get('current_account')
            if acc_name and acc_name in accounts:
                db[str(uid)]['accounts'][acc_name]['chats'] = []; save_db(db)
                await bot.answer_callback_query(call.id, "Очищено!")
                await bot.edit_message_text("💬 Чаты:\nпусто", call.message.chat.id, call.message.message_id, reply_markup=chats_menu_keyboard([])[0])

        elif data == 'set_text':
            user_states[uid] = {**user_states.get(uid, {}), 'step': 'setting_text'}
            await bot.edit_message_text("📝 Пришли текст:", call.message.chat.id, call.message.message_id, reply_markup=back_keyboard())

        elif data == 'set_delay':
            user_states[uid] = {**user_states.get(uid, {}), 'step': 'setting_delay'}
            await bot.edit_message_text("⏱ Пришли интервал (30-3600):", call.message.chat.id, call.message.message_id, reply_markup=back_keyboard())

        elif data == 'start_spam':
            acc_name = user_states.get(uid, {}).get('current_account')
            if not acc_name: await bot.answer_callback_query(call.id, "Выбери аккаунт!"); return
            acc = accounts.get(acc_name, {})
            if not acc.get('chats'): await bot.answer_callback_query(call.id, "Добавь чаты!"); return
            task_id = f"{uid}_{acc_name}"
            active_tasks[task_id] = True
            asyncio.create_task(spam_loop(acc['session'], uid, acc_name))
            await bot.edit_message_text(f"🚀 Запущено для @{acc.get('username', acc_name)}!", call.message.chat.id, call.message.message_id, reply_markup=back_keyboard())

        elif data == 'stop_spam':
            acc_name = user_states.get(uid, {}).get('current_account')
            if acc_name: active_tasks.pop(f"{uid}_{acc_name}", None)
            await bot.edit_message_text("⏹ Остановлено", call.message.chat.id, call.message.message_id, reply_markup=back_keyboard())

        elif data == 'status':
            acc_name = user_states.get(uid, {}).get('current_account')
            if not acc_name: await bot.answer_callback_query(call.id, "Выбери аккаунт!"); return
            acc = accounts.get(acc_name, {})
            act = f"{uid}_{acc_name}" in active_tasks
            await bot.edit_message_text(f"📊 @{acc.get('username', acc_name)}\nРассылка: {'🟢' if act else '🔴'}\nЧатов: {len(acc.get('chats',[]))}\nТекст: {acc.get('message','-')}\nИнтервал: {acc.get('delay',300)}с", call.message.chat.id, call.message.message_id, reply_markup=back_keyboard())

        elif data == 'back_main':
            await bot.edit_message_text("🏠 Меню:", call.message.chat.id, call.message.message_id, reply_markup=main_menu(acc_count > 0, acc_count))

    except Exception as e:
        logger.error(f"Callback error: {e}")

# --- Обработка текста ---
@bot.message_handler(func=lambda m: True)
async def handle_text(msg):
    uid = str(msg.from_user.id)
    state = user_states.get(uid, {})
    step = state.get('step')

    if step == 'adding_chat':
        chat = msg.text.strip()
        acc_name = state.get('current_account')
        if acc_name:
            db = load_db()
            chats = db[str(uid)]['accounts'][acc_name].get('chats', [])
            if chat not in chats:
                db[str(uid)]['accounts'][acc_name]['chats'] = chats + [chat]; save_db(db)
                await bot.send_message(msg.chat.id, f"✅ {chat} добавлен!", reply_markup=main_menu(True, len(get_accounts(uid))))
            else:
                await bot.send_message(msg.chat.id, "Уже есть", reply_markup=main_menu(True, len(get_accounts(uid))))
        del user_states[uid]
        return

    elif step == 'setting_text':
        text = msg.text.strip()
        acc_name = state.get('current_account')
        if acc_name:
            db = load_db()
            db[str(uid)]['accounts'][acc_name]['message'] = text; save_db(db)
            await bot.send_message(msg.chat.id, f"✅ Текст: {text}", reply_markup=main_menu(True, len(get_accounts(uid))))
        del user_states[uid]
        return

    elif step == 'setting_delay':
        try:
            delay = int(msg.text.strip())
            if 30 <= delay <= 3600:
                acc_name = state.get('current_account')
                if acc_name:
                    db = load_db()
                    db[str(uid)]['accounts'][acc_name]['delay'] = delay; save_db(db)
                    await bot.send_message(msg.chat.id, f"✅ Интервал: {delay}с", reply_markup=main_menu(True, len(get_accounts(uid))))
            else: await bot.send_message(msg.chat.id, "❌ 30-3600!", reply_markup=back_keyboard()); return
        except: await bot.send_message(msg.chat.id, "❌ Число!", reply_markup=back_keyboard()); return
        del user_states[uid]
        return

    db = load_db()
    acc_count = len(get_accounts(uid))
    await bot.send_message(msg.chat.id, "🏠 Меню:", reply_markup=main_menu(acc_count > 0, acc_count))

@bot.message_handler(commands=['start'])
async def start_cmd(msg):
    uid = str(msg.from_user.id)
    acc_count = len(get_accounts(uid))
    await bot.send_message(msg.chat.id, START_TEXT, reply_markup=main_menu(acc_count > 0, acc_count), parse_mode="Markdown")

async def restore_spam():
    db = load_db()
    for uid, user in db.items():
        for acc_name, acc in user.get('accounts', {}).items():
            if 'session' in acc and acc.get('chats'):
                task_id = f"{uid}_{acc_name}"
                active_tasks[task_id] = True
                asyncio.create_task(spam_loop(acc['session'], uid, acc_name))

async def main():
    await restore_spam()
    logger.info("Бот запущен!")
    await bot.polling(non_stop=True)

if __name__ == '__main__':
    asyncio.run(main())
