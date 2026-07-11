"""
Maintenance & Help Desk Bot ("The Repair Supervisor")
Scope: tracks broken infrastructure and open repair tickets reported by teachers.
Example: "Which room's AC has been reported broken?"
"""
import re

from chat.bots.base import BaseBot

_STOPWORDS = {
    "which", "has", "have", "been", "reported", "broken", "is", "the", "for",
    "please", "tell", "me", "show", "list", "open", "status", "still",
}

MAINTENANCE_KEYWORDS = [
    "ac", "electric", "wifi", "internet", "furniture", "chair", "desk",
    "infrastructure", "repair", "maintenance", "leak", "plumbing", "fan",
    "projector", "light", "door", "window", "wall", "roof", "water",
]


def _extract_keyword(text: str):
    words = re.findall(r"[A-Za-z]+", text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


class MaintenanceBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Repair Supervisor', the School ERP's Maintenance & Help "
            "Desk Bot. You track infrastructure complaints and open repair tickets "
            "reported by teachers/staff. Be practical and action-oriented, like "
            "someone managing a facilities team."
        )

    def build_context(self) -> str:
        from administration.models import Complaint
        from django.db.models import Q

        keywords = _extract_keyword(self.message)

        qs = Complaint.objects.filter(against_user__isnull=True).select_related("reporter")

        matched_keyword = None
        for kw in keywords + MAINTENANCE_KEYWORDS:
            if qs.filter(complaint_type__icontains=kw).exists() or qs.filter(description__icontains=kw).exists():
                matched_keyword = kw
                break
        if matched_keyword:
            qs = qs.filter(Q(complaint_type__icontains=matched_keyword) | Q(description__icontains=matched_keyword))

        open_qs = qs.filter(status__in=["Open", "In Progress"]).order_by("-created_at")
        open_count = open_qs.count()
        open_tickets = open_qs[:25]
        resolved_recent = qs.filter(status="Resolved").order_by("-resolved_at")[:5]

        lines = []
        if matched_keyword:
            lines.append(f"Keyword filter: '{matched_keyword}'")

        lines.append(f"Open/In-Progress tickets: {open_count}")
        if open_tickets:
            lines.append("Open tickets:")
            for c in open_tickets:
                lines.append(
                    f"- #{c.id} [{c.status}] {c.complaint_type}: {c.description[:120]} "
                    f"(reported by {c.reporter.full_name} on {c.created_at:%Y-%m-%d})"
                )
        else:
            lines.append("No open maintenance tickets found for this filter.")

        if resolved_recent:
            lines.append("Recently resolved tickets:")
            for c in resolved_recent:
                # ✅ SAFE: Check if resolved_at exists before formatting
                if c.resolved_at:
                    resolved_date = c.resolved_at.strftime('%Y-%m-%d')
                else:
                    resolved_date = 'Unknown date'
                lines.append(f"- #{c.id} {c.complaint_type}: resolved on {resolved_date}")

        return "\n".join(lines)