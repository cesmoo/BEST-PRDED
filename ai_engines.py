# ai_engines.py
import numpy as np
import time

class AIEmoji:
    CHECK = "✅"; CROSS = "❌"; INFO = "ℹ️"; HOURGLASS = "⏳"
    UP = "⬆️"; DOWN = "⬇️"; LEFT_RIGHT = "↔️"; SPARKLES = "✨"
    PATTERN = "🎯"; MARTINGALE = "🎲"; ANTIMARTINGALE = "🔄"
    TREND = "📊"; FIBONACCI = "🔢"; GOLDEN = "🎯"; MOMENTUM = "📈"
    MONTECARLO = "🎲"; NEURAL = "🧬"; REVERSAL = "⚡"; WAVE = "🌊"; CHAOS = "🎪"
    CHART_UP = "📈"; CHART_DOWN = "📉"; STAR = "⭐"
    ROBOT = "🤖"; BRAIN = "🧠"

# ========== 1. PATTERN AI (Improved) ==========
def detect_active_pattern(history_list):
    if len(history_list) < 4: return None, None, 0
    patterns_to_check = [
        ("BBSS→B", ["BIG", "BIG", "SMALL", "SMALL"], "BIG", 4),
        ("BBS→B", ["BIG", "BIG", "SMALL"], "BIG", 3),
        ("BSS→B", ["BIG", "SMALL", "SMALL"], "BIG", 3),
        ("SSBB→S", ["SMALL", "SMALL", "BIG", "BIG"], "SMALL", 4),
        ("SSB→S", ["SMALL", "SMALL", "BIG"], "SMALL", 3),
        ("SBB→S", ["SMALL", "BIG", "BIG"], "SMALL", 3),
        ("BSBS→B", ["BIG", "SMALL", "BIG", "SMALL"], "BIG", 4),
        ("SBSB→S", ["SMALL", "BIG", "SMALL", "BIG"], "SMALL", 4),
        ("BSB→B", ["BIG", "SMALL", "BIG"], "BIG", 3),
        ("SBS→S", ["SMALL", "BIG", "SMALL"], "SMALL", 3),
        ("BBB→B", ["BIG", "BIG", "BIG"], "BIG", 3),
        ("SSS→S", ["SMALL", "SMALL", "SMALL"], "SMALL", 3),
        ("BB→B", ["BIG", "BIG"], "BIG", 2),
        ("SS→S", ["SMALL", "SMALL"], "SMALL", 2),
        ("BBSB→B", ["BIG", "BIG", "SMALL", "BIG"], "BIG", 4),
        ("SSBS→S", ["SMALL", "SMALL", "BIG", "SMALL"], "SMALL", 4),
        ("BSBB→S", ["BIG", "SMALL", "BIG", "BIG"], "SMALL", 4),
        ("SBSS→B", ["SMALL", "BIG", "SMALL", "SMALL"], "BIG", 4),
    ]
    recent = history_list[-20:]
    best_pattern, best_next, best_score = None, None, 0
    for pattern_name, pattern_seq, next_pred, weight in patterns_to_check:
        pattern_len = len(pattern_seq)
        if len(recent) < pattern_len: continue
        match_count = 0; last_match_position = -1
        for i in range(len(recent) - pattern_len + 1):
            if recent[i:i+pattern_len] == pattern_seq:
                match_count += 1; last_match_position = i
        if match_count >= 2:
            recency_bonus = 2 if last_match_position >= len(recent) - pattern_len - 5 else 0
            score = (pattern_len * match_count * weight) + recency_bonus
            if score > best_score:
                best_score, best_pattern, best_next = score, pattern_name, next_pred
    return best_pattern, best_next, best_score

