# TODO

- [x] Verify TeacherAssignmentViewSet.perform_create for /api/teacher/assignments: already present and matches Assignment model + TeacherAssignmentSerializer expectations.
- [x] Verify server startup: `python manage.py check` reports no issues.
- [x] Verify attendance `is_locked` enforcement for teacher attendance updates: enforced in `attendance/views/teacher.py`.
- [ ] If any remaining hidden crash occurs during endpoint execution, capture stack trace and patch the exact view/serializer.

