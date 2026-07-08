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
from aiogram.types import BufferedInputFile, InputMediaPhoto, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import BaseMiddleware

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import warnings
warnings.filterwarnings("ignore")

from database import db
from ai_engines import AI_MODES, get_prediction, Emoji as AIEmoji

load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================
USERNAME = os.getenv("BIGWIN_USERNAME", "959675323878")
PASSWORD = os.getenv("BIGWIN_PASSWORD", "Mitheint11")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OWNER_ID = os.getenv("OWNER_ID")

if not all([BOT_TOKEN, CHANNEL_ID, OWNER_ID]):
    print("❌ Error: .env ဖိုင်ထဲတွင် အချက်အလက်များ ပြည့်စုံစွာ မပါဝင်ပါ။")
    exit()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Routers
auth_router = Router()   # Owner + Sudo
owner_router = Router()  # Owner only

# ==========================================
# 💎 PREMIUM EMOJI CONSTANTS
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
}

def premium_emoji(emoji_key, fallback):
    emoji_id = PREMIUM_EMOJI_IDS.get(emoji_key, "0")
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

class Emoji:
    # Premium Custom Emojis (၈ ခု)
    WIN_CHECK = premium_emoji("win_check", "✅")
    LOSE_CROSS = premium_emoji("lose_cross", "❌")
    ORDER = premium_emoji("order", "📝")
    GAME_ICON = premium_emoji("game", "🎮")
    CHART_ICON = premium_emoji("chart", "📊")
    CHART_UP = premium_emoji("chart_up", "📈")
    MONEY_ICON = premium_emoji("money", "💰")
    LOSS_ICON = premium_emoji("loss", "📉")
    BRAIN = premium_emoji("brain", "🧠")
    
    # Standard Emojis
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
    DICE = "🎲"
    TARGET = "🎯"
    CONTROLLER = "🕹️"
    MONEY = "💰"
    MONEY_BAG = "💵"
    COIN = "🪙"
    CHART_UP = "📈"
    CHART_DOWN = "📉"
    BAR_CHART = "📊"
    BANK = "🏦"
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
    MOMENTUM = "📈"
    MONTECARLO = "🎲"
    NEURAL = "🧬"
    REVERSAL = "⚡"
    WAVE = "🌊"
    CHAOS = "🎪"
    BET = "🎰"
    TICKET = "🎫"
    HASH = "#️⃣"
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
# SYSTEM VARIABLES
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = None
MAIN_MESSAGE_ID = None
SESSION_START_ISSUE = None
DEFAULT_AI_MODE = "ensemble"  # Default system AI mode
SUDO_USERS = set()
ACTIVE_USERS = set()  # Set of ALL active user IDs (for checking if any active)
OWNER_ACTIVE = False

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# ==========================================
# PERMISSION MIDDLEWARE
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
                await event.reply(f"{Emoji.LOCK} <b>Access Denied!</b>\n\n{Emoji.INFO} Owner & Sudo Users များသာ အသုံးပြုခွင့်ရှိပါသည်။")
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
                await event.reply(f"{Emoji.CROSS} {Emoji.CROWN} Owner သာ ဤ command ကိုသုံးခွင့်ရှိသည်။")
            elif isinstance(event, types.CallbackQuery):
                await event.answer("👑 Owner only!", show_alert=True)
            return
        return await handler(event, data)

auth_router.message.middleware(AuthMiddleware())
auth_router.callback_query.middleware(AuthMiddleware())
owner_router.message.middleware(OwnerOnlyMiddleware())
owner_router.callback_query.middleware(OwnerOnlyMiddleware())

# ==========================================
# API FUNCTIONS
# ==========================================
async def fetch_with_retry(session, url, headers, json_data, retries=1):
    for _ in range(retries):
        try:
            async with session.post(url, headers=headers, json=json_data, timeout=3.0) as response:
                if response.status == 200:
                    return await response.json()
        except Exception:
            await asyncio.sleep(0.2)
    return None

async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    json_data = {
        'username': USERNAME, 'pwd': PASSWORD, 'phonetype': 1, 'logintype': 'mobile',
        'packId': '', 'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6', 'language': 7,
        'random': '4fc4413428be43faa1a3f30d9745ae3a', 'signature': '5458639AF428AC897FDFF1102D82EB9C',
        'timestamp': int(time.time()),
    }
    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/Login', BASE_HEADERS, json_data)
    if data and data.get('code') == 0:
        token_str = data.get('data', {}) if isinstance(data.get('data'), str) else data.get('data', {}).get('token', '')
        CURRENT_TOKEN = f"Bearer {token_str}"
        print(f"{Emoji.CHECK} Login Success\n")
        return True
    return False

