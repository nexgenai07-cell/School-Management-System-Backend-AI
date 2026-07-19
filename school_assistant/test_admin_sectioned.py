"""
Sectioned Admin bot test -- same coverage as test_admin_full_coverage.py,
but split into small independent sections so you can test ONE category
at a time instead of the full ~700s run.

USAGE:
    python test_admin_sectioned.py list                 -> shows all section names
    python test_admin_sectioned.py rooms                -> runs only the "rooms" section
    python test_admin_sectioned.py classes_subjects_timetable
    python test_admin_sectioned.py all                  -> runs everything (same as the full test)

Run sections roughly in this order the first few times (later sections
assume earlier ones already created some data, e.g. "Physics Lab" room,
"12-D" class):
    rooms -> users_read -> events -> inventory -> tickets -> notifications
    -> stats -> classes_subjects_timetable -> student_profile
    -> teacher_parent_profile -> far_ctx -> finance -> approve_reject
    -> delete_accounts -> caption

EDIT THESE before running any section that needs them:
"""
import asyncio
import json
import sys
import time
import requests
import websockets

BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"

EMAIL = "alizamuskan1054@gmail.com"
PASSWORD = "YourStrongPassword123"

# ---- non-destructive test subjects (existing, active records) ----
STUDENT_NAME_FOR_TESTS = "Ashley Guerra"          # <-- EDIT karo
TEACHER_NAME_FOR_TESTS = "Megan Moore"  # <-- EDIT karo
PARENT_NAME_FOR_TESTS = "Roberto Alvarado"    # <-- EDIT karo

# ---- ⚠️ DESTRUCTIVE -- throwaway accounts ONLY, will be permanently deleted ----
STUDENT_NAME_FOR_DELETE_TEST = "Ryan Blair"  # <-- EDIT karo
TEACHER_NAME_FOR_DELETE_TEST = "Evelyn Dixon"  # <-- EDIT karo
PARENT_NAME_FOR_DELETE_TEST = "Brendan Rodriguez"    # <-- EDIT karo

PLACEHOLDERS = {
    "STUDENT_NAME_FOR_TESTS": STUDENT_NAME_FOR_TESTS,
    "TEACHER_NAME_FOR_TESTS": TEACHER_NAME_FOR_TESTS,
    "PARENT_NAME_FOR_TESTS": PARENT_NAME_FOR_TESTS,
    "STUDENT_NAME_FOR_DELETE_TEST": STUDENT_NAME_FOR_DELETE_TEST,
    "TEACHER_NAME_FOR_DELETE_TEST": TEACHER_NAME_FOR_DELETE_TEST,
    "PARENT_NAME_FOR_DELETE_TEST": PARENT_NAME_FOR_DELETE_TEST,
}

