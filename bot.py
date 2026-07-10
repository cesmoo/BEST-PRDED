# bot.py (မူရင်းအတိုင်း + Real/Virtual Mode + Playwright Auto-Bet)
import asyncio
import time
import os
import io
from datetime import datetime
from dotenv import load_dotenv
import aiohttp

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    BufferedInputFile, InputMediaPhoto,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import BaseMiddleware

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import warnings
warnings.filterwarnings("ignore")

from database import db
from ai_engines import AI_MODES, get_prediction

# ==========================================
# 1. CONFIGURATION
# ==========================================
load_dotenv()

USERNAME = os.getenv("BIGWIN_USERNAME", "959675323878")
PASSWORD = os.getenv("BIGWIN_PASSWORD", "Mitheint11")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OWNER_ID = os.getenv("OWNER_ID")

if not all([BOT_TOKEN, CHANNEL_ID, OWNER_ID]):
    print("❌ Error: .env ဖိုင်တွင် အချက်အလက်များ မပြည့်စုံပါ။")
    exit()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

auth_router = Router()
owner_router = Router()

# ==========================================
# 2. PREMIUM EMOJI CONSTANTS
# ==========================================
PREMIUM_EMOJI_IDS = {
    "win_check": "5852871561983299073",
    "lose_cross": "5852812849780362931",
    "order": "5936130851635990622",
    "game": "5936130851635990622",
    "chart": "5936130851635990622",
    "money": "5936130851635990622",
    "loss": "5936130851635990622",
    "brain": "5936130851635990622",
    "chart_up": "5936130851635990622",
    "momentum": "5936130851635990622",
    "chart_down": "5936130851635990622",
}


def premium_emoji(key, fallback):
    emoji_id = PREMIUM_EMOJI_IDS.get(key, "0")
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


class Emoji:
    # ========== Premium Emojis (Message Text အတွက်ပဲ) ==========
    WIN_CHECK = premium_emoji("win_check", "✅")
    LOSE_CROSS = premium_emoji("lose_cross", "❌")
    ORDER = premium_emoji("order", "📝")
    GAME_ICON = premium_emoji("game", "🎮")
    CHART_ICON = premium_emoji("chart", "📊")
    MONEY_ICON = premium_emoji("money", "💰")
    LOSS_ICON = premium_emoji("loss", "📉")
    BRAIN = premium_emoji("brain", "🧠")
    CHART_UP = premium_emoji("chart_up", "📈")
    MOMENTUM = premium_emoji("momentum", "📈")
    CHART_DOWN = premium_emoji("chart_down", "📉")

    # ========== Standard Emojis (Keyboard & Print အတွက်) ==========
    CHECK = "✅"
    CROSS = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    STAR = "⭐"
    CROWN = "👑"
    FIRE = "🔥"
    SPARKLES = "✨"
    LOCK = "🔒"
    UNLOCK = "🔓"
    KEY = "🔑"
    SHIELD = "🛡️"
    GAME = "🎮"
    MONEY = "💰"
    MONEY_BAG = "💵"
    COIN = "🪙"
    BAR_CHART = "📊"
    GEM = "💎"
    GOLD = "🥇"
    SILVER = "🥈"
    BRONZE = "🥉"
    ONLINE = "🟢"
    OFFLINE = "🔴"
    IDLE = "🟡"
    ROBOT = "🤖"
    PATTERN = "🎯"
    MARTINGALE = "🎲"
    ANTIMARTINGALE = "🔄"
    TREND = "📊"
    FIBONACCI = "🔢"
    GOLDEN = "🎯"
    MONTECARLO = "🎲"
    NEURAL = "🧬"
    REVERSAL = "⚡"
    WAVE = "🌊"
    CHAOS = "🎪"
    BET = "🎰"
    CLOCK = "⏰"
    HOURGLASS = "⏳"
    BULLSEYE = "🔴"
    GREEN_CIRCLE = "🟢"
    UP = "⬆️"
    DOWN = "⬇️"
    LEFT_RIGHT = "↔️"
    OWNER = "👑"
    SUDO = "🛡️"
    USER = "👤"
    BANNED = "🚫"


# ==========================================
# 3. SYSTEM VARIABLES
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = None
MAIN_MESSAGE_ID = None
SESSION_START_ISSUE = None
DEFAULT_AI_MODE = "ensemble"
SUDO_USERS = set()

# Default Bet Sequence (6 ဆင့်)
DEFAULT_BET_SEQUENCE = [100, 300, 900, 2700, 8100, 24300]
DEFAULT_MODE = "virtual"  # Default Mode (virtual / real)

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# Playwright Session သိမ်းရန် (Real Mode အတွက်)
playwright_sessions = {}