# ==========================================
# SEND NOTIFICATION
# ==========================================
async def send_bet_result_notification(user_id: int, bet: dict, actual_size: str, actual_number: int, is_win: bool, profit: float):
    try:
        user = await db.get_user(user_id)
        color_map = {0: "🟣 VIOLET", 1: "🟢 GREEN", 2: "🔴 RED", 3: "🟢 GREEN", 4: "🔴 RED", 5: "🟢 GREEN", 6: "🔴 RED", 7: "🟢 GREEN", 8: "🔴 RED", 9: "🟢 GREEN"}
        color = color_map.get(actual_number, "⚪ WHITE")
        
        if is_win:
            message = (
                f"{Emoji.WIN_CHECK} <b>WIN!</b> +{profit:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{Emoji.GAME_ICON} <b>WINGO_30S</b> : <code>{bet['issue_number']}</code>\n"
                f"{Emoji.CHART_ICON} <b>Result:</b> {actual_number} {Emoji.BULLSEYE if actual_size == 'BIG' else Emoji.GREEN_CIRCLE} {actual_size} {color}\n"
                f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.2f} Ks\n"
                f"{Emoji.CHART_UP} <b>Session Profit:</b> +{user['session_profit']:,.2f} / {user.get('profit_target', 30000):,.0f} Ks"
            )
        else:
            message = (
                f"{Emoji.LOSE_CROSS} <b>LOSE!</b> -{bet['bet_amount']:,.2f} Ks\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{Emoji.GAME_ICON} <b>WINGO_30S</b> : <code>{bet['issue_number']}</code>\n"
                f"{Emoji.CHART_ICON} <b>Result:</b> {actual_number} {Emoji.BULLSEYE if actual_size == 'BIG' else Emoji.GREEN_CIRCLE} {actual_size} {color}\n"
                f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.2f} Ks\n"
                f"{Emoji.LOSS_ICON} <b>Session Profit:</b> {user['session_profit']:,.2f} / {user.get('profit_target', 30000):,.0f} Ks"
            )
        await bot.send_message(chat_id=user_id, text=message)
    except Exception as e:
        print(f"Notification error {user_id}: {e}")

