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
BOT_TOKEN = '8706050462:AAFDuT53Q5CD6ZHBfAy09drphgLSN6xWfcA'
ADMIN_ID = "7113397602"
ADMIN_PASS = "12gleb34"
DB_FILE = 'users_data.json'

bot = AsyncTeleBot(BOT_TOKEN)
user_states = {}
active_tasks = {}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get('PORT',8080))), Handler).serve_forever(), daemon=True).start()

def load_db():
    return json.load(open(DB_FILE)) if os.path.exists(DB_FILE) else {}

def save_db(data):
    json.dump(data, open(DB_FILE, 'w'), indent=2, ensure_ascii=False)

def get_accounts(uid):
    return load_db().get(str(uid), {}).get('accounts', {})

def get_active_account(uid):
    accs = get_accounts(uid)
    if not accs:
        return None, None
    current = user_states.get(str(uid), {}).get('current_account')
    if current and current in accs:
        return current, accs[current]
    first_name = list(accs.keys())[0]
    user_states[str(uid)] = {'current_account': first_name}
    return first_name, accs[first_name]

def main_menu(uid):
    accs = get_accounts(uid)
    acc_count = len(accs)
    aname, acc = get_active_account(uid)
    is_authorized = acc is not None
    
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
        [InlineKeyboardButton("➕ Добавить чаты (списком)", callback_data='add_chat')],
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
        cycle = 1
        while task_id in active_tasks:
            for chat in chats:
                if task_id not in active_tasks: return
                try:
                    await client.send_message(chat, text)
                    logger.info(f"✅ {chat}")
                except Exception as e:
                    logger.warning(f"❌ {chat}: {e}")
                await asyncio.sleep(2)
            cycle += 1
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
                await bot.answer_callback_query(call.id, f"✅ Выбран @{accs[an].get('username',an)}")
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
                if user_states.get(uid,{}).get('current_account')==an:
                    user_states[uid]['current_account']=None
                await bot.answer_callback_query(call.id, "Удалён!")
                await bot.edit_message_text("👤 Обновлено", cid, mid, reply_markup=main_menu(uid))

        elif data=='chats_menu':
            aname, acc = get_active_account(uid)
            if not acc: await bot.answer_callback_query(call.id, "Войди в аккаунт!"); return
            chats=acc.get('chats',[])
            kb,cl=chats_menu_keyboard(chats)
            await bot.edit_message_text(f"💬 Чаты (@{acc.get('username',aname)}):\n{cl}", cid, mid, reply_markup=kb)

        elif data=='add_chat':
            user_states[uid]={**state,'step':'adding_chats'}
            await bot.edit_message_text("➕ Отправь чаты СПИСКОМ:\n• Каждый с новой строки\n• Или через запятую\n• @username или ID или ссылки", cid, mid, reply_markup=back_keyboard())

        elif data=='clear_chats':
            aname, acc = get_active_account(uid)
            if acc:
                db=load_db(); db[uid]['accounts'][aname]['chats']=[]; save_db(db)
                await bot.answer_callback_query(call.id, "Очищено!")
                await bot.edit_message_text("💬 Чаты:\nпусто", cid, mid, reply_markup=chats_menu_keyboard([])[0])

        elif data=='set_text':
            user_states[uid]={**state,'step':'setting_text'}
            await bot.edit_message_text("📝 Отправь текст рассылки:", cid, mid, reply_markup=back_keyboard())

        elif data=='set_delay':
            user_states[uid]={**state,'step':'setting_delay'}
            await bot.edit_message_text("⏱ Интервал в секундах (30-3600):", cid, mid, reply_markup=back_keyboard())

        elif data=='start_spam':
            aname, acc = get_active_account(uid)
            if not acc: await bot.answer_callback_query(call.id, "Войди в аккаунт!"); return
            if not acc.get('chats'): await bot.answer_callback_query(call.id, "Добавь чаты!"); return
            task_id = f"{uid}_{aname}"
            active_tasks.pop(task_id, None)
            active_tasks[task_id] = True
            asyncio.create_task(spam_loop(acc['session'], uid, aname))
            await bot.edit_message_text(f"🚀 Запущено для @{acc.get('username',aname)}!", cid, mid, reply_markup=back_keyboard())

        elif data=='stop_spam':
            aname, acc = get_active_account(uid)
            if aname: active_tasks.pop(f"{uid}_{aname}", None)
            await bot.edit_message_text("⏹ Стоп", cid, mid, reply_markup=back_keyboard())

        elif data=='status':
            aname, acc = get_active_account(uid)
            if not acc: await bot.answer_callback_query(call.id, "Войди в аккаунт!"); return
            act=f"{uid}_{aname}" in active_tasks
            await bot.edit_message_text(f"📊 @{acc.get('username',aname)}\nРассылка: {'🟢' if act else '🔴'}\nЧатов: {len(acc.get('chats',[]))}\nТекст: {acc.get('message','-')}\nИнтервал: {acc.get('delay',300)}с", cid, mid, reply_markup=back_keyboard())

        elif data=='back_main':
            await bot.edit_message_text("🏠 Меню:", cid, mid, reply_markup=main_menu(uid))
    except Exception as e:
        logger.error(f"Err: {e}")

@bot.message_handler(commands=['start'])
async def start(msg):
    uid = str(msg.from_user.id)
    await bot.send_message(msg.chat.id, "👋 Бот-рассыльщик\n\nВыбирай:", reply_markup=main_menu(uid))

@bot.message_handler(func=lambda m: True)
async def text(msg):
    uid=str(msg.from_user.id)
    state=user_states.get(uid,{})
    step=state.get('step')

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
        # Разделяем по запятым или переносам строк
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
