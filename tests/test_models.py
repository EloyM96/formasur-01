from datetime import date

from app.models import Student, StudentModel


def test_student_model_serializes_from_orm():
    student = Student(
        id=1,
        full_name="Ana Pérez",
        email="ana@example.com",
        course="PRL Básico",
        certificate_expires_at=date(2025, 5, 20),
    )

    model = StudentModel.model_validate(student)

    assert model.full_name == "Ana Pérez"
    assert model.email == "ana@example.com"
    assert model.certificate_expires_at == date(2025, 5, 20)
