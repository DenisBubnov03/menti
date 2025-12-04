from sqlalchemy.orm import Session
from data_base.models import Student, Salary, CuratorCommission, ManualProgress, \
    AutoProgress  # Добавлены CuratorCommission и прогресс-модели
from sqlalchemy import inspect
import config
from typing import Dict, Any

# =======================================================================
# 1. КОНСТАНТЫ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (Вне класса)
# =======================================================================

# Определяем ID директоров (по вашей логике)
DIRECTOR_ID_MANUAL = 1
DIRECTOR_ID_AUTO = 3


def _get_flow_roles_and_rates(student):
    """
    Определяет роли и процент фонда (20% или 30%) на основе привязки студента.
    """

    # 1. Определяем поток
    is_manual = bool(student.mentor_id)

    # 2. Определяем ID
    curator_id = student.mentor_id if is_manual else student.auto_mentor_id
    director_payout_id = DIRECTOR_ID_MANUAL if is_manual else DIRECTOR_ID_AUTO

    # 3. Проверка: Является ли Куратор Директором? (для определения 30% и исключения 10% бонуса)
    is_director_curator = (curator_id == director_payout_id)

    # 30% (если Директор-Куратор) или 20% (обычный Куратор)
    fund_percent = 0.30 if is_director_curator else 0.20

    return {
        "curator_id": curator_id,
        "director_id": director_payout_id,
        "is_director_curator": is_director_curator,
        "is_manual": is_manual,
        "fund_percent": fund_percent,
        "comment_suffix": "ручного направления" if is_manual else "авто направления"
    }


def _get_theme_price_for_flow(manager_instance, mentor_id: int, is_manual: bool) -> float:
    """Вызывает соответствующую функцию расчета цены темы для куратора/директора."""
    if is_manual:
        # Calls _calculate_amount_manual
        price, _ = manager_instance._calculate_amount_manual(mentor_id=mentor_id, amount=1.0)
    else:
        # Calls _calculate_amount_auto
        price, _ = manager_instance._calculate_amount_auto(mentor_id=mentor_id, amount=1.0)
    return price


# =======================================================================
# 2. ОСНОВНОЙ КЛАСС MANAGER
# =======================================================================

