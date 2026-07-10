# bot.py (API + Playwright + AI + Real/Virtual Mode - Fixed Keyboard & Custom Bet)
import asyncio
import os
import html
import random
import time
from datetime import datetime
from dotenv import load_dotenv
import aiohttp

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from playwright.async_api import async_playwright

from ai_engines import get_prediction, AI_MODES
from database import db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
USERNAME = os.getenv("BIGWIN_USERNAME")
PASSWORD = os.getenv("BIGWIN_PASSWORD")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Global variables
active_sessions = {}
virtual_balances = {}
user_target_input = {}
user_betsize_input = {}
DEFAULT_BET_SEQUENCE = [100, 300, 900, 2700, 8100, 24300]
DEFAULT_AI_MODE = "ensemble"
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = None

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app/',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# ==========================================================
# 🗂️ FSM States
# ==========================================================
class LoginForm(StatesGroup):
    select_site = State()
    enter_phone = State()
    enter_password = State()
    main_menu = State()
    choose_mode = State()

# ==========================================================
# ⌨️ Keyboards (2 Columns - ဘေးချင်းကပ်)
# ==========================================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 Login"), KeyboardButton(text="⚙️ Mode")],
            [KeyboardButton(text="📊 Status"), KeyboardButton(text="🧠 AI Mode")],
            [KeyboardButton(text="💲 Bet Size"), KeyboardButton(text="🎯 Target")],
            [KeyboardButton(text="🎰 Games")]
        ],
        resize_keyboard=True
    )

def get_logged_in_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Info"), KeyboardButton(text="🎰 Games")],
            [KeyboardButton(text="▶️ Start Auto-Bet"), KeyboardButton(text="⏹️ Stop Auto-Bet")],
            [KeyboardButton(text="📊 Status"), KeyboardButton(text="🧠 AI Mode")],
            [KeyboardButton(text="💲 Bet Size"), KeyboardButton(text="🎯 Target")],
            [KeyboardButton(text="🔐 Logout")]
        ],
        resize_keyboard=True
    )

def get_mode_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 Real Mode"), KeyboardButton(text="🟡 Virtual Mode")],
            [KeyboardButton(text="🔙 နောက်သို့")]
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
                row_buttons.append(InlineKeyboardButton(
                    text=f"{prefix}{info['name']}",
                    callback_data=f"usermode_{key}"
                ))
        builder.row(*row_buttons)
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="cmd_back"))
    return builder.as_markup()

def get_betsize_inline_keyboard(current_seq: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💰 100-300-900-2700-8100-24300 (6 Steps)",
        callback_data="setbetsize_100_300_900_2700_8100_24300"
    ))
    builder.row(InlineKeyboardButton(
        text="💰 100-300-900-2700-8100 (5 Steps)",
        callback_data="setbetsize_100_300_900_2700_8100"
    ))
    builder.row(InlineKeyboardButton(
        text="💰 50-150-450-1350-4050-12150 (Small 6 Steps)",
        callback_data="setbetsize_50_150_450_1350_4050_12150"
    ))
    builder.row(InlineKeyboardButton(
        text="💰 200-600-1800-5400-16200-48600 (Medium 6 Steps)",
        callback_data="setbetsize_200_600_1800_5400_16200_48600"
    ))
    builder.row(InlineKeyboardButton(
        text="✏️ Custom Bet Size",
        callback_data="betsize_custom"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="cmd_back"))
    return builder.as_markup()

def get_target_inline_keyboard():
    builder = InlineKeyboardBuilder()
    for amt in [10000, 30000, 50000, 100000]:
        builder.row(InlineKeyboardButton(
            text=f"🎯 {amt:,} Ks",
            callback_data=f"settarget_{amt}"
        ))
    builder.row(InlineKeyboardButton(
        text="✏️ Custom Target",
        callback_data="target_custom"
    ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="cmd_back"))
    return builder.as_markup()

