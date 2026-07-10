# bot.py
import asyncio
import os
import html
import time
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import BaseMiddleware

from playwright.async_api import async_playwright

from database import db
from ai_engines import AI_MODES, get_prediction

# ==========================================
# 1. CONFIGURATION & VARIABLES
# ==========================================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
auth_router = Router()

LAST_PROCESSED_ISSUE = None
DEFAULT_AI_MODE = "ensemble"
DEFAULT_BET_SEQUENCE = [10, 20, 40, 80]

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

active_sessions = {}

# ==========================================
# 2. FSM STATES & MIDDLEWARES
# ==========================================
class LoginForm(StatesGroup):
    select_site = State()
    enter_phone = State()
    enter_password = State()

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        sudo_users = await db.get_sudo_users()
        if str(user_id) != str(OWNER_ID) and user_id not in sudo_users:
            return await event.reply("🔒 <b>Access Denied!</b>")
        return await handler(event, data)

auth_router.message.middleware(AuthMiddleware())
auth_router.callback_query.middleware(AuthMiddleware())

# ==========================================
# 3. KEYBOARDS
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔐 Login")], [KeyboardButton(text="🎰 Games")]],
        resize_keyboard=True
    )

def get_site_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="777BIGWIN")], [KeyboardButton(text="🔙 နောက်သို့")]],
        resize_keyboard=True
    )

def get_logged_in_keyboard(is_auto_active: bool = False):
    auto_text = "⏹️ Stop Auto-Bet" if is_auto_active else "▶️ Start Auto-Bet"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=auto_text)],
            [KeyboardButton(text="💰 Balance"), KeyboardButton(text="🧠 AI Mode")],
            [KeyboardButton(text="📋 Info"), KeyboardButton(text="🎰 Games")],
            [KeyboardButton(text="🔐 Logout")]
        ],
        resize_keyboard=True
    )

def get_ai_mode_inline_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    modes_list = list(AI_MODES.items())
    for i in range(0, len(modes_list), 2):
        row_buttons = []
        for j in range(2):
            if i + j < len(modes_list):
                key, info = modes_list[i + j]
                prefix = "⭐ " if key == current_mode else ""
                row_buttons.append(InlineKeyboardButton(text=f"{prefix}{info['name']}", callback_data=f"usermode_{key}"))
        builder.row(*row_buttons)
    return builder.as_markup()

# ==========================================
# 4. PLAYWRIGHT AUTOMATION ENGINE
# ==========================================
async def execute_playwright_bet(page, bet_choice: str, amount: int):
    try:
        bet_choice = bet_choice.lower()
        if bet_choice == "big":
            await page.locator('.Betting__C-foot-b').click(timeout=4000) 
        elif bet_choice == "small":
            await page.locator('.Betting__C-foot-s').click(timeout=4000)
        else: return False

        await page.wait_for_timeout(500)
        
        amount_locator = page.locator(f"div.Betting__Popup-body-line-item", has_text=str(amount)).first
        await amount_locator.click(timeout=3000)
        await page.wait_for_timeout(300)

        confirm_btn = page.locator('.Betting__Popup-foot > div').last
        await confirm_btn.click(timeout=3000)
        await page.wait_for_timeout(1000)
        return True
    except Exception as e:
        print(f"Playwright Bet Error: {e}")
        return False

# ==========================================
# 5. EXACT FORMATTING
# ==========================================
def get_color_emoji(number):
    if number in [0, 5]: return "🟣 VIOLET"
    elif number in [2, 4, 6, 8]: return "🔴 RED"
    else: return "🟢 GREEN"

async def send_bet_notification(user_id, issue, size, amount, ai_name):
    msg = (
        f"⚡ WINGO_30S: {issue}\n"
        f"⚡ {size.upper()} | {amount:,.0f} Ks\n"
        f"⚡ {ai_name}"
    )
    await bot.send_message(chat_id=user_id, text=msg)

async def send_result_notification(user_id, bet, actual_number, is_win, profit):
    user = await db.get_user(user_id)
    session_profit = user.get('session_profit', 0)
    
    size_str = "BIG" if actual_number >= 5 else "SMALL"
    size_icon = "🔴" if size_str == "BIG" else "🟢"
    color_str = get_color_emoji(actual_number)
    
    sign = "+" if is_win else ""
    header = f"🟢 WIN! {sign}{profit:,.2f} Ks" if is_win else f"❌ LOSE! {profit:,.2f} Ks"
    profit_sign = "+" if session_profit > 0 else ""
    
    msg = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ WINGO_30S : {bet['issue_number']}\n"
        f"⚡ Result: {actual_number} {size_icon} {size_str} {color_str}\n"
        f"⚡ Balance: {user['balance']:,.2f} Ks\n"
        f"⚡ Profit: {profit_sign}{session_profit:,.2f} Ks"
    )
    await bot.send_message(chat_id=user_id, text=msg)

