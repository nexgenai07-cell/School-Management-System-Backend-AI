# academics/services.py
from django.db.models import Avg
from academics.models import ClassSection, Subject, Assignment, Grade, Timetable, Room
from accounts.models import TeacherProfile


def parse_class_section(class_section_str):
    class_name, section = class_section_str.rsplit("-", 1)
    return ClassSection.objects.get(class_name=class_name, section=section)


def get_exam_results_service(class_section=None, exam_type=None, subject=None):
    qs = Grade.objects.select_related("student__user", "subject")
    if class_section:
        qs = qs.filter(student__class_section=parse_class_section(class_section))
    if exam_type:
        qs = qs.filter(exam_type=exam_type)
    if subject:
        qs = qs.filter(subject__subject_name__icontains=subject)
    count = qs.count()
    avg = qs.aggregate(avg=Avg("obtained_marks"))["avg"]
    top = qs.order_by("-obtained_marks").first()
    return {
        "count": count,
        "average": round(avg, 1) if avg else None,
        "top_scorer": top.student.user.full_name if top else None,
        "top_score": float(top.obtained_marks) if top else None,
    }


def get_assignment_compliance_service(class_section=None):
    from accounts.models import StudentProfile
    assignments = Assignment.objects.all()
    if class_section:
        assignments = assignments.filter(class_section=parse_class_section(class_section))
    results = []
    for a in assignments:
        total = StudentProfile.objects.filter(class_section=a.class_section).count()
        submitted = a.submissions.count()
        results.append({
            "title": a.title, "class_section": str(a.class_section),
            "submitted": submitted, "total_students": total,
        })
    return results


def create_class_section_service(class_name, section, default_room=None):
    room = Room.objects.filter(name__iexact=default_room).first() if default_room else None
    cs, created = ClassSection.objects.get_or_create(
        class_name=class_name, section=section, defaults={"default_room": room}
    )
    if not created:
        raise ValueError(f"Class {class_name}-{section} pehle se exist karti hai.")
    return cs


def create_subject_service(subject_name, class_section, teacher_name=None):
    cs = parse_class_section(class_section)
    teacher = None
    if teacher_name:
        teacher = TeacherProfile.objects.filter(user__full_name__icontains=teacher_name).first()
    subject, created = Subject.objects.get_or_create(
        subject_name=subject_name, class_section=cs, defaults={"assigned_teacher": teacher}
    )
    if not created:
        raise ValueError(f"{subject_name} pehle se {class_section} mein exist karta hai.")
    return subject


def create_timetable_entry_service(class_section, subject_name, teacher_name, day, start_time, end_time, room_name=None):
    cs = parse_class_section(class_section)
    subject = Subject.objects.get(subject_name=subject_name, class_section=cs)
    teacher = TeacherProfile.objects.get(user__full_name__icontains=teacher_name)
    room = Room.objects.filter(name__iexact=room_name).first() if room_name else None
    entry = Timetable.objects.create(
        class_section=cs, subject=subject, teacher=teacher, room=room,
        day=day, start_time=start_time, end_time=end_time,
    )
    return entry


# ============================================================
# NEW SERVICES (ADD AT THE END)
# ============================================================

def get_student_grades_service(student_id, exam_type=None):
    from academics.models import Grade
    qs = Grade.objects.filter(student_id=student_id).select_related("subject")
    if exam_type:
        qs = qs.filter(exam_type=exam_type)
    return [
        {
            "subject": g.subject.subject_name,
            "exam_type": g.exam_type,
            "obtained_marks": float(g.obtained_marks),
            "total_marks": float(g.total_marks),
            "percentage": round((g.obtained_marks / g.total_marks * 100), 1) if g.total_marks else 0,
        }
        for g in qs
    ]