# ==========================================
# 4. PERMISSION MIDDLEWARE
# ==========================================
class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            user_id = event.from_user.id
        elif isinstance(event, types.CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        if str(user_id) != str(OWNER_ID) and user_id not in SUDO_USERS:
            if isinstance(event, types.Message):
                await event.reply("🔒 <b>Access Denied!</b>")
            elif isinstance(event, types.CallbackQuery):
                await event.answer("🔒 Access Denied!", show_alert=True)
            return

        return await handler(event, data)


class OwnerOnlyMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            user_id = event.from_user.id
        elif isinstance(event, types.CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        if str(user_id) != str(OWNER_ID):
            if isinstance(event, types.Message):
                await event.reply("❌ Owner only!")
            elif isinstance(event, types.CallbackQuery):
                await event.answer("👑 Owner only!", show_alert=True)
            return

        return await handler(event, data)


auth_router.message.middleware(AuthMiddleware())
auth_router.callback_query.middleware(AuthMiddleware())
owner_router.message.middleware(OwnerOnlyMiddleware())
owner_router.callback_query.middleware(OwnerOnlyMiddleware())


# ==========================================
# 5. KEYBOARD BUILDERS (Standard Emoji Only)
# ==========================================
def get_main_reply_keyboard(is_active: bool = False, mode: str = "virtual") -> ReplyKeyboardMarkup:
    """Main Reply Keyboard - Standard Emoji Only"""
    builder = ReplyKeyboardBuilder()

    if is_active:
        builder.row(KeyboardButton(text="⏹️ Stop Auto-Bet"))
    else:
        builder.row(KeyboardButton(text="▶️ Start Auto-Bet"))

    # Mode Selection
    mode_btn = "🔵 Real Mode" if mode == "real" else "🟡 Virtual Mode"
    builder.row(KeyboardButton(text=mode_btn), KeyboardButton(text="🧠 AI Mode"))

    builder.row(
        KeyboardButton(text="💰 Balance"),
        KeyboardButton(text="📊 Status"),
    )
    builder.row(
        KeyboardButton(text="⚙️ Settings"),
        KeyboardButton(text="📋 My Bets"),
    )
    builder.row(
        KeyboardButton(text="👑 Top 10"),
    )

    return builder.as_markup(resize_keyboard=True)


def get_settings_inline_keyboard() -> InlineKeyboardMarkup:
    """Settings Inline Keyboard - Standard Emoji Only"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(
        text="💎 Add Balance",
        callback_data="cmd_addbal"
    ))
    builder.row(InlineKeyboardButton(
        text="💵 Withdraw",
        callback_data="cmd_withdraw"
    ))
    builder.row(InlineKeyboardButton(
        text="🎯 Set Profit Target",
        callback_data="cmd_target"
    ))
    builder.row(InlineKeyboardButton(
        text="💲 Set Bet Size",
        callback_data="cmd_betsize"
    ))
    builder.row(InlineKeyboardButton(
        text="📈 Compare AI Modes",
        callback_data="cmd_compare"
    ))
    builder.row(InlineKeyboardButton(
        text="🔙 Back",
        callback_data="cmd_back"
    ))

    return builder.as_markup()


def get_ai_mode_inline_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    """AI Mode Selection Inline Keyboard - Standard Emoji Only"""
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

    builder.row(InlineKeyboardButton(
        text="🔙 Back to Main",
        callback_data="cmd_back"
    ))

    return builder.as_markup()


def get_add_balance_keyboard() -> InlineKeyboardMarkup:
    """Add Balance Inline Keyboard"""
    builder = InlineKeyboardBuilder()
    for amt in [10000, 50000, 100000, 500000]:
        builder.row(InlineKeyboardButton(
            text=f"💵 +{amt:,} Ks",
            callback_data=f"addbal_{amt}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="cmd_back"))
    return builder.as_markup()


def get_withdraw_keyboard() -> InlineKeyboardMarkup:
    """Withdraw Inline Keyboard"""
    builder = InlineKeyboardBuilder()
    for amt in [10000, 50000, 100000]:
        builder.row(InlineKeyboardButton(
            text=f"💵 -{amt:,} Ks",
            callback_data=f"withdraw_{amt}"
        ))
    builder.row(InlineKeyboardButton(text="💰 Withdraw All", callback_data="withdraw_all"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="cmd_back"))
    return builder.as_markup()


def get_betsize_inline_keyboard(current_seq: list) -> InlineKeyboardMarkup:
    """Bet Size Selection Inline Keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(
        text="💰 100-300-900-2700-8100-24300 (6 Steps - Default)",
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
        text="✏️ Custom Bet Size (စာရိုက်ထည့်ရန်)",
        callback_data="betsize_custom"
    ))
    builder.row(InlineKeyboardButton(
        text="🔙 Back to Settings",
        callback_data="cmd_back"
    ))

    return builder.as_markup()


# ==========================================
# 6. API FUNCTIONS (For History Data)
# ==========================================
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


# ==========================================
# 7. PLAYWRIGHT LOGIN (Real Mode)
# ==========================================
async def playwright_login(user_id: int, username: str, password: str):
    """Playwright ဖြင့် BigWin သို့ Login ဝင်ပြီး Page ကို သိမ်းဆည်းခြင်း"""
    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        viewport={'width': 390, 'height': 844},
        is_mobile=True
    )
    page = await context.new_page()
    try:
        await page.goto("https://www.777bigwingame.app/#/login", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Fill login form
        await page.fill('input[name="userNumber"]', username)
        await page.fill('input[placeholder="စကားဝှက်"]', password)
        await page.click('button.active')
        await page.wait_for_timeout(5000)

        # Close popup if any
        try:
            await page.click(".announcement-dialog__button")
        except:
            pass

        if "login" not in page.url.lower():
            # Go to WinGo page
            await page.goto("https://www.777bigwingame.app/#/home/AllLotteryGames/WinGo?id=1", wait_until="networkidle")
            await page.wait_for_timeout(2000)
            playwright_sessions[user_id] = {
                "playwright": p,
                "browser": browser,
                "page": page
            }
            return True
        else:
            await browser.close()
            await p.stop()
            return False
    except Exception as e:
        print(f"Playwright Login Error: {e}")
        await browser.close()
        await p.stop()
        return False


# ==========================================
# 8. NOTIFICATION SYSTEM
# ==========================================
async def send_bet_result_notification(user_id, bet, actual_size, actual_number, is_win, profit, mode="virtual"):
    try:
        user = await db.get_user(user_id)
        active_users = await db.get_active_users()
        is_active = user_id in active_users

        color_map = {
            0: "🟣 VIOLET", 1: "🟢 GREEN", 2: "🔴 RED",
            3: "🟢 GREEN", 4: "🔴 RED", 5: "🟢 GREEN",
            6: "🔴 RED", 7: "🟢 GREEN", 8: "🔴 RED", 9: "🟢 GREEN"
        }
        color = color_map.get(actual_number, "⚪ WHITE")
        session_profit = user.get('session_profit', 0)

        if is_win:
            message = (
                f"{Emoji.WIN_CHECK} <b>WIN!</b> +{profit:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{Emoji.GAME_ICON} <b>WINGO_30S</b> : <code>{bet['issue_number']}</code>\n"
                f"{Emoji.CHART_ICON} <b>Result:</b> {actual_number} "
                f"{Emoji.BULLSEYE if actual_size == 'BIG' else Emoji.GREEN_CIRCLE} "
                f"{actual_size} {color}\n"
                f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.2f} Ks\n"
                f"{Emoji.CHART_UP} <b>Profit:</b> +{session_profit:,.2f} Ks"
            )
        else:
            message = (
                f"{Emoji.LOSE_CROSS} <b>LOSE!</b> -{bet['bet_amount']:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{Emoji.GAME_ICON} <b>WINGO_30S</b> : <code>{bet['issue_number']}</code>\n"
                f"{Emoji.CHART_ICON} <b>Result:</b> {actual_number} "
                f"{Emoji.BULLSEYE if actual_size == 'BIG' else Emoji.GREEN_CIRCLE} "
                f"{actual_size} {color}\n"
                f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.2f} Ks\n"
                f"{Emoji.LOSS_ICON} <b>Profit:</b> {session_profit:,.2f} Ks"
            )

        await bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=get_main_reply_keyboard(is_active, mode)
        )
    except Exception as e:
        print(f"Notification error for {user_id}: {e}")


async def send_target_reached_notification(user_id: int, mode="virtual"):
    try:
        user = await db.get_user(user_id)
        target = user.get('profit_target', 30000)
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"{Emoji.SPARKLES} <b>🎯 Profit Target Reached!</b>\n\n"
                f"{Emoji.MONEY_ICON} Session Profit: {user['session_profit']:,.2f} Ks\n"
                f"🎯 Target: {target:,.0f} Ks\n\n"
                f"{Emoji.CHECK} Auto-bet ရပ်ထားပါပြီ။\n"
                f"🟢 ပြန်စရန်: <b>Start Auto-Bet</b> ကိုနှိပ်ပါ။"
            ),
            reply_markup=get_main_reply_keyboard(False, mode)
        )
    except Exception as e:
        print(f"Target notification error for {user_id}: {e}")


