"""
ACCOUNTS -- ADMIN-ROLE VIEWS
==============================
Shared auth views (Register/Profile/ChangePassword -- used by every
role) plus Admin-exclusive views (approvals, user management, roles).

Login itself uses djangorestframework-simplejwt's built-in
TokenObtainPairView directly in urls/admin.py -- no custom view needed.
"""
import random
import requests
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.contrib.auth.password_validation import validate_password

# ✅ Swagger imports (for API documentation)
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from accounts.models import User, Role, StudentProfile, TeacherProfile, PasswordResetToken, ParentProfile
from accounts.permissions import IsAdmin
from accounts.serializers.admin import (
    RegisterSerializer, ProfileSerializer, ChangePasswordSerializer,
    RoleSerializer, PendingUserSerializer, ApprovalActionSerializer,
    StudentProfileAdminSerializer, TeacherProfileAdminSerializer,
    UserAdminSerializer, ParentProfileAdminSerializer,
)


# ── SHARED AUTH VIEWS (every role uses these) ────────────────────────────

class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register -- open to anyone, no auth required."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/auth/profile -- works for whichever role is logged in."""
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """PUT /api/auth/change-password"""
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response({"detail": "Password updated successfully."})


# ── EMAILJS-BASED PASSWORD RESET (CUSTOM OTP) ─────────────────────────────

class PasswordResetRequestView(APIView):
    """POST /api/auth/request-otp -- Sends 6-digit OTP via EmailJS"""
    permission_classes = [AllowAny]

    def post(self, request):
        print(" CUSTOM OTP VIEW HIT ")
        email = request.data.get("email")

        if not email:
            return Response({"detail": "Email is required."}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "If that email is registered, an OTP has been sent."}, status=200)

        # Delete old tokens
        PasswordResetToken.objects.filter(user=user).delete()

        # Generate 6-digit OTP
        token = str(random.randint(100000, 999999))
        expires_at = timezone.now() + timedelta(minutes=15)
        PasswordResetToken.objects.create(user=user, token=token, expires_at=expires_at)

        # ✅ PRINT OTP TO CONSOLE (for testing)
        print(f"\n🔐 OTP for {user.email}: {token}")
        print(f"⏳ Expires in 15 minutes.\n")

        # ─── SEND EMAIL VIA EMAILJS ──────────────────────────────
        try:
            payload = {
                "service_id": settings.EMAILJS_SERVICE_ID,
                "template_id": settings.EMAILJS_TEMPLATE_ID,
                "user_id": settings.EMAILJS_PUBLIC_KEY,
                "accessToken": settings.EMAILJS_PRIVATE_KEY,
                "template_params": {
                    "to_email": user.email,
                    "to_name": user.full_name,
                    "otp_code": token,
                    "expiry_minutes": "15",
                }
            }

            response = requests.post(
                "https://api.emailjs.com/api/v1.0/email/send",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code != 200:
                print(f"⚠️ EmailJS Error: {response.text}")

        except Exception as e:
            print(f"⚠️ EmailJS Exception: {e}")

        return Response({"detail": "If that email is registered, an OTP has been sent."}, status=200)


class PasswordResetConfirmView(APIView):
    """POST /api/auth/request-otp/confirm -- Verify OTP and set new password"""
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not all([email, token, new_password]):
            return Response({"detail": "email, token, and new_password are required."}, status=400)

        try:
            user = User.objects.get(email=email)
            reset_obj = PasswordResetToken.objects.get(user=user, token=token, is_used=False)
        except (User.DoesNotExist, PasswordResetToken.DoesNotExist):
            return Response({"detail": "Invalid or expired token."}, status=400)

        if reset_obj.expires_at < timezone.now():
            return Response({"detail": "Token has expired."}, status=400)

        try:
            validate_password(new_password)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        user.set_password(new_password)
        user.save()
        reset_obj.is_used = True
        reset_obj.save()

        return Response({"detail": "Password reset successful."}, status=200)


# ── ADMIN-ONLY VIEWS ───────────────────────────────────────────────────────

class RoleListView(generics.ListAPIView):
    """GET /api/admin/roles"""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdmin]


