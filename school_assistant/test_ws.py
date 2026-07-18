"""Full-coverage Admin bot test -- exercises all 11 READ + all 12 WRITE
tools. Where a WRITE tool needs a specific record, we first call the
matching READ tool, then refer to it in context ("pehli wali...") so the
Agent resolves the real name itself -- this also doubles as a multi-turn
context test.

EDIT THIS before running: a student name that actually exists in your DB,
used for the scholarship-assignment test (no READ tool exposes student
names directly, so this one can't be discovered from conversation).
"""
import asyncio
import json
import time
import requests
import websockets

BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"

EMAIL = "alizamuskan1054@gmail.com"
PASSWORD = "YourStrongPassword123"

STUDENT_NAME_FOR_SCHOLARSHIP = "Wanda Walter"  # <-- EDIT karo

CONVERSATION = [
    # ---------- READ tools (11) ----------
    ("READ 1/11: pending users",           "pending users batao"),
    ("READ 2/11: fee summary",             "is mahine ki fee kitni collect hui?"),
    ("READ 3/11: attendance stats",        "overall attendance kitni hai?"),
    ("READ 4/11: exam results",            "exam results batao"),
    ("READ 5/11: assignment compliance",   "assignment compliance batao"),
    ("READ 6/11: inventory status",        "inventory status batao"),
    ("WRITE 1/12: update_inventory (ctx)", "isme se pehli item ki quantity 999 kar do"),
    ("CONFIRM",                            "yes"),
    ("READ 7/11: events",                  "upcoming events batao"),
    ("WRITE 2/12: create_event",           "'Science Exhibition' naam ka event banao 2026-12-05 18:00 Main Hall mein"),
    ("CONFIRM",                            "yes"),
    ("WRITE 3/12: draft_social_caption",   "Science Exhibition ke liye ek exciting social media caption likho"),
    ("READ 8/11: open complaints",         "open complaints kitni hain?"),
    ("WRITE 4/12: resolve_ticket (ctx)",   "inme se pehli complaint resolve kar do"),
    ("CONFIRM",                            "yes"),
    ("READ 9/11: scholarship distribution", "scholarship distribution batao"),
    ("WRITE 5/12: assign_scholarship",     "STUDENT_PLACEHOLDER ko 50% scholarship do"),
    ("CONFIRM",                            "yes"),
    ("READ 10/11: certificate requests",   "certificate requests batao"),
    ("WRITE 6/12: approve_certificate (ctx)", "inme se pehli certificate request approve kar do"),
    ("CONFIRM",                            "yes"),
    ("READ 11/11: notification history",   "notification history batao"),
    ("WRITE 7/12: send_notification",      "Teacher role ko ye message bhejo: 'Kal staff meeting hai 9 baje'"),
    ("CONFIRM",                            "yes"),
    ("WRITE 8/12: create_class_section",   "Class 11 section C banao"),
    ("CONFIRM",                            "yes"),
    ("WRITE 9/12: create_subject",         "Computer Science subject banao 11-C ke liye"),
    ("CONFIRM",                            "yes"),
    ("WRITE 10/12: create_timetable_entry", "11-C ke liye Computer Science ka slot banao Monday 10:00-11:00"),
    ("CONFIRM",                            "yes"),
    ("WRITE 11/12: approve_user (name)",   "pending users mein se pehle wale ko approve kar do"),
    ("CONFIRM",                            "yes"),
    ("WRITE 12/12: reject_user (name)",    "baaki bache pending users ko reject kar do"),
    ("CONFIRM",                            "yes"),
]


async def main():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    token = r.json()["access"]
    print("Logged in\n")

    r = requests.post(f"{BASE}/api/chat/sessions", json={}, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    session_id = r.json()["id"]
    print(f"Session #{session_id} created\n")

    uri = f"{WS_BASE}/ws/chat/{session_id}/?token={token}"
    start = time.time()

    async with websockets.connect(uri) as ws:
        print("WebSocket connected\n" + "=" * 70 + "\n")

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(raw)
            if data.get("type") == "message":
                print(f"WELCOME:\n{data['content']}\n" + "-" * 70 + "\n")
        except asyncio.TimeoutError:
            print("Koi welcome message nahi mila\n")

        conversation = CONVERSATION.copy()
        for i, (label, msg) in enumerate(conversation):
            if "STUDENT_PLACEHOLDER" in msg:
                msg = msg.replace("STUDENT_PLACEHOLDER", STUDENT_NAME_FOR_SCHOLARSHIP)

            elapsed = round(time.time() - start, 1)
            print(f"[{elapsed}s] [{label}]")
            print(f"You: {msg}")
            await ws.send(json.dumps({"message": msg}))

            while True:
                raw = await ws.recv()
                data = json.loads(raw)
                if data.get("type") in ("typing", "ping"):
                    continue
                if data.get("type") == "message":
                    elapsed = round(time.time() - start, 1)
                    print(f"[{elapsed}s] Bot:\n{data['content']}")
                    break
                if data.get("type") == "error":
                    print(f"Error: {data['error']}")
                    break
            print("-" * 70 + "\n")

        total = round(time.time() - start, 1)
        print(f"Full test complete after {total}s -- {len(CONVERSATION)} exchanges, all 23 tools exercised.")


asyncio.run(main())