# ==========================================
# CORE GAME LOGIC
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
    
    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers, json_data)
    
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
                
                # Settle bets
                settled_bets = await db.settle_bets(latest_issue, latest_size, latest_number)
                for bet in settled_bets:
                    is_win = bet["result"] == "WIN"
                    profit = bet["profit"]
                    await send_bet_result_notification(bet["user_id"], bet, latest_size, latest_number, is_win, profit)
                    
                    # Check profit target
                    user = await db.get_user(bet["user_id"])
                    if user["session_profit"] >= user.get("profit_target", 30000):
                        await db.deactivate_session(bet["user_id"])
                        try:
                            await bot.send_message(
                                chat_id=bet["user_id"],
                                text=f"{Emoji.SPARKLES} <b>🎯 Profit Target Reached!</b>\n\n"
                                f"{Emoji.MONEY_ICON} Session Profit: {user['session_profit']:,.2f} Ks\n"
                                f"{Emoji.CHART_UP} Target: {user.get('profit_target', 30000):,.0f} Ks\n\n"
                                f"{Emoji.CHECK} Auto-bet ရပ်ထားပါပြီ။\n"
                                f"{Emoji.ONLINE} ပြန်စရန်: <code>/active</code> or <code>.active</code>"
                            )
                        except:
                            pass
                
                if settled_bets:
                    print(f"💰 Settled {len(settled_bets)} bets for {latest_issue} - {latest_number} ({latest_size})")
                
                next_issue = str(int(latest_issue) + 1)
                history_docs = await db.get_history(5000)
                
                # Get active users
                active_users = await db.get_active_users()
                
                for user_id in active_users:
                    try:
                        user = await db.get_user(user_id)
                        user_session = await db.get_user_session(user_id)
                        user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
                        
                        # Get prediction based on user's AI mode
                        predicted_size, predicted_display, final_prob, reason = get_prediction(history_docs, user_ai_mode)
                        
                        # Save prediction
                        await db.save_prediction(next_issue, predicted_size, user_ai_mode)
                        
                        # Calculate bet amount based on lose streak
                        recent_bets = await db.get_user_bets(user_id, 10)
                        lose_streak = 0
                        for bet in recent_bets:
                            if bet.get("result") == "LOSE":
                                lose_streak += 1
                            else:
                                break
                        
                        bet_seq = user_session.get("bet_sequence", [100, 300, 900, 2700, 8100])
                        bet_amount = bet_seq[min(lose_streak, len(bet_seq)-1)]
                        
                        if user["balance"] >= bet_amount:
                            result = await db.place_bet(user_id, next_issue, bet_amount, predicted_size, user_ai_mode)
                            if result["success"]:
                                ai_name = AI_MODES.get(user_ai_mode, {}).get("name", "AI")
                                order_msg = (
                                    f"{Emoji.ORDER} <b>Order Placed!</b>\n"
                                    f"{Emoji.GAME_ICON} <b>WINGO_30S</b> : <code>{next_issue}</code>\n"
                                    f"{Emoji.CHART_ICON} <b>Order:</b> {predicted_size} | {bet_amount:,.0f} Ks\n"
                                    f"{Emoji.BRAIN} <b>Strategy:</b> {ai_name}"
                                )
                                try:
                                    await bot.send_message(chat_id=user_id, text=order_msg)
                                except:
                                    pass
                    except Exception as e:
                        print(f"Auto-bet error for {user_id}: {e}")
                
                # Update channel post (using default AI mode)
                default_pred, default_display, default_prob, default_reason = get_prediction(history_docs, DEFAULT_AI_MODE)
                await update_channel_post(next_issue, default_display, default_prob, default_reason)
                return True
        return False
    elif data and (data.get('code') == 401 or "token" in str(data.get('msg')).lower()):
        CURRENT_TOKEN = ""
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
            except:
                msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                MAIN_MESSAGE_ID = msg.message_id
        else:
            msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
            MAIN_MESSAGE_ID = msg.message_id
    except Exception as e:
        print(f"Channel update error: {e}")

def generate_chart(predictions):
    wins, losses = 0, 0
    bar_colors, bar_heights, history_wr = [], [], []
    latest_preds = list(reversed(predictions))[-20:]
    
    for i, p in enumerate(latest_preds):
        if 'WIN' in p.get('win_lose', ''):
            wins += 1; bar_colors.append('#00e5ff')
        else:
            losses += 1; bar_colors.append('#ff4444')
        bar_heights.append((wins / (i+1)) * 100)
        history_wr.append((wins / (i+1)) * 100)
    
    total_played = wins + losses
    win_rate = int((wins / total_played * 100)) if total_played > 0 else 0
    
    fig = plt.figure(figsize=(10.24, 7.68), facecolor='#1c1f26')
    fig.text(0.05, 0.93, "🏆 WIN GO PERFORMANCE", color='#ffffff', fontsize=26, fontweight='bold', ha='left')
    
    # Gauge chart
    ax_circle = fig.add_axes([0.08, 0.42, 0.35, 0.40])
    ax_circle.set_axis_off(); ax_circle.set_xlim(0, 1); ax_circle.set_ylim(0, 1)
    theta_bg = np.linspace(-1.25*np.pi, 0.25*np.pi, 200)
    ax_circle.plot(0.5 + 0.45*np.cos(theta_bg), 0.5 + 0.45*np.sin(theta_bg), color='#2c313c', linewidth=12)
    if win_rate > 0:
        end_angle = 0.25*np.pi - (win_rate/100) * 1.5 * np.pi
        theta_fg = np.linspace(0.25*np.pi, end_angle, 100)
        ax_circle.plot(0.5 + 0.45*np.cos(theta_fg), 0.5 + 0.45*np.sin(theta_fg), color='#00e5ff', linewidth=12)
    ax_circle.text(0.5, 0.75, f"{total_played}/20", color='#a3a8b5', fontsize=16, fontweight='bold', ha='center')
    ax_circle.text(0.5, 0.48, f"{win_rate}%", color='#00e5ff', fontsize=65, fontweight='bold', ha='center')
    
    # Bar chart
    ax_bar = fig.add_axes([0.55, 0.47, 0.38, 0.33])
    ax_bar.set_facecolor('#1c1f26'); ax_bar.set_xlim(-0.5, 19.5); ax_bar.set_ylim(0, 105)
    for spine in ax_bar.spines.values(): spine.set_visible(False)
    ax_bar.set_yticks([0, 25, 50, 75, 100])
    ax_bar.set_yticklabels(['0%', '25%', '50%', '75%', '100%'], color='#7a8294', fontsize=10)
    ax_bar.grid(axis='y', color='#2c313c', linewidth=1.5)
    if total_played > 0:
        x_pos = np.arange(total_played)
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.8, alpha=0.15, align='center')
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.45, alpha=0.9, align='center')
        ax_bar.plot(x_pos, history_wr, color='#00e5ff', linewidth=2.5, marker='o', markersize=6, markerfacecolor='#1c1f26', markeredgecolor='#00e5ff', markeredgewidth=2)
    ax_bar.set_xticks(np.arange(20)); ax_bar.set_xticklabels([str(i+1) for i in range(20)], color='#7a8294', fontsize=10)
    
    # Win/Loss boxes
    ax_win = fig.add_axes([0.05, 0.22, 0.28, 0.16]); ax_win.set_axis_off()
    rect_win = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#1de9b6")
    ax_win.add_patch(rect_win)
    ax_win.text(0.1, 0.75, "WINS", color='#004d40', fontsize=16, fontweight='bold')
    ax_win.text(0.1, 0.35, f"{wins}", color='#000000', fontsize=48, fontweight='bold')
    
    ax_lose = fig.add_axes([0.35, 0.22, 0.28, 0.16]); ax_lose.set_axis_off()
    rect_lose = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#ef5350")
    ax_lose.add_patch(rect_lose)
    ax_lose.text(0.1, 0.75, "LOSSES", color='#4d0000', fontsize=16, fontweight='bold')
    ax_lose.text(0.1, 0.35, f"{losses}", color='#ffffff', fontsize=48, fontweight='bold')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, facecolor='#1c1f26')
    buf.seek(0); plt.close(fig)
    return buf