def pattern_predict(history_docs):
    if len(history_docs) < 10: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.HOURGLASS} Pattern: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    active_pattern, next_pred, score = detect_active_pattern(all_history)
    if active_pattern and next_pred:
        prob = min(65 + (score * 2), 85)
        if next_pred == "BIG": return "BIG", f"BIG (အကြီး) 🔴", prob, f"{AIEmoji.PATTERN} Pattern: {active_pattern} → BIG"
        else: return "SMALL", f"SMALL (အသေး) 🟢", prob, f"{AIEmoji.PATTERN} Pattern: {active_pattern} → SMALL"
    recent_5 = all_history[-5:]
    big_in_5 = recent_5.count("BIG"); small_in_5 = recent_5.count("SMALL")
    if len(all_history) >= 4:
        last_4 = all_history[-4:]
        if last_4 == ["BIG", "SMALL", "BIG", "SMALL"]: return "BIG", "BIG (အကြီး) 🔴", 65.0, f"{AIEmoji.PATTERN} Pattern: BSBS → BIG"
        elif last_4 == ["SMALL", "BIG", "SMALL", "BIG"]: return "SMALL", "SMALL (အသေး) 🟢", 65.0, f"{AIEmoji.PATTERN} Pattern: SBSB → SMALL"
    if big_in_5 >= 3: return "BIG", "BIG (အကြီး) 🔴", 60.0, f"📊 Recent trend: BIG ({big_in_5}/5)"
    elif small_in_5 >= 3: return "SMALL", "SMALL (အသေး) 🟢", 60.0, f"📊 Recent trend: SMALL ({small_in_5}/5)"
    b_count = all_history.count("BIG"); s_count = all_history.count("SMALL")
    if b_count > s_count: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"📊 Majority: BIG ({b_count}:{s_count})"
    else: return "SMALL", "SMALL (အသေး) 🟢", 55.0, f"📊 Majority: SMALL ({b_count}:{s_count})"

# ========== 2. MARTINGALE AI ==========
def martingale_predict(history_docs):
    if len(history_docs) < 5: return "BIG", "BIG (အကြီး) 🔴", 60.0, f"{AIEmoji.MARTINGALE} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    recent_10 = all_history[-10:]; big = recent_10.count("BIG"); small = recent_10.count("SMALL")
    if big > small: return "SMALL", "SMALL (အသေး) 🟢", 65.0, f"{AIEmoji.MARTINGALE} Contrarian BIG:{big} SMALL:{small}"
    else: return "BIG", "BIG (အကြီး) 🔴", 65.0, f"{AIEmoji.MARTINGALE} Contrarian BIG:{big} SMALL:{small}"

# ========== 3. ANTI-MARTINGALE AI ==========
def anti_martingale_predict(history_docs):
    if len(history_docs) < 5: return "BIG", "BIG (အကြီး) 🔴", 60.0, f"{AIEmoji.ANTIMARTINGALE} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    recent_5 = all_history[-5:]; big_streak = small_streak = 0
    for r in reversed(recent_5):
        if r == "BIG": big_streak += 1; small_streak = 0
        else: small_streak += 1; big_streak = 0
    if big_streak >= 2: return "BIG", "BIG (အကြီး) 🔴", 70.0, f"{AIEmoji.ANTIMARTINGALE} BIG streak {big_streak}"
    elif small_streak >= 2: return "SMALL", "SMALL (အသေး) 🟢", 70.0, f"{AIEmoji.ANTIMARTINGALE} SMALL streak {small_streak}"
    else:
        last = all_history[-1] if all_history else "BIG"; emoji = "🔴" if last == "BIG" else "🟢"
        return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 60.0, f"{AIEmoji.ANTIMARTINGALE} Follow last"

# ========== 4. TREND FOLLOWING AI ==========
def trend_following_predict(history_docs):
    if len(history_docs) < 8: return "BIG", "BIG (အကြီး) 🔴", 58.0, f"{AIEmoji.TREND} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    big_8 = all_history[-8:].count("BIG") / 8; big_4 = all_history[-4:].count("BIG") / 4; trend = big_4 - big_8
    if trend > 0.1: return "BIG", "BIG (အကြီး) 🔴", 72.0, f"{AIEmoji.TREND} BIG +{trend*100:.0f}%"
    elif trend < -0.1: return "SMALL", "SMALL (အသေး) 🟢", 72.0, f"{AIEmoji.TREND} SMALL +{abs(trend)*100:.0f}%"
    else:
        last = all_history[-1]; emoji = "🔴" if last == "BIG" else "🟢"
        return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 60.0, f"{AIEmoji.TREND} Sideways"

