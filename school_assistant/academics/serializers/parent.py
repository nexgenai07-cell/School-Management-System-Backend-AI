from rest_framework import serializers
from academics.models import Grade, AssignmentSubmission

class ParentGradeSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.subject_name", read_only=True)

    class Meta:
        model = Grade
        fields = [
            "id", "subject_name", "exam_type",
            "obtained_marks", "total_marks", "exam_date"
        ]


class ParentAssignmentSubmissionSerializer(serializers.ModelSerializer):
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id", "assignment_title", "submitted_at", "marks", "feedback"
        ]