# ==========================================
# SCHEDULER
# ==========================================
async def auto_broadcaster():
    await db.init_indexes()
    global SUDO_USERS
    SUDO_USERS = await db.get_sudo_users()
    global ACTIVE_USERS
    ACTIVE_USERS = await db.get_active_users()
    
    print(f"{Emoji.CHECK} DB Connected | {Emoji.SHIELD} Sudo: {len(SUDO_USERS)} | 👥 Active: {len(ACTIVE_USERS)}")
    
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
                    pass
            await asyncio.sleep(0.5)

# ==========================================
# AUTH COMMANDS (Owner + Sudo)
# ==========================================

@auth_router.message(Command("start"))
@auth_router.message(lambda m: m.text and m.text.lower() in ['.start', '/start'])
async def send_welcome(message: types.Message):
    user = await db.get_user(message.from_user.id)
    is_active = message.from_user.id in (await db.get_active_users())
    user_session = await db.get_user_session(message.from_user.id)
    user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
    
    await message.reply(
        f"{Emoji.SPARKLES} <b>WIN GO AI Bot v4.0</b> {Emoji.SPARKLES}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.SHIELD} <b>Access:</b> {'Owner' if str(message.from_user.id) == str(OWNER_ID) else 'Sudo'}\n"
        f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} <b>Status:</b> {'✅ Active' if is_active else '❌ Inactive'}\n"
        f"{Emoji.BRAIN} <b>Your AI:</b> {AI_MODES.get(user_ai_mode, {}).get('name', 'AI')}\n"
        f"🎯 <b>Target:</b> {user.get('profit_target', 30000):,.0f} Ks\n\n"
        f"<b>Commands:</b>\n"
        f"<code>/active</code> or <code>.active</code> - Auto-bet စတင်ရန်\n"
        f"<code>/stop</code> or <code>.stop</code> - Auto-bet ရပ်ရန်\n"
        f"<code>/bet 100</code> or <code>.bet 100</code> - Manual လောင်းရန်\n"
        f"<code>/bal</code> or <code>.bal</code> - လက်ကျန်ကြည့်ရန်\n"
        f"<code>/addbal 50000</code> or <code>.addbal 50000</code> - ငွေထည့်ရန်\n"
        f"<code>/withdraw 50000</code> or <code>.withdraw 50000</code> - ငွေနှုတ်ရန်\n"
        f"<code>/mode</code> or <code>.mode</code> - AI Mode ပြောင်းရန် (၁၆ မျိုး)\n"
        f"<code>/target 50000</code> or <code>.target 50000</code> - Profit Target သတ်မှတ်ရန်\n"
        f"<code>/status</code> or <code>.status</code> - အခြေအနေကြည့်ရန်\n"
        f"<code>/top</code> or <code>.top</code> - Top 10"
    )