# ==========================================
# 9. CORE GAME LOGIC (API + Playwright)
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, MAIN_MESSAGE_ID, SESSION_START_ISSUE

    active_users = await db.get_active_users()
    if not active_users:
        return False

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

            is_new = False
            if not LAST_PROCESSED_ISSUE or int(latest_issue) > int(LAST_PROCESSED_ISSUE):
                is_new = True

            if is_new:
                LAST_PROCESSED_ISSUE = latest_issue
                if not SESSION_START_ISSUE:
                    SESSION_START_ISSUE = latest_issue

                await db.add_history(latest_issue, latest_number, latest_size)

                # Settle bets and send notifications
                settled_bets = await db.settle_bets(latest_issue, latest_size, latest_number)
                for bet in settled_bets:
                    is_win = bet["result"] == "WIN"
                    profit = bet["profit"]
                    # Get user's mode from session
                    user_session = await db.get_user_session(bet["user_id"])
                    mode = user_session.get("mode", "virtual")
                    await send_bet_result_notification(
                        bet["user_id"], bet, latest_size, latest_number, is_win, profit, mode
                    )
                    user = await db.get_user(bet["user_id"])
                    if user["session_profit"] >= user.get("profit_target", 30000):
                        await db.deactivate_session(bet["user_id"])
                        await send_target_reached_notification(bet["user_id"], mode)

                if settled_bets:
                    print(f"💰 Settled {len(settled_bets)} bets - {latest_number} ({latest_size})")

                next_issue = str(int(latest_issue) + 1)
                history_docs = await db.get_history(5000)
                active_users = await db.get_active_users()

                for user_id in active_users:
                    try:
                        user = await db.get_user(user_id)
                        user_session = await db.get_user_session(user_id)
                        user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
                        mode = user_session.get("mode", "virtual")

                        # Get prediction using user's AI mode
                        predicted_size, predicted_display, final_prob, reason = get_prediction(
                            history_docs, user_ai_mode
                        )
                        await db.save_prediction(next_issue, predicted_size, user_ai_mode)

                        # ========== LOSE STREAK WITH AUTO RESET ==========
                        recent_bets = await db.get_user_bets(user_id, 30)

                        lose_streak = 0
                        for bet in recent_bets:
                            if bet.get("result") == "LOSE":
                                lose_streak += 1
                            elif bet.get("result") == "WIN":
                                break

                        bet_seq = user_session.get("bet_sequence", DEFAULT_BET_SEQUENCE)
                        if lose_streak >= len(bet_seq):
                            print(f"🔄 User {user_id}: Streak reset! {lose_streak} losses (max {len(bet_seq)}), back to {bet_seq[0]}")
                            lose_streak = 0

                        bet_amount = bet_seq[lose_streak]

                        if user["balance"] >= bet_amount:
                            result = await db.place_bet(
                                user_id, next_issue, bet_amount, predicted_size, user_ai_mode
                            )
                            if result["success"]:
                                ai_name = AI_MODES.get(user_ai_mode, {}).get("name", "AI")

                                if lose_streak > 0:
                                    streak_info = f" | 📉 Streak: {lose_streak}/{len(bet_seq)}"
                                else:
                                    streak_info = ""

                                order_msg = (
                                    f"{Emoji.GAME_ICON} WINGO_30S: <code>{next_issue}</code>\n"
                                    f"{Emoji.CHART_ICON} {predicted_size} | {bet_amount:,.0f} Ks{streak_info}\n"
                                    f"{Emoji.BRAIN} {ai_name}"
                                )
                                await bot.send_message(
                                    chat_id=user_id, text=order_msg,
                                    reply_markup=get_main_reply_keyboard(True, mode)
                                )

                                # ========== PLAYWRIGHT AUTO-BET (Real Mode) ==========
                                if mode == "real" and user_id in playwright_sessions:
                                    page = playwright_sessions[user_id]["page"]
                                    try:
                                        # Click BIG/SMALL button based on prediction
                                        if predicted_size == "BIG":
                                            await page.click('.Betting__C-foot-b')
                                        else:
                                            await page.click('.Betting__C-foot-s')
                                        await page.wait_for_timeout(1000)

                                        # Select bet amount
                                        amount_selector = f"div.Betting__Popup-body-line-item:has-text('{bet_amount:,.0f}')"
                                        await page.click(amount_selector)
                                        await page.wait_for_timeout(500)

                                        # Confirm bet
                                        await page.click('.Betting__Popup-foot > div:last-child')
                                        await page.wait_for_timeout(1000)
                                        print(f"✅ Playwright Bet Placed: {user_id} - {next_issue} - {predicted_size} - {bet_amount}")
                                    except Exception as e:
                                        print(f"Playwright Bet Error for {user_id}: {e}")
                                # ====================================================

                    except Exception as e:
                        print(f"Auto-bet error for {user_id}: {e}")

                default_pred, default_display, default_prob, default_reason = get_prediction(
                    history_docs, DEFAULT_AI_MODE
                )
                await update_channel_post(next_issue, default_display, default_prob, default_reason)
                return True
        return False

    elif data and (data.get('code') == 401 or "token" in str(data.get('msg')).lower()):
        CURRENT_TOKEN = ""
        return False
    return False


# ==========================================
# 10. CHANNEL POST UPDATE (မူရင်းအတိုင်း)
# ==========================================
async def update_channel_post(next_issue, predicted_display, final_prob, reason):
    global MAIN_MESSAGE_ID, SESSION_START_ISSUE
    try:
        session_preds = await db.get_session_predictions(SESSION_START_ISSUE)

        table_str = "<code>Period    | Result  | W/L\n----------|---------|----\n"
        for p in session_preds[:10]:
            iss = p.get('issue_number', '0000000')
            iss_short = f"{iss[:3]}**{iss[-4:]}"
            act_size = p.get('actual_size', 'BIG')
            act_num = p.get('actual_number', 0)
            wl_str = "✅" if "WIN" in p.get("win_lose", "") else "❌"
            table_str += f"{iss_short:<10}| {act_num}-{act_size:<7} | {wl_str}\n"
        table_str += "</code>"

        img_buf = await asyncio.to_thread(generate_chart, session_preds)
        photo = BufferedInputFile(img_buf.read(), filename=f"chart_{int(time.time())}.png")

        sec_left = 30 - (int(time.time()) % 30)
        iss_display = f"{next_issue[:3]}**{next_issue[-4:]}"

        tg_caption = (
            f"<b>🏆 WIN GO (30 SECONDS)</b>\n"
            f"⏰ Next Result In: <b>{sec_left}s</b>\n\n"
            f"{table_str}\n"
            f"🎮 <b>Period:</b> {iss_display}\n"
            f"🤖 <b>AI ခန့်မှန်းချက် : {predicted_display}</b>\n"
            f"📊 <b>ဖြစ်နိုင်ခြေ : {final_prob}%</b>\n"
            f"ℹ️ <b>အကြောင်းပြချက် :</b>\n{reason}"
        )

        if MAIN_MESSAGE_ID:
            try:
                media = InputMediaPhoto(media=photo, caption=tg_caption, parse_mode="HTML")
                await bot.edit_message_media(chat_id=CHANNEL_ID, message_id=MAIN_MESSAGE_ID, media=media)
            except Exception:
                msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                MAIN_MESSAGE_ID = msg.message_id
        else:
            msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
            MAIN_MESSAGE_ID = msg.message_id
    except Exception as e:
        print(f"Channel update error: {e}")


