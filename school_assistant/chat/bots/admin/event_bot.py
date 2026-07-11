"""
Event Bot ("The Activity Director")
Scope: summarizes schedules, drafts parent alerts.
Example: "When's the next PTM scheduled?"
"""
import re

from django.utils import timezone

from chat.bots.base import BaseBot

_STOPWORDS = {
    "when", "is", "the", "next", "scheduled", "schedule", "for", "event",
    "events", "upcoming", "please", "tell", "me", "what", "about", "draft",
    "generate", "alert", "post", "announcement",
}


def _extract_keyword(text: str):
    words = re.findall(r"[A-Za-z]+", text.lower())
    candidates = [w for w in words if len(w) > 2 and w not in _STOPWORDS]
    return candidates


class EventBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Activity Director', the School ERP's Event Bot. You "
            "summarize upcoming/past school events and draft short parent alert "
            "messages when asked. Be upbeat but concise, like someone coordinating "
            "school activities. Base every date, venue, and name strictly on the "
            "context provided."
        )

    def build_context(self) -> str:
        from administration.models import SchoolEvent

        now = timezone.now()
        keywords = _extract_keyword(self.message)

        qs = SchoolEvent.objects.select_related("created_by_admin")
        matched_keyword = None
        for kw in keywords:
            if qs.filter(event_name__icontains=kw).exists():
                matched_keyword = kw
                break
        if matched_keyword:
            qs = qs.filter(event_name__icontains=matched_keyword)

        upcoming = qs.filter(event_date__gte=now).order_by("event_date")[:10]
        past = qs.filter(event_date__lt=now).order_by("-event_date")[:5]

        lines = []
        if matched_keyword:
            lines.append(f"Event name filter: '{matched_keyword}'")

        if upcoming:
            lines.append("Upcoming events:")
            for e in upcoming:
                lines.append(f"- {e.event_name} on {e.event_date:%Y-%m-%d %H:%M} at {e.venue or 'venue TBD'}")
        else:
            lines.append("No upcoming events found for this filter.")

        if past:
            lines.append("Recent past events:")
            for e in past:
                lines.append(f"- {e.event_name} on {e.event_date:%Y-%m-%d %H:%M} at {e.venue or 'unspecified venue'}")

        return "\n".join(lines)