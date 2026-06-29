# TODO / Fix Plan - Chat 500 Crash (Teacher/Student/Parent context)

## Step 1: Repo inspection
- [x] Read `school_assistant/chat/ai_service.py` to locate `_teacher_context`, `_student_context`, `_parent_context`.
- [x] Read `accounts/models.py` and `chat/models.py` to confirm profile relations.

## Step 2: Implement crash-proof context builders
- [ ] Update `_teacher_context(user)` to handle missing `user.teacher_profile` and missing related records (no subjects / assignments / grades / etc.).
- [ ] Update `_student_context(user)` to handle missing `user.student_profile` and missing related records.
- [ ] Update `_parent_context(user, child_id=None)` to handle missing `user.parent_profile` and missing children / active_child.
- [ ] Ensure errors never propagate to `get_ai_response`; return safe fallback strings.

## Step 3: Validate
- [ ] Run unit checks / Django system check (if available) and ensure server no longer returns 500.
- [ ] Manually test POST endpoints for teacher/student/parent chat message creation.

## Step 4: Optional data workflow fix (if profiles missing in DB)
- [ ] If profiles are truly not created during registration, ensure serializer/workflow creates them.
- [ ] If not required for this 500 fix, skip data migration.