SECTIONS = {

    "rooms": [
        ("READ [list_rooms] 1/22",                     "sab rooms ki list do"),
        ("WRITE [create_room] 1/37",                    "'Physics Lab' naam ka room banao, block A mein, capacity 35"),
        ("CONFIRM",                                     "yes"),
        ("CTX WRITE [update_room] 2/37",                "Physics Lab ki capacity 40 kar do"),
        ("CONFIRM",                                     "yes"),
        ("SETUP (create_room for delete test)",         "'TempRoomDelete' naam ka room banao capacity 10"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_room] 3/37",                    "TempRoomDelete room delete kar do"),
        ("CONFIRM",                                     "yes"),
    ],

    "users_read": [
        ("READ [list_users] 2/22",                      "sab active teachers ki list do"),
        ("CTX READ [get_user_details] 3/22",            "pehle wale teacher ki details do"),
        ("READ [get_pending_users] 4/22",               "pending users batao"),
    ],

    "events": [
        ("READ [get_events] 5/22",                      "upcoming events batao"),
        ("WRITE [create_event] propose",                "'Annual Sports Day' event banao 2026-11-15 09:00 Main Ground mein"),
        ("SWITCH TEST -- unrelated Q while pending",    "achha ye batao, inventory mein kitna saman hai?"),
        ("CONFIRM (finally confirms create_event)",     "yes"),
        ("CTX WRITE [update_event] 5/37",               "Annual Sports Day ka venue 'Sports Complex' kar do"),
        ("CONFIRM",                                     "yes"),
        ("SETUP (create_event for delete test)",        "'TempEventDelete' naam ka event banao 2026-01-01 10:00"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_event] 6/37",                   "TempEventDelete event delete kar do"),
        ("CONFIRM",                                     "yes"),
    ],

    "inventory": [
        ("READ [get_inventory_status] 6/22",            "inventory status batao"),
        ("WRITE [create_inventory] 7/37",               "'Projector' naam ka item add karo, category Electronics, quantity 5, room Physics Lab"),
        ("CONFIRM",                                     "yes"),
        ("CTX WRITE [update_inventory] 8/37",           "Physics Lab wale Projector ki quantity 8 kar do"),
        ("CONFIRM",                                     "yes"),
        ("SETUP (create_inventory for delete test)",    "'TempItemDelete' item add karo category Misc quantity 1"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_inventory] 9/37",               "TempItemDelete ko inventory se delete kar do"),
        ("CONFIRM",                                     "yes"),
    ],

    "tickets": [
        ("READ [get_open_tickets] 7/22",                "open complaints kitni hain?"),
        ("CTX WRITE [resolve_ticket] 10/37",            "inme se pehli complaint resolve kar do, remarks: 'Sorted'"),
        ("CONFIRM",                                     "yes"),
    ],

    "notifications": [
        ("READ [get_notification_history] 9/22",        "notification history batao"),
        ("WRITE [send_notification] 12/37",             "Student role ko ye message bhejo: 'Kal school mein half day hai'"),
        ("CONFIRM",                                     "yes"),
    ],

    "stats": [
        ("READ [get_scholarship_distribution] 10/22",   "scholarship distribution batao"),
        ("READ [get_attendance_stats] 11/22",           "overall attendance kitni hai?"),
        ("READ [get_exam_results] 12/22",               "exam results batao"),
        ("READ [get_assignment_compliance] 13/22",      "assignment compliance batao"),
    ],

    "classes_subjects_timetable": [
        ("READ [list_classes] 14/22",                   "sab classes batao"),
        ("WRITE [create_class_section] 13/37",          "Class 12 section D banao, room Physics Lab"),
        ("CONFIRM",                                     "yes"),
        ("READ [get_class_details] 15/22",              "12-D ki details do"),
        ("WRITE [update_class_section] 14/37",          "12-D ka teacher-in-charge TEACHER_NAME_FOR_TESTS laga do"),
        ("CONFIRM",                                     "yes"),
        ("SETUP (create_class_section for delete test)","Class 99 section Z banao"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_class_section] 15/37",          "99-Z class delete kar do"),
        ("CONFIRM",                                     "yes"),
        ("READ [list_subjects] 16/22",                  "12-D ke subjects batao"),
        ("WRITE [create_subject] 16/37",                "'AI Fundamentals' subject banao 12-D ke liye, teacher TEACHER_NAME_FOR_TESTS"),
        ("CONFIRM",                                     "yes"),
        ("CTX WRITE [update_subject] 17/37",            "AI Fundamentals ka naam 'Applied AI' kar do 12-D mein"),
        ("CONFIRM",                                     "yes"),
        ("SETUP (create_subject for delete test)",      "'TempSubjDelete' subject banao 12-D ke liye"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_subject] 18/37",                "TempSubjDelete ko 12-D se delete kar do"),
        ("CONFIRM",                                     "yes"),
        ("READ [list_timetable] 17/22",                 "12-D ka timetable batao"),
        ("WRITE [create_timetable_entry] 19/37",        "12-D ke liye Applied AI ka slot banao Wednesday 11:00-12:00, teacher TEACHER_NAME_FOR_TESTS, room Physics Lab"),
        ("CONFIRM",                                     "yes"),
        ("CTX WRITE [update_timetable_entry] 20/37",    "isi slot ka end time 12:30 kar do"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_timetable_entry] 21/37",        "12-D ka Wednesday 11:00 wala Applied AI slot delete kar do"),
        ("CONFIRM",                                     "yes"),
    ],

    "student_profile": [
        ("READ [get_student_profile] 18/22",            "STUDENT_NAME_FOR_TESTS ka profile batao"),
        ("WRITE [update_student_profile] 22/37",        "STUDENT_NAME_FOR_TESTS ka guardian phone 03001234567 kar do"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [assign_scholarship] 23/37",            "STUDENT_NAME_FOR_TESTS ko 50% scholarship do"),
        ("CONFIRM",                                     "yes"),
    ],

    "teacher_parent_profile": [
        ("WRITE [update_teacher_profile] 24/37",        "TEACHER_NAME_FOR_TESTS ki specialization 'AI & ML' set kar do"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [update_parent_profile] 25/37",         "PARENT_NAME_FOR_TESTS ka profile update kar do"),
        ("CONFIRM",                                     "yes"),
    ],

    "far_ctx": [
        ("FAR-CTX TEST -- references complaint from many turns ago",
         "wo complaint jo humne shuru mein resolve ki thi, uske remarks kya the?"),
    ],

    "finance": [
        ("WRITE [create_fee_structure] propose",        "12-D ke liye monthly fee Rs.5000 set karo"),
        ("SWITCH TEST -- unrelated Q while pending",    "achha ye batao TEACHER_NAME_FOR_TESTS ka schedule kya hai?"),
        ("CONFIRM (finally confirms create_fee_structure)", "yes"),
        ("READ [get_fee_summary] 19/22",                "is mahine ki fee summary batao"),
        ("CTX WRITE [update_fee_structure] 27/37",      "12-D ki fee Rs.5500 kar do"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [generate_monthly_challans] 28/37 ⚠️ generates for ALL students -- dev/test DB only",
         "2026-08 ke liye sab students ke challans generate karo"),
        ("CONFIRM",                                     "yes"),
        ("READ [get_challans] 20/22",                   "2026-08 ke challans batao"),
        ("CTX WRITE [update_challan] 29/37",            "inme se pehle challan ka status Paid kar do"),
        ("CONFIRM",                                     "yes"),
        ("READ [get_payments] 21/22",                   "payments history batao"),
        ("CTX WRITE [record_payment] 30/37",            "2026-08 ke dusre challan par Rs.2000 Cash payment record karo, date 2026-08-05"),
        ("CONFIRM",                                     "yes"),
        ("SETUP (generate_monthly_challans for delete test)", "2026-09 ke liye bhi sab students ke challans generate karo"),
        ("CONFIRM",                                     "yes"),
        ("READ (context for delete_challan)",           "2026-09 ke challans batao"),
        ("CTX WRITE [delete_challan] 31/37",            "inme se pehla challan delete kar do"),
        ("CONFIRM",                                     "yes"),
        ("SETUP (throwaway class + fee structure, no challans -- safe to delete)",
         "Class 100 section X banao"),
        ("CONFIRM",                                     "yes"),
        ("SETUP (fee structure for 100-X)",             "100-X ke liye monthly fee Rs.1000 set karo"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_fee_structure] 32/37",          "100-X ka fee structure delete kar do"),
        ("CONFIRM",                                     "yes"),
        ("CLEANUP (delete throwaway 100-X class)",      "100-X class delete kar do"),
        ("CONFIRM",                                     "yes"),
    ],

    "approve_reject": [
        ("WRITE [approve_user] 33/37",                  "pending users mein se pehle wale ko approve kar do"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [reject_user] 34/37",                   "baaki bache pending users ko reject kar do"),
        ("CONFIRM",                                     "yes"),
    ],

    "delete_accounts": [
        ("WRITE [delete_student_profile] 35/37 ⚠️ IRREVERSIBLE", "STUDENT_NAME_FOR_DELETE_TEST ka profile delete kar do"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_teacher_profile] 36/37 ⚠️ IRREVERSIBLE", "TEACHER_NAME_FOR_DELETE_TEST ka profile delete kar do"),
        ("CONFIRM",                                     "yes"),
        ("WRITE [delete_parent_profile] 37/37 ⚠️ IRREVERSIBLE", "PARENT_NAME_FOR_DELETE_TEST ka profile delete kar do"),
        ("CONFIRM",                                     "yes"),
    ],

    "caption": [
        ("READ [draft_social_caption] 22/22 (no confirm needed)", "Annual Sports Day ke liye ek exciting social media caption likho"),
    ],
}


async def run_conversation(conversation):
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

        for label, msg in conversation:
            for key, value in PLACEHOLDERS.items():
                msg = msg.replace(key, value)

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
        print(f"Section complete after {total}s -- {len(conversation)} exchanges.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in list(SECTIONS.keys()) + ["all"]:
        print("Available sections:\n")
        for name, conv in SECTIONS.items():
            print(f"  {name}  ({len(conv)} exchanges)")
        print("  all  (runs every section back to back)")
        print("\nUsage: python test_admin_sectioned.py <section_name>")
        return

    if sys.argv[1] == "all":
        conversation = [item for section in SECTIONS.values() for item in section]
    else:
        conversation = SECTIONS[sys.argv[1]]

    asyncio.run(run_conversation(conversation))


if __name__ == "__main__":
    main()