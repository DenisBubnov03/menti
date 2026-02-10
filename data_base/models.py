from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, DECIMAL, ForeignKey, DateTime, Boolean, Text, Numeric, \
    UniqueConstraint, TIMESTAMP, func
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
    rules_accepted = Column(Boolean, default=False, server_default="false")
    career_consultant_id = Column(Integer, ForeignKey("career_consultants.id"), nullable=True)
    career_consultant = relationship("CareerConsultant", back_populates="students")
    meta = relationship("StudentMeta", back_populates="student", uselist=False, lazy="select")

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
    m1_mentor_id = Column(Integer, nullable=True)
    m2_1_2_2_mentor_id = Column(Integer, nullable=True)
    m2_3_3_1_mentor_id = Column(Integer, nullable=True)
    m3_2_mentor_id = Column(Integer, nullable=True)
    m3_3_mentor_id = Column(Integer, nullable=True)
    m4_1_mentor_id = Column(Integer, nullable=True)
    m4_2_4_3_mentor_id = Column(Integer, nullable=True)
    m4_mock_exam_mentor_id = Column(Integer, nullable=True)

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
    m2_exam_mentor_id = Column(Integer, nullable=True)
    m3_exam_mentor_id = Column(Integer, nullable=True)
    m4_topic_mentor_id = Column(Integer, nullable=True)
    m5_topic_mentor_id = Column(Integer, nullable=True)
    m6_topic_mentor_id = Column(Integer, nullable=True)
    m7_topic_mentor_id = Column(Integer, nullable=True)


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

class FullstackTopicAssign(Base):
    __tablename__ = "fullstack_topic_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=False)
    topic_manual = Column(String(255), nullable=True)
    topic_auto = Column(String(255), nullable=True)
    assigned_at = Column(TIMESTAMP, nullable=False)


class Salary(Base):
    """
    Модель данных для таблицы Начислений (Salary).
    Фиксирует расчет суммы, причитающейся куратору за конкретное поступление.
    """
    __tablename__ = 'salary'
    salary_id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey('payments.id'), nullable=False)
    calculated_amount = Column(DECIMAL(10, 2), nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    comment = Column(Text, nullable=True)
    mentor_id = Column(Integer, nullable=False)
    date_calculated = Column(DateTime, default=datetime.now)  # Или Date

    def __repr__(self):
        # Используем self.salary_id для соответствия имени колонки
        return (f"<Salary(id={self.salary_id}, payment_id={self.payment_id}, "
                f"amount={self.calculated_amount}, paid={self.is_paid}, comment='{self.comment[:20]}...')>")


class Payout(Base):
    """
    Реестр фактических выплат кураторам.
    """
    __tablename__ = 'payouts'

    payout_id = Column(Integer, primary_key=True)
    mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=True)

    # 🔥 НОВОЕ ПОЛЕ: Ссылка на карьерного консультанта
    kk_id = Column(Integer, ForeignKey("career_consultants.id"), nullable=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    total_amount = Column(DECIMAL(10, 2), nullable=False)
    payout_status = Column(String(50), nullable=False, default='pending_transfer')
    payout_method = Column(String(50))

    date_processed = Column(DateTime)
    transaction_ref = Column(String(255))
    date_created = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (f"<Payout(id={self.payout_id}, mentor={self.mentor_id}, "
                f"amount={self.total_amount}, status={self.payout_status})>")

class CuratorCommission(Base):
    """
        Таблица учета 'Потолка' (Общего обязательства) перед ментором/директором.
        Создается при трудоустройстве.
        """
    __tablename__ = "curator_commissions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Ссылка на студента (Обязательно)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)

    # Ментор или Директор, которому мы должны
    curator_id = Column(Integer, ForeignKey("mentors.id"), nullable=False)

    # Ссылка на платеж (Опционально, обычно NULL при создании долга)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)

    # Общая сумма, которую мы обещаем выплатить (Потолок)
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)

    # Сколько уже выплатили по факту
    paid_amount = Column(Numeric(10, 2), nullable=False, default=0)

    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Уникальность ПАРЫ: Один студент не может иметь два долга перед ОДНИМ и тем же ментором.
    # Но может иметь долги перед разными менторами.
    __table_args__ = (
        UniqueConstraint('student_id', 'curator_id', name='uq_student_curator_debt'),
    )

    # Связи
    student = relationship("Student", backref="commissions_debt")
    curator = relationship("Mentor")

class CareerConsultant(Base):
    __tablename__ = "career_consultants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(Date, nullable=True)
    students = relationship("Student", back_populates="career_consultant")

    # Отношения
    # students = relationship("Student", back_populates="career_consultant")


class SalaryKK(Base):
    """
    Таблица начислений для Карьерных Консультантов (КК).
    """
    __tablename__ = 'salary_kk'

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey('payments.id'), nullable=False)
    kk_id = Column(Integer, ForeignKey('career_consultants.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)

    # 10% от текущего платежа
    calculated_amount = Column(Numeric(10, 2), nullable=False)

    # Сколько ВСЕГО КК должен получить (10% от ЗП студента)
    total_potential = Column(Numeric(10, 2), nullable=False)

    # Сколько ОСТАЛОСЬ получить после этого начисления
    remaining_limit = Column(Numeric(10, 2), nullable=False)

    is_paid = Column(Boolean, default=False, nullable=False)
    date_calculated = Column(DateTime, default=datetime.utcnow)
    comment = Column(Text, nullable=True)

    # Отношения
    student = relationship("Student")
    kk = relationship("CareerConsultant")
    payment = relationship("Payment")

class StudentMeta(Base):
    """
    Модель мета-данных студентов для реферальной системы и отслеживания источников.
    """
    __tablename__ = "student_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    is_referral = Column(Boolean, default=False, server_default="false")
    referrer_telegram = Column(String(50), nullable=True)
    source = Column(String(50), nullable=True)  # ОМ, Ютуб, Инстаграм, Авито, Сайт, Через знакомых, пусто
    payment_channel = Column(String(20), nullable=True)  # lava, ip, card, crypto — для вычета комиссии из ЗП директоров
    created_at = Column(Date, nullable=True)
    ref_paid = Column(Boolean, default=False, server_default="false")  # <--- Добавить это

    # Отношения
    student = relationship("Student", back_populates="meta")

    def __repr__(self):
        return f"<StudentMeta(id={self.id}, student_id={self.student_id}, is_referral={self.is_referral}, source={self.source})>"