# ==========================================
# 11. CHART GENERATOR (မူရင်းအတိုင်း)
# ==========================================
def generate_chart(predictions):
    wins, losses = 0, 0
    bar_colors, bar_heights, history_wr = [], [], []
    latest_preds = list(reversed(predictions))[-20:]

    for i, p in enumerate(latest_preds):
        if 'WIN' in p.get('win_lose', ''):
            wins += 1
            bar_colors.append('#00e5ff')
        else:
            losses += 1
            bar_colors.append('#ff4444')
        current_wr = (wins / (i + 1)) * 100
        bar_heights.append(current_wr)
        history_wr.append(current_wr)

    total_played = wins + losses
    win_rate = int((wins / total_played * 100)) if total_played > 0 else 0

    fig = plt.figure(figsize=(10.24, 7.68), facecolor='#1c1f26')
    fig.text(0.05, 0.93, "🏆 WIN GO PERFORMANCE", color='#ffffff', fontsize=26, fontweight='bold', ha='left')

    ax_circle = fig.add_axes([0.08, 0.42, 0.35, 0.40])
    ax_circle.set_axis_off()
    ax_circle.set_xlim(0, 1)
    ax_circle.set_ylim(0, 1)
    theta_bg = np.linspace(-1.25 * np.pi, 0.25 * np.pi, 200)
    ax_circle.plot(0.5 + 0.45 * np.cos(theta_bg), 0.5 + 0.45 * np.sin(theta_bg), color='#2c313c', linewidth=12)
    if win_rate > 0:
        end_angle = 0.25 * np.pi - (win_rate / 100) * 1.5 * np.pi
        theta_fg = np.linspace(0.25 * np.pi, end_angle, 100)
        ax_circle.plot(0.5 + 0.45 * np.cos(theta_fg), 0.5 + 0.45 * np.sin(theta_fg), color='#00e5ff', linewidth=12)
    ax_circle.text(0.5, 0.75, f"{total_played}/20", color='#a3a8b5', fontsize=16, fontweight='bold', ha='center')
    ax_circle.text(0.5, 0.48, f"{win_rate}%", color='#00e5ff', fontsize=65, fontweight='bold', ha='center')

    ax_bar = fig.add_axes([0.55, 0.47, 0.38, 0.33])
    ax_bar.set_facecolor('#1c1f26')
    ax_bar.set_xlim(-0.5, 19.5)
    ax_bar.set_ylim(0, 105)
    for spine in ax_bar.spines.values():
        spine.set_visible(False)
    ax_bar.set_yticks([0, 25, 50, 75, 100])
    ax_bar.set_yticklabels(['0%', '25%', '50%', '75%', '100%'], color='#7a8294', fontsize=10)
    ax_bar.grid(axis='y', color='#2c313c', linewidth=1.5)
    if total_played > 0:
        x_pos = np.arange(total_played)
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.8, alpha=0.15, align='center')
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.45, alpha=0.9, align='center')
        ax_bar.plot(x_pos, history_wr, color='#00e5ff', linewidth=2.5, marker='o',
                    markersize=6, markerfacecolor='#1c1f26', markeredgecolor='#00e5ff', markeredgewidth=2)
    ax_bar.set_xticks(np.arange(20))
    ax_bar.set_xticklabels([str(i + 1) for i in range(20)], color='#7a8294', fontsize=10)

    ax_win = fig.add_axes([0.05, 0.22, 0.28, 0.16])
    ax_win.set_axis_off()
    rect_win = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#1de9b6")
    ax_win.add_patch(rect_win)
    ax_win.text(0.1, 0.75, "WINS", color='#004d40', fontsize=16, fontweight='bold')
    ax_win.text(0.1, 0.35, f"{wins}", color='#000000', fontsize=48, fontweight='bold')

    ax_lose = fig.add_axes([0.35, 0.22, 0.28, 0.16])
    ax_lose.set_axis_off()
    rect_lose = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#ef5350")
    ax_lose.add_patch(rect_lose)
    ax_lose.text(0.1, 0.75, "LOSSES", color='#4d0000', fontsize=16, fontweight='bold')
    ax_lose.text(0.1, 0.35, f"{losses}", color='#ffffff', fontsize=48, fontweight='bold')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, facecolor='#1c1f26')
    buf.seek(0)
    plt.close(fig)
    return buf


# ==========================================
# 12. SCHEDULER
# ==========================================
async def auto_broadcaster():
    await db.init_indexes()
    global SUDO_USERS
    SUDO_USERS = await db.get_sudo_users()
    print(f"✅ DB Connected | 🛡️ Sudo: {len(SUDO_USERS)}")

    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            current_time = time.time()
            sec_passed = int(current_time) % 30
            active_users = await db.get_active_users()
            if active_users and 5 <= sec_passed <= 28:
                try:
                    is_processed = await check_game_and_predict(session)
                    if is_processed:
                        await asyncio.sleep(30 - (int(time.time()) % 30))
                        continue
                except Exception as e:
                    print(f"Scheduler error: {e}")
            await asyncio.sleep(0.5)


# ==========================================
# 13. COMMAND HANDLERS
# ==========================================
@auth_router.message(Command("start"))
@auth_router.message(lambda m: m.text and m.text.lower().strip() in ['.start', '/start'])
async def cmd_start(message: types.Message):
    user = await db.get_user(message.from_user.id)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users
    user_session = await db.get_user_session(message.from_user.id)
    user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
    mode = user_session.get("mode", "virtual")

    bet_seq = user_session.get("bet_sequence", DEFAULT_BET_SEQUENCE)
    bet_str = " → ".join([f"{b:,}" for b in bet_seq])

    await message.reply(
        f"{Emoji.SPARKLES} <b>WIN GO AI Bot v4.0</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>Access:</b> {'Owner' if str(message.from_user.id) == str(OWNER_ID) else 'Sudo'}\n"
        f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"🟢 <b>Status:</b> {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.BRAIN} <b>Your AI:</b> {AI_MODES.get(user_ai_mode, {}).get('name', 'AI')}\n"
        f"🎯 <b>Target:</b> {user.get('profit_target', 30000):,.0f} Ks\n"
        f"💲 <b>Bet Size:</b> {bet_str}\n\n"
        f"👇 <b>အောက်က Keyboard ကိုသုံးပါ:</b>",
        reply_markup=get_main_reply_keyboard(is_active, mode)
    )


