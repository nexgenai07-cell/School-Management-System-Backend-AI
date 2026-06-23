from rest_framework import viewsets
from accounts.permissions import IsTeacher
from attendance.models import Attendance, BehaviorLog
from attendance.serializers.teacher import TeacherAttendanceSerializer, TeacherBehaviorLogSerializer

class TeacherAttendanceViewSet(viewsets.ModelViewSet):
    """Teachers can mark and update attendance for their class."""
    serializer_class = TeacherAttendanceSerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        # restrict to attendance marked by this teacher
        return Attendance.objects.filter(marked_by=self.request.user.teacher_profile)

    def _assert_not_locked(self, obj: Attendance):
        if getattr(obj, "is_locked", False):
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Attendance record is locked for this day and cannot be modified.")

    def perform_create(self, serializer):
        # If some client sends is_locked=True, still ensure new records are unlocked.
        serializer.save(marked_by=self.request.user.teacher_profile, is_locked=False)

    def perform_update(self, serializer):
        self._assert_not_locked(self.get_object())
        serializer.save()

    def perform_destroy(self, instance: Attendance):
        self._assert_not_locked(instance)
        instance.delete()


class TeacherBehaviorLogViewSet(viewsets.ModelViewSet):
    """Teachers can file behavior logs for students."""
    serializer_class = TeacherBehaviorLogSerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        # restrict to logs filed by this teacher
        return BehaviorLog.objects.filter(reported_by=self.request.user.teacher_profile)

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user.teacher_profile)