# ==========================================
# 6. CORE GAME LOOP (AUTO BET)
# ==========================================
async def fetch_with_retry(session, url, headers, json_data):
    try:
        async with session.post(url, headers=headers, json=json_data, timeout=3.0) as resp:
            if resp.status == 200: return await resp.json()
    except: pass
    return None

async def auto_game_broadcaster_loop():
    global LAST_PROCESSED_ISSUE
    await db.init_indexes()
    
    async with aiohttp.ClientSession() as session:
        while True:
            sec_passed = int(time.time()) % 30
            
            if 5 <= sec_passed <= 26:
                json_data = {
                    'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7,
                    'random': '9ef85244056948ba8dcae7aee7758bf4', 'timestamp': int(time.time()),
                }
                data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', BASE_HEADERS, json_data)
                
                if data and data.get('code') == 0:
                    records = data.get("data", {}).get("list", [])
                    if records:
                        latest_record = records[0]
                        latest_issue = str(latest_record["issueNumber"])
                        latest_number = int(latest_record["number"])
                        latest_size = "BIG" if latest_number >= 5 else "SMALL"
                        
                        if not LAST_PROCESSED_ISSUE or int(latest_issue) > int(LAST_PROCESSED_ISSUE):
                            LAST_PROCESSED_ISSUE = latest_issue
                            await db.add_history(latest_issue, latest_number, latest_size)
                            
                            settled_bets = await db.settle_bets(latest_issue, latest_size, latest_number)
                            for bet in settled_bets:
                                is_win = bet["result"] == "WIN"
                                await send_result_notification(bet["user_id"], bet, latest_number, is_win, bet["profit"])
                            
                            next_issue = str(int(latest_issue) + 1)
                            history_docs = await db.get_history(100)
                            
                            for user_tg_id, session_data in list(active_sessions.items()):
                                if not session_data.get("is_auto_active"): continue
                                
                                u_session = await db.get_user_session(user_tg_id)
                                u_mode = u_session.get("ai_mode", DEFAULT_AI_MODE)
                                predicted_size, _, _, _ = get_prediction(history_docs, u_mode)
                                
                                recent_bets = await db.get_user_bets(user_tg_id, 30)
                                lose_streak = 0
                                for b in recent_bets:
                                    if b.get("result") == "LOSE": lose_streak += 1
                                    elif b.get("result") == "WIN": break
                                
                                bet_seq = u_session.get("bet_sequence", DEFAULT_BET_SEQUENCE)
                                if lose_streak >= len(bet_seq): lose_streak = 0
                                bet_amount = bet_seq[lose_streak]
                                
                                user_data = await db.get_user(user_tg_id)
                                if user_data["balance"] >= bet_amount:
                                    page = session_data["page"]
                                    is_success = await execute_playwright_bet(page, predicted_size, bet_amount)
                                    if is_success:
                                        await db.place_bet(user_tg_id, next_issue, bet_amount, predicted_size, u_mode)
                                        ai_name = AI_MODES.get(u_mode, {}).get("name", "AI")
                                        await send_bet_notification(user_tg_id, next_issue, predicted_size, bet_amount, ai_name)
                                        
                            await asyncio.sleep(20)
            await asyncio.sleep(0.5)

# ==========================================
# 7. LOGIN PROCESS HANDLERS
# ==========================================
@auth_router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 <b>မင်္ဂလာပါ!</b>\nအကောင့်ဝင်ရန် Login ကိုနှိပ်ပါ။", reply_markup=get_main_keyboard())

@auth_router.message(F.text == "🔐 Login")
async def login_start(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.select_site)
    await message.answer("🌐 <b>Please select a site to login:</b>", reply_markup=get_site_keyboard())

@auth_router.message(LoginForm.select_site)
async def process_site(message: types.Message, state: FSMContext):
    if message.text == "🔙 နောက်သို့":
        await state.clear()
        return await message.answer("Cancelled.", reply_markup=get_main_keyboard())
    await state.update_data(site=message.text)
    await state.set_state(LoginForm.enter_phone)
    await message.answer("📞 <b>Please enter your phone:</b>", reply_markup=ReplyKeyboardRemove())