# ==========================================
# 14. REPLY KEYBOARD HANDLERS
# ==========================================
@auth_router.message(lambda m: m.text and m.text.strip() == "▶️ Start Auto-Bet")
async def handle_start_button(message: types.Message):
    """Start Auto-Bet with Full Reset"""
    user_id = message.from_user.id
    active_users = await db.get_active_users()
    user_session = await db.get_user_session(user_id)
    mode = user_session.get("mode", "virtual")

    if user_id in active_users:
        await message.reply("✅ Already active!", reply_markup=get_main_reply_keyboard(True, mode))
        return

    # ========== FULL RESET ==========
    await db.reset_session_profit(user_id)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"session_profit": 0.0, "win_streak": 0, "lose_streak": 0}}
    )
    await db.bets.delete_many({"user_id": user_id, "result": None})

    # Activate session
    await db.activate_session(user_id, user_session.get("ai_mode", DEFAULT_AI_MODE))
    await db.user_sessions.update_one(
        {"user_id": user_id},
        {"$set": {"mode": mode}},
        upsert=True
    )

    user = await db.get_user(user_id)
    bet_seq = user_session.get("bet_sequence", DEFAULT_BET_SEQUENCE)
    bet_str = " → ".join([f"{b:,}" for b in bet_seq])

    # If Real Mode, ensure Playwright login
    if mode == "real":
        if user_id not in playwright_sessions:
            await message.reply("🔐 <b>Real Mode အတွက် Login လိုအပ်ပါသည်။\nကျေးဇူးပြု၍ /login [username] [password] ကို အသုံးပြုပါ။</b>")
            return

    await message.reply(
        f"✅ <b>Auto-Bet Activated!</b>\n\n"
        f"💰 Balance: {user['balance']:,.0f} Ks\n"
        f"🎯 Target: {user.get('profit_target', 30000):,.0f} Ks\n"
        f"💲 Bet Size: {bet_str}\n"
        f"🔄 Session Reset Complete! (Starting from {bet_seq[0]:,})\n\n"
        f"👇 Keyboard ကိုသုံးပါ:",
        reply_markup=get_main_reply_keyboard(True, mode)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == "⏹️ Stop Auto-Bet")
async def handle_stop_button(message: types.Message):
    """Stop Auto-Bet"""
    user_id = message.from_user.id
    active_users = await db.get_active_users()
    user_session = await db.get_user_session(user_id)
    mode = user_session.get("mode", "virtual")

    if user_id not in active_users:
        await message.reply("❌ Not active!", reply_markup=get_main_reply_keyboard(False, mode))
        return

    await db.deactivate_session(user_id)

    # Delete pending bets
    await db.bets.delete_many({"user_id": user_id, "result": None})

    user = await db.get_user(user_id)

    await message.reply(
        f"🔴 <b>Auto-Bet Stopped!</b>\n\n"
        f"💰 Balance: {user['balance']:,.0f} Ks\n"
        f"📈 Session Profit: {user['session_profit']:,.2f} Ks\n"
        f"🎯 Target: {user.get('profit_target', 30000):,.0f} Ks\n\n"
        f"🔄 Start ပြန်နှိပ်ရင် အားလုံး Reset လုပ်ပါမည်။",
        reply_markup=get_main_reply_keyboard(False, mode)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == "🔵 Real Mode" or m.text.strip() == "🟡 Virtual Mode")
async def handle_mode_switch(message: types.Message):
    """Toggle between Real and Virtual Mode"""
    user_id = message.from_user.id
    current_mode = "real" if "Real" in message.text else "virtual"
    await db.user_sessions.update_one(
        {"user_id": user_id},
        {"$set": {"mode": current_mode}},
        upsert=True
    )
    active_users = await db.get_active_users()
    is_active = user_id in active_users
    await message.reply(
        f"✅ <b>Mode switched to {current_mode.capitalize()}</b>",
        reply_markup=get_main_reply_keyboard(is_active, current_mode)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == "💰 Balance")
async def handle_bal_button(message: types.Message):
    user = await db.get_user(message.from_user.id)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users
    user_session = await db.get_user_session(message.from_user.id)
    mode = user_session.get("mode", "virtual")
    await message.reply(
        f"{Emoji.MONEY_ICON} <b>သင့်အကောင့်</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Status: {'Active' if is_active else 'Inactive'}\n"
        f"💵 Balance: {user['balance']:,.2f} Ks\n"
        f"📈 Session: {user['session_profit']:,.2f} Ks\n"
        f"🎯 Target: {user.get('profit_target', 30000):,.0f} Ks\n"
        f"✅ Wins: {user['total_wins']} | ❌ Losses: {user['total_losses']}",
        reply_markup=get_main_reply_keyboard(is_active, mode)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == "🧠 AI Mode")
async def handle_mode_button(message: types.Message):
    user_session = await db.get_user_session(message.from_user.id)
    current_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
    mode = user_session.get("mode", "virtual")
    await message.reply(
        f"🧠 <b>AI Mode ရွေးပါ (၁၆ မျိုး)</b>\n"
        f"📌 လက်ရှိ: <b>{AI_MODES.get(current_mode, {}).get('name', 'AI')}</b>\n\n"
        f"👇 အောက်က Button များမှရွေးပါ:",
        reply_markup=get_ai_mode_inline_keyboard(current_mode)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == "📊 Status")
async def handle_status_button(message: types.Message):
    user = await db.get_user(message.from_user.id)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users
    user_session = await db.get_user_session(message.from_user.id)
    pending = await db.get_pending_bets_count(message.from_user.id)
    mode = user_session.get("mode", "virtual")

    bet_seq = user_session.get("bet_sequence", DEFAULT_BET_SEQUENCE)
    bet_str = " → ".join([f"{b:,}" for b in bet_seq])

    recent_bets = await db.get_user_bets(message.from_user.id, 20)
    lose_streak = 0
    for bet in recent_bets:
        if bet.get("result") == "LOSE":
            lose_streak += 1
        elif bet.get("result") == "WIN":
            break

    await message.reply(
        f"📊 <b>သင့် Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Auto-Bet: {'Active' if is_active else 'Inactive'}\n"
        f"🧠 AI: {AI_MODES.get(user_session.get('ai_mode', DEFAULT_AI_MODE), {}).get('name', 'AI')}\n"
        f"💰 Balance: {user['balance']:,.0f} Ks\n"
        f"📈 Session Profit: {user['session_profit']:,.2f} Ks\n"
        f"🎯 Target: {user.get('profit_target', 30000):,.0f} Ks\n"
        f"💲 Bet Size: {bet_str}\n"
        f"📉 Current Streak: {lose_streak}/{len(bet_seq)}\n"
        f"⏳ Pending: {pending}\n"
        f"🔥 Best Streak: {user.get('best_streak', 0)}",
        reply_markup=get_main_reply_keyboard(is_active, mode)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == "⚙️ Settings")
async def handle_settings_button(message: types.Message):
    user_session = await db.get_user_session(message.from_user.id)
    mode = user_session.get("mode", "virtual")
    await message.reply(
        "⚙️ <b>Settings</b>\n\n👇 အောက်က Button များမှရွေးပါ:",
        reply_markup=get_settings_inline_keyboard()
    )


@auth_router.message(lambda m: m.text and m.text.strip() == "📋 My Bets")
async def handle_mybets_button(message: types.Message):
    bets = await db.get_user_bets(message.from_user.id, 10)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users
    user_session = await db.get_user_session(message.from_user.id)
    mode = user_session.get("mode", "virtual")
    text = "📋 <b>မှတ်တမ်း</b>\n"
    if bets:
        for bet in bets:
            if bet["result"] is None:
                status = "⏳"
            elif bet["result"] == "WIN":
                status = f"✅ +{bet['profit']:,.0f}"
            else:
                status = f"❌ -{bet['bet_amount']:,.0f}"
            text += f"{bet['issue_number']}: {bet['bet_amount']:,.0f}K {bet['predicted_size']} → {status}\n"
    else:
        text += "မရှိသေးပါ"
    await message.reply(text, reply_markup=get_main_reply_keyboard(is_active, mode))