# ==========================================================
# 🤖 Command Handlers
# ==========================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 <b>မင်္ဂလာပါ!</b>\nအကောင့်ဝင်ရန် Login ကိုနှိပ်ပါ။", reply_markup=get_main_keyboard())

@dp.message(F.text == "⚙️ Mode")
async def choose_mode(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.choose_mode)
    await message.answer(
        "🟢 <b>Mode ရွေးပါ:</b>\n\n"
        "🟢 Real Mode = အစစ် (BigWin API, Real Balance)\n"
        "🟡 Virtual Mode = Test (Virtual Balance)\n\n"
        "⚠️ နှစ်ခုလုံးက AI Prediction နဲ့ Bet Sequence အတူတူပါပဲ။ Balance ပဲကွာပါတယ်။",
        reply_markup=get_mode_keyboard()
    )

@dp.message(LoginForm.choose_mode)
async def process_mode(message: types.Message, state: FSMContext):
    if message.text == "🟢 Real Mode":
        await state.update_data(mode="real")
        await message.answer("✅ Real Mode ကိုရွေးပြီးပါပြီ။\nLogin ဝင်ရန် 🔐 Login ကိုနှိပ်ပါ။", reply_markup=get_main_keyboard())
        await state.clear()
    elif message.text == "🟡 Virtual Mode":
        await state.update_data(mode="virtual")
        user_id = message.from_user.id
        if user_id not in virtual_balances:
            virtual_balances[user_id] = 100000.0
        await message.answer(
            f"✅ Virtual Mode ကိုရွေးပြီးပါပြီ။\n"
            f"💰 Virtual Balance: {virtual_balances[user_id]:,.0f} Ks\n"
            f"🤖 Auto-Bet အတွက် <b>Start Auto-Bet</b> ကိုနှိပ်ပါ။",
            reply_markup=get_logged_in_keyboard()
        )
        await state.set_state(LoginForm.main_menu)
    elif message.text == "🔙 နောက်သို့":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=get_main_keyboard())

# ==========================================================
# 🔐 Login (Real Mode only)
# ==========================================================
@dp.message(F.text == "🔐 Login")
async def login_start(message: types.Message, state: FSMContext):
    if (await state.get_data()).get("mode") == "virtual":
        await message.answer("⚠️ Virtual Mode တွင် Login မလိုပါ။")
        return
    await state.set_state(LoginForm.select_site)
    await message.answer("🌐 <b>Please select a site to login:</b>", reply_markup=get_site_keyboard())

@dp.message(LoginForm.select_site)
async def process_site(message: types.Message, state: FSMContext):
    if message.text == "🔙 နောက်သို့":
        await state.clear()
        return await message.answer("Cancelled.", reply_markup=get_main_keyboard())
    await state.update_data(site=message.text)
    await state.set_state(LoginForm.enter_phone)
    await message.answer("📞 <b>Please enter your phone:</b>", reply_markup=ReplyKeyboardRemove())

