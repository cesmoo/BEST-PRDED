# bot.py (Real/Virtual Mode - AI Prediction + Auto-Bet + Full Features)
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
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from playwright.async_api import async_playwright

from ai_engines import get_prediction, AI_MODES
from database import db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Global variables
active_sessions = {}       # Real Mode: Playwright sessions
virtual_balances = {}      # Virtual Mode: in-memory balance
user_target_input = {}
user_betsize_input = {}
DEFAULT_BET_SEQUENCE = [100, 300, 900, 2700, 8100, 24300]
DEFAULT_AI_MODE = "ensemble"

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
# ⌨️ Keyboards
# ==========================================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 Login")],
            [KeyboardButton(text="🎰 Games")],
            [KeyboardButton(text="⚙️ Mode")],
            [KeyboardButton(text="📊 Status")],
            [KeyboardButton(text="🧠 AI Mode")],
            [KeyboardButton(text="💲 Bet Size")],
            [KeyboardButton(text="🎯 Target")]
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
            [KeyboardButton(text="🔐 Logout")],
            [KeyboardButton(text="📊 Status")],
            [KeyboardButton(text="🧠 AI Mode")],
            [KeyboardButton(text="💲 Bet Size")],
            [KeyboardButton(text="🎯 Target")]
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

# ... (Login/Playwright အပိုင်းကို မူရင်းအတိုင်းထားပါ၊ အောက်မှာ auto-bet ကို ပြင်ပါမယ်)

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

async def auto_bet_loop(user_id: int, state: FSMContext, mode: str, page=None):
    lose_streak = 0
    total_profit = 0.0
    balance = 0.0

    while True:
        try:
            data = await state.get_data()
            if not data.get("auto_bet_running"):
                break

            # Load user settings
            ai_mode = data.get("ai_mode", DEFAULT_AI_MODE)
            bet_sequence = data.get("bet_sequence", DEFAULT_BET_SEQUENCE)
            profit_target = data.get("profit_target", 30000.0)

            # Check profit target
            if total_profit >= profit_target:
                await state.update_data(auto_bet_running=False)
                await bot.send_message(user_id, f"🎯 Target Reached! Total Profit: {total_profit:,.2f} Ks")
                break

            # Get AI prediction
            history_docs = await db.get_history(50)
            if not history_docs:
                await asyncio.sleep(5)
                continue

            predicted_size, prob, display, reason = await get_ai_prediction(history_docs, ai_mode)
            ai_name = AI_MODES.get(ai_mode, {}).get("name", "AI")

            # Bet amount from sequence
            if lose_streak >= len(bet_sequence):
                lose_streak = 0
            bet_amount = bet_sequence[lose_streak]

            # ========== EXECUTE BET based on MODE ==========
            if mode == "real" and page:
                # Real Mode: Playwright
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
                    result_text = f"WIN! +{profit:,.2f} Ks"
                else:
                    profit = -bet_amount
                    lose_streak += 1
                    result_text = f"LOSE! -{bet_amount:,.2f} Ks"

                total_profit += profit
                balance = float(data.get("balance", "0").replace(",", ""))

            elif mode == "virtual":
                # Virtual Mode: In-memory
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
                    result_data = {"period": f"Virtual-{datetime.now().strftime('%H%M%S')}", "number": "N/A", "size": predicted_size, "color_emoji": "⚪"}
                else:
                    await bot.send_message(user_id, "⚠️ Virtual Balance မလုံလောက်ပါ။")
                    await state.update_data(auto_bet_running=False)
                    break

            # ========== SEND NOTIFICATION (Same format for both modes) ==========
            period_display = result_data.get("period", "N/A")
            await bot.send_message(
                user_id,
                f"⚡ WINGO_30S : {period_display}\n"
                f"⚡ {predicted_size.upper()} | {bet_amount:,.0f} Ks | 📉 Streak: {lose_streak}/{len(bet_sequence)}\n"
                f"🎯 {ai_name} | AI: {display} ({prob:.0f}%)\n\n"
                f"{result_text}\n"
                f"─────────────────────\n"
                f"⚡ WINGO_30S : {period_display}\n"
                f"⚡ Result: {result_data.get('number', 'N/A')} {result_data.get('color_emoji', '⚪')} {result_data.get('size', 'N/A')}\n"
                f"⚡ Balance: {balance:,.2f} Ks\n"
                f"⚡ Profit: {total_profit:,.2f} Ks"
            )

            # Wait for next period
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
        active_sessions.get(user_id, {}).get("page") if mode == "real" else None
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
    await message.answer("💲 Bet Size သတ်မှတ်ရန်", reply_markup=get_betsize_inline_keyboard(current_seq))

@dp.callback_query(lambda c: c.data and c.data.startswith("setbetsize_"))
async def cb_set_betsize(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.replace("setbetsize_", "").split("_")
    bet_seq = [int(x) for x in parts]
    await state.update_data(bet_sequence=bet_seq)
    await callback.message.edit_text(f"✅ Bet Size Updated: {' → '.join([f'{b:,}' for b in bet_seq])}")
    await callback.answer()

@dp.message(F.text == "🎯 Target")
async def handle_target(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_target = data.get("profit_target", 30000.0)
    await message.answer(f"🎯 Target: {current_target:,.0f} Ks", reply_markup=get_target_inline_keyboard())

@dp.callback_query(lambda c: c.data and c.data.startswith("settarget_"))
async def cb_set_target(callback: types.CallbackQuery, state: FSMContext):
    target = float(callback.data.replace("settarget_", ""))
    await state.update_data(profit_target=target)
    await callback.message.edit_text(f"✅ Target: {target:,.0f} Ks")
    await callback.answer()

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
    print("🚀 Auto-Bot (Real/Virtual + AI) Started...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot Stopped.")
