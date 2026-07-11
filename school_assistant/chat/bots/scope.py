"""
Keyword-based scope directory for every Admin bot.

This is a deterministic (not LLM-dependent) way to catch clearly
out-of-scope questions -- e.g. asking the Fee Bot about attendance.
Each bot_type maps to a human-readable label (matches the persona in
that bot's system_prompt) and a list of keywords/phrases that signal a
question genuinely belongs to that bot's domain.

Matching is typo-tolerant: single-word keywords are also checked with
fuzzy similarity (difflib), so a misspelling like "schoashi" still
matches "scholarship". Multi-word phrases ("financial aid") are matched
as plain substrings -- phrases are rare enough in short questions that
fuzzy-matching them isn't worth the false-positive risk.

Used by BaseBot.get_response() BEFORE any DB query or LLM call runs,
so an out-of-scope question never wastes a query or an API call --
it gets an instant, consistent redirect message instead.
"""
import re
import difflib

FUZZY_CUTOFF = 0.82          # 0-1, higher = stricter (0.82 catches 1-2 typo'd letters)
MIN_WORD_LEN_FOR_FUZZY = 4    # don't fuzzy-match very short words -- too many false hits

BOT_SCOPE = {
    "fee": {
        "label": "Fee Bot (The Accountant)",
        "keywords": [
            "fee", "fees", "payment", "payments", "paid", "unpaid", "due",
            "dues", "balance", "collection", "collected", "revenue",
            "invoice", "tuition", "receipt", "installment",
        ],
    },
    "attendance": {
        "label": "Attendance & Compliance Bot (The Registrar)",
        "keywords": [
            "attendance", "present", "absent", "absentee", "leave",
            "behavior", "behaviour", "discipline", "disciplinary",
        ],
    },
    "assignment": {
        "label": "Assignment Bot (The Course Coordinator)",
        "keywords": [
            "assignment", "assignments", "homework", "submission",
            "submissions", "submitted", "submit", "deadline",
        ],
    },
    "exam": {
        "label": "Exam Bot (The Academic Evaluator)",
        "keywords": [
            "exam", "exams", "grade", "grades", "marks", "result",
            "results", "topper", "score", "scorer", "test", "quiz",
            "midterm", "mid-term", "fail rate", "gpa",
        ],
    },
    "certificate": {
        "label": "Certificates Bot (The Document Writer)",
        "keywords": [
            "certificate", "certificates", "leaving certificate",
            "clearance", "clearance letter", "appreciation letter",
            "appreciation", "letter", "draft letter",
        ],
    },
    "scholarship": {
        "label": "Scholarship Bot (The Financial Aid Officer)",
        "keywords": [
            "scholarship", "scholarships", "concession", "concessions",
            "discount", "financial aid", "waiver",
        ],
    },
    "inventory": {
        "label": "Inventory Bot (The Store Manager)",
        "keywords": [
            "inventory", "stock", "item", "items", "asset", "assets",
            "laptop", "laptops", "furniture", "equipment", "store",
        ],
    },
    "event": {
        "label": "Event Bot (The Activity Director)",
        "keywords": [
            "event", "events", "ptm", "function", "sports day",
            "ceremony", "schedule", "annual day",
        ],
    },
    "maintenance": {
        "label": "Maintenance & Help Desk Bot (The Repair Supervisor)",
        "keywords": [
            "maintenance", "repair", "repairs", "broken", "fix", "ticket",
            "tickets", "complaint", "complaints", "infrastructure",
            "wifi", "electricity", "plumbing",
        ],
    },
    "media": {
        "label": "Media Bot (The Social Media Manager)",
        "keywords": [
            "post", "caption", "social media", "facebook", "linkedin",
            "publish", "announcement", "campaign",
        ],
    },
}


def _words(text_l: str):
    return re.findall(r"[a-z]+", text_l)


def _fuzzy_word_match(word: str, keyword: str) -> bool:
    if word == keyword:
        return True
    if len(word) < MIN_WORD_LEN_FOR_FUZZY or len(keyword) < MIN_WORD_LEN_FOR_FUZZY:
        return False
    return difflib.SequenceMatcher(None, word, keyword).ratio() >= FUZZY_CUTOFF


def bot_keyword_hit(bot_type: str, text_l: str) -> bool:
    """True if the message plausibly mentions bot_type's domain (exact or typo-tolerant)."""
    info = BOT_SCOPE.get(bot_type)
    if not info:
        return False

    words = _words(text_l)
    for kw in info["keywords"]:
        if " " in kw:
            if kw in text_l:
                return True
        else:
            if any(_fuzzy_word_match(w, kw) for w in words):
                return True
    return False


def find_other_matching_bot(current_bot_type: str, text_l: str):
    """Returns the label of another bot whose keywords match this message, if any."""
    for bot_type, info in BOT_SCOPE.items():
        if bot_type == current_bot_type:
            continue
        if bot_keyword_hit(bot_type, text_l):
            return info["label"]
    return None