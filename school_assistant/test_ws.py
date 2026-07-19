"""
Full-coverage Admin bot test -- exercises ALL 59 admin tools
(22 READ + 37 WRITE), plus two extra kinds of diagnostic tests:

  CTX   = context-carry test: a WRITE message deliberately does NOT name
          the record explicitly ("isme se pehli...", "isi ka...") -- it
          relies on the Agent resolving it from the READ/WRITE result
          just sent. Tests that short-term context actually works.

  SWITCH = topic-switch / interrupt test: while a PendingAction is open
          (bot is waiting for yes/no), we deliberately send an unrelated
          question instead of confirming. Per consumer.py's
          handle_pending_action(), ANY message that isn't exactly
          yes/haan/han or no/nahi/nhi falls into the else branch and
          returns "Pehle confirm karein ... (yes/no)" WITHOUT touching
          the pending action or answering the new question. So the
          expected/correct behavior is: the bot ignores the new
          question and re-asks for confirmation. If it instead answers
          the unrelated question or drops the pending action, that's a
          bug.

  FAR-CTX = far-context test: references something mentioned much
          earlier in the conversation. NOTE: get_chat_history() in
          consumer.py only pulls the last `limit=6` messages (3
          exchanges) from the DB into the agent's context window. So
          anything referenced more than ~3 exchanges back is NOT
          actually visible to the agent, even though it's still saved
          in the DB and visible in the chat UI. This test deliberately
          references something from well outside that window to check
          what the bot does when it can't resolve the reference --
          expected: it should ask for clarification / say it can't
          find it, NOT hallucinate an answer.

EDIT THESE before running -- must be REAL records that exist in your DB:
  STUDENT_NAME_FOR_TESTS / TEACHER_NAME_FOR_TESTS / PARENT_NAME_FOR_TESTS
      -> any existing ACTIVE (non-pending) student/teacher/parent.
      Used for profile-update / scholarship / class-in-charge tests.
      These records are modified but NOT deleted.

  STUDENT_NAME_FOR_DELETE_TEST / TEACHER_NAME_FOR_DELETE_TEST /
  PARENT_NAME_FOR_DELETE_TEST
      -> ⚠️ IRREVERSIBLE. These 3 accounts get PERMANENTLY DELETED
      (delete_student_profile / delete_teacher_profile /
      delete_parent_profile also delete the underlying User row).
      Use dedicated throwaway test accounts you created just for this
      purpose -- NEVER point these at real student/teacher/parent data.

Also make sure at least 2 users are sitting in "Pending" status before
running (for approve_user / reject_user), and that at least one open
complaint and one pending certificate request exist (for resolve_ticket
/ approve_certificate_request).
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

CONVERSATION = [

    # ===================== SECTION 1: ROOMS =====================
    ("READ [list_rooms] 1/22",                     "sab rooms ki list do"),
    ("WRITE [create_room] 1/37",                    "'Physics Lab' naam ka room banao, block A mein, capacity 35"),
    ("CONFIRM",                                     "yes"),
    ("CTX WRITE [update_room] 2/37",                "Physics Lab ki capacity 40 kar do"),
    ("CONFIRM",                                     "yes"),
    ("SETUP (create_room for delete test)",         "'TempRoomDelete' naam ka room banao capacity 10"),
    ("CONFIRM",                                     "yes"),
    ("WRITE [delete_room] 3/37",                    "TempRoomDelete room delete kar do"),
    ("CONFIRM",                                     "yes"),

    # ===================== SECTION 2: USERS (read) =====================
    ("READ [list_users] 2/22",                      "sab active teachers ki list do"),
    ("CTX READ [get_user_details] 3/22",            "pehle wale teacher ki details do"),
    ("READ [get_pending_users] 4/22",               "pending users batao"),

    # ===================== SECTION 3: EVENTS + SWITCH TEST 1 =====================
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

    # ===================== SECTION 4: INVENTORY =====================
    ("READ [get_inventory_status] 6/22",            "inventory status batao"),
    ("WRITE [create_inventory] 7/37",               "'Projector' naam ka item add karo, category Electronics, quantity 5, room Physics Lab"),
    ("CONFIRM",                                     "yes"),
    ("CTX WRITE [update_inventory] 8/37",           "Physics Lab wale Projector ki quantity 8 kar do"),
    ("CONFIRM",                                     "yes"),
    ("SETUP (create_inventory for delete test)",    "'TempItemDelete' item add karo category Misc quantity 1"),
    ("CONFIRM",                                     "yes"),
    ("WRITE [delete_inventory] 9/37",               "TempItemDelete ko inventory se delete kar do"),
    ("CONFIRM",                                     "yes"),

    # ===================== SECTION 5: TICKETS =====================
    ("READ [get_open_tickets] 7/22",                "open complaints kitni hain?"),
    ("CTX WRITE [resolve_ticket] 10/37",            "inme se pehli complaint resolve kar do, remarks: 'Sorted'"),
    ("CONFIRM",                                     "yes"),

    # ===================== SECTION 6: CERTIFICATES =====================
    # SKIPPED -- CertificateRequest model doesn't exist in chat.models yet.
    # get_certificate_requests / approve_certificate_request / request_certificate /
    # cancel_certificate_request / get_student_certificate_status all do
    # `from chat.models import CertificateRequest` which currently fails.
    # Known bug -- fix separately, then re-add these 2 lines:
    # ("READ [get_certificate_requests] 8/22",        "certificate requests batao"),
    # ("CTX WRITE [approve_certificate_request] 11/37","inme se pehli request approve kar do"),
    # ("CONFIRM",                                     "yes"),

    # ===================== SECTION 7: NOTIFICATIONS =====================
    ("READ [get_notification_history] 9/22",        "notification history batao"),
    ("WRITE [send_notification] 12/37",             "Student role ko ye message bhejo: 'Kal school mein half day hai'"),
    ("CONFIRM",                                     "yes"),

    # ===================== SECTION 8: PURE STATS READS =====================
    ("READ [get_scholarship_distribution] 10/22",   "scholarship distribution batao"),
    ("READ [get_attendance_stats] 11/22",           "overall attendance kitni hai?"),
    ("READ [get_exam_results] 12/22",               "exam results batao"),
    ("READ [get_assignment_compliance] 13/22",      "assignment compliance batao"),

    # ===================== SECTION 9: CLASSES / SUBJECTS / TIMETABLE =====================
    ("READ [list_classes] 14/22",                   "sab classes batao"),
    ("WRITE [create_class_section] 13/37",          "Class 12 section D banao, room Physics Lab"),
    ("CONFIRM",                                     "yes"),
    ("READ [get_class_details] 15/22",              "12-D ki details do"),
    ("WRITE [update_class_section] 14/37",          f"12-D ka teacher-in-charge TEACHER_NAME_FOR_TESTS laga do"),
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

    # ===================== SECTION 10: STUDENT PROFILE / SCHOLARSHIP =====================
    ("READ [get_student_profile] 18/22",            "STUDENT_NAME_FOR_TESTS ka profile batao"),
    ("WRITE [update_student_profile] 22/37",        "STUDENT_NAME_FOR_TESTS ka guardian phone 03001234567 kar do"),
    ("CONFIRM",                                     "yes"),
    ("WRITE [assign_scholarship] 23/37",            "STUDENT_NAME_FOR_TESTS ko 50% scholarship do"),
    ("CONFIRM",                                     "yes"),

    # ===================== SECTION 11: TEACHER / PARENT PROFILE =====================
    ("WRITE [update_teacher_profile] 24/37",        "TEACHER_NAME_FOR_TESTS ki specialization 'AI & ML' set kar do"),
    ("CONFIRM",                                     "yes"),
    ("WRITE [update_parent_profile] 25/37",         "PARENT_NAME_FOR_TESTS ka profile update kar do"),
    ("CONFIRM",                                     "yes"),

    # ===================== SECTION 12: FAR-CONTEXT DIAGNOSTIC =====================
    ("FAR-CTX TEST -- references complaint from many turns ago",
     "wo complaint jo humne shuru mein resolve ki thi, uske remarks kya the?"),

    # ===================== SECTION 13: FINANCE + SWITCH TEST 2 =====================
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

    # ===================== SECTION 14: APPROVE / REJECT PENDING USERS =====================
    ("WRITE [approve_user] 33/37",                  "pending users mein se pehle wale ko approve kar do"),
    ("CONFIRM",                                     "yes"),
    ("WRITE [reject_user] 34/37",                   "baaki bache pending users ko reject kar do"),
    ("CONFIRM",                                     "yes"),

    # ===================== SECTION 15: ⚠️ DESTRUCTIVE DELETES (dedicated throwaway accounts ONLY) =====================
    ("WRITE [delete_student_profile] 35/37 ⚠️ IRREVERSIBLE", "STUDENT_NAME_FOR_DELETE_TEST ka profile delete kar do"),
    ("CONFIRM",                                     "yes"),
    ("WRITE [delete_teacher_profile] 36/37 ⚠️ IRREVERSIBLE", "TEACHER_NAME_FOR_DELETE_TEST ka profile delete kar do"),
    ("CONFIRM",                                     "yes"),
    ("WRITE [delete_parent_profile] 37/37 ⚠️ IRREVERSIBLE", "PARENT_NAME_FOR_DELETE_TEST ka profile delete kar do"),
    ("CONFIRM",                                     "yes"),

    # ===================== SECTION 16: READ-ONLY GENERATION =====================
    ("READ [draft_social_caption] 22/22 (no confirm needed)", "Annual Sports Day ke liye ek exciting social media caption likho"),
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
        print(f"Full test complete after {total}s -- {len(CONVERSATION)} exchanges.")
        print("Coverage: 21/22 READ tools, 36/37 WRITE tools tested (57/59).")
        print("SKIPPED: get_certificate_requests, approve_certificate_request -- CertificateRequest model missing, known bug.")
        print("Plus CTX / SWITCH / FAR-CTX diagnostics.")


asyncio.run(main())