# ========== 5. FIBONACCI AI ==========
def fibonacci_predict(history_docs):
    if len(history_docs) < 10: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.FIBONACCI} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    fib_levels = [3, 5, 8, 13, 21]; results = []
    for level in fib_levels:
        if len(all_history) >= level:
            segment = all_history[-level:]; big_pct = segment.count("BIG") / level
            if 0.38 <= big_pct <= 0.62: results.append("BIG" if big_pct < 0.5 else "SMALL")
            elif big_pct > 0.618: results.append("SMALL")
            else: results.append("BIG")
    if results:
        final = max(set(results), key=results.count); emoji = "🔴" if final == "BIG" else "🟢"
        return final, f"{final} ({'အကြီး' if final == 'BIG' else 'အသေး'}) {emoji}", 68.0, f"{AIEmoji.FIBONACCI} {len(results)} levels"
    return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.FIBONACCI} Default"

# ========== 6. GOLDEN RATIO AI ==========
def golden_ratio_predict(history_docs):
    if len(history_docs) < 12: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.GOLDEN} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    lookback = min(21, len(all_history)); big_ratio = all_history[-lookback:].count("BIG") / lookback
    if big_ratio > 0.618: return "SMALL", "SMALL (အသေး) 🟢", 70.0, f"{AIEmoji.GOLDEN} {big_ratio*100:.1f}% > 61.8% {AIEmoji.DOWN}"
    elif big_ratio < 0.382: return "BIG", "BIG (အကြီး) 🔴", 70.0, f"{AIEmoji.GOLDEN} {big_ratio*100:.1f}% < 38.2% {AIEmoji.UP}"
    else:
        last = all_history[-1]; emoji = "🔴" if last == "BIG" else "🟢"
        return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 65.0, f"{AIEmoji.GOLDEN} Zone: {big_ratio*100:.1f}%"

# ========== 7. MOMENTUM AI ==========
def momentum_predict(history_docs):
    if len(history_docs) < 6: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.MOMENTUM} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    score = 0; weights = [5, 4, 3, 2, 1]
    for i, r in enumerate(all_history[-5:]):
        if r == "BIG": score += weights[i]
        else: score -= weights[i]
    if score > 3: return "BIG", "BIG (အကြီး) 🔴", 73.0, f"{AIEmoji.MOMENTUM} Strong BIG (+{score})"
    elif score < -3: return "SMALL", "SMALL (အသေး) 🟢", 73.0, f"{AIEmoji.MOMENTUM} Strong SMALL ({score})"
    else:
        last = all_history[-1]; emoji = "🔴" if last == "BIG" else "🟢"
        return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 58.0, f"{AIEmoji.MOMENTUM} Weak: {score}"

# ========== 8. MONTE CARLO AI ==========
def monte_carlo_predict(history_docs):
    if len(history_docs) < 15: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.MONTECARLO} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    np.random.seed(int(time.time())); big_prob = all_history.count("BIG") / len(all_history)
    big_wins = sum(1 for _ in range(1000) if np.random.choice(["BIG", "SMALL"], p=[big_prob, 1-big_prob]) == "BIG")
    if big_wins > 500:
        prob = (big_wins / 1000) * 100; return "BIG", "BIG (အကြီး) 🔴", min(prob, 80), f"{AIEmoji.MONTECARLO} BIG {prob:.1f}%"
    else:
        prob = ((1000 - big_wins) / 1000) * 100; return "SMALL", "SMALL (အသေး) 🟢", min(prob, 80), f"{AIEmoji.MONTECARLO} SMALL {prob:.1f}%"

# ========== 9. NEURAL PATTERN AI ==========
def neural_pattern_predict(history_docs):
    if len(history_docs) < 8: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.NEURAL} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    features = []
    for i in range(3, len(all_history)):
        window = all_history[i-3:i]; features.append({"big_ratio": window.count("BIG") / 3, "next": all_history[i]})
    current_ratio = all_history[-3:].count("BIG") / 3; similar_big = similar_small = 0
    for f in features:
        if abs(f["big_ratio"] - current_ratio) < 0.1:
            if f["next"] == "BIG": similar_big += 1
            else: similar_small += 1
    total = similar_big + similar_small
    if total > 0:
        big_prob = (similar_big / total) * 100
        if big_prob > 50: return "BIG", "BIG (အကြီး) 🔴", min(big_prob + 10, 85), f"{AIEmoji.NEURAL} {total} patterns BIG {big_prob:.0f}%"
        else: return "SMALL", "SMALL (အသေး) 🟢", min((100-big_prob) + 10, 85), f"{AIEmoji.NEURAL} {total} patterns SMALL {100-big_prob:.0f}%"
    return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.NEURAL} No similar patterns"

