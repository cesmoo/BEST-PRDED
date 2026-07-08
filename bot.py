# bot.py
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

# Routers
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
    # Premium
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
    
    # Standard
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
    
    # Reply Keyboard Icons (ဒီတွေမရှိလို့ error တက်တာ)
    SETTINGS = "⚙️"
    TARGET = "🎯"
    HISTORY = "📋"
    PLAY = "▶️"
    STOP = "⏹️"
    REFRESH = "🔄"
    BACK = "🔙"
    MENU = "📋"
    CHART = "📊"

# ==========================================
# 3. SYSTEM VARIABLES
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = None
MAIN_MESSAGE_ID = None
SESSION_START_ISSUE = None
DEFAULT_AI_MODE = "ensemble"
SUDO_USERS = set()

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

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
                await event.reply(f"{Emoji.LOCK} <b>Access Denied!</b>")
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
                await event.reply(f"{Emoji.CROSS} Owner only!")
            elif isinstance(event, types.CallbackQuery):
                await event.answer("👑 Owner only!", show_alert=True)
            return

        return await handler(event, data)


auth_router.message.middleware(AuthMiddleware())
auth_router.callback_query.middleware(AuthMiddleware())
owner_router.message.middleware(OwnerOnlyMiddleware())
owner_router.callback_query.middleware(OwnerOnlyMiddleware())


# ==========================================
# 5. KEYBOARD BUILDERS
# ==========================================

def get_main_reply_keyboard(is_active: bool = False) -> ReplyKeyboardMarkup:
    """Main Reply Keyboard (Custom Keyboard)"""
    builder = ReplyKeyboardBuilder()

    if is_active:
        builder.row(KeyboardButton(text=f"{Emoji.STOP} Stop Auto-Bet"))
    else:
        builder.row(KeyboardButton(text=f"{Emoji.PLAY} Start Auto-Bet"))

    builder.row(
        KeyboardButton(text=f"{Emoji.MONEY_ICON} Balance"),
        KeyboardButton(text=f"{Emoji.BRAIN} AI Mode"),
    )
    builder.row(
        KeyboardButton(text=f"{Emoji.CHART} Status"),
        KeyboardButton(text=f"{Emoji.SETTINGS} Settings"),
    )
    builder.row(
        KeyboardButton(text=f"{Emoji.HISTORY} My Bets"),
        KeyboardButton(text=f"{Emoji.CROWN} Top 10"),
    )

    return builder.as_markup(resize_keyboard=True)