@auth_router.message(lambda m: m.text and m.text.strip() == "👑 Top 10")
async def handle_top_button(message: types.Message):
    leaderboard = await db.get_leaderboard(10)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users
    user_session = await db.get_user_session(message.from_user.id)
    mode = user_session.get("mode", "virtual")
    text = "👑 <b>TOP 10</b>\n"
    for i, user in enumerate(leaderboard, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} <code>{user['user_id']}</code>: {user['balance']:,.0f} Ks\n"
    await message.reply(text, reply_markup=get_main_reply_keyboard(is_active, mode))


# ==========================================
# 15. PLAYWRIGHT LOGIN COMMAND
# ==========================================
@auth_router.message(Command("login"))
async def cmd_playwright_login(message: types.Message):
    """Playwright ဖြင့် Login ဝင်ရန်"""
    args = message.text.split()
    if len(args) < 3:
        await message.reply("⚠️ <b>အသုံးပြုနည်း:</b> /login [username] [password]")
        return
    username = args[1]
    password = args[2]
    user_id = message.from_user.id

    await message.reply("🔄 Playwright ဖြင့် Login ဝင်နေပါသည်...")
    success = await playwright_login(user_id, username, password)
    if success:
        await message.reply("✅ Playwright Login Successful! Real Mode အတွက် အဆင်သင့်ဖြစ်ပါပြီ။")
    else:
        await message.reply("❌ Playwright Login Failed! ကျေးဇူးပြု၍ username/password ကို စစ်ဆေးပါ။")


# ==========================================
# 16. TARGET INPUT HANDLER
# ==========================================
user_target_input = {}

