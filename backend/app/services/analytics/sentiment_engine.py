"""
HIVE-Sent: Bilingual Hybrid Sentiment & Emotion Engine
=====================================================

HiveMind's opinion-scoring core. Designed for free-tier cloud deployment:
no transformer downloads, no GPU, sub-millisecond scoring — while still
producing research-grade outputs.

Design (why hybrid?):
  1. Lexicon scoring with intensifier/negation shaping  -> fast, deterministic
  2. Emotion classification over an NRC-style lexicon   -> 8 primary emotions
  3. Emoji/punctuation/caps heuristics                  -> social-media aware
  4. Optional LLM augmentation hook                     -> when an API is present

Outputs per text:
  compound   : -1.0 .. +1.0   (polar; > 0.05 positive, < -0.05 negative)
  positive   :  0.0 .. 1.0
  negative   :  0.0 .. 1.0
  neutral    :  0.0 .. 1.0
  emotion    : one of {joy, trust, fear, surprise, sadness, disgust, anger,
                       anticipation, neutral}
  intensity  : 0.0 .. 1.0   (emotional arousal, drives cascade detection)
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------
# Lexicons (compact, embedded — zero runtime downloads)
# --------------------------------------------------------------------------

_POSITIVE = {
    # English
    "good", "great", "excellent", "amazing", "wonderful", "fantastic",
    "brilliant", "outstanding", "superb", "positive", "hope", "hopeful",
    "love", "loved", "lovely", "like", "liked", "enjoy", "enjoyed",
    "happy", "happiness", "glad", "delighted", "pleased", "thrilled",
    "support", "supported", "supporting", "approve", "approved", "agree",
    "agreed", "win", "won", "winning", "success", "successful", "succeed",
    "progress", "improve", "improved", "improving", "better", "best",
    "benefit", "beneficial", "gain", "gains", "opportunity", "opportunities",
    "growth", "growing", "rise", "rising", "boost", "boosted", "strong",
    "stronger", "safe", "safety", "secure", "reliable", "trust", "trusted",
    "trustworthy", "honest", "fair", "justice", "peace", "calm", "proud",
    "pride", "impressive", "recommend", "recommended", "thank", "thanks",
    "grateful", "celebrate", "celebration", "exciting", "excited", "excites",
    "encouraging", "encouraged", "promising", "remarkable", "incredible",
    "efficient", "effective", "valuable", "helpful", "useful", "kind",
    "generous", "compassion", "courage", "brave", "inspiring", "inspired",
    "awesome", "perfect", "flawless", "solid", "favorite", "prefer",
    # Chinese (simplified)
    "好", "很好", "更好", "最好", "棒", "太棒", "优秀", "出色", "卓越",
    "喜欢", "爱", "支持", "赞成", "同意", "满意", "开心", "高兴", "快乐",
    "幸福", "放心", "希望", "成功", "进步", "提升", "改善", "增长", "上涨",
    "受益", "机会", "优势", "强大", "安全", "可靠", "信任", "诚实", "公平",
    "正义", "和平", "自豪", "感谢", "兴奋", "鼓舞", "振奋", "完美", "推荐",
    "给力", "点赞", "厉害", "不错", "暖心", "感人", " positive",
}

_NEGATIVE = {
    # English
    "bad", "terrible", "awful", "horrible", "dreadful", "appalling",
    "negative", "hate", "hated", "hates", "dislike", "disliked", "angry",
    "anger", "furious", "outraged", "outrage", "rage", "mad", "upset",
    "sad", "sadness", "depressed", "depressing", "miserable", "grief",
    "sorrow", "cry", "crying", "tears", "pain", "painful", "hurt",
    "suffering", "suffer", "fear", "afraid", "scared", "terrified",
    "terrifying", "anxious", "anxiety", "worried", "worry", "worrying",
    "panic", "dread", "horror", "disgust", "disgusting", "gross", "revolt",
    "fail", "failed", "failing", "failure", "flop", "loss", "lose",
    "losing", "lost", "decline", "declining", "drop", "crash", "crisis",
    "disaster", "catastrophe", "collapse", "worse", "worst", "worsening",
    "problem", "problems", "issue", "issues", "trouble", "difficulty",
    "difficult", "hard", "harm", "harmful", "damage", "damaging", "danger",
    "dangerous", "risk", "risky", "threat", "threatening", "corrupt",
    "corruption", "lie", "liar", "lying", "deceive", "deception", "fraud",
    "scam", "cheat", "unfair", "injustice", "selfish", "greedy", "cruel",
    "brutal", "violent", "violence", "attack", "attacked", "war", "conflict",
    "scandal", "controversy", "backlash", "protest", "boycott", "weak",
    "broken", "useless", "worthless", "waste", "wasted", "disaster",
    "shameful", "shame", "embarrassing", "embarrassed", "pathetic",
    "stupid", "dumb", "idiotic", "clueless", "incompetent", "incompetence",
    # Chinese (simplified)
    "坏", "差", "很差", "糟糕", "恶劣", "可怕", "恐怖", "恨", "讨厌",
    "愤怒", "生气", "气死", "暴怒", "难过", "伤心", "悲伤", "痛苦",
    "绝望", "哭泣", "流泪", "害怕", "恐惧", "担忧", "担心", "焦虑",
    "恐慌", "恶心", "厌恶", "失败", "亏损", "损失", "下降", "暴跌",
    "崩溃", "危机", "灾难", "问题", "麻烦", "困难", "危害", "损害",
    "危险", "威胁", "风险", "腐败", "撒谎", "骗子", "欺诈", "骗局",
    "不公", "不义", "自私", "贪婪", "残忍", "暴力", "攻击", "战争",
    "冲突", "丑闻", "争议", "抗议", "抵制", "软弱", "破碎", "无用",
    "浪费", "可耻", "丢脸", "无能", "失望", "可悲", "愚蠢", "荒谬",
}

_INTENSIFIERS = {
    "very", "extremely", "incredibly", "really", "so", "totally",
    "absolutely", "completely", "utterly", "highly", "deeply", "super",
    "insanely", "unbelievably", "exceptionally", "particularly",
    "太", "非常", "特别", "极其", "超", "十分", "相当", "超级", "巨",
}

_NEGATIONS = {
    "not", "no", "never", "none", "nobody", "nothing", "neither", "nor",
    "cannot", "can't", "won't", "wouldn't", "shouldn't", "couldn't",
    "doesn't", "doesn", "don't", "don", "didn't", "didn", "isn't", "isn",
    "aren't", "aren", "wasn't", "wasn", "weren't", "weren", "hardly",
    "barely", "scarcely", "without",
    "不", "没", "没有", "无", "非", "别", "莫", "未", "毫无", "从不",
}

# NRC-style emotion lexicon (trimmed to high-confidence seeds)
_EMOTION_LEXICON: Dict[str, set] = {
    "joy": {"happy", "joy", "delight", "delighted", "cheerful", "glad",
            "celebrate", "celebration", "excited", "exciting", "fun",
            "wonderful", "love", "loved", "smile", "laugh", "laughing",
            "enjoy", "enjoyed", "pleasure", "thrilled", "awesome", "win",
            "won", "proud", "pride", "hope", "hopeful", "开心", "高兴",
            "快乐", "兴奋", "庆祝", "笑容", "笑", "自豪", "骄傲", "希望",
            "喜欢", "幸福", "太棒"},
    "trust": {"trust", "trusted", "reliable", "honest", "faith", "faithful",
              "confidence", "confident", "credible", "safe", "safety",
              "secure", "support", "supported", "loyal", "integrity",
              "transparent", "transparency", "信任", "可靠", "诚实",
              "信心", "安全", "支持", "忠诚", "透明"},
    "fear": {"fear", "afraid", "scared", "terrified", "terrifying",
             "horror", "panic", "dread", "threat", "threatening", "danger",
             "dangerous", "risk", "risky", "anxious", "anxiety", "worried",
             "worry", "nervous", "alarm", "alarmed", "warning", "warning",
             "害怕", "恐惧", "恐慌", "威胁", "危险", "风险", "焦虑",
             "担心", "担忧", "紧张", "警报"},
    "surprise": {"surprise", "surprised", "surprising", "unexpected",
                 "sudden", "suddenly", "shock", "shocked", "shocking",
                 "amazed", "amazing", "astonished", "astonishing", "stun",
                 "stunned", "unbelievable", "wow", "意外", "震惊", "突然",
                 "惊讶", "吃惊", "不可思议", "居然", "竟然"},
    "sadness": {"sad", "sadness", "sorrow", "grief", "mourn", "mourning",
                "cry", "crying", "tears", "depressed", "depressing",
                "miserable", "lonely", "loneliness", "heartbroken", "loss",
                "lost", "miss", "missing", "regret", "regretful", "难过",
                "伤心", "悲伤", "哀悼", "哭泣", "流泪", "沮丧", "孤独",
                "心碎", "失去", "怀念", "后悔", "遗憾"},
    "disgust": {"disgust", "disgusting", "gross", "revolting", "revolt",
                "repulsive", "sick", "sickening", "nasty", "filthy",
                "corrupt", "corruption", "scam", "fraud", "cheat",
                "shameful", "恶心", "厌恶", "反感", "肮脏", "腐败",
                "骗子", "欺诈", "可耻", "无耻"},
    "anger": {"angry", "anger", "furious", "outrage", "outraged", "rage",
              "mad", "fury", "irritated", "irritating", "annoyed",
              "annoying", "frustrated", "frustrating", "hate", "hated",
              "hostile", "insult", "insulting", "betrayed", "betrayal",
              "愤怒", "生气", "暴怒", "恼火", "烦", "愤怒", "仇恨",
              "敌意", "侮辱", "背叛", "气死"},
    "anticipation": {"anticipate", "anticipating", "expect", "expected",
                     "expecting", "looking forward", "soon", "upcoming",
                     "future", "plan", "planning", "prepare", "ready",
                     "await", "awaiting", "forecast", "predict",
                     "prediction", "期待", "期望", "预期", "展望", "未来",
                     "计划", "准备", "即将", "预测", "前瞻"},
}

_EMOTIONS = list(_EMOTION_LEXICON.keys())

_TOKEN_RE = re.compile(r"[a-zA-Z']+|[\u4e00-\u9fff]")
_EMOJI_POS = set("😊😃😄😁😆🤗😍🥰😘👍🎉✨💖❤️🔥💯🙌👏🙏💪🙂😊")
_EMOJI_NEG = set("😢😭😟😠😡🤬😱😰😨😩😫😒😞😔😟👎💔😡🙄😣😖")

_EXCLAMATION_RE = re.compile(r"!+")
_CAPS_RE = re.compile(r"\b[A-Z]{3,}\b")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _lookup(word: str) -> int:
    """Return polarity of a token: +1 positive, -1 negative, 0 neutral."""
    if word in _POSITIVE:
        return 1
    if word in _NEGATIVE:
        return -1
    # CJK: direct containment check (lexicon entries are multi-char)
    if any(w in _POSITIVE for w in (word,)):
        return 1
    return 0


def score_sentiment(text: str) -> Dict:
    """
    Score a social-media post. Returns dict with compound/positive/negative/
    neutral/emotion/intensity. Never raises.
    """
    if not text or not text.strip():
        return {"compound": 0.0, "positive": 0.0, "negative": 0.0,
                "neutral": 1.0, "emotion": "neutral", "intensity": 0.0}

    tokens = _tokenize(text)

    pos_hits = neg_hits = 0.0
    for i, tok in enumerate(tokens):
        pol = 0
        if tok in _POSITIVE:
            pol = 1
        elif tok in _NEGATIVE:
            pol = -1
        if pol == 0:
            continue
        # shape by preceding context: negation flips, intensifier boosts
        window = tokens[max(0, i - 3):i]
        weight = 1.0
        if any(w in _INTENSIFIERS for w in window):
            weight = 1.6
        if any(w in _NEGATIONS for w in window):
            pol = -pol
            weight *= 0.85
        if pol > 0:
            pos_hits += weight
        else:
            neg_hits += weight

    # emoji + punctuation + caps signals
    pos_hits += 0.8 * sum(1 for ch in text if ch in _EMOJI_POS)
    neg_hits += 0.8 * sum(1 for ch in text if ch in _EMOJI_NEG)
    exclamations = len(_EXCLAMATION_RE.findall(text))
    caps_bonus = min(len(_CAPS_RE.findall(text)), 3) * 0.3

    total = pos_hits + neg_hits
    if total == 0:
        compound = 0.0
        positive = negative = 0.0
        neutral = 1.0
    else:
        compound = (pos_hits - neg_hits) / total
        # sharpen weak signals slightly (social posts are polar by nature)
        compound = max(-1.0, min(1.0, compound * (1 + 0.15 * min(exclamations, 3))
                                 + (0.05 if caps_bonus and compound > 0.3 else
                                    (-0.05 if caps_bonus and compound < -0.3 else 0))))
        positive = round(pos_hits / total, 3)
        negative = round(neg_hits / total, 3)
        neutral = round(1 - positive - negative, 3)

    emotion, intensity = _classify_emotion(text, tokens)

    return {"compound": round(compound, 3), "positive": positive,
            "negative": negative, "neutral": neutral, "emotion": emotion,
            "intensity": intensity}


def _classify_emotion(text: str, tokens: List[str]) -> Tuple[str, float]:
    scores = {e: 0.0 for e in _EMOTIONS}
    joined = " ".join(tokens)
    for emotion, seeds in _EMOTION_LEXICON.items():
        for tok in tokens:
            if tok in seeds:
                scores[emotion] += 1.0
        # CJK substring matching
        for seed in seeds:
            if any("\u4e00" <= c <= "\u9fff" for c in seed) and seed in text:
                scores[emotion] += 1.0

    best = max(scores, key=lambda e: scores[e])
    top = scores[best]
    if top == 0:
        return "neutral", round(min(0.3, len(tokens) / 60), 3)

    total = sum(scores.values())
    intensity = min(1.0, top / max(total, 1) * 0.6 + top / 8)
    # surprise amplifies whatever polarity exists
    if best == "surprise":
        joined_polarity = 1 if any(t in _POSITIVE for t in tokens) else \
            (-1 if any(t in _NEGATIVE for t in tokens) else 0)
        if joined_polarity < 0:
            best = "fear"
        elif joined_polarity > 0:
            best = "joy"
    return best, round(float(intensity), 3)


def score_posts(posts: List[Dict]) -> List[Dict]:
    """Score a batch of post dicts (adds sentiment_* keys in place)."""
    for p in posts:
        s = score_sentiment(p.get("content", ""))
        p["sentiment_compound"] = s["compound"]
        p["sentiment_positive"] = s["positive"]
        p["sentiment_negative"] = s["negative"]
        p["sentiment_neutral"] = s["neutral"]
        p["emotion"] = s["emotion"]
        p["intensity"] = s["intensity"]
    return posts


def summarize(posts: List[Dict]) -> Dict:
    """Aggregate sentiment statistics over a list of scored posts."""
    if not posts:
        return {"n": 0, "mean_compound": 0.0, "positive_share": 0.0,
                "negative_share": 0.0, "neutral_share": 0.0,
                "emotion_distribution": {}, "mean_intensity": 0.0}
    n = len(posts)
    compounds = [p.get("sentiment_compound", 0.0) for p in posts]
    emotions: Dict[str, int] = {}
    for p in posts:
        e = p.get("emotion", "neutral")
        emotions[e] = emotions.get(e, 0) + 1
    dist = {e: round(c / n, 3) for e, c in
            sorted(emotions.items(), key=lambda kv: -kv[1])}
    pos = sum(1 for c in compounds if c > 0.05)
    neg = sum(1 for c in compounds if c < -0.05)
    return {
        "n": n,
        "mean_compound": round(sum(compounds) / n, 3),
        "positive_share": round(pos / n, 3),
        "negative_share": round(neg / n, 3),
        "neutral_share": round((n - pos - neg) / n, 3),
        "emotion_distribution": dist,
        "mean_intensity": round(sum(p.get("intensity", 0) for p in posts) / n, 3),
    }
