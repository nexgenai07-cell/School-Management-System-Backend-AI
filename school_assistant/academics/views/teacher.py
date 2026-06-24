from rest_framework import viewsets
from accounts.permissions import IsTeacher
from academics.models import Grade, Assignment, AssignmentSubmission
from academics.serializers.teacher import (
    TeacherGradeEntrySerializer, TeacherAssignmentSerializer, TeacherAssignmentSubmissionSerializer
)

class TeacherGradeViewSet(viewsets.ModelViewSet):
    """CRUD /api/teacher/grades"""
    serializer_class = TeacherGradeEntrySerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        # restrict to grades entered by this teacher
        return Grade.objects.filter(teacher__user=self.request.user)

    def perform_create(self, serializer):
        teacher_profile = self.request.user.teacher_profile
        serializer.save(teacher=teacher_profile)


class TeacherAssignmentViewSet(viewsets.ModelViewSet):
    """CRUD /api/teacher/assignments"""
    serializer_class = TeacherAssignmentSerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        # restrict to assignments created by this teacher
        return Assignment.objects.filter(teacher__user=self.request.user)

    def perform_create(self, serializer):
        teacher_profile = self.request.user.teacher_profile
        serializer.save(teacher=teacher_profile)


class TeacherSubmissionViewSet(viewsets.ModelViewSet):
    """CRUD /api/teacher/submissions"""
    serializer_class = TeacherAssignmentSubmissionSerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        # restrict to submissions for assignments owned by this teacher
        return AssignmentSubmission.objects.filter(assignment__teacher__user=self.request.user)
