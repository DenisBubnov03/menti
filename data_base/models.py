from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, DECIMAL, ForeignKey, DateTime, Boolean, Text, Numeric
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
    m5_start_date = Column(Date)

    def __repr__(self):
        return f"<Payment(id={self.id}, student_id={self.student_id}, mentor_id={self.mentor_id}, amount={self.amount}, date={self.payment_date})>"


Student.payments = relationship("Payment", back_populates="student", cascade="all, delete-orphan")
Mentor.payments = relationship("Payment", back_populates="mentor", cascade="all, delete-orphan")


class AutoProgress(Base):
    __tablename__ = "auto_progress"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    # Модули 1-8: просто факт открытия (можно добавить даты при необходимости)
    m1_opened = Column(Boolean, default=False)
    m2_opened = Column(Boolean, default=False)
    m3_opened = Column(Boolean, default=False)
    m4_opened = Column(Boolean, default=False)
    m5_opened = Column(Boolean, default=False)
    m6_opened = Column(Boolean, default=False)
    m7_opened = Column(Boolean, default=False)
    m8_opened = Column(Boolean, default=False)
    # Для 2 и 3 модуля — экзамен
    m2_exam_passed = Column(Boolean, default=False)
    m3_exam_passed = Column(Boolean, default=False)
    # Для 4-7 модулей — сдача темы
    m4_topic_passed = Column(Boolean, default=False)
    m5_topic_passed = Column(Boolean, default=False)
    m6_topic_passed = Column(Boolean, default=False)
    m7_topic_passed = Column(Boolean, default=False)