# Helper to handle both /command and .command
def both_commands(command_name):
    """Create filters for both /command and .command"""
    return lambda m: m.text and m.text.lower() in [f'/{command_name}', f'.{command_name}']

@auth_router.message(both_commands("active"))
@auth_router.message(Command("active"))
async def activate_user(message: types.Message):
    user_id = message.from_user.id
    active_users = await db.get_active_users()
    
    if user_id in active_users:
        await message.reply(f"{Emoji.CHECK} Auto-Bet Active ဖြစ်ပြီးသားပါ!")
        return
    
    user_session = await db.get_user_session(user_id)
    user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
    
    await db.activate_session(user_id, user_ai_mode)
    user = await db.get_user(user_id)
    ai_name = AI_MODES.get(user_ai_mode, {}).get("name", "AI")
    
    await message.reply(
        f"{Emoji.CHECK} <b>Auto-Bet Activated!</b>\n\n"
        f"{Emoji.GAME_ICON} <b>Game:</b> WINGO 30S\n"
        f"{Emoji.BRAIN} <b>Your AI:</b> {ai_name}\n"
        f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"🎯 <b>Target:</b> {user.get('profit_target', 30000):,.0f} Ks\n"
        f"{Emoji.MONEY_BAG} <b>Sequence:</b> 100 → 300 → 900 → 2,700 → 8,100\n\n"
        f"{Emoji.INFO} Profit Target ရောက်ရင် Auto-Stop ပါမယ်။\n"
        f"{Emoji.OFFLINE} ရပ်ရန်: <code>/stop</code> or <code>.stop</code>"
    )

@auth_router.message(both_commands("stop"))
@auth_router.message(Command("stop"))
async def deactivate_user(message: types.Message):
    user_id = message.from_user.id
    active_users = await db.get_active_users()
    
    if user_id not in active_users:
        await message.reply(f"{Emoji.CROSS} Auto-Bet Active မဖြစ်သေးပါ!")
        return
    
    await db.deactivate_session(user_id)
    user = await db.get_user(user_id)
    profit_emoji = Emoji.CHART_UP if user['session_profit'] > 0 else Emoji.CHART_DOWN
    
    await message.reply(
        f"{Emoji.OFFLINE} <b>Auto-Bet Stopped!</b>\n\n"
        f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"{profit_emoji} <b>Session Profit:</b> {user['session_profit']:,.2f} Ks\n"
        f"🎯 <b>Target:</b> {user.get('profit_target', 30000):,.0f} Ks\n\n"
        f"{Emoji.ONLINE} ပြန်စရန်: <code>/active</code> or <code>.active</code>"
    )

@auth_router.message(both_commands("mode"))
@auth_router.message(Command("mode"))
async def change_mode(message: types.Message):
    builder = InlineKeyboardBuilder()
    modes_list = list(AI_MODES.items())
    
    for i in range(0, len(modes_list), 2):
        row_buttons = []
        for j in range(2):
            if i + j < len(modes_list):
                key, info = modes_list[i + j]
                row_buttons.append(InlineKeyboardButton(text=info["name"], callback_data=f"usermode_{key}"))
        builder.row(*row_buttons)
    
    user_session = await db.get_user_session(message.from_user.id)
    user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
    current_name = AI_MODES.get(user_ai_mode, {}).get("name", "AI")
    
    await message.reply(
        f"{Emoji.BRAIN} <b>သင့် AI Mode ပြောင်းရန်</b>\n\n"
        f"📌 လက်ရှိ: <b>{current_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👇 ရွေးချယ်ပါ (၁၆ မျိုး):",
        reply_markup=builder.as_markup()
    )

@auth_router.callback_query(lambda c: c.data.startswith("usermode_"))
async def process_user_mode(callback: types.CallbackQuery):
    mode_key = callback.data.replace("usermode_", "")
    if mode_key in AI_MODES:
        await db.update_user_ai_mode(callback.from_user.id, mode_key)
        mode_name = AI_MODES[mode_key]["name"]
        await callback.message.edit_text(
            f"{Emoji.CHECK} <b>သင့် AI Mode ပြောင်းပြီးပါပြီ!</b>\n\n"
            f"{Emoji.BRAIN} လက်ရှိ: <b>{mode_name}</b>\n"
            f"{Emoji.INFO} {AI_MODES[mode_key]['desc']}\n\n"
            f"🔄 ပြန်ပြောင်းရန်: <code>/mode</code> or <code>.mode</code>"
        )
        await callback.answer(f"✅ {mode_name} သို့ပြောင်းပြီး!")