# ========== 10. QUICK REVERSAL AI ==========
def quick_reversal_predict(history_docs):
    if len(history_docs) < 5: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.REVERSAL} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    recent_5 = all_history[-5:]; alts = sum(1 for i in range(1, len(recent_5)) if recent_5[i] != recent_5[i-1])
    alt_rate = alts / (len(recent_5) - 1)
    if alt_rate > 0.75:
        last = recent_5[-1]; predicted = "SMALL" if last == "BIG" else "BIG"
        emoji = "🔴" if predicted == "BIG" else "🟢"
        return predicted, f"{predicted} ({'အကြီး' if predicted == 'BIG' else 'အသေး'}) {emoji}", 72.0, f"{AIEmoji.REVERSAL} Alt {alt_rate*100:.0f}%"
    else:
        last = recent_5[-1]; emoji = "🔴" if last == "BIG" else "🟢"
        return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 60.0, f"{AIEmoji.REVERSAL} Alt {alt_rate*100:.0f}%"

# ========== 11. WAVE ANALYSIS AI ==========
def wave_analysis_predict(history_docs):
    if len(history_docs) < 8: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.WAVE} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    waves = []; current = all_history[0]; count = 1
    for r in all_history[1:]:
        if r == current: count += 1
        else: waves.append((current, count)); current = r; count = 1
    waves.append((current, count))
    if len(waves) >= 3:
        last_wave = waves[-1]; prev_wave = waves[-2]
        if last_wave[1] >= 3 and prev_wave[0] != last_wave[0]:
            emoji = "🔴" if last_wave[0] == "BIG" else "🟢"
            return last_wave[0], f"{last_wave[0]} ({'အကြီး' if last_wave[0] == 'BIG' else 'အသေး'}) {emoji}", 70.0, f"{AIEmoji.WAVE} Impulse {last_wave[1]}"
        elif last_wave[1] <= 2:
            predicted = "SMALL" if last_wave[0] == "BIG" else "BIG"
            emoji = "🔴" if predicted == "BIG" else "🟢"
            return predicted, f"{predicted} ({'အကြီး' if predicted == 'BIG' else 'အသေး'}) {emoji}", 68.0, f"{AIEmoji.WAVE} Correction"
    last = all_history[-1]; emoji = "🔴" if last == "BIG" else "🟢"
    return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 58.0, f"{AIEmoji.WAVE} Default"

# ========== 12. CHAOS THEORY AI ==========
def chaos_theory_predict(history_docs):
    if len(history_docs) < 10: return "BIG", "BIG (အကြီး) 🔴", 55.0, f"{AIEmoji.CHAOS} Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    def entropy(seg):
        total = len(seg); big_p = seg.count("BIG") / total; small_p = seg.count("SMALL") / total
        e = 0
        for p in [big_p, small_p]:
            if p > 0: e -= p * np.log2(p)
        return e
    e3 = entropy(all_history[-3:]); e5 = entropy(all_history[-5:]); e10 = entropy(all_history[-10:])
    if e3 > e5 > e10:
        last = all_history[-3:][-1]; predicted = "SMALL" if last == "BIG" else "BIG"
        emoji = "🔴" if predicted == "BIG" else "🟢"
        return predicted, f"{predicted} ({'အကြီး' if predicted == 'BIG' else 'အသေး'}) {emoji}", 67.0, f"{AIEmoji.CHAOS} Entropy {AIEmoji.LEFT_RIGHT}"
    elif e3 < e5:
        majority = "BIG" if all_history[-5:].count("BIG") > all_history[-5:].count("SMALL") else "SMALL"
        emoji = "🔴" if majority == "BIG" else "🟢"
        return majority, f"{majority} ({'အကြီး' if majority == 'BIG' else 'အသေး'}) {emoji}", 65.0, f"{AIEmoji.CHAOS} Pattern {AIEmoji.SPARKLES}"
    last = all_history[-1]; emoji = "🔴" if last == "BIG" else "🟢"
    return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 55.0, f"{AIEmoji.CHAOS} Stable"

