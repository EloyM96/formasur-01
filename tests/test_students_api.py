from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import students as students_module
from app.models import Base, Course, Enrollment, Student


def _create_session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


class StubRuleSet:
    def evaluate(self, context):
        row = context["row"]
        certificate = row.get("certificate_expires_at")
        vencido = bool(certificate and certificate < "2024-01-01")
        horas_insuficientes = bool(
            row.get("hours_required") is not None
            and row.get("progress_hours", 0) < row.get("hours_required")
        )
        return {
            "vencido": vencido,
            "horas_insuficientes": horas_insuficientes,
        }


def test_list_students_non_compliance_filters(monkeypatch):
    SessionFactory = _create_session_factory()

    with SessionFactory() as session:
        course = Course(
            name="PRL Básico",
            hours_required=8,
            deadline_date=date(2024, 5, 20),
            source="xlsx",
        )
        session.add(course)
        session.flush()

        compliant = Student(
            full_name="Luis López",
            email="luis@example.com",
            course="PRL Básico",
            certificate_expires_at=date(2025, 1, 1),
        )
        non_compliant = Student(
            full_name="Ana Pérez",
            email="ana@example.com",
            course="PRL Básico",
            certificate_expires_at=date(2023, 12, 31),
        )
        session.add_all([compliant, non_compliant])
        session.flush()

        session.add_all(
            [
                Enrollment(
                    course_id=course.id,
                    student_id=compliant.id,
                    progress_hours=9.0,
                    status="active",
                ),
                Enrollment(
                    course_id=course.id,
                    student_id=non_compliant.id,
                    progress_hours=4.0,
                    status="active",
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(students_module, "get_ruleset", lambda: StubRuleSet())

    with SessionFactory() as session:
        data = students_module.list_non_compliant_students(session=session)
        assert data["total"] == 1
        assert data["items"][0]["student"]["full_name"] == "Ana Pérez"
        assert data["items"][0]["violations"] == [
            "vencido",
            "horas_insuficientes",
        ]

    with SessionFactory() as session:
        data = students_module.list_non_compliant_students(
            status="active", deadline_before="2024-06-01", session=session
        )
        assert data["total"] == 1

    with SessionFactory() as session:
        data = students_module.list_non_compliant_students(
            min_hours=5, session=session
        )
        assert data["total"] == 0

    with SessionFactory() as session:
        data = students_module.list_non_compliant_students(rule="vencido", session=session)
        assert data["total"] == 1

    with SessionFactory() as session:
        data = students_module.list_non_compliant_students(course="PRL", session=session)
        assert data["total"] == 1

    with SessionFactory() as session:
        data = students_module.list_non_compliant_students(
            deadline_before="2024-05-01", session=session
        )
        assert data["total"] == 0