@dp.message(LoginForm.enter_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(LoginForm.enter_password)
    await message.answer("🔑 <b>Please enter your password:</b>", reply_markup=ReplyKeyboardRemove())

@dp.message(LoginForm.enter_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    username = data.get('phone')
    user_tg_id = message.from_user.id
    
    loading_msg = await message.answer("🔄 <b>အကောင့်ဝင်နေပါသည်... ခဏစောင့်ပါ...</b>")
    
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36", 
        viewport={'width': 390, 'height': 844}, 
        is_mobile=True
    )
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
            let phone = document.querySelector('input[name="userNumber"]');
            fillVueInput(phone, user);
            let pass = document.querySelector('input[placeholder="စကားဝှက်"]') || 
                       document.querySelector('input[placeholder="Password"]') || 
                       document.querySelector('.passwordInput__container-input input');
            fillVueInput(pass, pwd);
        }
        """
        await page.evaluate(js_code, [username, password])
        await page.wait_for_timeout(1000)

        await page.evaluate("""
            () => {
                let btn = document.querySelector('button.active');
                if (btn) btn.click();
            }
        """)
        
        await page.wait_for_timeout(5000)
        
        try:
            close_selector = ".announcement-dialog__button"
            for _ in range(3):
                btn = await page.query_selector(close_selector)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(1000)
                else:
                    break
        except:
            pass
        
        if "login" not in page.url.lower():
            try:
                await page.goto("https://www.777bigwingame.app/#/main", wait_until="networkidle")
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"Info Page Error: {e}")

            user_id, nickname, balance_text = "N/A", "Unknown", "0.00 Ks"
            site_login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                nick_el = page.locator('.userInfo__container-content-nickname h3').first
                if await nick_el.is_visible(timeout=3000):
                    nickname = await nick_el.inner_text()
                uid_el = page.locator('.userInfo__container-content-uid span:nth-child(3)').first
                if await uid_el.is_visible(timeout=2000):
                    user_id = await uid_el.inner_text()
                balance_el = page.locator('.balance_info p.totalSavings__container-header__subtitle span').first
                if await balance_el.is_visible(timeout=2000):
                    balance_text = await balance_el.inner_text()
            except Exception as e:
                print(f"Scraping Error: {e}")

            await page.goto("https://www.777bigwingame.app/#/home/AllLotteryGames/WinGo?id=1", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            await state.update_data(
                is_logged_in=True, username=username, user_id=user_id.strip(),
                nickname=nickname.strip(), balance=balance_text.strip(), login_time=site_login_time.strip()
            )

            active_sessions[user_tg_id] = {
                "playwright": p,
                "browser": browser,
                "page": page
            }

            await message.answer(
                "✅ <b>LOGIN SUCCESSFUL</b>\n\n"
                "သင့်အကောင့်အချက်အလက်များကို ကြည့်ရှုရန် အောက်ပါ <b>📋 Info</b> ခလုတ်ကို နှိပ်ပါ။",
                reply_markup=get_logged_in_keyboard()
            )
            await state.set_state(LoginForm.main_menu)
        else:
            await message.answer("❌ <b>Login မအောင်မြင်ပါ။</b>", reply_markup=get_main_keyboard())
            await browser.close()
            await p.stop()
            await state.clear()

        await loading_msg.delete()

    except Exception as e:
        await message.answer(f"⚠️ <b>Error:</b> {html.escape(str(e))}", reply_markup=get_main_keyboard())
        await browser.close()
        await p.stop()
        await state.clear()
        await loading_msg.delete()

# ==========================================================
# 🔥 API Functions (History Data အတွက်)
# ==========================================================
async def fetch_with_retry(session, url, headers, json_data, retries=1):
    for _ in range(retries):
        try:
            async with session.post(url, headers=headers, json=json_data, timeout=3.0) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            await asyncio.sleep(0.2)
    return None

async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    json_data = {
        'username': USERNAME, 'pwd': PASSWORD, 'phonetype': 1, 'logintype': 'mobile',
        'packId': '', 'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6', 'language': 7,
        'random': '4fc4413428be43faa1a3f30d9745ae3a',
        'signature': '5458639AF428AC897FDFF1102D82EB9C',
        'timestamp': int(time.time()),
    }
    data = await fetch_with_retry(
        session, 'https://api.bigwinqaz.com/api/webapi/Login', BASE_HEADERS, json_data
    )
    if data and data.get('code') == 0:
        token_str = data.get('data', {})
        CURRENT_TOKEN = f"Bearer {token_str}" if isinstance(token_str, str) else f"Bearer {token_str.get('token', '')}"
        print("✅ Login Success\n")
        return True
    return False

async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE

    if not CURRENT_TOKEN:
        if not await login_and_get_token(session):
            return False

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7,
        'random': '9ef85244056948ba8dcae7aee7758bf4',
        'signature': '2EDB8C2B5264F62EC53116916A9EC05C',
        'timestamp': int(time.time()),
    }

    data = await fetch_with_retry(
        session, 'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers, json_data
    )

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
                print(f"✅ History updated: {latest_issue} - {latest_number} ({latest_size})")
                return True
    return False

# ==========================================================
# 🎯 AI Prediction + Auto-Bet Logic (Real & Virtual)
# ==========================================================
async def get_ai_prediction(history_docs, mode_key):
    predicted_size, display, prob, reason = get_prediction(history_docs, mode_key)
    return predicted_size, prob, display, reason

async def place_auto_bet(page, bet_type: str, amount: int):
    try:
        bet_choice = bet_type.lower()
        if bet_choice == "big":
            await page.locator('.Betting__C-foot-b').click(timeout=5000)
        elif bet_choice == "small":
            await page.locator('.Betting__C-foot-s').click(timeout=5000)
        else:
            return False
        await page.wait_for_timeout(1000)
        amount_locator = page.locator(f"div.Betting__Popup-body-line-item", has_text=str(amount)).first
        await amount_locator.click(timeout=3000)
        await page.wait_for_timeout(500)
        confirm_btn = page.locator('.Betting__Popup-foot > div').last
        await confirm_btn.click(timeout=3000)
        await page.wait_for_timeout(2000)
        return True
    except:
        return False

async def get_real_result(page):
    try:
        period_el = page.locator('.record-item .period').first
        number_el = page.locator('.record-item .number').first
        color_el = page.locator('.record-item .color').first
        period = await period_el.inner_text() if await period_el.is_visible() else "N/A"
        number = await number_el.inner_text() if await number_el.is_visible() else "N/A"
        color_text = await color_el.inner_text() if await color_el.is_visible() else "N/A"
        size = "BIG" if int(number) >= 5 else "SMALL" if number != "N/A" else "N/A"
        color_map = {"GREEN": "🟢", "RED": "🔴", "VIOLET": "🟣"}
        color_emoji = color_map.get(color_text.upper(), "⚪")
        return {"period": period.strip(), "number": number.strip(), "size": size, "color_emoji": color_emoji}
    except:
        return None

async def auto_bet_loop(user_id: int, state: FSMContext, mode: str, page=None, session=None):
    lose_streak = 0
    total_profit = 0.0
    balance = 0.0

    while True:
        try:
            data = await state.get_data()
            if not data.get("auto_bet_running"):
                break

            # 1. Update History from API (Real Mode only)
            if mode == "real" and session:
                await check_game_and_predict(session)

            # 2. Load user settings
            ai_mode = data.get("ai_mode", DEFAULT_AI_MODE)
            bet_sequence = data.get("bet_sequence", DEFAULT_BET_SEQUENCE)
            profit_target = data.get("profit_target", 30000.0)

            # Check profit target
            if total_profit >= profit_target:
                await state.update_data(auto_bet_running=False)
                await bot.send_message(user_id, f"🎯 Target Reached! Total Profit: {total_profit:,.2f} Ks")
                break

            # 3. Get AI prediction from DB history
            history_docs = await db.get_history(50)
            if not history_docs:
                await asyncio.sleep(5)
                continue

            predicted_size, prob, display, reason = await get_ai_prediction(history_docs, ai_mode)
            ai_name = AI_MODES.get(ai_mode, {}).get("name", "AI")

            # 4. Bet amount from sequence
            if lose_streak >= len(bet_sequence):
                lose_streak = 0
            bet_amount = bet_sequence[lose_streak]

            # 5. Execute Bet (Real = Playwright, Virtual = Simulation)
            if mode == "real" and page:
                success = await place_auto_bet(page, predicted_size, bet_amount)
                if not success:
                    await bot.send_message(user_id, "⚠️ Bet placement failed!")
                    continue

                await asyncio.sleep(28)
                result_data = await get_real_result(page)
                if not result_data:
                    await bot.send_message(user_id, "⚠️ Result not found!")
                    continue

                is_win = (result_data["size"] == predicted_size)
                if is_win:
                    profit = bet_amount * 0.96
                    lose_streak = 0
                else:
                    profit = -bet_amount
                    lose_streak += 1

                total_profit += profit
                balance = float(data.get("balance", "0").replace(",", ""))

            elif mode == "virtual":
                if virtual_balances.get(user_id, 0) >= bet_amount:
                    virtual_balances[user_id] -= bet_amount
                    if random.random() < 0.5:
                        profit = bet_amount * 0.96
                        virtual_balances[user_id] += bet_amount + profit
                        lose_streak = 0
                    else:
                        profit = -bet_amount
                        lose_streak += 1
                    total_profit += profit
                    balance = virtual_balances[user_id]
                    result_data = {"period": f"{datetime.now().strftime('%Y%m%d%H%M%S')}", "number": "N/A", "size": predicted_size, "color_emoji": "⚪"}
                else:
                    await bot.send_message(user_id, "⚠️ Balance မလုံလောက်ပါ။")
                    await state.update_data(auto_bet_running=False)
                    break

            # 6. Send Notification (ခင်ဗျားလိုချင်တဲ့ပုံစံအတိုင်း)
            period_display = result_data.get("period", "N/A")
            win_emoji = "✅" if is_win else "❌"
            win_lose_text = f"{win_emoji} WIN! +{profit:,.2f} Ks" if is_win else f"{win_emoji} LOSE! -{bet_amount:,.2f} Ks"

            await bot.send_message(
                user_id,
                f"🎮 WINGO_30S: {period_display}\n"
                f"📊 {predicted_size.upper()} | {bet_amount:,.0f} Ks\n"
                f"🧠 {ai_name}\n\n"
                f"{win_lose_text}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎮 WINGO_30S : {period_display}\n"
                f"📊 Result: {result_data.get('number', 'N/A')} {result_data.get('color_emoji', '⚪')} {result_data.get('size', 'N/A')}\n"
                f"💰 Balance: {balance:,.2f} Ks\n"
                f"📈 Profit: {total_profit:,.2f} Ks"
            )

            # 7. Wait for next period
            await asyncio.sleep(30 - (datetime.now().second % 30))

        except Exception as e:
            print(f"Auto-Bet Error: {e}")
            await asyncio.sleep(5)

# ==========================================================
# 🕹️ Start/Stop Auto-Bet
# ==========================================================
@dp.message(F.text == "▶️ Start Auto-Bet")
async def start_auto_bet(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    mode = data.get("mode", "virtual")
    ai_mode = data.get("ai_mode", DEFAULT_AI_MODE)
    bet_sequence = data.get("bet_sequence", DEFAULT_BET_SEQUENCE)

    if mode == "real" and user_id not in active_sessions:
        await message.answer("⚠️ Real Mode အတွက် Login ဝင်ရန်လိုပါသည်။")
        return

    await state.update_data(auto_bet_running=True)
    bet_str = " → ".join([f"{b:,}" for b in bet_sequence])
    await message.answer(
        f"🚀 <b>Auto-Bet စတင်နေပါသည်...</b>\n"
        f"Mode: {mode}\n"
        f"AI: {AI_MODES.get(ai_mode, {}).get('name', 'AI')}\n"
        f"Bet Sequence: {bet_str}"
    )

    asyncio.create_task(auto_bet_loop(
        user_id, state, mode,
        active_sessions.get(user_id, {}).get("page") if mode == "real" else None,
        None  # session ကို main ကနေ ရယူမယ်
    ))

@dp.message(F.text == "⏹️ Stop Auto-Bet")
async def stop_auto_bet(message: types.Message, state: FSMContext):
    await state.update_data(auto_bet_running=False)
    await message.answer("⏹️ <b>Auto-Bet ရပ်တန့်သွားပါပြီ။</b>")

# ==========================================================
# 📋 Info, Status, AI Mode, Bet Size, Target, Logout, Games
# ==========================================================
@dp.message(F.text == "📋 Info")
async def show_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('user_id', 'N/A')
    username = data.get('username', 'N/A')
    nickname = data.get('nickname', 'Unknown')
    balance = data.get('balance', '0.00 Ks')
    login_time = data.get('login_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    await message.answer(
        f"👤 <b>User Information:</b>\n"
        f"├─ 🆔 <b>User ID:</b> {user_id}\n"
        f"├─ 📱 <b>Username:</b> {username}\n"
        f"├─ 🏷️ <b>Nickname:</b> {nickname}\n"
        f"├─ 💰 <b>Balance:</b> {balance}\n"
        f"├─ 📅 <b>Login Date:</b> {login_time}\n"
        f"└─ ✅ <b>Allow Withdraw:</b> Yes\n",
        reply_markup=get_logged_in_keyboard()
    )

@dp.message(F.text == "📊 Status")
async def show_status(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode", "virtual")
    ai_mode = data.get("ai_mode", DEFAULT_AI_MODE)
    bet_sequence = data.get("bet_sequence", DEFAULT_BET_SEQUENCE)
    profit_target = data.get("profit_target", 30000.0)
    is_running = data.get("auto_bet_running", False)
    bet_str = " → ".join([f"{b:,}" for b in bet_sequence])
    await message.answer(
        f"📊 <b>Status</b>\n"
        f"Mode: {mode}\n"
        f"AI: {AI_MODES.get(ai_mode, {}).get('name', 'AI')}\n"
        f"Bet Sequence: {bet_str}\n"
        f"🎯 Target: {profit_target:,.0f} Ks\n"
        f"🔄 Auto-Bet: {'Running' if is_running else 'Stopped'}"
    )

@dp.message(F.text == "🧠 AI Mode")
async def handle_ai_mode(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_mode = data.get("ai_mode", DEFAULT_AI_MODE)
    await message.answer(
        f"🧠 <b>AI Mode ရွေးပါ</b>\n"
        f"📌 လက်ရှိ: {AI_MODES.get(current_mode, {}).get('name', 'AI')}",
        reply_markup=get_ai_mode_inline_keyboard(current_mode)
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("usermode_"))
async def cb_user_mode_select(callback: types.CallbackQuery, state: FSMContext):
    mode_key = callback.data.replace("usermode_", "")
    if mode_key in AI_MODES:
        await state.update_data(ai_mode=mode_key)
        await callback.message.edit_text(f"✅ AI Mode: {AI_MODES[mode_key]['name']}")
        await callback.answer()

@dp.message(F.text == "💲 Bet Size")
async def handle_betsize(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_seq = data.get("bet_sequence", DEFAULT_BET_SEQUENCE)
    current_str = " → ".join([f"{b:,}" for b in current_seq])
    await message.answer(
        f"💲 <b>Bet Size သတ်မှတ်ရန်</b>\n\n"
        f"📌 လက်ရှိ: {current_str} ({len(current_seq)} ဆင့်)\n\n"
        f"👇 Preset ရွေးပါ သို့မဟုတ် Custom ထည့်ပါ:",
        reply_markup=get_betsize_inline_keyboard(current_seq)
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("setbetsize_"))
async def cb_set_betsize(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.replace("setbetsize_", "").split("_")
    bet_seq = [int(x) for x in parts]
    await state.update_data(bet_sequence=bet_seq)
    bet_str = " → ".join([f"{b:,}" for b in bet_seq])
    await callback.message.edit_text(
        f"✅ <b>Bet Size သတ်မှတ်ပြီး!</b>\n\n"
        f"💲 Sequence ({len(bet_seq)} ဆင့်): {bet_str}",
        reply_markup=get_betsize_inline_keyboard(bet_seq)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "betsize_custom")
async def cb_betsize_custom(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_betsize_input[user_id] = True
    await callback.message.edit_text(
        f"✏️ <b>Custom Bet Size သတ်မှတ်ရန်</b>\n\n"
        f"👇 <b>အောက်ပါပုံစံအတိုင်း စာရိုက်ထည့်ပါ:</b>\n"
        f"<code>100-300-900-2700-8100-24300</code>\n\n"
        f"Cancel: <code>/cancel</code>"
    )
    await callback.answer()

@dp.message(lambda m: m.text and '-' in m.text and m.from_user.id in user_betsize_input)
async def handle_betsize_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        parts = message.text.strip().split('-')
        bet_seq = [float(p.strip().replace(',', '')) for p in parts if p.strip()]
        await state.update_data(bet_sequence=bet_seq)
        del user_betsize_input[user_id]
        bet_str = " → ".join([f"{b:,.0f}" for b in bet_seq])
        await message.reply(
            f"✅ <b>Custom Bet Size သတ်မှတ်ပြီး!</b>\n"
            f"💲 Sequence: {bet_str}",
            reply_markup=get_logged_in_keyboard() if user_id in active_sessions else get_main_keyboard()
        )
    except:
        await message.reply("❌ ပုံစံမှားနေပါသည်။ ဥပမာ: 100-300-900")

@dp.message(F.text == "🎯 Target")
async def handle_target(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_target = data.get("profit_target", 30000.0)
    await message.answer(
        f"🎯 <b>Profit Target သတ်မှတ်ရန်</b>\n\n"
        f"📌 လက်ရှိ: {current_target:,.0f} Ks\n\n"
        f"👇 ပမာဏရွေးပါ သို့မဟုတ် Custom ထည့်ပါ:",
        reply_markup=get_target_inline_keyboard()
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("settarget_"))
async def cb_set_target(callback: types.CallbackQuery, state: FSMContext):
    target = float(callback.data.replace("settarget_", ""))
    await state.update_data(profit_target=target)
    await callback.message.edit_text(f"✅ <b>Profit Target သတ်မှတ်ပြီး!</b>\n🎯 Target: {target:,.0f} Ks")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "target_custom")
async def cb_target_custom(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_target_input[user_id] = True
    await callback.message.edit_text(
        f"✏️ <b>Custom Profit Target ထည့်ရန်</b>\n\n"
        f"👇 ဂဏန်းထည့်ပါ (ဥပမာ: <code>50000</code>):\n"
        f"Cancel: <code>/cancel</code>"
    )
    await callback.answer()

@dp.message(lambda m: m.text and m.text.strip().isdigit() and m.from_user.id in user_target_input)
async def handle_target_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        target = float(message.text.strip())
        await state.update_data(profit_target=target)
        del user_target_input[user_id]
        active_users = await db.get_active_users()
        await message.reply(
            f"✅ <b>Profit Target သတ်မှတ်ပြီး!</b>\n🎯 Target: {target:,.0f} Ks",
            reply_markup=get_logged_in_keyboard() if user_id in active_users else get_main_keyboard()
        )
    except:
        await message.reply("❌ ဂဏန်းသာထည့်ပါ။")

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_target_input:
        del user_target_input[user_id]
    if user_id in user_betsize_input:
        del user_betsize_input[user_id]
    await message.reply("✅ Cancelled.")

@dp.message(LoginForm.main_menu, F.text == "🔐 Logout")
async def logout(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id in active_sessions:
        try:
            await active_sessions[user_tg_id]["browser"].close()
            await active_sessions[user_tg_id]["playwright"].stop()
        except:
            pass
        del active_sessions[user_tg_id]
    await state.clear()
    await message.answer("👋 Logout လုပ်ပြီးပါပြီ။", reply_markup=get_main_keyboard())

@dp.message(F.text == "🎰 Games")
async def games(message: types.Message):
    await message.answer("🎮 Win Go 30s", reply_markup=get_main_keyboard())

@dp.callback_query(lambda c: c.data == "cmd_back")
async def cb_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

# ==========================================================
# 🚀 Main
# ==========================================================
async def main():
    print("🚀 Auto-Bot (API + Playwright + AI) Started...")
    await bot.delete_webhook(drop_pending_updates=True)

    # Real Mode အတွက် API Session ကို ကြိုတင်ပြင်ဆင်ထားမယ်
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot Stopped.")
