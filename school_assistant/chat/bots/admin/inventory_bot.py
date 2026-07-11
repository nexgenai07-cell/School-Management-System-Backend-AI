"""
Inventory Bot ("The Store Manager")
Scope: checks stock status of assets.
Example: "How many functional laptops are in the computer lab?"
"""
import re

from chat.bots.base import BaseBot

_STOPWORDS = {
    "how", "many", "much", "is", "are", "the", "in", "of", "there", "functional",
    "working", "broken", "items", "item", "check", "stock", "status", "show",
    "list", "please", "tell", "me", "give",
}


def _extract_keywords(text: str):
    words = re.findall(r"[A-Za-z]+", text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


class InventoryBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Store Manager', the School ERP's Inventory Bot. You report "
            "stock counts of school assets by item and location. Be precise with "
            "numbers. Note: this system currently only tracks total quantity per "
            "item + room + category -- it does NOT track individual condition "
            "(working/broken) per unit. If asked about 'functional' or 'broken' "
            "items, say the system tracks total quantity only and give that count, "
            "rather than inventing a functional/broken split."
        )

    def build_context(self) -> str:
        from administration.models import Inventory

        keywords = _extract_keywords(self.message)
        qs = Inventory.objects.all()

        matched_item = None
        matched_room = None
        for kw in keywords:
            if not matched_item:
                item_match = qs.filter(item_name__icontains=kw).first()
                if item_match:
                    matched_item = kw
            if not matched_room:
                room_match = qs.filter(assigned_to_room__icontains=kw).first()
                if room_match:
                    matched_room = kw

        filtered = qs
        lines = []
        if matched_item:
            filtered = filtered.filter(item_name__icontains=matched_item)
            lines.append(f"Item filter: '{matched_item}'")
        if matched_room:
            filtered = filtered.filter(assigned_to_room__icontains=matched_room)
            lines.append(f"Room filter: '{matched_room}'")

        filtered = filtered.order_by("assigned_to_room", "item_name")[:50]

        if not filtered:
            lines.append("No matching inventory items found.")
            return "\n".join(lines)

        total_qty = sum(i.total_quantity for i in filtered)
        lines.append(f"Matching items: {filtered.count()}, total quantity: {total_qty}")
        for item in filtered:
            lines.append(
                f"- {item.item_name} [{item.category}]: {item.total_quantity} units "
                f"@ {item.assigned_to_room or 'unassigned room'} "
                f"(last updated: {item.last_updated:%Y-%m-%d})"
            )

        return "\n".join(lines)