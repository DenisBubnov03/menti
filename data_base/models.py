from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, DECIMAL, ForeignKey, DateTime, Boolean, Text, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from data_base import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fio = Column(String(255), nullable=False)
    telegram = Column(String(50), unique=True, nullable=False)
    chat_id = Column(String(50), unique=True, nullable=True)
    contract_signed = Column(Boolean, default=False, server_default="false")
    start_date = Column(Date, nullable=True)
    training_type = Column(String(255), nullable=True)
    total_cost = Column(DECIMAL(10, 2), nullable=True)
    payment_amount = Column(DECIMAL(10, 2), nullable=True)
    last_call_date = Column(Date, nullable=True)
    company = Column(String(255), nullable=True)
    employment_date = Column(Date, nullable=True)
    salary = Column(DECIMAL(10, 2), default=0, server_default="0")
    fully_paid = Column(String(10), default="Нет", server_default="Нет")
    training_status = Column(String(255), default="Учится", server_default="Учится")
    commission = Column(String(255), nullable=True)
    commission_paid = Column(DECIMAL(10, 2), default=0, server_default="0")
    mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=False)
    auto_mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=True)

class Mentor(Base):
    __tablename__ = "mentors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    chat_id = Column(String, nullable=True)
    direction = Column(String, unique=True, nullable=False)


class Homework(Base):
    __tablename__ = "homework"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    module = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    status = Column(String, default="ожидает проверки")
    created_at = Column(DateTime, default=datetime.utcnow)
    mentor_id = Column(Integer, ForeignKey('mentors.id'))
    student = relationship("Student", backref="homeworks")

class Payment(Base):
    """
    Модель платежей для отслеживания оплат студентов.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный ID платежа
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)  # Привязка к студенту
    mentor_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)  # Привязка к ментору
    amount = Column(Numeric(10, 2), nullable=False)  # Сумма платежа
    payment_date = Column(Date, nullable=False)  # Дата платежа
    comment = Column(Text, nullable=True)  # Комментарий к платежу (например, "Первый платеж")
    status = Column(String(20), default="не подтвержден", nullable=False)

    # Отношения (если нужны)
    student = relationship("Student", back_populates="payments")
    mentor = relationship("Mentor", back_populates="payments")

class ManualProgress(Base):
    __tablename__ = "manual_progress"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)

    m1_start_date = Column(Date)
    m1_submission_date = Column(Date)
    m1_homework = Column(Boolean)

    m2_1_start_date = Column(Date)
    m2_2_start_date = Column(Date)
    m2_1_2_2_submission_date = Column(Date)
    m2_1_homework = Column(Boolean)

    m2_3_start_date = Column(Date)
    m3_1_start_date = Column(Date)
    m2_3_3_1_submission_date = Column(Date)
    m2_3_homework = Column(Boolean)
    m3_1_homework = Column(Boolean)

    m3_2_start_date = Column(Date)
    m3_2_submission_date = Column(Date)
    m3_2_homework = Column(Boolean)

    m3_3_start_date = Column(Date)
    m3_3_submission_date = Column(Date)
    m3_3_homework = Column(Boolean)

    m4_1_start_date = Column(Date)
    m4_1_submission_date = Column(Date)

    m4_2_start_date = Column(Date)
    m4_3_start_date = Column(Date)
    m4_2_4_3_submission_date = Column(Date)
    m4_5_homework = Column(Boolean)
    m4_mock_exam_passed_date = Column(Date)
    m5_start_date = Column(Date)

    def __repr__(self):
        return f"<Payment(id={self.id}, student_id={self.student_id}, mentor_id={self.mentor_id}, amount={self.amount}, date={self.payment_date})>"


Student.payments = relationship("Payment", back_populates="student", cascade="all, delete-orphan")
Mentor.payments = relationship("Payment", back_populates="mentor", cascade="all, delete-orphan")


class AutoProgress(Base):
    __tablename__ = "auto_progress"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    # Модули 1-8: даты открытия
    m1_start_date = Column(Date)
    m2_start_date = Column(Date)
    m3_start_date = Column(Date)
    m4_start_date = Column(Date)
    m5_start_date = Column(Date)
    m6_start_date = Column(Date)
    m7_start_date = Column(Date)
    m8_start_date = Column(Date)
    # Для 2 и 3 модуля — даты сдачи экзаменов
    m2_exam_passed_date = Column(Date)
    m3_exam_passed_date = Column(Date)
    # Для 4-7 модулей — даты сдачи тем
    m4_topic_passed_date = Column(Date)
    m5_topic_passed_date = Column(Date)
    m6_topic_passed_date = Column(Date)
    m7_topic_passed_date = Column(Date)


class AIHomeworkCheck(Base):
    __tablename__ = "ai_homework_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("homework.id"), nullable=False)
    topic = Column(String, nullable=False)
    model = Column(String, nullable=False)
    status = Column(String, nullable=False)  # queued, running, done, error
    result_json = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    homework = relationship("Homework", backref="ai_checks")
