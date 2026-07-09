## 📁 `PSP-AUTO-BETTING-V5.py` 
# PSP-AUTO-BETTING-V5.py
"""
PSP AUTO BETTING V5
- API History + AI Prediction (16 Modes)
- Playwright Browser Automation for Real Betting
- Virtual Mode (Play Money)
- Session Save & Reuse
- Premium Emojis for Messages
- Standard Emojis for Keyboards
"""

import asyncio
import os
import html
import random
import time
import math
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from playwright.async_api import async_playwright

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID", "0")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==========================================================
# PREMIUM EMOJI CONSTANTS
# ==========================================================
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
    """Premium Emojis for Messages | Standard for Keyboards"""
    # Premium (Message Text Only)
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

    # Standard (Keyboard & System)
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
    TARGET = "🎯"


# ==========================================================
# API CONFIGURATION
# ==========================================================
BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

# ==========================================================
# FSM States
# ==========================================================
class LoginForm(StatesGroup):
    enter_phone = State()
    enter_password = State()
    main_menu = State()
    set_bet_size = State()
    set_target = State()

# ==========================================================
# Global Settings
# ==========================================================
is_bot_running = False
AUTHORIZED_USERS = set()
USER_SESSIONS = {}

DEFAULT_BET_SEQUENCE = [100, 300, 900, 2700, 8100, 24300]
DEFAULT_AI_MODE = "pattern"
DEFAULT_PROFIT_TARGET = 30000

VIRTUAL_BALANCES = {}
DEFAULT_PATTERN = ["BIG", "SMALL", "BIG", "BIG"]

# ==========================================================
# Virtual Balance System
# ==========================================================
def get_virtual_balance(user_id: int) -> dict:
    if user_id not in VIRTUAL_BALANCES:
        VIRTUAL_BALANCES[user_id] = {
            "balance": 100000.0,
            "session_profit": 0.0,
            "total_wins": 0,
            "total_losses": 0,
            "best_streak": 0,
            "current_streak": 0,
        }
    return VIRTUAL_BALANCES[user_id]


def update_virtual_balance(user_id: int, amount: float, operation: str = "add") -> dict:
    vbal = get_virtual_balance(user_id)
    if operation == "add":
        vbal["balance"] += amount
    elif operation == "subtract":
        vbal["balance"] -= amount
    elif operation == "set":
        vbal["balance"] = amount
    return vbal

# ==========================================================
# Keyboards (Standard Emoji Only)
# ==========================================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Login")],
            [KeyboardButton(text="Status")]
        ],
        resize_keyboard=True
    )