@auth_router.callback_query(lambda c: c.data == "cmd_target")
async def cb_target(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_target_input[user_id] = True
    user = await db.get_user(user_id)
    await callback.message.edit_text(
        f"🎯 <b>Profit Target သတ်မှတ်ရန်</b>\n\n"
        f"📌 လက်ရှိ: <b>{user.get('profit_target', 30000):,.0f} Ks</b>\n\n"
        f"👇 <b>ပမာဏကို စာရိုက်ထည့်ပါ:</b>\n"
        f"ဥပမာ: <code>30000</code> or <code>50000</code>\n\n"
        f"ℹ️ Target ရောက်ရင် Auto-Stop ပါမည်။\n"
        f"Cancel: <code>/cancel</code>"
    )
    await callback.answer()


@auth_router.message(lambda m: m.text and m.text.strip().isdigit() and m.from_user.id in user_target_input)
async def handle_target_input(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_target_input:
        return
    try:
        target = float(message.text.strip())
        if target <= 0:
            await message.reply("❌ 0 ထက်ကြီးရပါမည်။", reply_markup=get_main_reply_keyboard(False))
            return
        await db.update_profit_target(user_id, target)
        del user_target_input[user_id]
        active_users = await db.get_active_users()
        is_active = user_id in active_users
        user_session = await db.get_user_session(user_id)
        mode = user_session.get("mode", "virtual")
        await message.reply(
            f"✅ <b>Profit Target သတ်မှတ်ပြီး!</b>\n🎯 Target: <b>{target:,.0f} Ks</b>",
            reply_markup=get_main_reply_keyboard(is_active, mode)
        )
    except ValueError:
        await message.reply("❌ ဂဏန်းများသာထည့်ပါ။", reply_markup=get_main_reply_keyboard(False))


@auth_router.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_target_input:
        del user_target_input[user_id]
    if user_id in user_betsize_input:
        del user_betsize_input[user_id]
    active_users = await db.get_active_users()
    user_session = await db.get_user_session(user_id)
    mode = user_session.get("mode", "virtual")
    await message.reply("✅ Cancelled.", reply_markup=get_main_reply_keyboard(user_id in active_users, mode))


# ==========================================
# 17. INLINE KEYBOARD CALLBACK HANDLERS
# ==========================================
@auth_router.callback_query(lambda c: c.data and c.data.startswith("usermode_"))
async def cb_user_mode_select(callback: types.CallbackQuery):
    mode_key = callback.data.replace("usermode_", "")
    if mode_key in AI_MODES:
        await db.update_user_ai_mode(callback.from_user.id, mode_key)
        await callback.message.edit_text(
            f"✅ <b>AI Mode ပြောင်းပြီး!</b>\n🧠 {AI_MODES[mode_key]['name']}\nℹ️ {AI_MODES[mode_key]['desc']}"
        )
        await callback.answer(f"✅ {AI_MODES[mode_key]['name']}")


@auth_router.callback_query(lambda c: c.data == "cmd_compare")
async def cb_compare(callback: types.CallbackQuery):
    await callback.answer("Comparing...")
    history_docs = await db.get_history(100)
    if len(history_docs) < 20:
        await callback.message.edit_text("Data မလုံလောက်သေးပါ။")
        return
    test_docs = history_docs[:80]
    results = {}
    for mode_key, mode_info in AI_MODES.items():
        correct = total = 0
        for i in range(len(test_docs) - 10):
            segment = test_docs[i + 10:i:-1]
            if len(segment) >= 10:
                try:
                    pred_size, _, _, _ = mode_info["func"](segment)
                    if pred_size == test_docs[i].get("size", "BIG"):
                        correct += 1
                    total += 1
                except:
                    pass
        results[mode_key] = {"name": mode_info["name"], "accuracy": (correct / total * 100) if total > 0 else 0}
    sorted_results = sorted(results.items(), key=lambda x: x[1]["accuracy"], reverse=True)
    text = "📊 <b>AI COMPARISON (Top 5)</b>\n"
    for i, (key, data) in enumerate(sorted_results[:5], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {data['name']}: {data['accuracy']:.1f}%\n"
    await callback.message.edit_text(text)


@auth_router.callback_query(lambda c: c.data == "cmd_addbal")
async def cb_addbal(callback: types.CallbackQuery):
    await callback.message.edit_text("💎 <b>ငွေထည့်ရန်</b>\n👇 ပမာဏရွေးပါ:", reply_markup=get_add_balance_keyboard())
    await callback.answer()


@auth_router.callback_query(lambda c: c.data and c.data.startswith("addbal_"))
async def cb_process_addbal(callback: types.CallbackQuery):
    amount = float(callback.data.replace("addbal_", ""))
    user = await db.update_balance(callback.from_user.id, amount, "add")
    await callback.message.edit_text(f"✅ +{amount:,.0f} Ks\n💰 Balance: {user['balance']:,.0f} Ks")
    await callback.answer(f"✅ +{amount:,} Ks")


@auth_router.callback_query(lambda c: c.data == "cmd_withdraw")
async def cb_withdraw(callback: types.CallbackQuery):
    await callback.message.edit_text("💵 <b>ငွေနှုတ်ရန်</b>\n👇 ပမာဏရွေးပါ:", reply_markup=get_withdraw_keyboard())
    await callback.answer()


@auth_router.callback_query(lambda c: c.data and c.data.startswith("withdraw_"))
async def cb_process_withdraw(callback: types.CallbackQuery):
    data = callback.data.replace("withdraw_", "")
    user = await db.get_user(callback.from_user.id)
    amount = user['balance'] if data == "all" else float(data)
    if amount > user['balance']:
        await callback.answer("Not enough!", show_alert=True)
        return
    await db.update_balance(callback.from_user.id, amount, "subtract")
    updated = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(f"✅ -{amount:,.0f} Ks\n💰 Balance: {updated['balance']:,.0f} Ks")
    await callback.answer(f"✅ -{amount:,} Ks")


# ==========================================
# 18. BET SIZE HANDLERS
# ==========================================
@auth_router.callback_query(lambda c: c.data == "cmd_betsize")
async def cb_betsize(callback: types.CallbackQuery):
    """Show Bet Size options"""
    user_session = await db.get_user_session(callback.from_user.id)
    current_seq = user_session.get("bet_sequence", DEFAULT_BET_SEQUENCE)
    current_str = " → ".join([f"{b:,}" for b in current_seq])

    await callback.message.edit_text(
        f"💲 <b>Bet Size သတ်မှတ်ရန်</b>\n\n"
        f"📌 လက်ရှိ: <b>{current_str}</b> ({len(current_seq)} ဆင့်)\n\n"
        f"👇 Preset ရွေးပါ သို့မဟုတ် Custom ထည့်ပါ:",
        reply_markup=get_betsize_inline_keyboard(current_seq)
    )
    await callback.answer()


@auth_router.callback_query(lambda c: c.data and c.data.startswith("setbetsize_"))
async def cb_set_betsize(callback: types.CallbackQuery):
    """Process preset bet size selection"""
    parts = callback.data.replace("setbetsize_", "").split("_")
    bet_seq = [int(x) for x in parts]

    await db.user_sessions.update_one(
        {"user_id": callback.from_user.id},
        {"$set": {"bet_sequence": bet_seq}},
        upsert=True
    )

    bet_str = " → ".join([f"{b:,}" for b in bet_seq])

    await callback.message.edit_text(
        f"✅ <b>Bet Size သတ်မှတ်ပြီး!</b>\n\n"
        f"💲 Sequence ({len(bet_seq)} ဆင့်): <b>{bet_str}</b>\n\n"
        f"🔄 နောက်ဆုံးအဆင့် ({bet_seq[-1]:,}) ထိရှုံးရင် {bet_seq[0]:,} ကနေ Auto Reset ပါမည်။",
        reply_markup=get_settings_inline_keyboard()
    )
    await callback.answer(f"✅ Bet Size Updated! ({len(bet_seq)} steps)")


# Bet Size Custom Input State
user_betsize_input = {}

@auth_router.callback_query(lambda c: c.data == "betsize_custom")
async def cb_betsize_custom(callback: types.CallbackQuery):
    """Start custom bet size input"""
    user_id = callback.from_user.id
    user_betsize_input[user_id] = True

    user_session = await db.get_user_session(user_id)
    current_seq = user_session.get("bet_sequence", DEFAULT_BET_SEQUENCE)
    current_str = " → ".join([f"{b:,}" for b in current_seq])

    await callback.message.edit_text(
        f"✏️ <b>Custom Bet Size သတ်မှတ်ရန်</b>\n\n"
        f"📌 လက်ရှိ ({len(current_seq)} ဆင့်): <b>{current_str}</b>\n\n"
        f"👇 <b>အောက်ပါပုံစံအတိုင်း စာရိုက်ထည့်ပါ:</b>\n"
        f"<code>100-300-900-2700-8100-24300</code>\n\n"
        f"ℹ️ ဂဏန်းများ dash (-) ခြားပြီးထည့်ပါ။\n"
        f"ℹ️ နောက်ဆုံးအဆင့်ထိရှုံးရင် ပထမအဆင့်ကနေ Auto Reset ပါမည်။\n"
        f"Cancel: <code>/cancel</code>"
    )
    await callback.answer()


@auth_router.message(lambda m: m.text and '-' in m.text and m.from_user.id in user_betsize_input)
async def handle_betsize_input(message: types.Message):
    """Process custom bet size input"""
    user_id = message.from_user.id

    if user_id not in user_betsize_input:
        return

    try:
        parts = message.text.strip().split('-')
        if len(parts) < 2:
            await message.reply("❌ အနည်းဆုံး ၂ ဆင့်ထည့်ပါ။ ဥပမာ: 100-300")
            return

        bet_seq = []
        for p in parts:
            val = float(p.strip().replace(',', ''))
            if val <= 0:
                await message.reply("❌ 0 ထက်ကြီးရပါမည်။")
                return
            bet_seq.append(val)

        await db.user_sessions.update_one(
            {"user_id": user_id},
            {"$set": {"bet_sequence": bet_seq}},
            upsert=True
        )

        del user_betsize_input[user_id]

        bet_str = " → ".join([f"{b:,.0f}" for b in bet_seq])

        active_users = await db.get_active_users()
        is_active = user_id in active_users
        user_session = await db.get_user_session(user_id)
        mode = user_session.get("mode", "virtual")

        await message.reply(
            f"✅ <b>Custom Bet Size သတ်မှတ်ပြီး!</b>\n\n"
            f"💲 Sequence ({len(bet_seq)} ဆင့်): <b>{bet_str}</b>\n\n"
            f"🔄 နောက်ဆုံးအဆင့် ({bet_seq[-1]:,.0f}) ထိရှုံးရင် {bet_seq[0]:,.0f} ကနေ Auto Reset ပါမည်။",
            reply_markup=get_main_reply_keyboard(is_active, mode)
        )

    except ValueError:
        await message.reply("❌ ဂဏန်းများသာထည့်ပါ။ ဥပမာ: 100-300-900-2700-8100-24300")


@auth_router.callback_query(lambda c: c.data == "cmd_back")
async def cb_back(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    active_users = await db.get_active_users()
    is_active = callback.from_user.id in active_users
    user_session = await db.get_user_session(callback.from_user.id)
    user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
    mode = user_session.get("mode", "virtual")
    await callback.message.edit_text(
        f"✨ <b>WIN GO AI Bot v4.0</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance: {user['balance']:,.0f} Ks\n"
        f"🟢 Status: {'Active' if is_active else 'Inactive'}\n"
        f"🧠 AI: {AI_MODES.get(user_ai_mode, {}).get('name', 'AI')}\n"
        f"🎯 Target: {user.get('profit_target', 30000):,.0f} Ks\n\n"
        f"👇 Keyboard ကိုသုံးပါ:"
    )
    await callback.answer()


# ==========================================
# 19. OWNER ONLY COMMANDS (မူရင်းအတိုင်း)
# ==========================================
@owner_router.message(Command("addsudo"))
@owner_router.message(lambda m: m.text and m.text.lower().strip() in ['.addsudo', '/addsudo'])
async def cmd_add_sudo(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("<code>/addsudo [user_id]</code> or <code>.addsudo [user_id]</code>")
            return
        target_id = int(parts[1])
        await db.add_sudo(target_id, message.from_user.id)
        global SUDO_USERS
        SUDO_USERS = await db.get_sudo_users()
        await message.reply(f"✅ Sudo Added: <code>{target_id}</code>")
    except ValueError:
        await message.reply("❌ User ID ဂဏန်းသာထည့်ပါ။")


@owner_router.message(Command("delsudo"))
@owner_router.message(lambda m: m.text and m.text.lower().strip() in ['.delsudo', '/delsudo'])
async def cmd_del_sudo(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("<code>/delsudo [user_id]</code> or <code>.delsudo [user_id]</code>")
            return
        target_id = int(parts[1])
        await db.remove_sudo(target_id)
        global SUDO_USERS
        SUDO_USERS = await db.get_sudo_users()
        await message.reply(f"✅ Sudo Removed: <code>{target_id}</code>")
    except ValueError:
        await message.reply("❌ User ID ဂဏန်းသာထည့်ပါ။")


@owner_router.message(Command("give"))
@owner_router.message(lambda m: m.text and m.text.lower().strip().startswith('.give'))
async def cmd_give_balance(message: types.Message):
    """Owner မှ User ကို Balance ထည့်ပေးရန်"""
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply(
                "❌ <b>အသုံးပြုနည်း:</b>\n"
                "<code>/give [user_id] [amount]</code>\n"
                "<code>.give [user_id] [amount]</code>\n\n"
                "ဥပမာ: <code>.give 123456789 50000</code>"
            )
            return
        target_id = int(parts[1])
        amount = float(parts[2])
        if amount <= 0:
            await message.reply("❌ 0 ထက်ကြီးရပါမည်။")
            return
        receiver = await db.update_balance(target_id, amount, "add")
        await message.reply(
            f"✅ <b>ငွေထည့်ပေးပြီးပါပြီ!</b>\n\n"
            f"👤 User: <code>{target_id}</code>\n"
            f"💵 +{amount:,.0f} Ks\n"
            f"💰 Balance: {receiver['balance']:,.0f} Ks"
        )
        try:
            await bot.send_message(
                chat_id=target_id,
                text=f"🎁 <b>ငွေထည့်ပေးခြင်းခံရပါသည်!</b>\n━━━━━━━━━━━━━━━━━━\n💵 +{amount:,.0f} Ks\n💰 Balance: {receiver['balance']:,.0f} Ks\n━━━━━━━━━━━━━━━━━━\n👑 Owner မှ ထည့်ပေးခြင်းဖြစ်ပါသည်။"
            )
        except:
            pass
    except ValueError:
        await message.reply("❌ <code>.give [user_id] [amount]</code> ပုံစံဖြင့်ထည့်ပါ။")


@owner_router.message(Command("take"))
@owner_router.message(lambda m: m.text and m.text.lower().strip().startswith('.take'))
async def cmd_take_balance(message: types.Message):
    """Owner မှ User Balance ပြန်နှုတ်ရန်"""
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply(
                "❌ <b>အသုံးပြုနည်း:</b>\n"
                "<code>/take [user_id] [amount]</code>\n"
                "<code>.take [user_id] [amount]</code>\n\n"
                "ဥပမာ: <code>.take 123456789 50000</code>"
            )
            return
        target_id = int(parts[1])
        amount = float(parts[2])
        if amount <= 0:
            await message.reply("❌ 0 ထက်ကြီးရပါမည်။")
            return
        user = await db.get_user(target_id)
        if amount > user['balance']:
            await message.reply(f"❌ လက်ကျန်ငွေ မလုံလောက်ပါ!\n💰 Balance: {user['balance']:,.0f} Ks")
            return
        updated = await db.update_balance(target_id, amount, "subtract")
        await message.reply(
            f"✅ <b>ငွေနှုတ်ပြီးပါပြီ!</b>\n\n"
            f"👤 User: <code>{target_id}</code>\n"
            f"💵 -{amount:,.0f} Ks\n"
            f"💰 Balance: {updated['balance']:,.0f} Ks"
        )
        try:
            await bot.send_message(
                chat_id=target_id,
                text=f"⚠️ <b>ငွေနှုတ်ယူခြင်းခံရပါသည်!</b>\n━━━━━━━━━━━━━━━━━━\n💵 -{amount:,.0f} Ks\n💰 Balance: {updated['balance']:,.0f} Ks"
            )
        except:
            pass
    except ValueError:
        await message.reply("❌ <code>.take [user_id] [amount]</code> ပုံစံဖြင့်ထည့်ပါ။")


@owner_router.message(Command("setbal"))
@owner_router.message(lambda m: m.text and m.text.lower().strip().startswith('.setbal'))
async def cmd_set_balance(message: types.Message):
    """Owner မှ User Balance သတ်မှတ်ရန်"""
    try:
        parts = message.text.split()
        if len(parts) == 2:
            amount = float(parts[1])
            if amount < 0:
                await message.reply("❌ 0 သို့မဟုတ် အပေါင်းကိန်းဖြစ်ရပါမည်။")
                return
            user = await db.update_balance(message.from_user.id, amount, "set")
            await message.reply(f"✅ Balance: <b>{user['balance']:,.0f} Ks</b>")
        elif len(parts) == 3:
            target_id = int(parts[1])
            amount = float(parts[2])
            if amount < 0:
                await message.reply("❌ 0 သို့မဟုတ် အပေါင်းကိန်းဖြစ်ရပါမည်။")
                return
            user = await db.update_balance(target_id, amount, "set")
            await message.reply(f"✅ User <code>{target_id}</code> Balance: <b>{user['balance']:,.0f} Ks</b>")
        else:
            await message.reply("<code>/setbal 50000</code> or <code>.setbal 50000</code>\n<code>/setbal [id] 50000</code> or <code>.setbal [id] 50000</code>")
    except ValueError:
        await message.reply("❌ ဂဏန်းများသာ ထည့်ပါ။")


@owner_router.message(Command("sudolist"))
@owner_router.message(lambda m: m.text and m.text.lower().strip() in ['.sudolist', '/sudolist'])
async def cmd_sudo_list(message: types.Message):
    global SUDO_USERS
    if not SUDO_USERS:
        await message.reply("📋 No sudo users.")
        return
    text = "🛡️ <b>SUDO USERS</b>\n"
    for i, uid in enumerate(SUDO_USERS, 1):
        text += f"{i}. <code>{uid}</code>\n"
    await message.reply(text)


# ==========================================
# 20. INITIALIZATION & MAIN
# ==========================================
async def init_system():
    global DEFAULT_AI_MODE, SUDO_USERS
    await db.init_indexes()
    SUDO_USERS = await db.get_sudo_users()
    DEFAULT_AI_MODE = await db.get_setting("default_ai_mode", "ensemble")
    print(f"✅ System Ready | AI: {DEFAULT_AI_MODE} | Sudo: {len(SUDO_USERS)}")


async def main():
    await init_system()
    print("\n✨ WIN GO AI Bot v4.0 - 6 Step Bet Sequence + Auto Reset + Playwright\n")
    print(f"👑 Owner: {OWNER_ID}")
    print(f"🧠 Default AI: {DEFAULT_AI_MODE}")
    print(f"💲 Default Bet: 100→300→900→2700→8100→24300")
    print(f"🛡️ Sudo Users: {len(SUDO_USERS)}\n")

    dp.include_router(auth_router)
    dp.include_router(owner_router)

    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔴 Bot Stopped")
