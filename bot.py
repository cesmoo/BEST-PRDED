# bot.py (Real/Virtual Mode - Identical Logic, Only Balance Differs)
import asyncio
import os
import html
import random
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from playwright.async_api import async_playwright

from ai_engines import get_prediction, AI_MODES
from database import db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Real Mode: Playwright sessions (for API interaction)
active_sessions = {}
# Virtual Mode: In-memory virtual balances
virtual_balances = {}

# ==========================================================
# 🗂️ FSM States
# ==========================================================
class LoginForm(StatesGroup):
    select_site = State()
    enter_phone = State()
    enter_password = State()
    main_menu = State()
    choose_mode = State()
    auto_bet_running = State()

# ==========================================================
# ⌨️ Keyboards (Identical for both modes)
# ==========================================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 Login")],
            [KeyboardButton(text="🎰 Games")],
            [KeyboardButton(text="⚙️ Mode")]
        ],
        resize_keyboard=True
    )

def get_site_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="777BIGWIN")],
            [KeyboardButton(text="🔙 နောက်သို့")]
        ],
        resize_keyboard=True
    )

def get_mode_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 Real Mode")],
            [KeyboardButton(text="🟡 Virtual Mode")],
            [KeyboardButton(text="🔙 နောက်သို့")]
        ],
        resize_keyboard=True
    )

def get_logged_in_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Info")],
            [KeyboardButton(text="🎰 Games")],
            [KeyboardButton(text="▶️ Start Auto-Bet")],
            [KeyboardButton(text="⏹️ Stop Auto-Bet")],
            [KeyboardButton(text="🔐 Logout")]
        ],
        resize_keyboard=True
    )

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
            virtual_balances[user_id] = 100000.0  # default virtual balance
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
    data = await state.get_data()
    if data.get("mode") == "virtual":
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
# 🎯 Core Logic (Identical for Real & Virtual)
# ==========================================================
async def get_ai_prediction(history_docs, mode_key="ensemble"):
    predicted_size, display, prob, reason = get_prediction(history_docs, mode_key)
    return predicted_size, prob

async def get_real_result(page):
    """Scrape latest result from WinGo page"""
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
        
        return {
            "period": period.strip(),
            "number": number.strip(),
            "size": size,
            "color": color_text.strip(),
            "color_emoji": color_emoji
        }
    except:
        return None

async def place_auto_bet(page, bet_type: str, amount: int):
    """Place bet using Playwright (Real Mode)"""
    try:
        bet_choice = bet_type.lower()
        if bet_choice == "big":
            await page.locator('.Betting__C-foot-b').click(timeout=5000)
        elif bet_choice == "small":
            await page.locator('.Betting__C-foot-s').click(timeout=5000)
        elif bet_choice == "red":
            await page.locator('.Betting__C-head-r').click(timeout=5000)
        elif bet_choice == "green":
            await page.locator('.Betting__C-head-g').click(timeout=5000)
        elif bet_choice in ["violet", "purple"]:
            await page.locator('.Betting__C-head-p').click(timeout=5000)
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
    except Exception as e:
        print(f"Place bet error: {e}")
        return False