def get_logged_in_keyboard(is_real_logged: bool = False):
    buttons = [
        [KeyboardButton(text="Info"), KeyboardButton(text="Balance")],
        [KeyboardButton(text="Bet Size"), KeyboardButton(text="AI Mode")],
        [KeyboardButton(text="Set Target"), KeyboardButton(text="Status")],
    ]
    
    if is_real_logged:
        buttons.append([KeyboardButton(text="Real Auto-Bet"), KeyboardButton(text="Stop")])
        buttons.append([KeyboardButton(text="Virtual Auto-Bet")])
    else:
        buttons.append([KeyboardButton(text="Virtual Auto-Bet"), KeyboardButton(text="Stop")])
    
    buttons.append([KeyboardButton(text="Logout")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_ai_mode_keyboard():
    builder = InlineKeyboardBuilder()
    
    ai_modes = [
        ("pattern", "Pattern AI"),
        ("martingale", "Martingale AI"),
        ("anti_martingale", "Anti-Martingale"),
        ("trend_following", "Trend Following"),
        ("fibonacci", "Fibonacci AI"),
        ("golden_ratio", "Golden Ratio"),
        ("momentum", "Momentum AI"),
        ("monte_carlo", "Monte Carlo"),
        ("neural_pattern", "Neural Pattern"),
        ("quick_reversal", "Quick Reversal"),
        ("wave_analysis", "Wave Analysis"),
        ("chaos_theory", "Chaos Theory"),
        ("ensemble", "Ensemble AI"),
        ("bayesian", "Bayesian AI"),
        ("markov_chain", "Markov Chain"),
        ("ml_style", "ML Style AI"),
    ]
    
    for key, name in ai_modes:
        builder.row(InlineKeyboardButton(text=name, callback_data=f"ai_{key}"))
    
    builder.row(InlineKeyboardButton(text="Close", callback_data="ai_close"))
    return builder.as_markup()

# ==========================================================
# Command Handlers
# ==========================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    if str(message.from_user.id) != str(OWNER_ID) and message.from_user.id not in AUTHORIZED_USERS:
        await message.answer(
            f"{Emoji.LOCK} <b>Access Denied!</b>\n\n"
            "This bot is for authorized users only.",
            reply_markup=get_main_keyboard()
        )
        return
    
    vbal = get_virtual_balance(message.from_user.id)
    
    await message.answer(
        f"{Emoji.SPARKLES} <b>PSP AUTO BETTING V5</b>\n"
        f"{Emoji.BRAIN} API Prediction + Browser Betting (16 AI Modes)\n\n"
        f"{Emoji.MONEY_ICON} Virtual Balance: <b>{vbal['balance']:,.0f} Ks</b>\n\n"
        f"{Emoji.KEY} <b>Login</b> for Real Mode\n"
        f"{Emoji.GAME} <b>Virtual Mode</b> - No login needed",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    global is_bot_running
    is_bot_running = False
    await message.answer(f"{Emoji.CHECK} Auto-Bet stop signal sent.")


@dp.message(Command("adduser"))
async def cmd_add_user(message: types.Message):
    if str(message.from_user.id) != str(OWNER_ID):
        return await message.answer(f"{Emoji.CROSS} Owner only!")
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return await message.answer("<code>/adduser [user_id]</code>")
        user_id = int(parts[1])
        AUTHORIZED_USERS.add(user_id)
        await message.answer(f"{Emoji.CHECK} User <code>{user_id}</code> added.")
    except:
        await message.answer(f"{Emoji.CROSS} Invalid user ID.")


@dp.message(Command("deluser"))
async def cmd_del_user(message: types.Message):
    if str(message.from_user.id) != str(OWNER_ID):
        return await message.answer(f"{Emoji.CROSS} Owner only!")
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return await message.answer("<code>/deluser [user_id]</code>")
        user_id = int(parts[1])
        AUTHORIZED_USERS.discard(user_id)
        await message.answer(f"{Emoji.CHECK} User <code>{user_id}</code> removed.")
    except:
        await message.answer(f"{Emoji.CROSS} Invalid user ID.")

# ==========================================================
# API Functions
# ==========================================================
async def fetch_api(session, url, json_data, retries=2):
    for _ in range(retries):
        try:
            async with session.post(url, headers=BASE_HEADERS, json=json_data, timeout=5.0) as resp:
                if resp.status == 200:
                    return await resp.json()
        except:
            await asyncio.sleep(0.3)
    return None


async def get_game_history(session) -> list:
    json_data = {
        'pageSize': 20,
        'pageNo': 1,
        'typeId': 30,
        'language': 7,
        'random': '9ef85244056948ba8dcae7aee7758bf4',
        'signature': '2EDB8C2B5264F62EC53116916A9EC05C',
        'timestamp': int(time.time()),
    }
    
    data = await fetch_api(
        session,
        'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList',
        json_data
    )
    
    if data and data.get('code') == 0:
        records = data.get('data', {}).get('list', [])
        return [
            {
                'issue_number': str(r['issueNumber']),
                'number': int(r['number']),
                'size': 'BIG' if int(r['number']) >= 5 else 'SMALL'
            }
            for r in records
        ]
    return []

# ==========================================================
# AI Prediction Functions (16 Modes)
# ==========================================================
def predict_next(history: list, ai_mode: str = "pattern") -> str:
    if len(history) < 5:
        return 'BIG'
    
    recent = [h['size'] for h in history[:20]]
    
    ai_functions = {
        "pattern": predict_pattern,
        "martingale": predict_martingale,
        "anti_martingale": predict_anti_martingale,
        "trend_following": predict_trend,
        "fibonacci": predict_fibonacci,
        "golden_ratio": predict_golden_ratio,
        "momentum": predict_momentum,
        "monte_carlo": predict_monte_carlo,
        "neural_pattern": predict_neural_pattern,
        "quick_reversal": predict_quick_reversal,
        "wave_analysis": predict_wave_analysis,
        "chaos_theory": predict_chaos_theory,
        "ensemble": predict_ensemble,
        "bayesian": predict_bayesian,
        "markov_chain": predict_markov_chain,
        "ml_style": predict_ml_style,
    }
    
    func = ai_functions.get(ai_mode, predict_pattern)
    return func(recent)


def predict_pattern(recent: list) -> str:
    if len(recent) >= 4 and recent[:4] == ['BIG', 'BIG', 'SMALL', 'SMALL']:
        return 'BIG'
    if len(recent) >= 4 and recent[:4] == ['SMALL', 'SMALL', 'BIG', 'BIG']:
        return 'SMALL'
    if len(recent) >= 4 and recent[:4] == ['BIG', 'SMALL', 'BIG', 'SMALL']:
        return 'BIG'
    if len(recent) >= 4 and recent[:4] == ['SMALL', 'BIG', 'SMALL', 'BIG']:
        return 'SMALL'
    if len(recent) >= 3 and recent[:3] == ['BIG', 'BIG', 'BIG']:
        return 'BIG'
    if len(recent) >= 3 and recent[:3] == ['SMALL', 'SMALL', 'SMALL']:
        return 'SMALL'
    if len(recent) >= 3 and recent[:3] == ['BIG', 'BIG', 'SMALL']:
        return 'BIG'
    if len(recent) >= 3 and recent[:3] == ['SMALL', 'SMALL', 'BIG']:
        return 'SMALL'
    
    last_5 = recent[:5]
    big_count = last_5.count('BIG')
    small_count = last_5.count('SMALL')
    if big_count > small_count:
        return 'BIG'
    elif small_count > big_count:
        return 'SMALL'
    return 'BIG' if recent[0] == 'SMALL' else 'SMALL'


def predict_martingale(recent: list) -> str:
    last_10 = recent[:10]
    big_count = last_10.count('BIG')
    small_count = last_10.count('SMALL')
    return 'SMALL' if big_count > small_count else 'BIG'


def predict_anti_martingale(recent: list) -> str:
    last_3 = recent[:3]
    if last_3.count('BIG') >= 2:
        return 'BIG'
    elif last_3.count('SMALL') >= 2:
        return 'SMALL'
    return recent[0]


def predict_trend(recent: list) -> str:
    last_8 = recent[:8]
    last_4 = recent[:4]
    big_8 = last_8.count('BIG') / 8
    big_4 = last_4.count('BIG') / 4
    trend = big_4 - big_8
    return 'BIG' if trend > 0 else 'SMALL'


def predict_fibonacci(recent: list) -> str:
    fib_levels = [3, 5, 8, 13, 21]
    results = []
    for level in fib_levels:
        if len(recent) >= level:
            segment = recent[:level]
            big_pct = segment.count('BIG') / level
            if 0.38 <= big_pct <= 0.62:
                results.append('BIG' if big_pct < 0.5 else 'SMALL')
            elif big_pct > 0.618:
                results.append('SMALL')
            else:
                results.append('BIG')
    if results:
        return max(set(results), key=results.count)
    return recent[0]


def predict_golden_ratio(recent: list) -> str:
    lookback = min(21, len(recent))
    segment = recent[:lookback]
    big_ratio = segment.count('BIG') / lookback
    if big_ratio > 0.618:
        return 'SMALL'
    elif big_ratio < 0.382:
        return 'BIG'
    return recent[0]


def predict_momentum(recent: list) -> str:
    weights = [5, 4, 3, 2, 1]
    score = 0
    for i, r in enumerate(recent[:5]):
        if r == 'BIG':
            score += weights[i]
        else:
            score -= weights[i]
    if score > 3:
        return 'BIG'
    elif score < -3:
        return 'SMALL'
    return recent[0]


def predict_monte_carlo(recent: list) -> str:
    big_prob = recent.count('BIG') / len(recent)
    big_wins = sum(1 for _ in range(500) if random.random() < big_prob)
    return 'BIG' if big_wins > 250 else 'SMALL'


def predict_neural_pattern(recent: list) -> str:
    if len(recent) < 6:
        return recent[0]
    current_window = recent[:3]
    current_ratio = current_window.count('BIG') / 3
    similar_big = similar_small = 0
    for i in range(3, len(recent) - 1):
        window = recent[i:i+3]
        ratio = window.count('BIG') / 3
        if abs(ratio - current_ratio) < 0.1:
            if i + 3 < len(recent) and recent[i+3] == 'BIG':
                similar_big += 1
            else:
                similar_small += 1
    if similar_big + similar_small > 0:
        return 'BIG' if similar_big > similar_small else 'SMALL'
    return recent[0]


def predict_quick_reversal(recent: list) -> str:
    if len(recent) < 4:
        return recent[0]
    last_4 = recent[:4]
    alts = sum(1 for i in range(1, len(last_4)) if last_4[i] != last_4[i-1])
    alt_rate = alts / (len(last_4) - 1)
    if alt_rate > 0.75:
        return 'SMALL' if last_4[0] == 'BIG' else 'BIG'
    return last_4[0]


def predict_wave_analysis(recent: list) -> str:
    if len(recent) < 6:
        return recent[0]
    waves = []
    current = recent[0]
    count = 1
    for r in recent[1:10]:
        if r == current:
            count += 1
        else:
            waves.append((current, count))
            current = r
            count = 1
    waves.append((current, count))
    if len(waves) >= 3:
        last_wave = waves[-1]
        if last_wave[1] >= 3:
            return last_wave[0]
        elif last_wave[1] <= 2:
            return 'SMALL' if last_wave[0] == 'BIG' else 'BIG'
    return recent[0]


def predict_chaos_theory(recent: list) -> str:
    if len(recent) < 8:
        return recent[0]
    def entropy(seg):
        total = len(seg)
        big_p = seg.count('BIG') / total
        small_p = seg.count('SMALL') / total
        e = 0
        for p in [big_p, small_p]:
            if p > 0:
                e -= p * math.log2(p)
        return e
    e3 = entropy(recent[:3])
    e5 = entropy(recent[:5])
    if e3 > e5:
        return 'SMALL' if recent[0] == 'BIG' else 'BIG'
    elif e3 < e5:
        return 'BIG' if recent[:5].count('BIG') > recent[:5].count('SMALL') else 'SMALL'
    return recent[0]


def predict_ensemble(recent: list) -> str:
    predictions = [
        predict_pattern(recent), predict_martingale(recent),
        predict_anti_martingale(recent), predict_trend(recent),
        predict_fibonacci(recent), predict_golden_ratio(recent),
        predict_momentum(recent), predict_quick_reversal(recent),
    ]
    big_votes = predictions.count('BIG')
    small_votes = predictions.count('SMALL')
    return 'BIG' if big_votes >= small_votes else 'SMALL'


def predict_bayesian(recent: list) -> str:
    if len(recent) < 8:
        return recent[0]
    big_after_big = small_after_small = 0
    big_total = small_total = 0
    for i in range(1, min(15, len(recent))):
        if recent[i-1] == 'BIG':
            big_total += 1
            if recent[i] == 'BIG':
                big_after_big += 1
        else:
            small_total += 1
            if recent[i] == 'SMALL':
                small_after_small += 1
    p_bb = big_after_big / big_total if big_total > 0 else 0.5
    p_ss = small_after_small / small_total if small_total > 0 else 0.5
    if recent[0] == 'BIG':
        return 'BIG' if p_bb > 0.5 else 'SMALL'
    return 'SMALL' if p_ss > 0.5 else 'BIG'


def predict_markov_chain(recent: list) -> str:
    if len(recent) < 6:
        return recent[0]
    transitions = {}
    for i in range(2, len(recent)):
        state = (recent[i-2], recent[i-1])
        next_val = recent[i]
        if state not in transitions:
            transitions[state] = {"BIG": 0, "SMALL": 0}
        transitions[state][next_val] += 1
    current_state = (recent[1], recent[0])
    if current_state in transitions:
        counts = transitions[current_state]
        total = counts["BIG"] + counts["SMALL"]
        if total > 0:
            return 'BIG' if counts["BIG"] / total > 0.5 else 'SMALL'
    return recent[0]


def predict_ml_style(recent: list) -> str:
    if len(recent) < 10:
        return recent[0]
    last_3 = recent[:3].count('BIG') / 3
    last_5 = recent[:5].count('BIG') / 5
    last_8 = recent[:8].count('BIG') / 8
    trend = recent[:4].count('BIG') / 4 - last_8
    score = (last_3 - 0.5) * 0.4 + (last_5 - 0.5) * 0.3 + (last_8 - 0.5) * 0.2 + trend * 0.1
    return 'BIG' if score > 0 else 'SMALL'

# ==========================================================
# Login Flow
# ==========================================================
@dp.message(F.text == "Login")
async def login_start(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.enter_phone)
    await message.answer(
        f"{Emoji.INFO} <b>Enter your phone number:</b>\n"
        "Example: <code>959675323878</code>",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(LoginForm.enter_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.isdigit():
        return await message.answer(f"{Emoji.CROSS} Numbers only!")
    await state.update_data(phone=phone)
    await state.set_state(LoginForm.enter_password)
    await message.answer(f"{Emoji.KEY} <b>Enter your password:</b>")


@dp.message(LoginForm.enter_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    username = data.get('phone')
    
    loading_msg = await message.answer(f"{Emoji.HOURGLASS} <b>Logging in... Please wait...</b>")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = await browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
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
                    element.blur();
                    return true;
                }
                let phone = document.querySelector('input[name="userNumber"]');
                fillVueInput(phone, user);
                let pass = document.querySelector('input[placeholder="Password"]') || 
                           document.querySelector('input[placeholder="စကားဝှက်"]') || 
                           document.querySelector('.passwordInput__container-input input');
                fillVueInput(pass, pwd);
            }
            """
            await page.evaluate(js_code, [username, password])
            await page.wait_for_timeout(1000)
            
            await page.evaluate("() => { let btn = document.querySelector('button.active'); if (btn) btn.click(); }")
            await page.wait_for_timeout(5000)
            
            if "login" not in page.url.lower():
                session_file = f"session_{message.from_user.id}.json"
                await context.storage_state(path=session_file)
                USER_SESSIONS[message.from_user.id] = session_file
                
                try:
                    await page.goto("https://www.777bigwingame.app/#/main", wait_until="networkidle")
                    await page.wait_for_timeout(3000)
                except:
                    pass
                
                nickname, user_id, balance_text = "Unknown", "N/A", "0.00 Ks"
                login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                try:
                    nick_el = page.locator('.userInfo__container-content-nickname h3').first
                    if await nick_el.is_visible(timeout=3000):
                        nickname = await nick_el.inner_text()
                    uid_el = page.locator('.userInfo__container-content-uid span:nth-child(3)').first
                    if await uid_el.is_visible():
                        user_id = await uid_el.inner_text()
                    bal_el = page.locator('.balance_info p.totalSavings__container-header__subtitle span').first
                    if await bal_el.is_visible():
                        balance_text = await bal_el.inner_text()
                except:
                    pass
                
                await state.update_data(
                    is_logged_in=True,
                    is_real_logged=True,
                    username=username,
                    user_id=user_id.strip(),
                    nickname=nickname.strip(),
                    balance=balance_text.strip(),
                    login_time=login_time,
                    bet_sequence=DEFAULT_BET_SEQUENCE.copy(),
                    ai_mode=DEFAULT_AI_MODE,
                    profit_target=DEFAULT_PROFIT_TARGET,
                )
                
                await state.set_state(LoginForm.main_menu)
                await loading_msg.delete()
                await message.answer(
                    f"{Emoji.CHECK} <b>LOGIN SUCCESSFUL!</b>\n\n"
                    f"{Emoji.USER} Nickname: <b>{nickname}</b>\n"
                    f"{Emoji.MONEY_ICON} Real Balance: <b>{balance_text}</b>\n\n"
                    f"{Emoji.BRAIN} 16 AI Modes + Browser Betting Ready!",
                    reply_markup=get_logged_in_keyboard(is_real_logged=True)
                )
            else:
                await loading_msg.delete()
                await message.answer(
                    f"{Emoji.CROSS} <b>Login failed!</b>",
                    reply_markup=get_main_keyboard()
                )
                await state.clear()
        except Exception as e:
            await loading_msg.delete()
            await message.answer(
                f"{Emoji.WARNING} Error: {html.escape(str(e))}",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
        finally:
            await browser.close()

# ==========================================================
# Main Menu Handlers
# ==========================================================
@dp.message(LoginForm.main_menu, F.text == "Info")
async def show_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    is_real = data.get('is_real_logged', False)
    vbal = get_virtual_balance(message.from_user.id)
    bet_seq = data.get('bet_sequence', DEFAULT_BET_SEQUENCE)
    
    info_text = f"{Emoji.INFO} <b>=== User Info ===</b>\n\n"
    
    if is_real:
        info_text += (
            f"{Emoji.SHIELD} <b>[Real Mode]</b>\n"
            f"{Emoji.USER} {data.get('nickname', 'Unknown')}\n"
            f"ID: {data.get('user_id', 'N/A')}\n"
            f"{Emoji.MONEY_ICON} Real Balance: {data.get('balance', '0.00')}\n\n"
        )
    
    info_text += (
        f"{Emoji.GAME} <b>[Virtual Mode]</b>\n"
        f"{Emoji.MONEY_ICON} Balance: {vbal['balance']:,.0f} Ks\n"
        f"{Emoji.CHART_UP} Session Profit: {vbal['session_profit']:,.0f} Ks\n"
        f"{Emoji.CHECK} Wins: {vbal['total_wins']} | {Emoji.CROSS} Losses: {vbal['total_losses']}\n\n"
        f"{Emoji.MONEY_BAG} Bet Size: {' -> '.join([str(b) for b in bet_seq])}\n"
        f"{Emoji.BRAIN} AI Mode: {data.get('ai_mode', DEFAULT_AI_MODE)}\n"
        f"{Emoji.TARGET} Target: {data.get('profit_target', DEFAULT_PROFIT_TARGET):,} Ks\n"
    )
    
    await message.answer(info_text, reply_markup=get_logged_in_keyboard(is_real))


@dp.message(LoginForm.main_menu, F.text == "Balance")
async def check_balance(message: types.Message, state: FSMContext):
    data = await state.get_data()
    is_real = data.get('is_real_logged', False)
    vbal = get_virtual_balance(message.from_user.id)
    
    if is_real:
        session_file = USER_SESSIONS.get(message.from_user.id, f"session_{message.from_user.id}.json")
        if os.path.exists(session_file):
            msg = await message.answer(f"{Emoji.HOURGLASS} Checking live balance...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
                context = await browser.new_context(storage_state=session_file, viewport={'width': 390, 'height': 844}, is_mobile=True)
                page = await context.new_page()
                try:
                    await page.goto("https://www.777bigwingame.app/#/main", wait_until="networkidle")
                    await page.wait_for_timeout(3000)
                    bal_el = page.locator('.balance_info p.totalSavings__container-header__subtitle span').first
                    if await bal_el.is_visible(timeout=3000):
                        live_bal = await bal_el.inner_text()
                        await state.update_data(balance=live_bal)
                        await msg.edit_text(
                            f"{Emoji.MONEY_ICON} <b>Real Balance:</b> {live_bal}\n"
                            f"{Emoji.GAME} <b>Virtual Balance:</b> {vbal['balance']:,.0f} Ks\n"
                            f"{Emoji.CHART_UP} Virtual Profit: {vbal['session_profit']:,.0f} Ks"
                        )
                    else:
                        await msg.edit_text(f"{Emoji.WARNING} Balance not found.")
                finally:
                    await browser.close()
        else:
            await message.answer(
                f"{Emoji.CROSS} Real: No session.\n"
                f"{Emoji.MONEY_ICON} Virtual Balance: {vbal['balance']:,.0f} Ks"
            )
    else:
        await message.answer(
            f"{Emoji.MONEY_ICON} <b>Virtual Balance:</b> {vbal['balance']:,.0f} Ks\n"
            f"{Emoji.CHART_UP} Session Profit: {vbal['session_profit']:,.0f} Ks\n"
            f"{Emoji.CHECK} Wins: {vbal['total_wins']} | {Emoji.CROSS} Losses: {vbal['total_losses']}"
        )


@dp.message(LoginForm.main_menu, F.text == "Bet Size")
async def set_bet_size_start(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.set_bet_size)
    data = await state.get_data()
    current_seq = data.get('bet_sequence', DEFAULT_BET_SEQUENCE)
    current_str = " -> ".join([str(b) for b in current_seq])
    
    await message.answer(
        f"{Emoji.MONEY_BAG} <b>Set Bet Size</b>\n\n"
        f"Current: <b>{current_str}</b>\n\n"
        f"Enter amounts separated by '-':\n"
        f"<code>100-300-900-2700-8100-24300</code>",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(LoginForm.set_bet_size)
async def set_bet_size_save(message: types.Message, state: FSMContext):
    try:
        amounts = [int(x.strip()) for x in message.text.strip().split('-')]
        if len(amounts) < 2:
            return await message.answer(f"{Emoji.CROSS} Minimum 2 steps required.")
        await state.update_data(bet_sequence=amounts)
        await state.set_state(LoginForm.main_menu)
        data = await state.get_data()
        is_real = data.get('is_real_logged', False)
        await message.answer(
            f"{Emoji.CHECK} Bet Size: {' -> '.join([str(a) for a in amounts])}",
            reply_markup=get_logged_in_keyboard(is_real)
        )
    except:
        await message.answer(f"{Emoji.CROSS} Invalid format. Use numbers separated by '-'.")


@dp.message(LoginForm.main_menu, F.text == "AI Mode")
async def show_ai_modes(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_ai = data.get('ai_mode', DEFAULT_AI_MODE)
    await message.answer(
        f"{Emoji.BRAIN} <b>Select AI Mode (16 Modes)</b>\n"
        f"Current: <b>{current_ai}</b>",
        reply_markup=get_ai_mode_keyboard()
    )


@dp.callback_query(lambda c: c.data and c.data.startswith("ai_") and c.data != "ai_close")
async def select_ai_mode(callback: types.CallbackQuery, state: FSMContext):
    ai_mode = callback.data.replace("ai_", "")
    ai_names = {
        "pattern": "Pattern AI", "martingale": "Martingale AI",
        "anti_martingale": "Anti-Martingale", "trend_following": "Trend Following",
        "fibonacci": "Fibonacci AI", "golden_ratio": "Golden Ratio",
        "momentum": "Momentum AI", "monte_carlo": "Monte Carlo",
        "neural_pattern": "Neural Pattern", "quick_reversal": "Quick Reversal",
        "wave_analysis": "Wave Analysis", "chaos_theory": "Chaos Theory",
        "ensemble": "Ensemble AI", "bayesian": "Bayesian AI",
        "markov_chain": "Markov Chain", "ml_style": "ML Style AI",
    }
    await state.update_data(ai_mode=ai_mode)
    await callback.message.edit_text(f"{Emoji.CHECK} AI Mode: <b>{ai_names.get(ai_mode, ai_mode)}</b>")
    await callback.answer(f"Selected: {ai_names.get(ai_mode, ai_mode)}")


@dp.callback_query(lambda c: c.data == "ai_close")
async def close_ai_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@dp.message(LoginForm.main_menu, F.text == "Set Target")
async def set_target_start(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.set_target)
    data = await state.get_data()
    current_target = data.get('profit_target', DEFAULT_PROFIT_TARGET)
    await message.answer(
        f"{Emoji.TARGET} <b>Set Profit Target</b>\n"
        f"Current: <b>{current_target:,} Ks</b>\n\n"
        f"Enter amount:\n<code>30000</code>",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(LoginForm.set_target)
async def set_target_save(message: types.Message, state: FSMContext):
    try:
        target = int(message.text.strip())
        if target <= 0:
            return await message.answer(f"{Emoji.CROSS} Must be greater than 0.")
        await state.update_data(profit_target=target)
        await state.set_state(LoginForm.main_menu)
        data = await state.get_data()
        is_real = data.get('is_real_logged', False)
        await message.answer(
            f"{Emoji.CHECK} Target: <b>{target:,} Ks</b>",
            reply_markup=get_logged_in_keyboard(is_real)
        )
    except:
        await message.answer(f"{Emoji.CROSS} Numbers only.")


@dp.message(LoginForm.main_menu, F.text == "Status")
async def show_status(message: types.Message, state: FSMContext):
    global is_bot_running
    data = await state.get_data()
    is_real = data.get('is_real_logged', False)
    vbal = get_virtual_balance(message.from_user.id)
    
    status_text = (
        f"{Emoji.BAR_CHART} <b>=== System Status ===</b>\n\n"
        f"{Emoji.ROBOT} Auto-Bet: {'RUNNING' if is_bot_running else 'STOPPED'}\n"
        f"{Emoji.SHIELD} Real Mode: {'Logged In' if is_real else 'Not Logged'}\n"
        f"{Emoji.MONEY_ICON} Virtual Balance: {vbal['balance']:,.0f} Ks\n"
        f"{Emoji.CHART_UP} Virtual Profit: {vbal['session_profit']:,.0f} Ks\n"
        f"{Emoji.BRAIN} AI: {data.get('ai_mode', DEFAULT_AI_MODE)}\n"
        f"{Emoji.TARGET} Target: {data.get('profit_target', DEFAULT_PROFIT_TARGET):,} Ks\n"
        f"{Emoji.MONEY_BAG} Bet Size: {' -> '.join([str(b) for b in data.get('bet_sequence', DEFAULT_BET_SEQUENCE)])}\n"
    )
    await message.answer(status_text, reply_markup=get_logged_in_keyboard(is_real))


@dp.message(LoginForm.main_menu, F.text == "Logout")
async def logout(message: types.Message, state: FSMContext):
    await state.clear()
    session_file = f"session_{message.from_user.id}.json"
    if os.path.exists(session_file):
        os.remove(session_file)
    USER_SESSIONS.pop(message.from_user.id, None)
    await message.answer(
        f"{Emoji.CHECK} Logged out successfully.",
        reply_markup=get_main_keyboard()
    )


# ==========================================================
# VIRTUAL AUTO-BET MODE
# ==========================================================
@dp.message(F.text == "Virtual Auto-Bet")
async def start_virtual_autobet(message: types.Message, state: FSMContext):
    global is_bot_running
    
    if is_bot_running:
        return await message.answer(f"{Emoji.WARNING} Auto-Bet is already running!")
    
    current_state = await state.get_state()
    if current_state != LoginForm.main_menu:
        await state.set_state(LoginForm.main_menu)
    
    data = await state.get_data()
    bet_sequence = data.get('bet_sequence', DEFAULT_BET_SEQUENCE)
    profit_target = data.get('profit_target', DEFAULT_PROFIT_TARGET)
    ai_mode = data.get('ai_mode', DEFAULT_AI_MODE)
    
    is_bot_running = True
    status_msg = await message.answer(
        f"{Emoji.GAME} <b>Virtual Auto-Bet Started!</b>\n"
        f"{Emoji.BRAIN} AI Mode: {ai_mode}"
    )
    
    asyncio.create_task(
        run_virtual_betting_loop(message, status_msg, bet_sequence, profit_target, ai_mode)
    )


async def run_virtual_betting_loop(message, status_msg, bet_sequence, profit_target, ai_mode):
    global is_bot_running
    
    vbal = get_virtual_balance(message.from_user.id)
    current_step = 0
    
    # Get API history for AI prediction
    async with aiohttp.ClientSession() as api_session:
        while is_bot_running:
            current_amount = bet_sequence[current_step]
            
            # Get prediction from API
            history = await get_game_history(api_session)
            if history and len(history) >= 5:
                prediction = predict_next(history, ai_mode)
            else:
                prediction = DEFAULT_PATTERN[current_step % len(DEFAULT_PATTERN)]
            
            display_type = "BIG" if prediction == "BIG" else "SMALL"
            
            if vbal["balance"] < current_amount:
                await message.answer(
                    f"{Emoji.CROSS} <b>Insufficient Balance!</b>\n"
                    f"{Emoji.MONEY_ICON} Balance: {vbal['balance']:,.0f} Ks\n"
                    f"{Emoji.OFFLINE} Auto-bet stopped."
                )
                is_bot_running = False
                break
            
            vbal["balance"] -= current_amount
            
            step_text = f"(Step {current_step + 1}/{len(bet_sequence)})"
            await message.answer(
                f"{Emoji.ORDER} <b>Virtual Bet Placed!</b>\n"
                f"{Emoji.GAME_ICON} WINGO 30S: {display_type}\n"
                f"{Emoji.CHART_ICON} Amount: <b>{current_amount} Ks</b> {step_text}\n"
                f"{Emoji.BRAIN} AI ({ai_mode}): {prediction}\n"
                f"{Emoji.MONEY_ICON} Balance: {vbal['balance']:,.0f} Ks\n"
                f"{Emoji.HOURGLASS} Waiting for result..."
            )
            
            await asyncio.sleep(30)
            
            won = random.random() < 0.5
            
            if won:
                win_amount = current_amount * 1.96
                profit = win_amount - current_amount
                vbal["balance"] += win_amount
                vbal["session_profit"] += profit
                vbal["total_wins"] += 1
                vbal["current_streak"] += 1
                if vbal["current_streak"] > vbal["best_streak"]:
                    vbal["best_streak"] = vbal["current_streak"]
                
                await message.answer(
                    f"{Emoji.WIN_CHECK} <b>WIN!</b> +{profit:.0f} Ks\n"
                    f"{Emoji.MONEY_ICON} Balance: {vbal['balance']:,.0f} Ks\n"
                    f"{Emoji.CHART_UP} Session Profit: +{vbal['session_profit']:,.0f} Ks\n"
                    f"{Emoji.UP} Reset to {bet_sequence[0]} Ks"
                )
                current_step = 0
                
                if vbal["session_profit"] >= profit_target:
                    await message.answer(
                        f"{Emoji.SPARKLES} <b>Target Reached!</b>\n"
                        f"{Emoji.MONEY_ICON} +{vbal['session_profit']:,.0f} Ks\n"
                        f"{Emoji.OFFLINE} Stopped."
                    )
                    is_bot_running = False
                    break
            else:
                vbal["session_profit"] -= current_amount
                vbal["total_losses"] += 1
                vbal["current_streak"] = 0
                current_step += 1
                
                if current_step >= len(bet_sequence):
                    await message.answer(
                        f"{Emoji.WARNING} <b>Sequence Lost!</b>\n"
                        f"{Emoji.LOSS_ICON} Session: {vbal['session_profit']:,.0f} Ks\n"
                        f"{Emoji.UP} Auto-reset to {bet_sequence[0]} Ks"
                    )
                    current_step = 0
                else:
                    await message.answer(
                        f"{Emoji.LOSE_CROSS} <b>LOSE!</b> -{current_amount} Ks\n"
                        f"{Emoji.MONEY_ICON} Balance: {vbal['balance']:,.0f} Ks\n"
                        f"{Emoji.LOSS_ICON} Session: {vbal['session_profit']:,.0f} Ks\n"
                        f"{Emoji.DOWN} Next: <b>{bet_sequence[current_step]} Ks</b>"
                    )
            
            await asyncio.sleep(5)
    
    await message.answer(
        f"{Emoji.OFFLINE} <b>Virtual Auto-Bet Stopped.</b>\n"
        f"{Emoji.MONEY_ICON} Final Balance: {vbal['balance']:,.0f} Ks\n"
        f"{Emoji.CHART_UP} Session P/L: {vbal['session_profit']:,.0f} Ks"
    )


# ==========================================================
# REAL AUTO-BET MODE (API Prediction + Playwright Browser)
# ==========================================================
@dp.message(LoginForm.main_menu, F.text == "Real Auto-Bet")
async def start_real_autobet(message: types.Message, state: FSMContext):
    global is_bot_running
    
    if is_bot_running:
        return await message.answer(f"{Emoji.WARNING} Auto-Bet is already running!")
    
    data = await state.get_data()
    if not data.get('is_real_logged'):
        return await message.answer(f"{Emoji.CROSS} Please Login first for Real Mode.")
    
    session_file = USER_SESSIONS.get(message.from_user.id, f"session_{message.from_user.id}.json")
    if not os.path.exists(session_file):
        return await message.answer(f"{Emoji.CROSS} Session not found. Please Login again.")
    
    bet_sequence = data.get('bet_sequence', DEFAULT_BET_SEQUENCE)
    profit_target = data.get('profit_target', DEFAULT_PROFIT_TARGET)
    ai_mode = data.get('ai_mode', DEFAULT_AI_MODE)
    
    is_bot_running = True
    status_msg = await message.answer(
        f"{Emoji.HOURGLASS} <b>Starting Real Auto-Bet...</b>\n"
        f"{Emoji.BRAIN} AI Mode: {ai_mode} (16 modes)\n"
        f"{Emoji.GAME} API Prediction + Browser Betting"
    )
    
    asyncio.create_task(
        run_real_betting_loop(
            message, status_msg, session_file,
            bet_sequence, profit_target, ai_mode
        )
    )


async def place_bet_on_page(page, bet_type: str, amount: int) -> bool:
    try:
        if amount >= 1000 and amount % 1000 == 0:
            base_amt = 1000
        elif amount >= 100 and amount % 100 == 0:
            base_amt = 100
        else:
            base_amt = 10
        
        multiplier = amount // base_amt
        selector = "div.Betting__C-foot-b" if bet_type == "BIG" else "div.Betting__C-foot-s"
        
        await page.locator(selector).first.click()
        await page.wait_for_timeout(1000)
        await page.locator(f"div.Betting__Popup-body-line-item:has-text('{base_amt}')").first.click()
        await page.wait_for_timeout(500)
        
        js_code = f"""
        () => {{
            let inputField = document.querySelector('input#van-field-1-input');
            if(inputField) {{
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(inputField, '{multiplier}');
                inputField.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }}
        """
        await page.evaluate(js_code)
        await page.wait_for_timeout(500)
        await page.locator("div.Betting__Popup-foot-s").first.click()
        return True
    except Exception as e:
        print(f"Place bet error: {e}")
        return False


async def check_if_won(page) -> bool:
    try:
        win_selectors = [
            "div.WinningTip__C-body-l1:has-text('Congratulations')",
            "div.WinningTip__C-body-l1:has-text('ဂုဏ်ယူပါတယ်')",
        ]
        for sel in win_selectors:
            if await page.locator(sel).is_visible(timeout=3000):
                await page.evaluate("document.body.click()")
                return True
        
        lose_selectors = [
            "div.WinningTip__C-body-l1:has-text('Try again')",
            "div.WinningTip__C-body-l1:has-text('ထပ်ကြိုးစားပါ')",
        ]
        for sel in lose_selectors:
            if await page.locator(sel).is_visible(timeout=3000):
                await page.evaluate("document.body.click()")
                return False
        
        return False
    except:
        return False


async def run_real_betting_loop(message, status_msg, session_file, bet_sequence, profit_target, ai_mode):
    global is_bot_running
    
    async with aiohttp.ClientSession() as api_session:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = await browser.new_context(storage_state=session_file, viewport={'width': 390, 'height': 844}, is_mobile=True)
            page = await context.new_page()
            
            try:
                await status_msg.edit_text(f"{Emoji.HOURGLASS} Navigating to WINGO 30S...")
                await page.goto(
                    "https://www.777bigwingame.app/#/home/AllLotteryGames/WinGo?id=1",
                    wait_until="networkidle"
                )
                await page.wait_for_timeout(4000)
                
                if "login" in page.url.lower():
                    is_bot_running = False
                    return await status_msg.edit_text(f"{Emoji.CROSS} Session expired. Please Login again.")
                
                await status_msg.edit_text(
                    f"{Emoji.CHECK} <b>Real Auto-Bet Started!</b>\n"
                    f"{Emoji.BRAIN} AI: {ai_mode} (16 modes)\n"
                    f"{Emoji.MONEY_BAG} Sequence: {' -> '.join([str(b) for b in bet_sequence])}\n"
                    f"{Emoji.TARGET} Target: {profit_target:,} Ks\n"
                )
                
                current_step = 0
                total_profit = 0
                
                while is_bot_running:
                    # STEP 1: Get prediction from API
                    history = await get_game_history(api_session)
                    
                    if history and len(history) >= 5:
                        prediction = predict_next(history, ai_mode)
                        latest = history[0]
                        
                        await message.answer(
                            f"{Emoji.BAR_CHART} <b>API Data:</b>\n"
                            f"Latest: {latest['issue_number']} = {latest['number']} ({latest['size']})\n"
                            f"{Emoji.BRAIN} <b>AI ({ai_mode}): {prediction}</b>"
                        )
                    else:
                        prediction = DEFAULT_PATTERN[current_step % len(DEFAULT_PATTERN)]
                        await message.answer(
                            f"{Emoji.WARNING} API failed, using fallback: <b>{prediction}</b>"
                        )
                    
                    # STEP 2: Place bet via Playwright Browser
                    current_amount = bet_sequence[current_step]
                    display_type = "BIG" if prediction == "BIG" else "SMALL"
                    step_text = f"(Step {current_step + 1}/{len(bet_sequence)})"
                    
                    if await place_bet_on_page(page, bet_type=prediction, amount=current_amount):
                        await message.answer(
                            f"{Emoji.ORDER} <b>Real Bet Placed!</b>\n"
                            f"{Emoji.GAME_ICON} WINGO 30S: {display_type}\n"
                            f"{Emoji.CHART_ICON} Amount: <b>{current_amount} Ks</b> {step_text}\n"
                            f"{Emoji.BRAIN} AI ({ai_mode}): {prediction}\n"
                            f"{Emoji.HOURGLASS} Waiting for result..."
                        )
                        
                        await asyncio.sleep(35)
                        await page.reload()
                        await page.wait_for_timeout(3000)
                        
                        if await check_if_won(page):
                            profit = current_amount * 0.96
                            total_profit += profit
                            
                            await message.answer(
                                f"{Emoji.WIN_CHECK} <b>WIN!</b> +{profit:.0f} Ks\n"
                                f"{Emoji.MONEY_ICON} Session: +{total_profit:.0f} Ks\n"
                                f"{Emoji.UP} Reset to {bet_sequence[0]} Ks"
                            )
                            current_step = 0
                            
                            if total_profit >= profit_target:
                                await message.answer(
                                    f"{Emoji.SPARKLES} <b>Target Reached!</b>\n"
                                    f"{Emoji.MONEY_ICON} +{total_profit:.0f} Ks\n"
                                    f"{Emoji.OFFLINE} Stopped."
                                )
                                is_bot_running = False
                                break
                        else:
                            total_profit -= current_amount
                            current_step += 1
                            
                            if current_step >= len(bet_sequence):
                                await message.answer(
                                    f"{Emoji.WARNING} <b>Sequence Lost!</b>\n"
                                    f"{Emoji.LOSS_ICON} Session: {total_profit:.0f} Ks\n"
                                    f"{Emoji.OFFLINE} Stopped."
                                )
                                is_bot_running = False
                                break
                            else:
                                await message.answer(
                                    f"{Emoji.LOSE_CROSS} <b>LOSE!</b> -{current_amount} Ks\n"
                                    f"{Emoji.LOSS_ICON} Session: {total_profit:.0f} Ks\n"
                                    f"{Emoji.DOWN} Next: <b>{bet_sequence[current_step]} Ks</b>"
                                )
                    else:
                        await message.answer(f"{Emoji.WARNING} Failed to place bet. Retrying...")
                    
                    await asyncio.sleep(5)
                    
            except Exception as e:
                await message.answer(f"{Emoji.WARNING} Error: {html.escape(str(e))}")
            finally:
                is_bot_running = False
                await browser.close()
                await api_session.close()
                await message.answer(
                    f"{Emoji.OFFLINE} <b>Real Auto-Bet Stopped.</b>\n"
                    f"{Emoji.MONEY_ICON} Session P/L: {total_profit:.0f} Ks"
                )


@dp.message(F.text == "Stop")
async def stop_autobet(message: types.Message):
    global is_bot_running
    is_bot_running = False
    await message.answer(f"{Emoji.CHECK} <b>Stop signal sent.</b>")


# ==========================================================
# MAIN
# ==========================================================
async def main():
    if OWNER_ID and OWNER_ID != "0":
        AUTHORIZED_USERS.add(int(OWNER_ID))
    
    print("=" * 60)
    print("PSP AUTO BETTING V5")
    print("=" * 60)
    print("16 AI Modes + API Prediction + Browser Betting")
    print("Virtual Mode: ENABLED")
    print("Real Mode: ENABLED (Playwright)")
    print(f"Owner: {OWNER_ID}")
    print("=" * 60 + "\n")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot Stopped")