# ========== 13. ENSEMBLE AI ==========
def ensemble_predict(history_docs):
    if len(history_docs) < 10: return "BIG", "BIG (အကြီး) 🔴", 55.0, "🤖 Ensemble: Data စုဆောင်းဆဲ..."
    predictors = [pattern_predict, martingale_predict, anti_martingale_predict, trend_following_predict, fibonacci_predict, golden_ratio_predict, momentum_predict, monte_carlo_predict, neural_pattern_predict, quick_reversal_predict, wave_analysis_predict, chaos_theory_predict]
    predictions = []
    for predictor in predictors:
        try:
            size, _, prob, _ = predictor(history_docs); predictions.append((size, prob))
        except: pass
    if not predictions: return "BIG", "BIG (အကြီး) 🔴", 55.0, "🤖 Ensemble: Error"
    big_votes = sum(1 for p in predictions if p[0] == "BIG"); small_votes = sum(1 for p in predictions if p[0] == "SMALL")
    total = big_votes + small_votes
    if big_votes > small_votes:
        confidence = (big_votes / total) * 100; return "BIG", "BIG (အကြီး) 🔴", min(confidence + 10, 90), f"🤖 Ensemble: {big_votes}/{total} votes BIG ({confidence:.0f}%)"
    else:
        confidence = (small_votes / total) * 100; return "SMALL", "SMALL (အသေး) 🟢", min(confidence + 10, 90), f"🤖 Ensemble: {small_votes}/{total} votes SMALL ({confidence:.0f}%)"

# ========== 14. BAYESIAN AI ==========
def bayesian_predict(history_docs):
    if len(history_docs) < 10: return "BIG", "BIG (အကြီး) 🔴", 55.0, "📐 Bayesian: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    recent = all_history[-20:]; big_after_big = small_after_small = 0; big_total = small_total = 0
    for i in range(1, len(recent)):
        if recent[i-1] == "BIG": big_total += 1
        else: small_total += 1
    for i in range(1, len(recent)):
        if recent[i-1] == "BIG" and recent[i] == "BIG": big_after_big += 1
        elif recent[i-1] == "SMALL" and recent[i] == "SMALL": small_after_small += 1
    p_big_after_big = big_after_big / big_total if big_total > 0 else 0.5
    p_small_after_small = small_after_small / small_total if small_total > 0 else 0.5
    last = recent[-1]
    if last == "BIG":
        if p_big_after_big > 0.5: return "BIG", "BIG (အကြီး) 🔴", min(p_big_after_big * 100 + 15, 80), f"📐 Bayesian: P(BIG|BIG)={p_big_after_big*100:.0f}%"
        else: return "SMALL", "SMALL (အသေး) 🟢", min((1-p_big_after_big) * 100 + 15, 80), f"📐 Bayesian: P(SMALL|BIG)={(1-p_big_after_big)*100:.0f}%"
    else:
        if p_small_after_small > 0.5: return "SMALL", "SMALL (အသေး) 🟢", min(p_small_after_small * 100 + 15, 80), f"📐 Bayesian: P(SMALL|SMALL)={p_small_after_small*100:.0f}%"
        else: return "BIG", "BIG (အကြီး) 🔴", min((1-p_small_after_small) * 100 + 15, 80), f"📐 Bayesian: P(BIG|SMALL)={(1-p_small_after_small)*100:.0f}%"

# ========== 15. MARKOV CHAIN AI ==========
def markov_chain_predict(history_docs):
    if len(history_docs) < 8: return "BIG", "BIG (အကြီး) 🔴", 55.0, "🔗 Markov: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    transitions = {}
    for i in range(2, len(all_history)):
        state = (all_history[i-2], all_history[i-1]); next_val = all_history[i]
        if state not in transitions: transitions[state] = {"BIG": 0, "SMALL": 0}
        transitions[state][next_val] += 1
    current_state = (all_history[-2], all_history[-1])
    if current_state in transitions:
        counts = transitions[current_state]; total = counts["BIG"] + counts["SMALL"]
        if total > 0:
            big_prob = (counts["BIG"] / total) * 100
            if big_prob > 50: return "BIG", "BIG (အကြီး) 🔴", min(big_prob + 10, 82), f"🔗 Markov: {current_state} → BIG {big_prob:.0f}%"
            else: return "SMALL", "SMALL (အသေး) 🟢", min((100-big_prob) + 10, 82), f"🔗 Markov: {current_state} → SMALL {100-big_prob:.0f}%"
    last = all_history[-1]; emoji = "🔴" if last == "BIG" else "🟢"
    return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 58.0, "🔗 Markov: 1st order"