@auth_router.message(both_commands("target"))
@auth_router.message(Command("target"))
async def set_profit_target(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/target 50000</code> or <code>.target 50000</code>")
            return
        target = float(parts[1])
        if target <= 0:
            await message.reply(f"{Emoji.CROSS} 0 ထက်ကြီးရပါမည်။")
            return
        await db.update_profit_target(message.from_user.id, target)
        await db.users.update_one(
            {"user_id": message.from_user.id},
            {"$set": {"profit_target": target}}
        )
        await message.reply(
            f"{Emoji.CHECK} <b>Profit Target သတ်မှတ်ပြီးပါပြီ!</b>\n\n"
            f"🎯 Target: <b>{target:,.0f} Ks</b>\n"
            f"{Emoji.INFO} ဤပမာဏရောက်ရင် Auto-Stop ပါမည်။"
        )
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@auth_router.message(both_commands("status"))
@auth_router.message(Command("status"))
async def show_status(message: types.Message):
    user = await db.get_user(message.from_user.id)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users
    user_session = await db.get_user_session(message.from_user.id)
    user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
    
    pending = await db.get_pending_bets_count(message.from_user.id)
    profit_emoji = Emoji.CHART_UP if user['session_profit'] > 0 else Emoji.CHART_DOWN if user['session_profit'] < 0 else "➖"
    
    await message.reply(
        f"{Emoji.BAR_CHART} <b>သင့် Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} <b>Auto-Bet:</b> {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.BRAIN} <b>AI Mode:</b> {AI_MODES.get(user_ai_mode, {}).get('name', 'AI')}\n"
        f"{Emoji.MONEY_ICON} <b>Balance:</b> {user['balance']:,.0f} Ks\n"
        f"{profit_emoji} <b>Session Profit:</b> {user['session_profit']:,.2f} Ks\n"
        f"🎯 <b>Target:</b> {user.get('profit_target', 30000):,.0f} Ks\n"
        f"⏳ <b>Pending:</b> {pending}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.CHECK} Wins: {user['total_wins']} | {Emoji.CROSS} Losses: {user['total_losses']}\n"
        f"{Emoji.FIRE} Best Streak: {user.get('best_streak', 0)}"
    )

@auth_router.message(both_commands("bal"))
@auth_router.message(Command("bal"))
async def check_balance(message: types.Message):
    user = await db.get_user(message.from_user.id)
    active_users = await db.get_active_users()
    is_active = message.from_user.id in active_users
    wr = (user['total_wins'] / user['total_bets'] * 100) if user['total_bets'] > 0 else 0
    profit_e = Emoji.CHART_UP if user['profit'] > 0 else Emoji.CHART_DOWN if user['profit'] < 0 else "➖"
    
    await message.reply(
        f"{Emoji.MONEY_ICON} <b>သင့်အကောင့်</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{Emoji.ONLINE if is_active else Emoji.OFFLINE} Status: {'Active' if is_active else 'Inactive'}\n"
        f"{Emoji.MONEY_BAG} Balance: {user['balance']:,.2f} Ks\n"
        f"🎯 Session: {user['session_profit']:,.2f} / {user.get('profit_target', 30000):,.0f} Ks\n"
        f"{Emoji.GAME} Bets: {user['total_bets']} | WR: {wr:.1f}%\n"
        f"{profit_e} Total P/L: {user['profit']:,.2f} Ks"
    )

@auth_router.message(both_commands("addbal"))
@auth_router.message(Command("addbal"))
async def add_balance(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/addbal 50000</code> or <code>.addbal 50000</code>")
            return
        amount = float(parts[1])
        if amount <= 0 or amount > 1000000:
            await message.reply(f"{Emoji.CROSS} 1 - 1,000,000 Ks အတွင်းထည့်ပါ။")
            return
        user = await db.update_balance(message.from_user.id, amount, "add")
        await message.reply(f"{Emoji.CHECK} +{amount:,.0f} Ks\n{Emoji.MONEY_ICON} Balance: {user['balance']:,.0f} Ks")
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@auth_router.message(both_commands("withdraw"))
@auth_router.message(Command("withdraw"))
async def withdraw_balance(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/withdraw 50000</code> or <code>.withdraw 50000</code> or <code>/withdraw all</code>")
            return
        user = await db.get_user(message.from_user.id)
        if parts[1].lower() == "all":
            amount = user['balance']
            if amount <= 0:
                await message.reply(f"{Emoji.CROSS} နှုတ်ယူရန် ငွေမရှိပါ!"); return
        else:
            amount = float(parts[1])
            if amount <= 0 or amount > user['balance']:
                await message.reply(f"{Emoji.CROSS} ငွေပမာဏမမှန်ပါ!"); return
        await db.update_balance(message.from_user.id, amount, "subtract")
        updated = await db.get_user(message.from_user.id)
        await message.reply(f"{Emoji.CHECK} -{amount:,.0f} Ks\n{Emoji.MONEY_ICON} Balance: {updated['balance']:,.0f} Ks")
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@auth_router.message(both_commands("bet"))
@auth_router.message(Command("bet"))
async def place_bet_command(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/bet 100</code> or <code>.bet 100-300-900</code>")
            return
        
        bet_params = parts[1]
        if '-' in bet_params:
            bet_amounts = [float(x.strip()) for x in bet_params.split('-')]
            recent_bets = await db.get_user_bets(message.from_user.id, 10)
            lose_streak = sum(1 for b in recent_bets if b.get("result") == "LOSE")
            bet_amount = bet_amounts[min(lose_streak, len(bet_amounts)-1)]
        else:
            bet_amount = float(bet_params)
        
        if not LAST_PROCESSED_ISSUE:
            await message.reply(f"{Emoji.CROSS} ဒေတာမရသေးပါ။"); return
        
        next_issue = str(int(LAST_PROCESSED_ISSUE) + 1)
        history_docs = await db.get_history(5000)
        user_session = await db.get_user_session(message.from_user.id)
        user_ai_mode = user_session.get("ai_mode", DEFAULT_AI_MODE)
        predicted_size, _, _, _ = get_prediction(history_docs, user_ai_mode)
        
        result = await db.place_bet(message.from_user.id, next_issue, bet_amount, predicted_size, user_ai_mode)
        if result["success"]:
            ai_name = AI_MODES.get(user_ai_mode, {}).get("name", "AI")
            await message.reply(
                f"{Emoji.ORDER} <b>Order Placed!</b>\n"
                f"{Emoji.GAME_ICON} WINGO_30S: <code>{next_issue}</code>\n"
                f"{Emoji.CHART_ICON} {predicted_size} | {bet_amount:,.0f} Ks\n"
                f"{Emoji.BRAIN} {ai_name}"
            )
        else:
            await message.reply(result["message"])
    except ValueError:
        await message.reply(f"{Emoji.CROSS} ဂဏန်းများသာ ထည့်ပါ။")

@auth_router.message(both_commands("top"))
@auth_router.message(Command("top"))
async def show_leaderboard(message: types.Message):
    leaderboard = await db.get_leaderboard(10)
    if not leaderboard:
        await message.reply(f"{Emoji.INFO} ဒေတာမရှိသေးပါ။"); return
    
    top_text = f"{Emoji.CROWN} <b>TOP 10</b>\n━━━━━━━━━━━━━━━━━━\n"
    for i, user in enumerate(leaderboard, 1):
        medal = Emoji.GOLD if i == 1 else Emoji.SILVER if i == 2 else Emoji.BRONZE if i == 3 else f"{i}."
        wr = (user['total_wins'] / user['total_bets'] * 100) if user['total_bets'] > 0 else 0
        top_text += f"{medal} <code>{user['user_id']}</code>\n   {Emoji.MONEY} {user['balance']:,.0f} | WR {wr:.1f}%\n"
    await message.reply(top_text)

@auth_router.message(both_commands("mybets"))
@auth_router.message(Command("mybets"))
async def show_my_bets(message: types.Message):
    bets = await db.get_user_bets(message.from_user.id, 10)
    if not bets:
        await message.reply(f"{Emoji.INFO} မှတ်တမ်းမရှိသေးပါ။"); return
    
    text = f"{Emoji.GAME} <b>မှတ်တမ်း</b>\n━━━━━━━━━━━━━━━━━━\n"
    for bet in bets:
        if bet["result"] is None: status = "⏳"
        elif bet["result"] == "WIN": status = f"{Emoji.CHECK} +{bet['profit']:,.0f}"
        else: status = f"{Emoji.CROSS} -{bet['bet_amount']:,.0f}"
        text += f"{bet['issue_number']}: {bet['bet_amount']:,.0f}K {bet['predicted_size']} → {status}\n"
    await message.reply(text)

# ==========================================
# OWNER ONLY COMMANDS
# ==========================================
@owner_router.message(Command("addsudo"))
@owner_router.message(lambda m: m.text and m.text.lower() == '.addsudo')
async def add_sudo(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/addsudo [user_id]</code>"); return
        target_id = int(parts[1])
        await db.add_sudo(target_id, message.from_user.id)
        global SUDO_USERS
        SUDO_USERS = await db.get_sudo_users()
        await message.reply(f"{Emoji.CHECK} Sudo Added: <code>{target_id}</code>")
    except ValueError:
        await message.reply(f"{Emoji.CROSS} User ID ဂဏန်းသာ")

@owner_router.message(Command("delsudo"))
@owner_router.message(lambda m: m.text and m.text.lower() == '.delsudo')
async def del_sudo(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply(f"{Emoji.INFO} <code>/delsudo [user_id]</code>"); return
        target_id = int(parts[1])
        await db.remove_sudo(target_id)
        global SUDO_USERS
        SUDO_USERS = await db.get_sudo_users()
        await message.reply(f"{Emoji.CHECK} Sudo Removed: <code>{target_id}</code>")
    except ValueError:
        await message.reply(f"{Emoji.CROSS} User ID ဂဏန်းသာ")

@owner_router.message(Command("sudolist"))
@owner_router.message(lambda m: m.text and m.text.lower() == '.sudolist')
async def list_sudo(message: types.Message):
    global SUDO_USERS
    if not SUDO_USERS:
        await message.reply("No sudo users."); return
    text = f"{Emoji.SHIELD} <b>SUDO USERS</b>\n" + "\n".join(f"• <code>{uid}</code>" for uid in SUDO_USERS)
    await message.reply(text)

@owner_router.message(Command("broadcast"))
@owner_router.message(lambda m: m.text and m.text.lower() == '.broadcast')
async def broadcast(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(f"{Emoji.INFO} <code>/broadcast [msg]</code>"); return
    all_users = await db.users.find().to_list(length=None)
    success = 0
    for u in all_users:
        try:
            await bot.send_message(chat_id=u["user_id"], text=f"📢 {parts[1]}")
            success += 1
        except: pass
        await asyncio.sleep(0.05)
    await message.reply(f"✅ Sent to {success}/{len(all_users)}")

@owner_router.message(Command("setdefaultai"))
@owner_router.message(lambda m: m.text and m.text.lower() == '.setdefaultai')
async def set_default_ai(message: types.Message):
    global DEFAULT_AI_MODE
    parts = message.text.split()
    if len(parts) < 2:
        modes = ", ".join(AI_MODES.keys())
        await message.reply(f"{Emoji.INFO} <code>/setdefaultai [mode]</code>\nModes: {modes}"); return
    mode = parts[1].lower()
    if mode in AI_MODES:
        DEFAULT_AI_MODE = mode
        await db.set_setting("default_ai_mode", mode)
        await message.reply(f"{Emoji.CHECK} Default AI: {AI_MODES[mode]['name']}")
    else:
        await message.reply(f"{Emoji.CROSS} Invalid mode!")

async def init_system():
    global DEFAULT_AI_MODE, SUDO_USERS
    await db.init_indexes()
    SUDO_USERS = await db.get_sudo_users()
    DEFAULT_AI_MODE = await db.get_setting("default_ai_mode", "ensemble")
    print(f"{Emoji.CHECK} System Initialized | Default AI: {DEFAULT_AI_MODE} | Sudo: {len(SUDO_USERS)}")

async def main():
    await init_system()
    print(f"\n{Emoji.SPARKLES} WIN GO AI Bot v4.0 - Multi-User AI System {Emoji.SPARKLES}")
    print(f"{Emoji.CROWN} Owner: {OWNER_ID}")
    print(f"{Emoji.BRAIN} AI Modes: 16 | {Emoji.MONEY_ICON} Profit Target | {Emoji.SHIELD} Sudo System\n")
    
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