# ==========================================================
# 🔄 Auto-Bet Loop (Unified for Real & Virtual)
# ==========================================================
async def auto_bet_loop(user_id: int, state: FSMContext, mode: str, page=None):
    lose_streak = 0
    bet_sequence = [100, 300, 900, 2700, 8100, 24300]  # 6 steps
    total_profit = 0.0
    balance = 0.0

    while True:
        try:
            data = await state.get_data()
            if not data.get("auto_bet_running"):
                break

            # Get AI prediction
            history_docs = await db.get_history(50)
            if not history_docs:
                await asyncio.sleep(5)
                continue

            predicted_size, prob = await get_ai_prediction(history_docs, "ensemble")
            ai_name = "Golden Ratio"  # or any AI mode name

            # Bet amount from sequence
            if lose_streak >= len(bet_sequence):
                lose_streak = 0
            bet_amount = bet_sequence[lose_streak]

            # ========== EXECUTE BET (Real or Virtual) ==========
            if mode == "real" and page:
                # Real Mode: Place bet via Playwright
                success = await place_auto_bet(page, predicted_size, bet_amount)
                if not success:
                    await bot.send_message(user_id, "⚠️ Bet placement failed!")
                    continue

                # Wait for result
                await asyncio.sleep(28)

                # Scrape result
                result_data = await get_real_result(page)
                if not result_data:
                    await bot.send_message(user_id, "⚠️ Result not found!")
                    continue

                # Determine win/lose
                is_win = (result_data["size"] == predicted_size)
                if is_win:
                    profit = bet_amount * 0.96
                    lose_streak = 0
                    result_text = f"WIN! +{profit:,.2f} Ks"
                else:
                    profit = -bet_amount
                    lose_streak += 1
                    result_text = f"LOSE! -{bet_amount:,.2f} Ks"

                total_profit += profit
                balance = float(data.get("balance", "0").replace(",", ""))  # real balance from login

            else:
                # Virtual Mode: Simulate with virtual balance
                if virtual_balances.get(user_id, 0) >= bet_amount:
                    virtual_balances[user_id] -= bet_amount
                    if random.random() < 0.5:
                        profit = bet_amount * 0.96
                        virtual_balances[user_id] += bet_amount + profit
                        lose_streak = 0
                        result_text = f"WIN! +{profit:,.2f} Ks"
                    else:
                        profit = -bet_amount
                        lose_streak += 1
                        result_text = f"LOSE! -{bet_amount:,.2f} Ks"
                    
                    total_profit += profit
                    balance = virtual_balances[user_id]
                    result_data = {"period": f"Virtual-{datetime.now().strftime('%H%M%S')}"}
                else:
                    await bot.send_message(user_id, "⚠️ Virtual Balance မလုံလောက်ပါ။ Auto-Bet ရပ်နေပါသည်။")
                    await state.update_data(auto_bet_running=False)
                    break

            # ========== SEND NOTIFICATION (Identical for both modes) ==========
            period_display = result_data.get("period", "N/A")
            await bot.send_message(
                user_id,
                f"⚡ WINGO_30S : {period_display}\n"
                f"⚡ {predicted_size.upper()} | {bet_amount:,.0f} Ks | 📉 Streak: {lose_streak}/{len(bet_sequence)}\n"
                f"🎯 {ai_name}\n\n"
                f"{result_text}\n"
                f"─────────────────────\n"
                f"⚡ WINGO_30S : {period_display}\n"
                f"⚡ Result: {result_data.get('number', 'N/A')} {result_data.get('color_emoji', '⚪')} {result_data.get('size', 'N/A')} {result_data.get('color_emoji', '⚪')}\n"
                f"⚡ Balance: {balance:,.2f} Ks\n"
                f"⚡ Profit: {total_profit:,.2f} Ks"
            )

            # Wait for next period
            await asyncio.sleep(30 - (datetime.now().second % 30))

        except Exception as e:
            print(f"Auto-Bet Error: {e}")
            await asyncio.sleep(5)

# ==========================================================
# 🕹️ Start/Stop Auto-Bet (Unified)
# ==========================================================
@dp.message(F.text == "▶️ Start Auto-Bet")
async def start_auto_bet(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    mode = data.get("mode", "virtual")

    if mode == "real" and user_id not in active_sessions:
        await message.answer("⚠️ Real Mode အတွက် Login ဝင်ရန်လိုပါသည်။")
        return

    await state.update_data(auto_bet_running=True)
    await message.answer(
        f"🚀 <b>Auto-Bet စတင်နေပါသည်...</b>\n"
        f"Mode: {mode}\n"
        f"Bet Sequence: 100→300→900→2700→8100→24300\n"
        f"AI: Golden Ratio"
    )

    asyncio.create_task(auto_bet_loop(
        user_id,
        state,
        mode,
        active_sessions.get(user_id, {}).get("page") if mode == "real" else None
    ))

@dp.message(F.text == "⏹️ Stop Auto-Bet")
async def stop_auto_bet(message: types.Message, state: FSMContext):
    await state.update_data(auto_bet_running=False)
    await message.answer("⏹️ <b>Auto-Bet ရပ်တန့်သွားပါပြီ။</b>")

# ==========================================================
# 📋 Info & Logout
# ==========================================================
@dp.message(LoginForm.main_menu, F.text == "📋 Info")
async def show_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('user_id', 'N/A')
    username = data.get('username', 'N/A')
    nickname = data.get('nickname', 'Unknown')
    balance = data.get('balance', '0.00 Ks')
    login_time = data.get('login_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    info_text = (
        "👤 <b>User Information:</b>\n"
        "├─ 🆔 <b>User ID:</b> {user_id}\n"
        "├─ 📱 <b>Username:</b> {username}\n"
        "├─ 🏷️ <b>Nickname:</b> {nickname}\n"
        "├─ 💰 <b>Balance:</b> {balance}\n"
        "├─ 📅 <b>Login Date:</b> {login_time}\n"
        "└─ ✅ <b>Allow Withdraw:</b> Yes\n"
    ).format(
        user_id=user_id, username=username, nickname=nickname, 
        balance=balance, login_time=login_time
    )
    await message.answer(info_text, reply_markup=get_logged_in_keyboard())

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
    await message.answer("👋 အကောင့်ထွက်ပြီးပါပြီ။", reply_markup=get_main_keyboard())

@dp.message(F.text == "🎰 Games")
async def games(message: types.Message):
    await message.answer(
        "🎮 <b>Game ရွေးချယ်ရန်:</b>\n"
        "Win Go 30s ကို ရွေးချယ်ထားပါသည်။\n"
        "Auto Bet အတွက် <b>Start Auto-Bet</b> ကိုနှိပ်ပါ။",
        reply_markup=get_main_keyboard()
    )

# ==========================================================
# 🚀 Main
# ==========================================================
async def main():
    print("🚀 Auto-Bot (Real/Virtual - Unified Logic) စတင်နေပါပြီ...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