@auth_router.message(LoginForm.enter_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(LoginForm.enter_password)
    await message.answer("🔑 <b>Please enter your password:</b>", reply_markup=ReplyKeyboardRemove())

@auth_router.message(LoginForm.enter_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    username = data.get('phone')
    user_tg_id = message.from_user.id
    
    loading_msg = await message.answer("🔄 <b>အကောင့်ဝင်နေပါသည်... ခဏစောင့်ပါ...</b>")
    
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
    context = await browser.new_context(user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36", viewport={'width': 390, 'height': 844}, is_mobile=True)
    page = await context.new_page()
    
    try:
        await page.goto("https://www.777bigwingame.app/#/login", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        js_code = """
        ([user, pwd]) => {
            function fillVueInput(element, value) {
                if (!element) return false;
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(element, value);
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
                element.blur();
                return true;
            }
            fillVueInput(document.querySelector('input[name="userNumber"]'), user);
            let pass = document.querySelector('input[placeholder="စကားဝှက်"]') || document.querySelector('input[placeholder="Password"]');
            fillVueInput(pass, pwd);
        }
        """
        await page.evaluate(js_code, [username, password])
        await page.wait_for_timeout(1000)
        await page.evaluate("""() => { let btn = document.querySelector('button.active'); if (btn) btn.click(); }""")
        await page.wait_for_timeout(5000)
        
        if "login" not in page.url.lower():
            try:
                await page.goto("https://www.777bigwingame.app/#/main", wait_until="networkidle")
                await page.wait_for_timeout(3000)
            except: pass

            uid, nick, bal = "N/A", "Unknown", "0.00 Ks"
            try:
                if await page.locator('.userInfo__container-content-nickname h3').first.is_visible(timeout=2000):
                    nick = await page.locator('.userInfo__container-content-nickname h3').first.inner_text()
                if await page.locator('.userInfo__container-content-uid span:nth-child(3)').first.is_visible(timeout=2000):
                    uid = await page.locator('.userInfo__container-content-uid span:nth-child(3)').first.inner_text()
                if await page.locator('.balance_info p.totalSavings__container-header__subtitle span').first.is_visible(timeout=2000):
                    bal = await page.locator('.balance_info p.totalSavings__container-header__subtitle span').first.inner_text()
            except: pass

            try:
                bal_float = float(bal.replace("Ks", "").replace(",", "").strip())
                await db.update_balance(user_tg_id, bal_float, "set")
            except: pass

            await page.goto("https://www.777bigwingame.app/#/home/AllLotteryGames/WinGo?id=1", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            await state.update_data(is_logged_in=True, username=username, user_id=uid.strip(), nickname=nick.strip(), balance=bal.strip())
            await state.set_state(None)

            active_sessions[user_tg_id] = {"playwright": p, "browser": browser, "page": page, "is_auto_active": False}

            await message.answer("✅ <b>LOGIN SUCCESSFUL</b>\n\nAuto-Bet စတင်ရန် <b>▶️ Start Auto-Bet</b> ခလုတ်ကို နှိပ်ပါ။", reply_markup=get_logged_in_keyboard(False))
        else:
            await message.answer("❌ Login မအောင်မြင်ပါ။ စကားဝှက် မှားယွင်းနေနိုင်ပါသည်။", reply_markup=get_main_keyboard())
            await browser.close()
            await p.stop()
            await state.clear()
        await loading_msg.delete()
    except Exception as e:
        await message.answer(f"⚠️ Error: {html.escape(str(e))}", reply_markup=get_main_keyboard())
        try:
            await browser.close()
            await p.stop()
        except: pass
        await state.clear()
        await loading_msg.delete()

# ==========================================
# 8. MENUS & CONTROL HANDLERS (ROBUST EMOJI MATCH)
# ==========================================
# Emojis ကွဲလွဲမှုကို ကျော်လွှားရန် .contains() စနစ်ပြောင်းလဲထားသည်
@auth_router.message(F.text.contains("Start Auto-Bet"))
async def handle_start(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ Bot Restart ဖြစ်သွားပါသဖြင့် အရင်ဆုံး <b>🔐 Login</b> ပြန်ဝင်ပေးပါ။", reply_markup=get_main_keyboard())
    active_sessions[user_tg_id]["is_auto_active"] = True
    await db.activate_session(user_tg_id)
    await db.reset_session_profit(user_tg_id)
    await message.answer("🟢 <b>Auto-Bet စတင်ပါပြီ!</b>\nနောက်ပွဲစဉ်စောင့်ကြည့်ပြီး AI ဖြင့် အလိုအလျောက် ထိုးပေးပါမည်။", reply_markup=get_logged_in_keyboard(True))

@auth_router.message(F.text.contains("Stop Auto-Bet"))
async def handle_stop(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ Bot Restart ဖြစ်သွားပါသဖြင့် အရင်ဆုံး <b>🔐 Login</b> ပြန်ဝင်ပေးပါ။", reply_markup=get_main_keyboard())
    active_sessions[user_tg_id]["is_auto_active"] = False
    await db.deactivate_session(user_tg_id)
    await message.answer("🔴 <b>Auto-Bet ရပ်တန့်ပါပြီ!</b>", reply_markup=get_logged_in_keyboard(False))

@auth_router.message(F.text.contains("Balance"))
async def handle_balance(message: types.Message):
    if message.from_user.id not in active_sessions:
        return await message.answer("⚠️ အရင်ဆုံး <b>🔐 Login</b> ဝင်ပေးပါ။", reply_markup=get_main_keyboard())
    user = await db.get_user(message.from_user.id)
    is_active = active_sessions[message.from_user.id]["is_auto_active"]
    await message.answer(f"💰 <b>Balance:</b> {user['balance']:,.2f} Ks\n📈 <b>Session Profit:</b> {user.get('session_profit', 0):,.2f} Ks", reply_markup=get_logged_in_keyboard(is_active))

@auth_router.message(F.text.contains("AI Mode"))
async def handle_mode(message: types.Message):
    if message.from_user.id not in active_sessions:
        return await message.answer("⚠️ အရင်ဆုံး <b>🔐 Login</b> ဝင်ပေးပါ။", reply_markup=get_main_keyboard())
    session = await db.get_user_session(message.from_user.id)
    current_mode = session.get("ai_mode", DEFAULT_AI_MODE)
    await message.answer(f"🧠 <b>AI Mode ရွေးပါ (၁၆ မျိုး)</b>\n📌 လက်ရှိ: <b>{AI_MODES.get(current_mode, {}).get('name', 'AI')}</b>", reply_markup=get_ai_mode_inline_keyboard(current_mode))

@auth_router.callback_query(F.data.startswith("usermode_"))
async def cb_user_mode(callback: types.CallbackQuery):
    await callback.answer() # Inline button loading လည်ပြီး ငြိမ်သွားမှုကို ဖြေရှင်းရန် တုံ့ပြန်ချက်ပေးခြင်း
    mode_key = callback.data.replace("usermode_", "")
    if mode_key in AI_MODES:
        await db.update_user_ai_mode(callback.from_user.id, mode_key)
        # လက်ရှိရွေးလိုက်တဲ့ Mode ကိုပါ Inline Keyboard မှာ ကြယ်ပွင့်ပြောင်းရန် ပြန်ဆွဲခြင်း
        await callback.message.edit_text(
            f"✅ <b>AI Mode ပြောင်းပြီး!</b>\n🧠 {AI_MODES[mode_key]['name']}\n\n👇 အခြား Mode သို့ ထပ်မံပြောင်းလဲနိုင်သည်-",
            reply_markup=get_ai_mode_inline_keyboard(mode_key)
        )

@auth_router.message(F.text.contains("Info"))
async def show_info(message: types.Message, state: FSMContext):
    if message.from_user.id not in active_sessions:
        return await message.answer("⚠️ အရင်ဆုံး <b>🔐 Login</b> ဝင်ပေးပါ။", reply_markup=get_main_keyboard())
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    is_auto = active_sessions[message.from_user.id]["is_auto_active"]
    await message.answer(
        f"👤 <b>User Information:</b>\n"
        f"├─ 🆔 <b>User ID:</b> {data.get('user_id', user['user_id'])}\n"
        f"├─ 📱 <b>Username:</b> {data.get('username', 'N/A')}\n"
        f"├─ 🏷️ <b>Nickname:</b> {data.get('nickname', 'Unknown')}\n"
        f"├─ 💰 <b>Balance:</b> {user['balance']:,.2f} Ks\n"
        f"└─ 🤖 <b>Auto-Bet Status:</b> {'Active 🟢' if is_auto else 'Inactive 🔴'}",
        reply_markup=get_logged_in_keyboard(is_auto)
    )

@auth_router.message(F.text.contains("Games"))
async def games(message: types.Message):
    if message.from_user.id not in active_sessions:
        return await message.answer("⚠️ အရင်ဆုံး <b>🔐 Login</b> ဝင်ပေးပါ။", reply_markup=get_main_keyboard())
    is_auto = active_sessions[message.from_user.id]["is_auto_active"]
    await message.answer("🎮 <b>Win Go 30s</b> ကို ရွေးချယ်ထားပါသည်။ Auto Bet စနစ်ဖွင့်ထားပါက နောက်ကွယ်မှ အလိုအလျောက် ထိုးပေးပါမည်။", reply_markup=get_logged_in_keyboard(is_auto))

@auth_router.message(F.text.contains("Logout"))
async def logout(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id in active_sessions:
        try:
            await active_sessions[user_tg_id]["browser"].close()
            await active_sessions[user_tg_id]["playwright"].stop()
        except: pass
        del active_sessions[user_tg_id]
    await db.deactivate_session(user_tg_id)
    await state.clear()
    await message.answer("👋 အကောင့်ထွက်ပြီးပါပြီ။", reply_markup=get_main_keyboard())

# ==========================================
# 9. MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Bot Started! (Playwright Multi-User + DB Sync)")
    dp.include_router(auth_router)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_game_broadcaster_loop())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot Stopped!")
