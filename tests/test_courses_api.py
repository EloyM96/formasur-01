from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import courses as courses_module
from app.models import Base, Course, Enrollment, Notification, Student


def _create_session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


class StubRuleSet:
    def evaluate(self, context):
        row = context["row"]
        progress = row.get("progress_hours") or 0
        required = row.get("hours_required") or 0
        return {
            "horas_insuficientes": progress < required,
            "sin_actividad": progress <= 0,
        }


def test_course_list_and_detail(monkeypatch):
    SessionFactory = _create_session_factory()

    with SessionFactory() as session:
        course = Course(
            name="PRL Básico",
            hours_required=20,
            deadline_date=date(2024, 12, 31),
            source="xlsx",
        )
        session.add(course)
        session.flush()
        course_id = course.id

        active = Student(
            full_name="Laura García",
            email="laura@example.com",
            course=course.name,
            certificate_expires_at=date(2025, 1, 10),
        )
        idle = Student(
            full_name="Jorge Ruiz",
            email="jorge@example.com",
            course=course.name,
            certificate_expires_at=date(2024, 11, 20),
        )
        session.add_all([active, idle])
        session.flush()

        enrollment_active = Enrollment(
            course_id=course.id,
            student_id=active.id,
            progress_hours=10.0,
            status="active",
        )
        enrollment_idle = Enrollment(
            course_id=course.id,
            student_id=idle.id,
            progress_hours=0.0,
            status="active",
        )
        session.add_all([enrollment_active, enrollment_idle])
        session.flush()

        session.add_all(
            [
                Notification(
                    enrollment_id=enrollment_active.id,
                    channel="email",
                    adapter="EmailSMTPAdapter",
                    recipient=active.email,
                    status="sent",
                    payload={},
                ),
                Notification(
                    enrollment_id=enrollment_idle.id,
                    channel="sms",
                    adapter="CLIAdapter",
                    recipient="+34123456",
                    status="sent",
                    payload={},
                ),
                Notification(
                    enrollment_id=enrollment_idle.id,
                    channel="whatsapp",
                    adapter="WhatsAppCLIAdapter",
                    recipient="+34987654",
                    status="sent",
                    payload={},
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(courses_module, "_RULESET_CACHE", StubRuleSet())

    with SessionFactory() as session:
        data = courses_module.list_courses(session=session)

    assert data["total"] == 1
    summary = data["items"][0]
    assert summary["course"]["name"] == "PRL Básico"
    assert summary["metrics"]["total_enrollments"] == 2
    assert summary["metrics"]["non_compliant_enrollments"] == 2
    assert summary["metrics"]["zero_hours_enrollments"] == 1
    assert summary["notifications"]["total"] == 3
    assert summary["notifications"]["by_channel"]["email"] == 1

    with SessionFactory() as session:
        detail = courses_module.course_detail(course_id=course_id, session=session)

    assert detail["course"]["name"] == "PRL Básico"
    assert len(detail["students"]) == 2
    violations_sets = [set(item["violations"]) for item in detail["students"]]
    assert any("sin_actividad" in violations for violations in violations_sets)
    assert any(item["has_no_activity"] for item in detail["students"])
    channel_maps = [item["notifications"]["by_channel"] for item in detail["students"]]
    assert any(ch and ch.get("whatsapp") == 1 for ch in channel_maps)


def test_course_update(monkeypatch):
    SessionFactory = _create_session_factory()

    with SessionFactory() as session:
        course = Course(
            name="PRL Avanzado",
            hours_required=15,
            deadline_date=date(2024, 10, 1),
            source="xlsx",
        )
        session.add(course)
        session.commit()
        course_id = course.id

    monkeypatch.setattr(courses_module, "_RULESET_CACHE", StubRuleSet())

    payload = courses_module.CourseUpdatePayload(
        deadline_date=date(2024, 11, 1),
        hours_required=18,
    )

    with SessionFactory() as session:
        updated = courses_module.update_course(
            course_id=course_id,
            payload=payload,
            session=session,
        )

    assert updated["deadline_date"] == date(2024, 11, 1)
    assert updated["hours_required"] == 18