def get_student_report_card_service(student_id, term=None):
    from accounts.models import StudentProfile
    from academics.models import Grade
    student = StudentProfile.objects.select_related("class_section").get(id=student_id)
    qs = Grade.objects.filter(student_id=student_id).select_related("subject")
    if term:
        qs = qs.filter(exam_type=term)
    grades = []
    total_percentage = 0
    for g in qs:
        pct = (g.obtained_marks / g.total_marks * 100) if g.total_marks else 0
        grades.append({"subject": g.subject.subject_name, "grade": round(pct, 1)})
        total_percentage += pct
    gpa = round(total_percentage / len(grades), 1) if grades else 0
    return {
        "student_name": student.user.full_name,
        "class_section": str(student.class_section),
        "gpa": gpa,
        "subjects": grades,
    }


def get_student_timetable_service(class_section_id):
    from academics.models import Timetable
    slots = Timetable.objects.filter(class_section_id=class_section_id).select_related("subject", "teacher__user")
    return [
        {
            "day": s.day,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "subject": s.subject.subject_name,
            "teacher": s.teacher.user.full_name,
        }
        for s in slots.order_by("day", "start_time")
    ]


def get_student_assignments_service(student_id, status=None):
    from accounts.models import StudentProfile
    from academics.models import Assignment, AssignmentSubmission
    student = StudentProfile.objects.get(id=student_id)
    assignments = Assignment.objects.filter(class_section=student.class_section).select_related("subject")
    submissions = AssignmentSubmission.objects.filter(student_id=student_id).values_list("assignment_id", flat=True)
    results = []
    for a in assignments:
        is_submitted = a.id in submissions
        is_graded = AssignmentSubmission.objects.filter(assignment=a, student_id=student_id, marks__isnull=False).exists()
        assignment_status = "Graded" if is_graded else ("Submitted" if is_submitted else "Pending")
        if status and assignment_status.lower() != status.lower():
            continue
        results.append({
            "id": a.id,
            "title": a.title,
            "subject": a.subject.subject_name,
            "due_date": a.due_date.strftime("%Y-%m-%d"),
            "status": assignment_status,
        })
    return results


def get_assignment_details_service(assignment_id, student_id=None):
    from academics.models import Assignment
    assignment = Assignment.objects.select_related("subject", "class_section").get(id=assignment_id)
    result = {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "subject": assignment.subject.subject_name,
        "class_section": str(assignment.class_section),
        "due_date": assignment.due_date.strftime("%Y-%m-%d %H:%M"),
        "attachment_url": assignment.attachment_url,
    }
    if student_id:
        from academics.models import AssignmentSubmission
        submission = AssignmentSubmission.objects.filter(assignment_id=assignment_id, student_id=student_id).first()
        result["submitted"] = bool(submission)
        if submission:
            result["file_url"] = submission.file_url
            result["marks"] = float(submission.marks) if submission.marks is not None else None
            result["feedback"] = submission.feedback
    return result


def submit_assignment_service(assignment_id, student_id, file_url):
    from academics.models import Assignment, AssignmentSubmission
    from django.utils import timezone
    assignment = Assignment.objects.get(id=assignment_id)
    submission, created = AssignmentSubmission.objects.get_or_create(
        assignment=assignment,
        student_id=student_id,
        defaults={"file_url": file_url},
    )
    if not created:
        submission.file_url = file_url
        submission.submitted_at = timezone.now()
        submission.save()
    return submission


def delete_submission_service(assignment_id, student_id):
    from academics.models import AssignmentSubmission
    submission = AssignmentSubmission.objects.get(assignment_id=assignment_id, student_id=student_id)
    if submission.marks is not None:
        raise ValueError("Assignment already graded, cannot delete.")
    submission.delete()
    return True


def get_teacher_classes_service(teacher_id):
    from academics.models import Subject
    subjects = Subject.objects.filter(assigned_teacher_id=teacher_id).select_related("class_section")
    seen = set()
    result = []
    for s in subjects:
        key = s.class_section.id
        if key not in seen:
            seen.add(key)
            result.append({
                "id": s.class_section.id,
                "class_name": s.class_section.class_name,
                "section": s.class_section.section,
            })
    return result