class SalaryManager:
    """
    Класс отвечает за расчет комиссии и создание записи в таблице salary.
    """

    # --- СТАРЫЕ МЕТОДЫ (Используются для расчета theme_price) ---

    def _calculate_amount_manual(self, mentor_id: int, amount: float) -> tuple[float, str]:
        base_rate_kurator = config.Config.MANUAL_CURATOR_RESERVE_PERCENT
        count_calls_total = config.Config.MANUAL_CALLS_TOTAL
        course_cost = config.Config.FULLSTACK_MANUAL_COURSE_COST
        base_rate_dir = config.Config.MANUAL_DIR_RESERVE_PERCENT

        # Здесь используется base_rate_kurator (20%) или base_rate_dir (30%)
        if mentor_id != 1:
            try:
                calls_price = (course_cost * base_rate_kurator) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0
            comment = "Оплата за 1 принятую тему ручного направления куратору. "
            return calls_price, comment
        else:
            try:
                calls_price = (course_cost * base_rate_dir) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0
            comment = "Оплата за 1 принятую тему ручного направления директору."
            return calls_price, comment

    def _calculate_amount_auto(self, mentor_id: int, amount: float) -> tuple[float, str]:
        base_rate_kurator = config.Config.AUTO_CURATOR_RESERVE_PERCENT
        count_calls_total = config.Config.AUTO_CALLS_TOTAL
        course_cost = config.Config.FULLSTACK_AUTO_COURSE_COST
        base_rate_dir = config.Config.AUTO_DIR_RESERVE_PERCENT

        if mentor_id != 3:
            try:
                calls_price = (course_cost * base_rate_kurator) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0
            comment = "Оплата за 1 принятую тему авто направления куратору. "
            return calls_price, comment
        else:
            try:
                calls_price = (course_cost * base_rate_dir) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0
            comment = f"Оплата за 1 принятую тему авто направления директору. "
            return calls_price, comment

    # --- ИНИЦИАЛИЗАЦИЯ (Создание Долга) ---

    def init_curator_commission(self, session: Session, student_id: int, student_salary: float):
        """
        Создает/обновляет запись о долге перед куратором (20% или 30% от ЗП ученика).
        """
        from data_base.models import Student, CuratorCommission

        student = session.query(Student).filter_by(id=student_id).first()
        if not student: return None

        roles = _get_flow_roles_and_rates(student)
        if not roles["curator_id"]: return None

        # Расчет Общего Бюджета Куратора (20% или 30%)
        total_commission_value = float(student_salary) * roles["fund_percent"]

        # Проверяем, нет ли уже записи
        existing_debt = session.query(CuratorCommission).filter_by(student_id=student_id).first()

        if existing_debt:
            # Обновляем, если есть
            existing_debt.total_amount = total_commission_value
            existing_debt.curator_id = roles["curator_id"]
            session.add(existing_debt)
            return existing_debt

        # Создаем новую запись
        new_commission = CuratorCommission(
            student_id=student_id,
            curator_id=roles["curator_id"],
            payment_id=None,
            total_amount=total_commission_value,
            paid_amount=0.0
        )
        session.add(new_commission)
        return new_commission

    # --- ПОДСЧЕТ ТЕМ (Static Method) ---

    @staticmethod
    def count_all_completed_tasks(session: Session, student_id: int, is_manual_flow: bool) -> dict:
        """
        Считает общее количество сданных тем/модулей для ОДНОГО ученика.
        """
        # Локальный импорт моделей
        from data_base.models import ManualProgress, AutoProgress

        if is_manual_flow:
            ProgressModel = ManualProgress
            TASK_FIELDS = [
                'm1_submission_date', 'm2_1_2_2_submission_date', 'm2_3_3_1_submission_date',
                'm3_2_submission_date', 'm3_3_submission_date', 'm4_1_submission_date',
                'm4_2_4_3_submission_date', 'm4_mock_exam_passed_date'
            ]
        else:
            ProgressModel = AutoProgress
            TASK_FIELDS = [
                'm2_exam_passed_date', 'm3_exam_passed_date', 'm4_topic_passed_date',
                'm5_topic_passed_date', 'm6_topic_passed_date', 'm7_topic_passed_date'
            ]

        progress = session.query(ProgressModel).filter_by(student_id=student_id).first()
        total_completed_tasks = 0

        if progress:
            completed_count = 0
            for field_name in TASK_FIELDS:
                submission_date = getattr(progress, field_name, None)
                if submission_date is not None:
                    completed_count += 1
            total_completed_tasks = completed_count

        return {
            'total_tasks': total_completed_tasks,
            'details': {student_id: total_completed_tasks}
        }

    # --- ОСНОВНАЯ ФУНКЦИЯ РАСПРЕДЕЛЕНИЯ ПЛАТЕЖА ---

    def create_salary_entry_from_payment(self, session: Session, payment_id: int, student_id: int,
                                         payment_amount: float):
        """
        Логика распределения входящего платежа 'Комиссия':
        1. Директор: 10% от суммы платежа (если не ведет студента).
        2. Куратор/Директор: Выплата накопленной комиссии (за темы) в пределах платежа.
        """
        from data_base.models import Student, Salary, CuratorCommission
        import config

        payment_amount = float(payment_amount)
        student = session.query(Student).filter_by(id=student_id).first()
        if not student: return

        # 1. Получаем все долги
        debts = session.query(CuratorCommission).filter_by(student_id=student_id).all()
        if not debts: return

        # Константы (проверьте ID!)
        DIRECTOR_ID_MANUAL = 1
        DIRECTOR_ID_AUTO = 3

        # Список запланированных выплат: [{'debt_record': obj, 'amount': float, 'comment': str}, ...]
        planned_payouts = []
        total_planned_amount = 0.0

        # ==========================================
        # ЭТАП 1: РАСЧЕТ ИДЕАЛЬНЫХ ВЫПЛАТ
        # ==========================================
        for debt_record in debts:
            remaining_debt = float(debt_record.total_amount) - float(debt_record.paid_amount)
            if remaining_debt <= 0: continue

            mentor_id = debt_record.curator_id
            calculated_amount = 0.0
            comment = ""

            # --- Логика определения роли ---
            is_bonus_receiver = (mentor_id in [DIRECTOR_ID_MANUAL, DIRECTOR_ID_AUTO]) and \
                                (mentor_id != student.mentor_id) and \
                                (mentor_id != student.auto_mentor_id)

            if is_bonus_receiver:
                # --- ДИРЕКТОР (БОНУС) ---
                # Логика: Доля от платежа должна соответствовать доле долга от всей ЗП
                if float(student.salary) > 0:
                    share = payment_amount / float(student.salary)
                    calculated_amount = float(debt_record.total_amount) * share
                else:
                    # Фоллбек: 10% от платежа, если ЗП кривая
                    calculated_amount = payment_amount * 0.10

                comment = f"Бонус Директора: доля от {payment_amount}"

            else:
                # --- КУРАТОР (ЗА РАБОТУ) ---
                target_is_manual = (mentor_id == student.mentor_id) or (mentor_id == DIRECTOR_ID_MANUAL)

                # Считаем прогресс
                progress_data = SalaryManager.count_all_completed_tasks(session, student_id, target_is_manual)
                completed_themes = progress_data['total_tasks']

                # Цена темы = Весь Долг / Всего Тем
                total_calls = config.Config.MANUAL_CALLS_TOTAL if target_is_manual else config.Config.AUTO_CALLS_TOTAL
                if total_calls > 0:
                    price_per_theme = float(debt_record.total_amount) / total_calls
                else:
                    price_per_theme = 0

                earned_total = price_per_theme * completed_themes
                to_pay = earned_total - float(debt_record.paid_amount)

                calculated_amount = max(0.0, to_pay)
                if student.mentor_id != 1 or student.auto_mentor_id != 3:
                    comment = f"Куратор: {completed_themes} тем * {price_per_theme:.2f}"
                else:
                    comment = f"Директор: {completed_themes} тем * {price_per_theme:.2f}"

            # Лимит: нельзя заплатить больше, чем остаток долга
            calculated_amount = min(calculated_amount, remaining_debt)

            if calculated_amount > 0:
                planned_payouts.append({
                    "debt_record": debt_record,
                    "amount": calculated_amount,
                    "comment": comment,
                    "mentor_id": mentor_id,
                    "remaining_debt_after": remaining_debt - calculated_amount  # Для инфо
                })
                total_planned_amount += calculated_amount

        # ==========================================
        # ЭТАП 2: БАЛАНСИРОВКА (ЕСЛИ ДЕНЕГ НЕ ХВАТАЕТ)
        # ==========================================
        # Если мы насчитали выплат на 60к, а платеж всего 50к -> уменьшаем всем пропорционально
        ratio = 1.0
        if total_planned_amount > payment_amount:
            ratio = payment_amount / total_planned_amount
            # Например: 50000 / 60000 = 0.8333...

        # ==========================================
        # ЭТАП 3: СОХРАНЕНИЕ
        # ==========================================
        for plan in planned_payouts:
            final_amount = plan["amount"] * ratio

            # Округляем до 2 знаков, чтобы не было копеек
            final_amount = round(final_amount, 2)

            if final_amount > 0:
                # Добавляем инфо о коэффициенте в комментарий, если он был применен
                final_comment = plan["comment"]
                if ratio < 1.0:
                    final_comment += f" (Скорректировано: {ratio:.2f})"

                final_comment += f". Остаток долга: {plan['remaining_debt_after'] + (plan['amount'] - final_amount):.2f}"

                # Запись в Salary
                session.add(Salary(
                    payment_id=payment_id,
                    mentor_id=plan["mentor_id"],
                    calculated_amount=final_amount,
                    comment=final_comment,
                    is_paid=False
                ))

                # Обновление долга
                debt_record = plan["debt_record"]
                debt_record.paid_amount = float(debt_record.paid_amount) + final_amount
                session.add(debt_record)

                # Обновление студента
                student.commission_paid = float(student.commission_paid or 0) + final_amount
                session.add(student)
    def _calculate_commission_curator_fullstack(self, session: Session, mentor_id: int, telegram: str,):
        pass

    def _calculate_commission_dir(self, session: Session, mentor_id: int, telegram: str,):
        pass

    def _calculate_commission_dir_fullstack(self, session: Session, mentor_id: int, telegram: str,):
        pass


