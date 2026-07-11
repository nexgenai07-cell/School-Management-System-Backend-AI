"""
Media Bot ("The Social Media Manager")
Scope: generates social captions from existing school updates/achievements.
Example: "Generate an FB post for Annual Sports Day."

Note: this bot only *drafts* caption text. Actually publishing to
Facebook/LinkedIn goes through the existing Make.com webhook + the
MediaCampaignLog record, which the Admin triggers separately after
approving the draft here.
"""
import re

from django.utils import timezone

from chat.bots.base import BaseBot

_STOPWORDS = {
    "generate", "write", "draft", "post", "for", "about", "the", "facebook",
    "linkedin", "fb", "caption", "please", "make", "create", "announcement",
}


def _extract_keyword(text: str):
    words = re.findall(r"[A-Za-z]+", text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


class MediaBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Social Media Manager', the School ERP's Media Bot. You "
            "draft short, engaging Facebook/LinkedIn captions celebrating school "
            "achievements and events. Use an upbeat, professional school-brand "
            "tone with relevant emojis and 2-4 hashtags. Base every fact (event "
            "name, date, winner names) strictly on the context provided -- never "
            "invent details you don't have. If nothing relevant is found, say so "
            "and ask the Admin for more specifics instead of making something up."
        )

    def build_context(self) -> str:
        from administration.models import SchoolEvent, EventParticipation

        keywords = _extract_keyword(self.message)
        events_qs = SchoolEvent.objects.all()

        matched_keyword = None
        for kw in keywords:
            if events_qs.filter(event_name__icontains=kw).exists():
                matched_keyword = kw
                break

        if matched_keyword:
            events_qs = events_qs.filter(event_name__icontains=matched_keyword)

        events_qs = events_qs.order_by("-event_date")[:5]

        lines = []
        if matched_keyword:
            lines.append(f"Event name filter: '{matched_keyword}'")

        if not events_qs:
            lines.append("No matching school events found for this request.")
            return "\n".join(lines)

        for event in events_qs:
            when = "upcoming" if event.event_date >= timezone.now() else "past"
            lines.append(f"Event: {event.event_name} ({when}), {event.event_date:%Y-%m-%d}, venue: {event.venue or 'TBD'}")
            participants = (
                EventParticipation.objects.filter(event=event)
                .select_related("student__user")
                .exclude(position="")
                .order_by("position")[:10]
            )
            if participants:
                lines.append("  Notable results/winners:")
                for p in participants:
                    lines.append(f"  - {p.student.user.full_name}: {p.position or p.role}")

        return "\n".join(lines)