class PendingApprovalListView(generics.ListAPIView):
    """GET /api/admin/approvals -- list every account awaiting approval."""
    queryset = User.objects.filter(status="Pending")
    serializer_class = PendingUserSerializer
    permission_classes = [IsAdmin]


class ApprovalActionView(APIView):
    """PUT /api/admin/approvals/{user_id}"""
    permission_classes = [IsAdmin]

    def put(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        if action == "approve":
            user.status = "Active"
            user.save()

            if user.role.role_name == "Student":
                student_profile = StudentProfile.objects.get(user=user)
                
                # ✅ AUTO-GENERATE ROLL NUMBER (class-wise)
                student_profile.roll_number = StudentProfile.generate_roll_number(
                    student_profile.class_section
                )
                
                # ✅ AUTO-GENERATE REGISTRATION NUMBER (global)
                student_profile.registration_number = StudentProfile.generate_registration_number()
                
                student_profile.save()

        else:  # reject
            user.status = "Rejected"
            user.save()

            if user.role.role_name == "Parent":
                try:
                    parent_profile = user.parent_profile
                    parent_profile.delete()
                except Exception:
                    pass

        return Response({"detail": f"User {action}d successfully.", "status": user.status})


class UserViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/users"""
    queryset = User.objects.all().order_by("-created_at")
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'status', 'is_active', 'is_staff']
    search_fields = ['full_name', 'email']
    ordering_fields = ['created_at', 'full_name', 'email']
    ordering = ['-created_at']


class StudentProfileViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/student-profiles"""
    queryset = StudentProfile.objects.select_related("user").all()
    serializer_class = StudentProfileAdminSerializer
    permission_classes = [IsAdmin]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['class_section', 'scholarship_percentage']
    search_fields = ['user__full_name', 'roll_number', 'guardian_name']
    ordering_fields = ['user__full_name', 'roll_number']
    ordering = ['user__full_name']

    @swagger_auto_schema(
        operation_description="Delete a student profile and its associated user account (cascade deletes all related records)",
        responses={204: "No Content", 404: "Not Found"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """Delete the StudentProfile and the associated User"""
        user = instance.user
        instance.delete()  # StudentProfile delete
        user.delete()      # User delete (cascade will remove all related records)


class TeacherProfileViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/teacher-profiles"""
    queryset = TeacherProfile.objects.select_related("user").all()
    serializer_class = TeacherProfileAdminSerializer
    permission_classes = [IsAdmin]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['qualification', 'specialization']
    search_fields = ['user__full_name', 'cnic']
    ordering_fields = ['user__full_name', 'joining_date']
    ordering = ['user__full_name']

    @swagger_auto_schema(
        operation_description="Delete a teacher profile and its associated user account (cascade deletes all related records)",
        responses={204: "No Content", 404: "Not Found"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """Delete the TeacherProfile and the associated User"""
        user = instance.user
        instance.delete()  # TeacherProfile delete
        user.delete()      # User delete


class ParentProfileViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/parent-profiles"""
    queryset = ParentProfile.objects.select_related("user").all()
    serializer_class = ParentProfileAdminSerializer
    permission_classes = [IsAdmin]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = []
    search_fields = ['user__full_name', 'user__email']
    ordering_fields = ['user__full_name', 'created_at']
    ordering = ['user__full_name']

    @swagger_auto_schema(
        operation_description="Delete a parent profile and its associated user account (cascade deletes all related records)",
        responses={204: "No Content", 404: "Not Found"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """Delete the ParentProfile and the associated User"""
        user = instance.user
        instance.delete()  # ParentProfile delete
        user.delete()      # User delete (cascade will remove ParentStudentLink rows)