def get_settings_inline_keyboard() -> InlineKeyboardMarkup:
    """Settings Inline Keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(
        text=f"{Emoji.GEM} Add Balance",
        callback_data="cmd_addbal"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{Emoji.MONEY_BAG} Withdraw",
        callback_data="cmd_withdraw"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{Emoji.TARGET} Set Profit Target",
        callback_data="cmd_target"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{Emoji.CHART_UP} Compare AI Modes",
        callback_data="cmd_compare"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{Emoji.BACK} Back",
        callback_data="cmd_back"
    ))

    return builder.as_markup()


def get_ai_mode_inline_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    """AI Mode Selection Inline Keyboard (၁၆ မျိုးစလုံး)"""
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
        text=f"{Emoji.BACK} Back to Main",
        callback_data="cmd_back"
    ))

    return builder.as_markup()


# ==========================================
# 6. API FUNCTIONS
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
        'username': USERNAME,
        'pwd': PASSWORD,
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
        'language': 7,
        'random': '4fc4413428be43faa1a3f30d9745ae3a',
        'signature': '5458639AF428AC897FDFF1102D82EB9C',
        'timestamp': int(time.time()),
    }

    data = await fetch_with_retry(
        session,
        'https://api.bigwinqaz.com/api/webapi/Login',
        BASE_HEADERS,
        json_data
    )

    if data and data.get('code') == 0:
        token_str = data.get('data', {})
        if isinstance(token_str, str):
            CURRENT_TOKEN = f"Bearer {token_str}"
        else:
            CURRENT_TOKEN = f"Bearer {token_str.get('token', '')}"
        print(f"{Emoji.CHECK} Login Success\n")
        return True

    return False


# ==========================================
# 7. NOTIFICATION SYSTEM
# ==========================================
async def send_bet_result_notification(user_id, bet, actual_size, actual_number, is_win, profit):
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
            reply_markup=get_main_reply_keyboard(is_active)
        )

    except Exception as e:
        print(f"Notification error for {user_id}: {e}")


async def send_target_reached_notification(user_id: int):
    try:
        user = await db.get_user(user_id)
        target = user.get('profit_target', 30000)

        await bot.send_message(
            chat_id=user_id,
            text=(
                f"{Emoji.SPARKLES} <b>🎯 Profit Target Reached!</b>\n\n"
                f"{Emoji.MONEY_ICON} Session Profit: {user['session_profit']:,.2f} Ks\n"
                f"{Emoji.TARGET} Target: {target:,.0f} Ks\n\n"
                f"{Emoji.CHECK} Auto-bet ရပ်ထားပါပြီ။\n"
                f"{Emoji.ONLINE} ပြန်စရန်: <b>Start Auto-Bet</b> ကိုနှိပ်ပါ။"
            ),
            reply_markup=get_main_reply_keyboard(False)
        )
    except Exception as e:
        print(f"Target notification error for {user_id}: {e}")


# ==========================================
# 8. CORE GAME LOGIC
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
        session,
        'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList',
        headers,
        json_data
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

                settled_bets = await db.settle_bets(latest_issue, latest_size, latest_number)
                for bet in settled_bets:
                    is_win = bet["result"] == "WIN"
                    profit = bet["profit"]
                    await send_bet_result_notification(
                        bet["user_id"], bet, latest_size, latest_number, is_win, profit
                    )

                    user = await db.get_user(bet["user_id"])
                    if user["session_profit"] >= user.get("profit_target", 30000):
                        await db.deactivate_session(bet["user_id"])
                        await send_target_reached_notification(bet["user_id"])

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

                        predicted_size, predicted_display, final_prob, reason = get_prediction(
                            history_docs, user_ai_mode
                        )
                        await db.save_prediction(next_issue, predicted_size, user_ai_mode)

                        recent_bets = await db.get_user_bets(user_id, 10)
                        lose_streak = 0
                        for bet in recent_bets:
                            if bet.get("result") == "LOSE":
                                lose_streak += 1
                            else:
                                break

                        bet_seq = user_session.get("bet_sequence", [100, 300, 900, 2700, 8100])
                        bet_amount = bet_seq[min(lose_streak, len(bet_seq) - 1)]

                        if user["balance"] >= bet_amount:
                            result = await db.place_bet(
                                user_id, next_issue, bet_amount, predicted_size, user_ai_mode
                            )
                            if result["success"]:
                                ai_name = AI_MODES.get(user_ai_mode, {}).get("name", "AI")
                                order_msg = (
                                    #f"{Emoji.ORDER} <b>Order Placed!</b>\n"
                                    f"{Emoji.GAME_ICON} WINGO_30S: <code>{next_issue}</code>\n"
                                    f"{Emoji.CHART_ICON} {predicted_size} | {bet_amount:,.0f} Ks\n"
                                    f"{Emoji.BRAIN} {ai_name}"
                                )
                                await bot.send_message(
                                    chat_id=user_id,
                                    text=order_msg,
                                    reply_markup=get_main_reply_keyboard(True)
                                )
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
            f"{Emoji.CLOCK} Next Result In: <b>{sec_left}s</b>\n\n"
            f"{table_str}\n"
            f"{Emoji.GAME} <b>Period:</b> {iss_display}\n"
            f"{Emoji.ROBOT} <b>AI ခန့်မှန်းချက် : {predicted_display}</b>\n"
            f"{Emoji.BAR_CHART} <b>ဖြစ်နိုင်ခြေ : {final_prob}%</b>\n"
            f"{Emoji.INFO} <b>အကြောင်းပြချက် :</b>\n{reason}"
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
# 9. CHART GENERATOR
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
# 10. SCHEDULER
# ==========================================
async def auto_broadcaster():
    await db.init_indexes()
    global SUDO_USERS
    SUDO_USERS = await db.get_sudo_users()
    print(f"{Emoji.CHECK} DB Connected | {Emoji.SHIELD} Sudo: {len(SUDO_USERS)}")

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
                        sleep_time = 30 - (int(time.time()) % 30)
                        await asyncio.sleep(sleep_time)
                        continue
                except Exception as e:
                    print(f"Scheduler error: {e}")

            await asyncio.sleep(0.5)


# ==========================================
# 11. COMMAND HANDLERS
# ==========================================
@auth_router.message(Command("start"))
@auth_router.message(lambda m: m.text and m.text.lower().strip() in ['.start', '/start'])
async def cmd_start(message: types.Message):
    """Welcome message with Reply Keyboard"""
    user = await db.get_user(message.from_user.id)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users

    user_session = await db.get_user_session(message.from_user.id)
    user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)

    await message.reply(
        f"{Emoji.SPARKLES} <b>WIN GO AI Bot v4.0</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.SHIELD} <b>Access:</b> {'Owner' if str(message.from_user.id) == str(OWNER_ID) else 'Sudo'}\n"
        f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} <b>Status:</b> {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.BRAIN} <b>Your AI:</b> {AI_MODES.get(user_ai_mode, {}).get('name', 'AI')}\n"
        f"{Emoji.TARGET} <b>Target:</b> {user.get('profit_target', 30000):,.0f} Ks\n\n"
        f"👇 <b>အောက်က Keyboard ကိုသုံးပါ:</b>",
        reply_markup=get_main_reply_keyboard(is_active)
    )


# ==========================================
# 12. REPLY KEYBOARD HANDLERS (Custom Keyboard)
# ==========================================

@auth_router.message(lambda m: m.text and m.text.strip() == f"{Emoji.PLAY} Start Auto-Bet")
async def handle_start_button(message: types.Message):
    """Start Auto-Bet from Reply Keyboard"""
    user_id = message.from_user.id
    active_users = await db.get_active_users()

    if user_id in active_users:
        await message.reply(
            f"{Emoji.CHECK} Already active!",
            reply_markup=get_main_reply_keyboard(True)
        )
        return

    user_session = await db.get_user_session(user_id)
    await db.activate_session(user_id, user_session.get("ai_mode", DEFAULT_AI_MODE))
    user = await db.get_user(user_id)

    await message.reply(
        f"{Emoji.CHECK} <b>Auto-Bet Activated!</b>\n\n"
        f"{Emoji.MONEY_ICON} Balance: {user['balance']:,.0f} Ks\n"
        f"{Emoji.TARGET} Target: {user.get('profit_target', 30000):,.0f} Ks\n\n"
        f"👇 Keyboard ကိုသုံးပါ:",
        reply_markup=get_main_reply_keyboard(True)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == f"{Emoji.STOP} Stop Auto-Bet")
async def handle_stop_button(message: types.Message):
    """Stop Auto-Bet from Reply Keyboard"""
    user_id = message.from_user.id
    active_users = await db.get_active_users()

    if user_id not in active_users:
        await message.reply(
            f"{Emoji.CROSS} Not active!",
            reply_markup=get_main_reply_keyboard(False)
        )
        return

    await db.deactivate_session(user_id)
    user = await db.get_user(user_id)

    await message.reply(
        f"{Emoji.OFFLINE} <b>Auto-Bet Stopped!</b>\n\n"
        f"{Emoji.MONEY_ICON} Balance: {user['balance']:,.0f} Ks\n"
        f"{Emoji.CHART_UP} Session Profit: {user['session_profit']:,.2f} Ks\n\n"
        f"👇 Keyboard ကိုသုံးပါ:",
        reply_markup=get_main_reply_keyboard(False)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == f"{Emoji.MONEY_ICON} Balance")
async def handle_bal_button(message: types.Message):
    """Show balance from Reply Keyboard"""
    user = await db.get_user(message.from_user.id)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users

    await message.reply(
        f"{Emoji.MONEY_ICON} <b>သင့်အကောင့်</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} Status: {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.MONEY_BAG} Balance: {user['balance']:,.2f} Ks\n"
        f"{Emoji.CHART_UP} Session: {user['session_profit']:,.2f} Ks\n"
        f"{Emoji.TARGET} Target: {user.get('profit_target', 30000):,.0f} Ks\n"
        f"{Emoji.CHECK} Wins: {user['total_wins']} | {Emoji.CROSS} Losses: {user['total_losses']}",
        reply_markup=get_main_reply_keyboard(is_active)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == f"{Emoji.BRAIN} AI Mode")
async def handle_mode_button(message: types.Message):
    """Show AI Mode selection (Inline Keyboard) from Reply Keyboard"""
    user_session = await db.get_user_session(message.from_user.id)
    current_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)

    await message.reply(
        f"{Emoji.BRAIN} <b>AI Mode ရွေးပါ (၁၆ မျိုး)</b>\n"
        f"📌 လက်ရှိ: <b>{AI_MODES.get(current_mode, {}).get('name', 'AI')}</b>\n\n"
        f"👇 အောက်က Inline Button များမှရွေးပါ:",
        reply_markup=get_ai_mode_inline_keyboard(current_mode)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == f"{Emoji.CHART} Status")
async def handle_status_button(message: types.Message):
    """Show status from Reply Keyboard"""
    user = await db.get_user(message.from_user.id)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users

    user_session = await db.get_user_session(message.from_user.id)
    pending = await db.get_pending_bets_count(message.from_user.id)

    await message.reply(
        f"{Emoji.BAR_CHART} <b>သင့် Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} Auto-Bet: {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.BRAIN} AI: {AI_MODES.get(user_session.get('ai_mode', DEFAULT_AI_MODE), {}).get('name', 'AI')}\n"
        f"{Emoji.MONEY_ICON} Balance: {user['balance']:,.0f} Ks\n"
        f"{Emoji.CHART_UP} Session Profit: {user['session_profit']:,.2f} Ks\n"
        f"{Emoji.TARGET} Target: {user.get('profit_target', 30000):,.0f} Ks\n"
        f"⏳ Pending: {pending}\n"
        f"{Emoji.FIRE} Best Streak: {user.get('best_streak', 0)}",
        reply_markup=get_main_reply_keyboard(is_active)
    )


@auth_router.message(lambda m: m.text and m.text.strip() == f"{Emoji.SETTINGS} Settings")
async def handle_settings_button(message: types.Message):
    """Show Settings (Inline Keyboard) from Reply Keyboard"""
    await message.reply(
        f"{Emoji.SETTINGS} <b>Settings</b>\n\n"
        f"👇 အောက်က Inline Button များမှရွေးပါ:",
        reply_markup=get_settings_inline_keyboard()
    )


@auth_router.message(lambda m: m.text and m.text.strip() == f"{Emoji.HISTORY} My Bets")
async def handle_mybets_button(message: types.Message):
    """Show bet history from Reply Keyboard"""
    bets = await db.get_user_bets(message.from_user.id, 10)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users

    text = f"{Emoji.GAME} <b>မှတ်တမ်း</b>\n"
    if bets:
        for bet in bets:
            if bet["result"] is None:
                status = "⏳"
            elif bet["result"] == "WIN":
                status = f"{Emoji.CHECK} +{bet['profit']:,.0f}"
            else:
                status = f"{Emoji.CROSS} -{bet['bet_amount']:,.0f}"
            text += f"{bet['issue_number']}: {bet['bet_amount']:,.0f}K {bet['predicted_size']} → {status}\n"
    else:
        text += "မရှိသေးပါ"

    await message.reply(text, reply_markup=get_main_reply_keyboard(is_active))


@auth_router.message(lambda m: m.text and m.text.strip() == f"{Emoji.CROWN} Top 10")
async def handle_top_button(message: types.Message):
    """Show leaderboard from Reply Keyboard"""
    leaderboard = await db.get_leaderboard(10)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users

    text = f"{Emoji.CROWN} <b>TOP 10</b>\n"
    for i, user in enumerate(leaderboard, 1):
        medal = Emoji.GOLD if i == 1 else Emoji.SILVER if i == 2 else Emoji.BRONZE if i == 3 else f"{i}."
        text += f"{medal} <code>{user['user_id']}</code>: {user['balance']:,.0f} Ks\n"

    await message.reply(text, reply_markup=get_main_reply_keyboard(is_active))


# ==========================================
# 13. TARGET INPUT HANDLER (စာရိုက်ထည့်ရန်)
# ==========================================
# User state tracking for target input
user_target_input = {}

@auth_router.callback_query(lambda c: c.data == "cmd_target")
async def cb_target(callback: types.CallbackQuery):
    """Start target input - စာရိုက်ထည့်ဖို့ prompt"""
    user_id = callback.from_user.id
    user_target_input[user_id] = True

    user = await db.get_user(user_id)

    await callback.message.edit_text(
        f"{Emoji.TARGET} <b>Profit Target သတ်မှတ်ရန်</b>\n\n"
        f"📌 လက်ရှိ: <b>{user.get('profit_target', 30000):,.0f} Ks</b>\n\n"
        f"👇 <b>ပမာဏကို စာရိုက်ထည့်ပါ:</b>\n"
        f"ဥပမာ: <code>30000</code> or <code>50000</code>\n\n"
        f"{Emoji.INFO} Target ရောက်ရင် Auto-Stop ပါမည်。\n"
        f"Cancel လုပ်ရန်: <code>/cancel</code>"
    )
    await callback.answer()


@auth_router.message(lambda m: m.text and m.text.strip().isdigit() and m.from_user.id in user_target_input)
async def handle_target_input(message: types.Message):
    """Process target input"""
    user_id = message.from_user.id

    if user_id not in user_target_input:
        return

    try:
        target = float(message.text.strip())
        if target <= 0:
            await message.reply(
                f"{Emoji.CROSS} 0 ထက်ကြီးရပါမည်။ ထပ်ကြိုးစားပါ:",
                reply_markup=get_main_reply_keyboard(False)
            )
            return

        await db.update_profit_target(user_id, target)
        del user_target_input[user_id]

        active_users = await db.get_active_users()
        is_active = user_id in active_users

        await message.reply(
            f"{Emoji.CHECK} <b>Profit Target သတ်မှတ်ပြီးပါပြီ!</b>\n\n"
            f"{Emoji.TARGET} Target: <b>{target:,.0f} Ks</b>\n"
            f"{Emoji.INFO} ဤပမာဏရောက်ရင် Auto-Stop ပါမည်။",
            reply_markup=get_main_reply_keyboard(is_active)
        )
    except ValueError:
        await message.reply(
            f"{Emoji.CROSS} ဂဏန်းများသာထည့်ပါ။ ဥပမာ: 30000",
            reply_markup=get_main_reply_keyboard(False)
        )


@auth_router.message(Command("cancel"))
@auth_router.message(lambda m: m.text and m.text.strip().lower() == '/cancel')
async def cmd_cancel(message: types.Message):
    """Cancel target input"""
    user_id = message.from_user.id
    if user_id in user_target_input:
        del user_target_input[user_id]

    active_users = await db.get_active_users()
    is_active = user_id in active_users

    await message.reply(
        f"{Emoji.CHECK} Cancelled.",
        reply_markup=get_main_reply_keyboard(is_active)
    )


# ==========================================
# 14. INLINE KEYBOARD CALLBACK HANDLERS
# ==========================================

@auth_router.callback_query(lambda c: c.data and c.data.startswith("usermode_"))
async def cb_user_mode_select(callback: types.CallbackQuery):
    """Process AI mode selection from Inline Keyboard"""
    mode_key = callback.data.replace("usermode_", "")

    if mode_key in AI_MODES:
        await db.update_user_ai_mode(callback.from_user.id, mode_key)

        await callback.message.edit_text(
            f"{Emoji.CHECK} <b>AI Mode ပြောင်းပြီး!</b>\n"
            f"{Emoji.BRAIN} {AI_MODES[mode_key]['name']}\n"
            f"{Emoji.INFO} {AI_MODES[mode_key]['desc']}",
            reply_markup=None
        )
        await callback.answer(f"✅ {AI_MODES[mode_key]['name']}")


@auth_router.callback_query(lambda c: c.data == "cmd_compare")
async def cb_compare(callback: types.CallbackQuery):
    """Compare AI modes"""
    await callback.answer("Comparing...")

    history_docs = await db.get_history(100)
    if len(history_docs) < 20:
        await callback.message.edit_text("Data မလုံလောက်သေးပါ。")
        return

    test_docs = history_docs[:80]
    results = {}

    for mode_key, mode_info in AI_MODES.items():
        correct = 0
        total = 0
        for i in range(len(test_docs) - 10):
            segment = test_docs[i + 10:i:-1]
            if len(segment) >= 10:
                try:
                    pred_size, _, _, _ = mode_info["func"](segment)
                    if pred_size == test_docs[i].get("size", "BIG"):
                        correct += 1
                    total += 1
                except Exception:
                    pass
        accuracy = (correct / total * 100) if total > 0 else 0
        results[mode_key] = {"name": mode_info["name"], "accuracy": accuracy}

    sorted_results = sorted(results.items(), key=lambda x: x[1]["accuracy"], reverse=True)

    text = f"{Emoji.BAR_CHART} <b>AI COMPARISON (Top 5)</b>\n"
    for i, (key, data) in enumerate(sorted_results[:5], 1):
        medal = Emoji.GOLD if i == 1 else Emoji.SILVER if i == 2 else Emoji.BRONZE if i == 3 else f"{i}."
        text += f"{medal} {data['name']}: {data['accuracy']:.1f}%\n"

    await callback.message.edit_text(text)
    await callback.answer()


@auth_router.callback_query(lambda c: c.data == "cmd_addbal")
async def cb_addbal(callback: types.CallbackQuery):
    """Show add balance options"""
    builder = InlineKeyboardBuilder()
    for amt in [10000, 50000, 100000, 500000]:
        builder.row(InlineKeyboardButton(
            text=f"{Emoji.MONEY_BAG} +{amt:,} Ks",
            callback_data=f"addbal_{amt}"
        ))
    builder.row(InlineKeyboardButton(text=f"{Emoji.BACK} Back", callback_data="cmd_back"))

    await callback.message.edit_text(
        f"{Emoji.MONEY_ICON} <b>ငွေထည့်ရန်</b>\n👇 ပမာဏရွေးပါ:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@auth_router.callback_query(lambda c: c.data and c.data.startswith("addbal_"))
async def cb_process_addbal(callback: types.CallbackQuery):
    """Process add balance"""
    amount = float(callback.data.replace("addbal_", ""))
    user = await db.update_balance(callback.from_user.id, amount, "add")

    await callback.message.edit_text(
        f"{Emoji.CHECK} +{amount:,.0f} Ks\n{Emoji.MONEY_ICON} Balance: {user['balance']:,.0f} Ks"
    )
    await callback.answer(f"✅ +{amount:,} Ks")


@auth_router.callback_query(lambda c: c.data == "cmd_withdraw")
async def cb_withdraw(callback: types.CallbackQuery):
    """Show withdraw options"""
    builder = InlineKeyboardBuilder()
    for amt in [10000, 50000, 100000]:
        builder.row(InlineKeyboardButton(
            text=f"{Emoji.MONEY_BAG} -{amt:,} Ks",
            callback_data=f"withdraw_{amt}"
        ))
    builder.row(InlineKeyboardButton(text="💰 Withdraw All", callback_data="withdraw_all"))
    builder.row(InlineKeyboardButton(text=f"{Emoji.BACK} Back", callback_data="cmd_back"))

    await callback.message.edit_text(
        f"{Emoji.MONEY_ICON} <b>ငွေနှုတ်ရန်</b>\n👇 ပမာဏရွေးပါ:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@auth_router.callback_query(lambda c: c.data and c.data.startswith("withdraw_"))
async def cb_process_withdraw(callback: types.CallbackQuery):
    """Process withdraw"""
    data = callback.data.replace("withdraw_", "")
    user = await db.get_user(callback.from_user.id)
    amount = user['balance'] if data == "all" else float(data)

    if amount > user['balance']:
        await callback.answer("Not enough balance!", show_alert=True)
        return

    await db.update_balance(callback.from_user.id, amount, "subtract")
    updated = await db.get_user(callback.from_user.id)

    await callback.message.edit_text(
        f"{Emoji.CHECK} -{amount:,.0f} Ks\n{Emoji.MONEY_ICON} Balance: {updated['balance']:,.0f} Ks"
    )
    await callback.answer(f"✅ -{amount:,} Ks")


@auth_router.callback_query(lambda c: c.data == "cmd_back")
async def cb_back(callback: types.CallbackQuery):
    """Back to main menu"""
    user = await db.get_user(callback.from_user.id)
    active_users = await db.get_active_users()
    is_active = callback.from_user.id in active_users
    user_session = await db.get_user_session(callback.from_user.id)
    user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)

    await callback.message.edit_text(
        f"{Emoji.SPARKLES} <b>WIN GO AI Bot v4.0</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.MONEY_ICON} Balance: {user['balance']:,.0f} Ks\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} Status: {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.BRAIN} AI: {AI_MODES.get(user_ai_mode, {}).get('name', 'AI')}\n"
        f"{Emoji.TARGET} Target: {user.get('profit_target', 30000):,.0f} Ks\n\n"
        f"👇 Keyboard ကိုသုံးပါ:"
    )
    await callback.answer()


# ==========================================
# 15. OWNER ONLY COMMANDS
# ==========================================
@owner_router.message(Command("addsudo"))
async def cmd_add_sudo(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("/addsudo [user_id]")
            return
        target_id = int(parts[1])
        await db.add_sudo(target_id, message.from_user.id)
        global SUDO_USERS
        SUDO_USERS = await db.get_sudo_users()
        await message.reply(f"{Emoji.CHECK} Sudo Added: <code>{target_id}</code>")
    except ValueError:
        await message.reply("User ID ဂဏန်းသာထည့်ပါ။")


@owner_router.message(Command("delsudo"))
async def cmd_del_sudo(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("/delsudo [user_id]")
            return
        target_id = int(parts[1])
        await db.remove_sudo(target_id)
        global SUDO_USERS
        SUDO_USERS = await db.get_sudo_users()
        await message.reply(f"{Emoji.CHECK} Sudo Removed: <code>{target_id}</code>")
    except ValueError:
        await message.reply("User ID ဂဏန်းသာထည့်ပါ။")


# ==========================================
# 16. INITIALIZATION & MAIN
# ==========================================
async def init_system():
    global DEFAULT_AI_MODE, SUDO_USERS
    await db.init_indexes()
    SUDO_USERS = await db.get_sudo_users()
    DEFAULT_AI_MODE = await db.get_setting("default_ai_mode", "ensemble")
    print(f"{Emoji.CHECK} System Ready | AI: {DEFAULT_AI_MODE} | Sudo: {len(SUDO_USERS)}")


async def main():
    await init_system()
    print(f"\n{Emoji.SPARKLES} WIN GO AI Bot v4.0 - Reply + Inline Keyboard System\n")
    print(f"{Emoji.CROWN} Owner: {OWNER_ID}")
    print(f"{Emoji.BRAIN} Default AI: {DEFAULT_AI_MODE}")
    print(f"{Emoji.SHIELD} Sudo Users: {len(SUDO_USERS)}\n")

    dp.include_router(auth_router)
    dp.include_router(owner_router)

    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Emoji.OFFLINE} Bot Stopped")