# ========== 16. ML STYLE AI ==========
def ml_style_predict(history_docs):
    if len(history_docs) < 12: return "BIG", "BIG (အကြီး) 🔴", 55.0, "🧪 ML Style: Data စုဆောင်းဆဲ..."
    docs = list(reversed(history_docs)); all_history = [d.get('size', 'BIG') for d in docs]
    recent = all_history[-12:]
    features = {
        "last_3_big_ratio": recent[-3:].count("BIG") / 3,
        "last_5_big_ratio": recent[-5:].count("BIG") / 5,
        "last_8_big_ratio": recent[-8:].count("BIG") / 8,
        "trend": recent[-4:].count("BIG") / 4 - recent[-8:].count("BIG") / 8,
    }
    score = 0
    score += (features["last_3_big_ratio"] - 0.5) * 0.4
    score += (features["last_5_big_ratio"] - 0.5) * 0.3
    score += (features["last_8_big_ratio"] - 0.5) * 0.2
    score += features["trend"] * 0.1
    if score > 0.05: return "BIG", "BIG (အကြီး) 🔴", min(55 + abs(score) * 100, 78), f"🧪 ML Style: Score +{score:.3f} → BIG"
    elif score < -0.05: return "SMALL", "SMALL (အသေး) 🟢", min(55 + abs(score) * 100, 78), f"🧪 ML Style: Score {score:.3f} → SMALL"
    else:
        last = recent[-1]; emoji = "🔴" if last == "BIG" else "🟢"
        return last, f"{last} ({'အကြီး' if last == 'BIG' else 'အသေး'}) {emoji}", 55.0, f"🧪 ML Style: Neutral {score:.3f}"

# ========== AI MODES DICTIONARY ==========
AI_MODES = {
    "pattern": {"func": pattern_predict, "name": "🎯 Pattern AI", "desc": "Pattern Auto-Switch"},
    "martingale": {"func": martingale_predict, "name": "🎲 Martingale AI", "desc": "Contrarian Strategy"},
    "anti_martingale": {"func": anti_martingale_predict, "name": "🔄 Anti-Martingale AI", "desc": "Trend Follow"},
    "trend_following": {"func": trend_following_predict, "name": "📊 Trend Following", "desc": "MA Trend Analysis"},
    "fibonacci": {"func": fibonacci_predict, "name": "🔢 Fibonacci AI", "desc": "Fib Retracement"},
    "golden_ratio": {"func": golden_ratio_predict, "name": "🎯 Golden Ratio", "desc": "61.8% Rule"},
    "momentum": {"func": momentum_predict, "name": "📈 Momentum AI", "desc": "Weighted Momentum"},
    "monte_carlo": {"func": monte_carlo_predict, "name": "🎲 Monte Carlo", "desc": "1000x Simulation"},
    "neural_pattern": {"func": neural_pattern_predict, "name": "🧬 Neural Pattern", "desc": "Pattern Similarity"},
    "quick_reversal": {"func": quick_reversal_predict, "name": "⚡ Quick Reversal", "desc": "Alternation Detection"},
    "wave_analysis": {"func": wave_analysis_predict, "name": "🌊 Wave Analysis", "desc": "Elliott Wave"},
    "chaos_theory": {"func": chaos_theory_predict, "name": "🎪 Chaos Theory", "desc": "Entropy Analysis"},
    "ensemble": {"func": ensemble_predict, "name": "🤖 Ensemble AI", "desc": "12 AI Voting System"},
    "bayesian": {"func": bayesian_predict, "name": "📐 Bayesian AI", "desc": "Conditional Probability"},
    "markov_chain": {"func": markov_chain_predict, "name": "🔗 Markov Chain", "desc": "Transition Matrix"},
    "ml_style": {"func": ml_style_predict, "name": "🧪 ML Style AI", "desc": "Weighted Features"},
}

def get_prediction(history_docs, mode):
    mode_info = AI_MODES.get(mode)
    if mode_info: return mode_info["func"](history_docs)
    return AI_MODES["pattern"]["func"](history_docs)
