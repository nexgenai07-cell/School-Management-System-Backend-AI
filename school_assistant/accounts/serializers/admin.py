"""
ACCOUNTS -- ADMIN-ROLE SERIALIZERS
===================================
Covers: User management, account approvals, role listing, and the
shared authentication serializers (register/login/profile/change-password).

NOTE on the auth serializers below (RegisterSerializer, ProfileSerializer,
ChangePasswordSerializer): these are NOT admin-exclusive -- every role
registers and logs in through the same endpoints. They live in this file
(rather than duplicated in teacher.py/student.py/parent.py) because the
underlying logic is identical for all four roles; only the *fields shown*
differ slightly (e.g. Student picks a class, Parent enters a roll number).
Dev B's url files for Teacher/Student/Parent just import and reuse these
same serializers/views -- see the comment in urls/admin.py for how.
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

from accounts.models import User, Role, StudentProfile, TeacherProfile, ParentProfile, ParentStudentLink


# ── SHARED AUTH SERIALIZERS (used by every role) ────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles the "Dynamic Registration Gateway" (Page 3): the same endpoint
    is used by Teacher/Student/Parent signups, with role-specific extra
    fields accepted and validated depending on `role_name`.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    role_name = serializers.ChoiceField(choices=["Teacher", "Student", "Parent"], write_only=True)

    # Role-specific optional fields -- which ones are required is
    # enforced in validate() below, based on role_name.
    class_section_id = serializers.IntegerField(write_only=True, required=False)
    cnic = serializers.CharField(write_only=True, required=False)
    child_roll_number = serializers.CharField(write_only=True, required=False)
    relation = serializers.ChoiceField(choices=["Father", "Mother", "Guardian"], write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id", "full_name", "email", "password", "role_name",
            "class_section_id", "cnic", "child_roll_number", "relation",
        ]

    def validate(self, data):
        role_name = data["role_name"]

        if role_name == "Student" and not data.get("class_section_id"):
            raise serializers.ValidationError({"class_section_id": "Required for Student signup."})

        if role_name == "Teacher" and not data.get("cnic"):
            raise serializers.ValidationError({"cnic": "Required for Teacher signup."})

        if role_name == "Parent":
            if not data.get("child_roll_number"):
                raise serializers.ValidationError({"child_roll_number": "Required for Parent signup."})
            if not data.get("relation"):
                raise serializers.ValidationError({"relation": "Required for Parent signup."})
            # The child's roll number must already exist -- a student is
            # always approved (and assigned a roll number by Admin) BEFORE
            # any parent can register and link to them.
            if not StudentProfile.objects.filter(roll_number=data["child_roll_number"]).exists():
                raise serializers.ValidationError(
                    {"child_roll_number": "No student found with this roll number. Ask Admin to confirm it first."}
                )
        return data

    def create(self, validated_data):
        role_name = validated_data.pop("role_name")
        class_section_id = validated_data.pop("class_section_id", None)
        cnic = validated_data.pop("cnic", None)
        child_roll_number = validated_data.pop("child_roll_number", None)
        relation = validated_data.pop("relation", None)
        password = validated_data.pop("password")

        role = Role.objects.get(role_name=role_name)
        user = User.objects.create_user(
            email=validated_data["email"], full_name=validated_data["full_name"],
            role=role, password=password,
        )  # status defaults to "Pending" -- Admin must approve before login works fully

        if role_name == "Student":
            StudentProfile.objects.create(user=user, class_section_id=class_section_id)
        elif role_name == "Teacher":
            TeacherProfile.objects.create(user=user, cnic=cnic)
        elif role_name == "Parent":
            parent_profile = ParentProfile.objects.create(user=user)
            student = StudentProfile.objects.get(roll_number=child_roll_number)
            ParentStudentLink.objects.create(parent=parent_profile, student=student, relation=relation)

        return user


class ProfileSerializer(serializers.ModelSerializer):
    """GET/PUT /api/auth/profile -- works identically for every role."""

    role_name = serializers.CharField(source="role.role_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "role_name", "status", "created_at"]
        read_only_fields = ["email", "status", "created_at"]  # email change should go through a separate verified flow


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


# ── ADMIN-ONLY SERIALIZERS ───────────────────────────────────────────────

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "role_name", "description"]


class PendingUserSerializer(serializers.ModelSerializer):
    """Read-only view of a user awaiting approval, for the Approvals Panel (Page 6)."""

    role_name = serializers.CharField(source="role.role_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "role_name", "status", "created_at"]


class ApprovalActionSerializer(serializers.Serializer):
    """PUT /api/admin/approvals/{user_id} -- approve or reject a pending account."""

    action = serializers.ChoiceField(choices=["approve", "reject"])
    # Only used when approving a Student -- Admin assigns the roll number
    # here, since students don't set it themselves at signup (see
    # StudentProfile.roll_number's docstring in models.py).
    roll_number = serializers.CharField(required=False, allow_blank=True)


class StudentProfileAdminSerializer(serializers.ModelSerializer):
    """For the User Profile Master List (Page 7) -- lets Admin edit scholarship %, roll number, etc."""

    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            "id", "full_name", "email", "roll_number", "class_section",
            "guardian_name", "guardian_phone", "scholarship_percentage", "date_of_birth",
        ]


class TeacherProfileAdminSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = TeacherProfile
        fields = ["id", "full_name", "email", "cnic", "qualification", "specialization", "joining_date"]


class UserAdminSerializer(serializers.ModelSerializer):
    """Full user record for the master user-management list (CRUD /api/admin/users)."""

    role_name = serializers.CharField(source="role.role_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "role_name", "status", "is_active", "created_at"]
        read_only_fields = ["created_at"]