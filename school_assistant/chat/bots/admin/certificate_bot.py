"""
Certificates Bot ("The Document Writer")
Scope: drafts leaving certificates, clearance letters, appreciation texts.
Example: "Generate a merit certificate for Zain Ali."

Note: this bot only *drafts* the wording for the Admin to review. Saving
the final approved text to the Certificate table happens through the
existing certificate-generate API (administration app), not here.
"""
from chat.bots.base import BaseBot
from chat.bots.utils import resolve_student

CERT_TYPE_KEYWORDS = {
    "leaving": "leaving",
    "clearance": "clearance",
    "merit": "merit",
    "appreciation": "appreciation",
    "event": "event",
}


class CertificateBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Document Writer', the School ERP's Certificates Bot. You "
            "draft formal school documents: leaving certificates, clearance letters, "
            "merit/appreciation certificates, and event certificates. Write in "
            "professional, formal certificate language. Leave a [School Name] and "
            "[Principal Signature] placeholder where appropriate. Base every fact you "
            "state (name, class, roll number, dates, achievements) strictly on the "
            "context provided -- never invent a fact you don't have."
        )

    def build_context(self) -> str:
        student = resolve_student(self.message)
        if not student:
            return (
                "No matching student was found by name or roll number in the "
                "message. Ask the Admin to confirm the student's full name or "
                "roll number before drafting anything."
            )

        text_l = self.message.lower()
        cert_type = next((v for k, v in CERT_TYPE_KEYWORDS.items() if k in text_l), "merit")

        lines = [
            f"Requested certificate type: {cert_type}",
            f"Student: {student.user.full_name}",
            f"Roll number: {student.roll_number or 'not assigned'}",
            f"Class section: {student.class_section}",
            f"Guardian: {student.guardian_name or 'not on file'}",
        ]

        from academics.models import Grade
        from administration.models import EventParticipation

        top_grades = (
            Grade.objects.filter(student=student, exam_type="Final")
            .select_related("subject")
            .order_by("-obtained_marks")[:5]
        )
        if top_grades:
            lines.append("Recent Final exam results:")
            for g in top_grades:
                lines.append(f"- {g.subject.subject_name}: {g.obtained_marks}/{g.total_marks}")

        participations = (
            EventParticipation.objects.filter(student=student)
            .select_related("event")
            .order_by("-event__event_date")[:5]
        )
        if participations:
            lines.append("Event participation history:")
            for p in participations:
                lines.append(f"- {p.event.event_name} ({p.event.event_date:%Y-%m-%d}): {p.role} {p.position}")

        return "\n".join(lines)