def get_teacher_timetable_service(teacher_id):
    from academics.models import Timetable
    slots = Timetable.objects.filter(teacher_id=teacher_id).select_related("class_section", "subject")
    return [
        {
            "day": s.day,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "subject": s.subject.subject_name,
            "class_section": str(s.class_section),
        }
        for s in slots.order_by("day", "start_time")
    ]


def get_class_list_service(class_section_id):
    from accounts.models import StudentProfile
    students = StudentProfile.objects.filter(class_section_id=class_section_id).select_related("user")
    return [
        {
            "id": s.id,
            "full_name": s.user.full_name,
            "roll_number": s.roll_number,
        }
        for s in students
    ]


def upload_grades_service(class_section_id, subject_id, exam_type, marks_data):
    from academics.models import Grade, Subject
    from accounts.models import StudentProfile
    subject = Subject.objects.get(id=subject_id)
    created = []
    for entry in marks_data:
        student = StudentProfile.objects.get(roll_number=entry["roll_number"], class_section_id=class_section_id)
        grade, _ = Grade.objects.update_or_create(
            student=student,
            subject_id=subject_id,
            exam_type=exam_type,
            defaults={
                "obtained_marks": entry["marks"],
                "total_marks": 100,
                "teacher_id": subject.assigned_teacher_id,
            },
        )
        created.append(grade)
    return created


def update_grade_service(grade_id, obtained_marks):
    from academics.models import Grade
    grade = Grade.objects.get(id=grade_id)
    grade.obtained_marks = obtained_marks
    grade.save()
    return grade


def get_class_grades_service(class_section_id, subject_id, exam_type):
    from academics.models import Grade
    grades = Grade.objects.filter(
        student__class_section_id=class_section_id,
        subject_id=subject_id,
        exam_type=exam_type,
    ).select_related("student__user")
    return [
        {
            "student_name": g.student.user.full_name,
            "roll_number": g.student.roll_number,
            "obtained_marks": float(g.obtained_marks),
            "total_marks": float(g.total_marks),
        }
        for g in grades
    ]


def create_assignment_service(class_section_id, subject_id, title, description, due_date, teacher_id):
    from academics.models import Assignment
    assignment = Assignment.objects.create(
        class_section_id=class_section_id,
        subject_id=subject_id,
        title=title,
        description=description,
        due_date=due_date,
        teacher_id=teacher_id,
    )
    return assignment


def update_assignment_service(assignment_id, title=None, description=None, due_date=None, attachment_url=None):
    from academics.models import Assignment
    assignment = Assignment.objects.get(id=assignment_id)
    if title is not None:
        assignment.title = title
    if description is not None:
        assignment.description = description
    if due_date is not None:
        assignment.due_date = due_date
    if attachment_url is not None:
        assignment.attachment_url = attachment_url
    assignment.save()
    return assignment


def delete_assignment_service(assignment_id):
    from academics.models import Assignment
    assignment = Assignment.objects.get(id=assignment_id)
    assignment.delete()
    return True
# ============================================================
# CHILD ALIASES (for Parent tools)
# ============================================================

def get_child_grades_service(child_id, exam_type=None):
    """Alias for get_student_grades_service (parent views child)."""
    return get_student_grades_service(child_id, exam_type)


def get_child_report_card_service(child_id, term=None):
    """Alias for get_student_report_card_service."""
    return get_student_report_card_service(child_id, term)


def get_child_timetable_service(class_section_id):
    """Alias for get_student_timetable_service."""
    return get_student_timetable_service(class_section_id)


def get_child_assignments_service(child_id, status=None):
    """Alias for get_student_assignments_service."""
    return get_student_assignments_service(child_id, status)


def get_child_assignment_details_service(assignment_id, child_id=None):
    """Alias for get_assignment_details_service."""
    return get_assignment_details_service(assignment_id, child_id)