"""Offline deterministic simulation content — the demo pack.

Every generator is seeded, so a run with the same seed replays bit-for-bit.
This powers DEMO MODE (no API key) and acts as fallback if the LLM fails.
"""
import random

FIRST = ["Maya", "Leo", "Sofia", "Arjun", "Elena", "Marcus", "Priya", "Jonas",
         "Aisha", "Tom", "Nadia", "Felix", "Grace", "Omar", "Lena", "David",
         "Zara", "Kenji", "Ines", "Victor", "Amara", "Ravi", "Clara", "Sam",
         "Yuki", "Oliver", "Tara", "Noah", "Iris", "Diego", "Hana", "Peter",
         "Leila", "Ethan", "Nina", "Oscar", "Mia", "Rafael", "June", "Alex"]
LAST = ["Chen", "Alvarez", "Novak", "Rao", "Petrova", "Okafor", "Kim",
        "Larsen", "Haddad", "Weber", "Tanaka", "Moreau", "Silva", "Novikova",
        "Adeyemi", "Fischer", "Costa", "Nakamura", "Berg", "Mensah", "Ito",
        "Romero", "Kaur", "Lindqvist", "Dubois", "Santos", "Vogel", "Cho",
        "Farouk", "Marino", "Quinn", "Sato", "Ali", "Brandt", "Cruz", "Deshpande"]

ARCHETYPES = [
    ("Market Analyst", 0.16), ("Influencer", 0.14), ("Policy Expert", 0.12),
    ("Journalist", 0.12), ("Community Activist", 0.10), ("Startup Founder", 0.10),
    ("Data Scientist", 0.10), ("Academic", 0.08), ("PR Strategist", 0.08),
]

GENERIC_TOPICS = [
    "the announcement", "market reaction", "regulatory review", "public trust",
    "media framing", "job impact", "adoption curve", "competitive response",
    "the official statement", "community sentiment", "risk assessment",
    "long-term effects", "viral narratives", "expert consensus", "policy outlook",
]

# Action templates keyed by sentiment polarity. {i}=interest {t}=topic {o}=other agent
POST_TEMPLATES = {
    "pos": [
        "Honestly optimistic about {i} — the fundamentals here are stronger than critics admit.",
        "Big picture: {t} is accelerating progress, not blocking it. Watching closely.",
        "This is the most encouraging signal we've seen on {t} in months.",
        "Credit where due — whoever drove {i} read the room perfectly.",
        "Holding my position: {t} looks like a net win for most people.",
        "If {t} keeps trending this way, the upside case writes itself.",
    ],
    "neg": [
        "I can't be the only one uneasy about {t}. The risks are being waved away.",
        "Every cycle of hype around {i} ends the same way. Caution.",
        "The framing on {t} conveniently ignores who pays the cost.",
        "Deeply skeptical of {t} — we've seen this movie before.",
        "This reads like damage control on {i}, not substance.",
        "Mark my words: {t} is where this story turns sour.",
    ],
    "neu": [
        "Two things can be true about {t}. Waiting for harder data.",
        "Still mapping the second-order effects of {i}. Too early to call.",
        "Noticing the loudest voices on {t} have the least evidence.",
        "Tracking {t}: the signal-to-noise ratio is rough right now.",
        "Before hot takes on {i}, let's look at the actual timeline.",
        "Question worth asking about {t}: who benefits, who absorbs the risk?",
    ],
}
REPLY_TEMPLATES = {
    "pos": ["@{o} exactly this — {t} is being undersold, not oversold.",
            "@{o} agree, and I'd add: the momentum behind {i} is real.",
            "@{o} well said. The pessimists on {t} keep moving goalposts."],
    "neg": ["@{o} respectfully disagree — {t} deserves far more scrutiny.",
            "@{o} you're reading {i} too generously. Look at the incentives.",
            "@{o} counterpoint: {t} could easily break the other way."],
    "neu": ["@{o} both sides of {t} have a point, which is exactly the problem.",
            "@{o} fair take. The honest answer on {i} is still 'it depends'.",
            "@{o} interesting — but {t} needs a control group, not vibes."],
}
ENDORSE_TEMPLATES = {
    "pos": ["This. ⤴ The clearest take on {t} yet.",
            "Signal-boosting @{o} on {i} — more people should see this."],
    "neg": ["Quoting because @{o}'s read on {t} aged poorly already.",
            "Savage but fair thread on {i}."],
    "neu": ["Bookmarking this analysis of {t}.",
            "@{o} raises the question nobody wanted to ask about {i}."],
}
DISPUTE_TEMPLATES = {
    "pos": ["The doom-posting about {t} is out of step with the data.",
            "Disagree with the consensus: {i} is trending better than feared."],
    "neg": ["Strongly disagree with @{o}: {t} is not 'fine', it's fragile.",
            "Calling it now — the optimism around {i} is misplaced."],
    "neu": ["Pushing back on @{o}: {t} is messier than either side admits.",
            "Unpopular view: {i} is neither triumph nor disaster. It's a tradeoff."],
}

GOALS = [
    "Shape the narrative before it hardens",
    "Protect my community from the fallout",
    "Be first to call the turning point",
    "Keep the debate honest and evidence-based",
    "Grow my audience with sharp takes",
    "Watch for regulatory red flags",
    "Find the angle everyone else missed",
    "Translate expert knowledge for the public",
]

BIO_TEMPLATES = [
    "{arch} focused on {i1} and {i2}. Posts daily, argues weekly.",
    "{arch} watching {i1}. Skeptical of hype, loyal to data.",
    "Independent {arch}. Known for early calls on {i2}.",
    "{arch} — previously wrong about {i1}, determined to be right about {i2}.",
    "Career {arch}. Believes {i1} decides the next decade.",
]

EVENT_KEYWORDS_NEG = ["scandal", "crash", "ban", "lawsuit", "leak", "fraud",
                      "outage", "recall", "layoffs", "breach", "fine", "collapse",
                      "crisis", "resign"]
EVENT_KEYWORDS_POS = ["launch", "partnership", "breakthrough", "approval",
                      "growth", "record", "deal", "funding", "win", "reversal",
                      "upgrade", "expansion"]

REPORT_OPENINGS = [
    "The swarm converged on a cautious but legible trajectory.",
    "Agent interactions produced a clear majority narrative with a vocal minority faction.",
    "Emergent behavior settled into a stable pattern after early volatility.",
]


def classify_event(text: str, rng: random.Random) -> float:
    """Rough polarity of an injected event, in [-1, 1]."""
    t = text.lower()
    score = 0.0
    for w in EVENT_KEYWORDS_NEG:
        if w in t:
            score -= 0.5
    for w in EVENT_KEYWORDS_POS:
        if w in t:
            score += 0.5
    if score == 0:
        score = rng.uniform(-0.25, 0.25)
    return max(-1.0, min(1.0, score))


def pick_template(rng: random.Random, table: dict, sentiment: float) -> str:
    key = "pos" if sentiment > 0.15 else "neg" if sentiment < -0.15 else "neu"
    return rng.choice(table[key])
