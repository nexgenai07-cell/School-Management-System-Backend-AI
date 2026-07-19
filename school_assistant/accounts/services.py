'''
PERSON 1 -- services.py for 'accounts' app
Business logic + Casbin permission checks live here.
Existing models.py/views/serializers in this app are NOT touched.
'''
from accounts.models import User, StudentProfile, TeacherProfile, ParentProfile


def get_pending_users_service(role=None):
    qs = User.objects.filter(status="Pending").select_related("role")
    if role:
        qs = qs.filter(role__role_name__iexact=role)
    return list(qs.values("id", "full_name", "role__role_name"))


def approve_user_service(user_id, roll_number=None):
    user = User.objects.select_related("role").get(id=user_id)
    if user.status != "Pending":
        raise ValueError(f"{user.full_name} already {user.status}.")
    user.status = "Active"
    user.save()
    if user.role.role_name == "Student":
        profile = user.student_profile
        if roll_number:
            profile.roll_number = roll_number
        elif not profile.roll_number:
            profile.roll_number = StudentProfile.generate_roll_number(profile.class_section)
        if not profile.registration_number:
            profile.registration_number = StudentProfile.generate_registration_number()
        profile.save()
    return user


def reject_user_service(user_id):
    user = User.objects.get(id=user_id)
    if user.status != "Pending":
        raise ValueError(f"{user.full_name} already {user.status}.")
    user.status = "Rejected"
    user.save()
    return user


def get_scholarship_distribution_service(class_section=None):
    from academics.services import parse_class_section
    qs = StudentProfile.objects.select_related("user", "class_section")
    if class_section:
        qs = qs.filter(class_section=parse_class_section(class_section))
    dist = {0: 0, 50: 0, 100: 0}
    for pct in qs.values_list("scholarship_percentage", flat=True):
        dist[pct] = dist.get(pct, 0) + 1
    return dist


def assign_scholarship_service(student_id, percentage):
    if percentage not in (0, 50, 100):
        raise ValueError("Scholarship sirf 0, 50, ya 100 ho sakti hai.")
    profile = StudentProfile.objects.select_related("user").get(id=student_id)
    profile.scholarship_percentage = percentage
    profile.save()
    return profile


# ============================================================
# NEW SERVICES (ADD AT THE END)
# ============================================================

def get_student_profile_service(student_id):
    from accounts.models import StudentProfile
    profile = StudentProfile.objects.select_related("user", "class_section").get(id=student_id)
    return {
        "id": profile.id,
        "full_name": profile.user.full_name,
        "email": profile.user.email,
        "roll_number": profile.roll_number,
        "registration_number": profile.registration_number,
        "class_section": str(profile.class_section),
        "guardian_name": profile.guardian_name,
        "guardian_phone": profile.guardian_phone,
        "scholarship_percentage": profile.scholarship_percentage,
        "date_of_birth": profile.date_of_birth,
    }


def update_student_profile_service(student_id, class_section_id=None, guardian_name=None,
                                   guardian_phone=None, scholarship_percentage=None, date_of_birth=None):
    profile = StudentProfile.objects.get(id=student_id)
    if class_section_id is not None:
        profile.class_section_id = class_section_id
    if guardian_name is not None:
        profile.guardian_name = guardian_name
    if guardian_phone is not None:
        profile.guardian_phone = guardian_phone
    if scholarship_percentage is not None:
        if scholarship_percentage not in (0, 50, 100):
            raise ValueError("Scholarship must be 0, 50, or 100.")
        profile.scholarship_percentage = scholarship_percentage
    if date_of_birth is not None:
        profile.date_of_birth = date_of_birth
    profile.save()
    return profile


def get_teacher_profile_service(teacher_id):
    from accounts.models import TeacherProfile
    profile = TeacherProfile.objects.select_related("user").get(id=teacher_id)
    return {
        "id": profile.id,
        "full_name": profile.user.full_name,
        "email": profile.user.email,
        "cnic": profile.cnic,
        "qualification": profile.qualification,
        "specialization": profile.specialization,
        "joining_date": profile.joining_date,
    }


def update_teacher_profile_service(teacher_id, qualification=None, specialization=None, joining_date=None):
    profile = TeacherProfile.objects.get(id=teacher_id)
    if qualification is not None:
        profile.qualification = qualification
    if specialization is not None:
        profile.specialization = specialization
    if joining_date is not None:
        profile.joining_date = joining_date
    profile.save()
    return profile


def get_parent_profile_service(user_id):
    from accounts.models import ParentProfile, ParentStudentLink
    parent = ParentProfile.objects.select_related("user").get(user_id=user_id)
    children_count = ParentStudentLink.objects.filter(parent=parent).count()
    return {
        "id": parent.id,
        "full_name": parent.user.full_name,
        "email": parent.user.email,
        "children_count": children_count,
    }


def update_parent_profile_service(user_id, phone=None, address=None):
    # Add phone/address fields to ParentProfile if needed
    from accounts.models import ParentProfile
    parent = ParentProfile.objects.get(user_id=user_id)
    # If you add phone/address fields, update them here.
    parent.save()
    return parent


def get_my_children_service(user_id):
    from accounts.models import ParentProfile, ParentStudentLink
    parent = ParentProfile.objects.get(user_id=user_id)
    links = ParentStudentLink.objects.filter(parent=parent).select_related("student__user", "student__class_section")
    return [
        {
            "id": link.student.id,
            "full_name": link.student.user.full_name,
            "roll_number": link.student.roll_number,
            "class_section": str(link.student.class_section),
            "relation": link.relation,
        }
        for link in links
    ]


def set_active_child_service(session, child_id):
    from accounts.models import StudentProfile
    child = StudentProfile.objects.get(id=child_id)
    session.active_child = child
    session.save()
    return child


def get_student_scholarship_status_service(student_id):
    from accounts.models import StudentProfile
    profile = StudentProfile.objects.get(id=student_id)
    return {
        "scholarship_percentage": profile.scholarship_percentage,
        "is_on_scholarship": profile.scholarship_percentage > 0,
    }


def get_child_scholarship_status_service(child_id):
    return get_student_scholarship_status_service(child_id)
# Add to accounts/services.py (at the end)

def delete_student_profile_service(student_id):
    from accounts.models import StudentProfile
    student = StudentProfile.objects.select_related("user").get(id=student_id)
    user = student.user
    student.delete()
    user.delete()
    return True


def delete_teacher_profile_service(teacher_id):
    from accounts.models import TeacherProfile
    teacher = TeacherProfile.objects.select_related("user").get(id=teacher_id)
    user = teacher.user
    teacher.delete()
    user.delete()
    return True


def delete_parent_profile_service(parent_id):
    from accounts.models import ParentProfile
    parent = ParentProfile.objects.select_related("user").get(id=parent_id)
    user = parent.user
    parent.delete()
    user.delete()
    return True
# ============================================================
# NEW (59-tool plan)
# ============================================================

def list_users_service(role=None, status=None):
    qs = User.objects.select_related("role").all()
    if role:
        qs = qs.filter(role__role_name__iexact=role)
    if status:
        qs = qs.filter(status__iexact=status)
    return list(qs.values("id", "full_name", "role__role_name", "status")[:50])


def get_user_details_service(user_name):
    matches = User.objects.filter(full_name__icontains=user_name).select_related("role")
    count = matches.count()
    if count == 0:
        return None, f"'{user_name}' naam ka koi user nahi mila."
    if count > 1:
        names = ", ".join(f"{u.full_name} ({u.role.role_name})" for u in matches)
        return None, f"Multiple users '{user_name}' se match karte hain: {names}."
    return matches.first(), None