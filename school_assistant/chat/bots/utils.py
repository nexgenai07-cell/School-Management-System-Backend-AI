"""
Lightweight intent / entity extraction helpers shared by every Admin bot.

This is intentionally NOT a full NLP pipeline -- it's a set of small,
predictable regex + keyword parsers that pull out the handful of things
an Admin's question typically contains (a class-section, a student, a
date range, a percentage threshold). Each bot uses whichever of these
apply to its domain, then narrows its DB query with them instead of
always dumping the entire table into the LLM's context.

If nothing is found, every function safely returns None (or an empty
queryset for `resolve_class_section`) so a bot can fall back to a
sensible default (e.g. "this month", "all sections").
"""
import re
import calendar
from datetime import timedelta
from django.utils import timezone

MONTH_NAMES = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTH_NAMES.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})


def extract_class_section(text: str):
    """
    Finds things like '10-A', '10 A', 'class 9-B', 'Grade 6 C'.
    Returns (class_name, section) tuple or None.
    """
    match = re.search(r"\b(\d{1,2})\s*[-/]?\s*([A-Za-z])\b", text)
    if match:
        return match.group(1), match.group(2).upper()
    return None


def resolve_class_section(text: str):
    """Returns a ClassSection queryset filtered from the message, or None if not mentioned."""
    from academics.models import ClassSection

    found = extract_class_section(text)
    if not found:
        return None
    class_name, section = found
    qs = ClassSection.objects.filter(class_name__iexact=class_name, section__iexact=section)
    return qs.first()


def extract_roll_number(text: str):
    """Matches roll-number-like tokens, e.g. 'STU-2024-011', 'R1023'."""
    match = re.search(r"\b([A-Za-z]{2,6}-?\d{2,6}(?:-\d{1,4})?)\b", text)
    return match.group(1) if match else None


def resolve_student(text: str):
    """
    Tries to resolve a single StudentProfile mentioned by name or roll
    number in free text. Returns a StudentProfile instance or None.
    """
    from accounts.models import StudentProfile

    roll = extract_roll_number(text)
    if roll:
        student = StudentProfile.objects.filter(roll_number__iexact=roll).select_related("user").first()
        if student:
            return student

    # Fall back to a loose name match: try progressively shorter windows
    # of consecutive capitalized-looking words (handles "Zain Ali", etc.)
    words = re.findall(r"[A-Za-z]+", text)
    candidates = [w for w in words if len(w) > 2 and w.lower() not in _STOPWORDS]
    for window in (3, 2, 1):
        for i in range(len(candidates) - window + 1):
            phrase = " ".join(candidates[i:i + window])
            match = (
                StudentProfile.objects.filter(user__full_name__icontains=phrase)
                .select_related("user")
                .first()
            )
            if match:
                return match
    return None


def extract_date_range(text: str, default_days: int = None):
    """
    Parses common date-range phrases into (start_date, end_date) using
    Asia/Karachi "today". Recognizes: 'this month', 'last month',
    'last N days', 'this year', a bare month name (with optional year).

    If nothing is recognized: defaults to the last `default_days` days
    when given, otherwise the current calendar month.
    """
    text_l = text.lower()
    today = timezone.localdate()

    days_match = re.search(r"last\s+(\d{1,3})\s+days?", text_l)
    if days_match:
        n = int(days_match.group(1))
        return today - timedelta(days=n), today

    if "last month" in text_l:
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        return last_month_end.replace(day=1), last_month_end

    if "this year" in text_l:
        return today.replace(month=1, day=1), today

    for name, month_num in MONTH_NAMES.items():
        if re.search(rf"\b{name}\b", text_l):
            year_match = re.search(r"\b(20\d{2})\b", text_l)
            year = int(year_match.group(1)) if year_match else today.year
            last_day = calendar.monthrange(year, month_num)[1]
            from datetime import date
            return date(year, month_num, 1), date(year, month_num, last_day)

    if default_days is not None:
        return today - timedelta(days=default_days), today

    # Default: "this month" (also covers no date mentioned at all)
    first_of_month = today.replace(day=1)
    return first_of_month, today


def extract_percentage(text: str, default: int = 75):
    """Finds a threshold like '75%' or 'below 80 percent'. Defaults to 75."""
    match = re.search(r"(\d{1,3})\s*(?:%|percent)", text.lower())
    if match:
        return min(int(match.group(1)), 100)
    return default


def resolve_subject(text: str):
    """Loosely matches a Subject by name mentioned anywhere in the text."""
    from academics.models import Subject

    words = re.findall(r"[A-Za-z]+", text)
    candidates = [w for w in words if len(w) > 2 and w.lower() not in _STOPWORDS]
    for window in (2, 1):
        for i in range(len(candidates) - window + 1):
            phrase = " ".join(candidates[i:i + window])
            match = Subject.objects.filter(subject_name__icontains=phrase).first()
            if match:
                return match
    return None


def extract_exam_type(text: str):
    """Maps loose phrasing ('finals', 'mid term', 'quiz') to a Grade.EXAM_TYPE_CHOICES value."""
    text_l = text.lower()
    if "final" in text_l:
        return "Final"
    if "mid" in text_l and "term" in text_l:
        return "Mid-Term"
    if "quiz" in text_l:
        return "Quiz"
    if "assignment" in text_l:
        return "Assignment"
    return None


_STOPWORDS = {
    "the", "and", "for", "how", "many", "much", "who", "what", "when", "where",
    "this", "that", "with", "has", "have", "not", "yet", "are", "was", "were",
    "class", "section", "month", "year", "student", "students", "please",
    "show", "list", "give", "tell", "about", "from", "which", "term", "topper",
    "finals", "exam", "results",
}