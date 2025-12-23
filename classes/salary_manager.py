# classes/salary_manager.py

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

    # ❗ ИСПРАВЛЕНИЕ: Добавлен объект student
    def _calculate_amount_manual(self, student: Student, mentor_id: int, amount: float) -> tuple[float, str]:

        # 1. ОПРЕДЕЛЕНИЕ СТОИМОСТИ КУРСА
        is_fullstack = (student.mentor_id is not None) and (student.auto_mentor_id is not None)

        if is_fullstack:
            # Для фуллстека берем стоимость из конфига
            course_cost = config.Config.FULLSTACK_MANUAL_COURSE_COST
        elif student.total_cost:
            # ДЛЯ НЕ-ФУЛЛСТЕКА берем стоимость из поля total_cost
            course_cost = float(student.total_cost)
        else:
            # Фоллбек
            course_cost = config.Config.FULLSTACK_MANUAL_COURSE_COST

        base_rate_kurator = config.Config.MANUAL_CURATOR_RESERVE_PERCENT
        count_calls_total = config.Config.MANUAL_CALLS_TOTAL
        base_rate_dir = config.Config.MANUAL_DIR_RESERVE_PERCENT

        # 2. ОСНОВНОЙ РАСЧЕТ (использует динамический course_cost)
        if mentor_id != 1:
            try:
                calls_price = (course_cost * base_rate_kurator) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = ("Оплата за 1 принятую тему ручного направления куратору. ")
            return calls_price, comment
        else:
            try:
                calls_price = (course_cost * base_rate_dir) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = ("Оплата за 1 принятую тему ручного направления директору.")
            return calls_price, comment

    def _calculate_amount_auto(self, student: Student, mentor_id: int, amount: float) -> tuple[float, str]:

        # 1. ОПРЕДЕЛЕНИЕ СТОИМОСТИ КУРСА
        is_fullstack = (student.mentor_id is not None) and (student.auto_mentor_id is not None)

        if is_fullstack:
            course_cost = config.Config.FULLSTACK_AUTO_COURSE_COST
        elif student.total_cost:
            # ДЛЯ НЕ-ФУЛЛСТЕКА берем стоимость из поля total_cost
            course_cost = float(student.total_cost)
        else:
            course_cost = config.Config.FULLSTACK_AUTO_COURSE_COST

        base_rate_kurator = config.Config.AUTO_CURATOR_RESERVE_PERCENT
        count_calls_total = config.Config.AUTO_CALLS_TOTAL
        base_rate_dir = config.Config.AUTO_DIR_RESERVE_PERCENT

        # 2. ОСНОВНОЙ РАСЧЕТ
        if mentor_id != 3:
            try:
                calls_price = (course_cost * base_rate_kurator) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = ("Оплата за 1 принятую тему авто направления куратору. ")
            return calls_price, comment
        else:
            try:
                calls_price = (course_cost * base_rate_dir) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = (f"Оплата за 1 принятую тему авто направления директору. ")
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

    # =======================================================================
    # 3. ЛОГИКА ИНИЦИАЛИЗАЦИИ 10% БОНУСА ДИРЕКТОРА
    # =======================================================================

    def init_director_bonus_commission(self, session: Session, student: Student):
        """
        Создает запись о 10% долге перед Директором при добавлении нового студента.
        Применяется только для Ручного и Автотестирования, если Директор не является куратором.
        """
        # 1. Проверка типа обучения и директора
        training_type = student.training_type.strip().lower() if student.training_type else ""
        director_id = None
        mentor_id_field = None
        direction_name = None

        if training_type == "ручное тестирование":
            director_id = DIRECTOR_ID_MANUAL  # ID = 1
            mentor_id_field = student.mentor_id
            direction_name = "Ручное тестирование"
        elif training_type == "автотестирование":
            director_id = DIRECTOR_ID_AUTO  # ID = 3
            mentor_id_field = student.auto_mentor_id
            direction_name = "Автотестирование"
        elif training_type == "фуллстек":
            # Для фуллстека бонус не начисляется при добавлении (по условию)
            return None
        else:
            return None  # Неизвестный тип

        # 2. Проверка, что Директор не является куратором студента
        if director_id == mentor_id_field:
            print(
                f"Warn: Director {director_id} is also the curator for student {student.telegram}. Skipping 10% bonus init.")
            return None

        # 3. Проверка стоимости
        if not student.total_cost or float(student.total_cost) <= 0:
            print(f"Warn: Student {student.telegram} has no total_cost. Skipping 10% bonus init.")
            return None

        # 4. Расчет 10% комиссии
        bonus_percent = 0.10
        total_commission_value = float(student.total_cost) * bonus_percent

        # 5. Проверка: нет ли уже такой записи
        from data_base.models import CuratorCommission
        existing_debt = session.query(CuratorCommission).filter_by(
            student_id=student.id,
            curator_id=director_id
        ).first()

        if existing_debt:
            print(
                f"Warn: Director bonus already exists for student {student.telegram} and director {director_id}. Skipping init.")
            return existing_debt

        # 6. Создаем новую запись в CuratorCommission
        new_commission = CuratorCommission(
            student_id=student.id,
            curator_id=director_id,
            payment_id=None,
            total_amount=total_commission_value,
            paid_amount=0.0
        )
        session.add(new_commission)
        print(
            f"Info: Initialized 10% director bonus ({total_commission_value:.2f}₽) for student {student.telegram} ({direction_name})")
        return new_commission

    # --- ПОДСЧЕТ ТЕМ (Static Method) ---

    @staticmethod
    def count_all_completed_tasks(session: Session, student_id: int, is_manual_flow: bool,
                                  target_mentor_id: int = None) -> dict:
        """
        Считает количество тем, сданных КОНКРЕТНОМУ ментору (target_mentor_id).
        Если target_mentor_id не передан, считает все сданные темы (старая логика).
        """
        from data_base.models import ManualProgress, AutoProgress

        if is_manual_flow:
            ProgressModel = ManualProgress
            # Словарь: поле_даты -> поле_ментора
            TASK_MAP = {
                'm1_submission_date': 'm1_mentor_id',
                'm2_1_2_2_submission_date': 'm2_1_2_2_mentor_id',
                'm2_3_3_1_submission_date': 'm2_3_3_1_mentor_id',
                'm3_2_submission_date': 'm3_2_mentor_id',
                'm3_3_submission_date': 'm3_3_mentor_id',
                'm4_1_submission_date': 'm4_1_mentor_id',
                'm4_2_4_3_submission_date': 'm4_2_4_3_mentor_id',
                'm4_mock_exam_passed_date': 'm4_mock_exam_mentor_id'
            }
        else:
            ProgressModel = AutoProgress
            TASK_MAP = {
                'm2_exam_passed_date': 'm2_exam_mentor_id',
                'm3_exam_passed_date': 'm3_exam_mentor_id',
                'm4_topic_passed_date': 'm4_topic_mentor_id',
                'm5_topic_passed_date': 'm5_topic_mentor_id',
                'm6_topic_passed_date': 'm6_topic_mentor_id',
                'm7_topic_passed_date': 'm7_topic_mentor_id'
            }

        progress = session.query(ProgressModel).filter_by(student_id=student_id).first()
        total_completed_tasks = 0

        if progress:
            for date_field, mentor_field in TASK_MAP.items():
                submission_date = getattr(progress, date_field, None)

                # Тема должна быть сдана
                if submission_date is not None:
                    # Если нам важен конкретный ментор - проверяем ID
                    if target_mentor_id is not None:
                        accepted_by_id = getattr(progress, mentor_field, None)
                        if accepted_by_id == target_mentor_id:
                            total_completed_tasks += 1
                    else:
                        # Если ID не важен (считаем "вообще" прогресс студента), просто плюсуем
                        total_completed_tasks += 1

        return {
            'total_tasks': total_completed_tasks,
            'details': {student_id: total_completed_tasks}
        }
    # --- ОСНОВНАЯ ФУНКЦИЯ РАСПРЕДЕЛЕНИЯ ПЛАТЕЖА ---

        # Внутри SalaryManager

    def create_salary_entry_from_payment(self, session: Session, payment_id: int, student_id: int,
                                             payment_amount: float):
            """
            Распределяет платеж, учитывая КТО именно принимал темы (Вариант 3: Именная метка).
            """
            from data_base.models import Student, Salary, CuratorCommission
            import config

            payment_amount = float(payment_amount)
            student = session.query(Student).filter_by(id=student_id).first()
            if not student: return

            debts = session.query(CuratorCommission).filter_by(student_id=student_id).all()
            if not debts: return

            DIRECTOR_ID_MANUAL = 1
            DIRECTOR_ID_AUTO = 3

            planned_payouts = []
            total_planned_amount = 0.0

            for debt_record in debts:
                remaining_debt = float(debt_record.total_amount) - float(debt_record.paid_amount)
                if remaining_debt <= 0: continue

                mentor_id = debt_record.curator_id
                calculated_amount = 0.0
                comment = ""

                # 1. Проверяем, это Бонус Директора? (Выплата за факт денег)
                is_bonus_receiver = (mentor_id in [DIRECTOR_ID_MANUAL, DIRECTOR_ID_AUTO]) and \
                                    (mentor_id != student.mentor_id) and \
                                    (mentor_id != student.auto_mentor_id)

                if is_bonus_receiver:
                    # --- ЛОГИКА БОНУСА (Не зависит от сданных тем) ---
                    base_val = float(student.total_cost) if student.total_cost else float(student.salary)
                    if base_val > 0:
                        share = payment_amount / base_val
                        calculated_amount = float(debt_record.total_amount) * share
                    else:
                        calculated_amount = payment_amount * 0.10  # Фоллбек

                    comment = f"Бонус Директора за {student.telegram}: доля от {payment_amount}"

                else:
                    # --- ЛОГИКА КУРАТОРА (Платим только за ЕГО темы) ---

                    # Определяем, в какой таблице искать (Ручной или Авто)
                    # Если ментор закреплен как ручной (или это Директор ручного), ищем в ManualProgress
                    target_is_manual = (mentor_id == student.mentor_id) or (mentor_id == DIRECTOR_ID_MANUAL)

                    # 🔥 ВАЖНО: Передаем target_mentor_id=mentor_id
                    # Это заставит функцию считать только темы, где mX_mentor_id == этому ментору
                    progress_data = SalaryManager.count_all_completed_tasks(
                        session,
                        student_id,
                        target_is_manual,
                        target_mentor_id=mentor_id  # <--- ВОТ ГЛАВНОЕ ИЗМЕНЕНИЕ
                    )

                    completed_themes_by_him = progress_data['total_tasks']

                    # Цена темы = Весь Долг Этого Человека / Всего Тем в курсе
                    total_calls = config.Config.MANUAL_CALLS_TOTAL if target_is_manual else config.Config.AUTO_CALLS_TOTAL
                    if total_calls > 0:
                        price_per_theme = float(debt_record.total_amount) / total_calls
                    else:
                        price_per_theme = 0

                    # Считаем заработанное ИМЕННО ИМ
                    earned_total = price_per_theme * completed_themes_by_him

                    # Вычитаем то, что уже выплатили ИМЕННО ЕМУ
                    to_pay = earned_total - float(debt_record.paid_amount)

                    calculated_amount = max(0.0, to_pay)
                    comment = f"Комиссия за {student.telegram}: {completed_themes_by_him} своих тем * {price_per_theme:.2f}"

                # Лимиты
                calculated_amount = min(calculated_amount, remaining_debt)

                if calculated_amount > 0:
                    planned_payouts.append({
                        "debt_record": debt_record,
                        "amount": calculated_amount,
                        "comment": comment,
                        "mentor_id": mentor_id,
                        "remaining_debt_after": remaining_debt - calculated_amount
                    })
                    total_planned_amount += calculated_amount

            # Балансировка (если денег не хватает на всех)
            ratio = 1.0
            if total_planned_amount > payment_amount:
                ratio = payment_amount / total_planned_amount

            # Сохранение
            for plan in planned_payouts:
                final_amount = round(plan["amount"] * ratio, 2)
                if final_amount > 0:
                    final_comment = plan["comment"]
                    if ratio < 1.0:
                        final_comment += f" (Скорр: {ratio:.2f})"

                    session.add(Salary(
                        payment_id=payment_id,
                        mentor_id=plan["mentor_id"],
                        calculated_amount=final_amount,
                        comment=final_comment + f". Остаток: {plan['remaining_debt_after'] + (plan['amount'] - final_amount):.2f}",
                        is_paid=False
                    ))

                    debt_record = plan["debt_record"]
                    debt_record.paid_amount = float(debt_record.paid_amount) + final_amount
                    session.add(debt_record)

                    student.commission_paid = float(student.commission_paid or 0) + final_amount
                    session.add(student)

    def handle_legacy_additional_payment(self, session: Session, payment_id: int, student_id: int,
                                         payment_amount: float):
        """
        Обрабатывает платеж "Доплата" для студентов, начавших обучение до 01.12.2025 (не Fullstack).
        Начисляет 20% куратору и 10% директору от суммы платежа (без учета долга CuratorCommission).
        """
        from data_base.models import Student, Salary
        from datetime import date

        # Дата, до которой действует старая логика
        CUTOFF_DATE = date(2025, 12, 1)

        student = session.query(Student).filter_by(id=student_id).first()
        payment_amount = float(payment_amount)

        if not student or payment_amount <= 0:
            return None

        training_type_lower = student.training_type.strip().lower() if student.training_type else ""

        # 1. Проверка условий: до 01.12.2025 и не Fullstack
        is_legacy = student.start_date and student.start_date < CUTOFF_DATE
        is_not_fullstack = training_type_lower != "фуллстек"

        if not (is_legacy and is_not_fullstack):
            return None  # Условия не выполнены, пропускаем

        # 2. Определяем IDs и направление (DIRECTOR_ID_MANUAL = 1, DIRECTOR_ID_AUTO = 3)
        if training_type_lower == "ручное тестирование":
            curator_id = student.mentor_id
            director_id = DIRECTOR_ID_MANUAL  # ID 1
            direction = "ручного направления"
        elif training_type_lower == "автотестирование":
            curator_id = student.auto_mentor_id
            director_id = DIRECTOR_ID_AUTO  # ID 3
            direction = "авто направления"
        else:
            # Не должен сюда попасть из-за проверки is_not_fullstack
            return None

        if not curator_id:
            print(
                f"Warn: Student {student.telegram} ({student_id}) has no curator for {direction}. Skipping legacy payment handling.")
            return None

        # 3. Расчет и начисление Куратору (20%)
        curator_percent = 0.20
        curator_payout = round(payment_amount * curator_percent, 2)

        curator_salary = Salary(
            payment_id=payment_id,
            mentor_id=curator_id,
            calculated_amount=curator_payout,
            comment=f"Доплата от студента {student.fio} ({student.telegram}) - {int(curator_percent * 100)}% ({direction})",
            is_paid=False
        )
        session.add(curator_salary)

        # 4. Расчет и начисление Директору (10%)
        director_percent = 0.10
        director_payout = round(payment_amount * director_percent, 2)

        director_salary = Salary(
            payment_id=payment_id,
            mentor_id=director_id,
            calculated_amount=director_payout,
            comment=f"Бонус Директора ({int(director_percent * 100)}%) за Доплату от студента {student.fio} ({student.telegram}) - {direction}",
            is_paid=False
        )
        session.add(director_salary)

        print(
            f"Info: Processed legacy additional payment for student {student_id}. Curator {curator_payout}₽, Director {director_payout}₽.")

        # Обновляем commission_paid студента
        student.commission_paid = float(student.commission_paid or 0) + curator_payout + director_payout
        session.add(student)

        return [curator_salary, director_salary]

    def create_commission_for_manual_task(self, session: Session, mentor_id: int, telegram: str, topic_name: str,
                                          student_id: int):
        """
        Создает и сохраняет новую запись в salary за факт сдачи одной темы.
        """
        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return None

        commission_sum, commission_comment = self._calculate_amount_manual(
            student=student,  # ❗ ПЕРЕДАЕМ СТУДЕНТА
            mentor_id=mentor_id,
            amount=1.0
        )
        final_comment = f"Принял {topic_name} у {telegram}. {commission_comment}"
        new_salary_entry = Salary(
            payment_id=None,
            mentor_id=mentor_id,
            calculated_amount=commission_sum,
            comment=final_comment,
        )

        session.add(new_salary_entry)
        return new_salary_entry

    def create_commission_for_auto_task(self, session: Session, mentor_id: int, telegram: str, topic_name: str,
                                        student_id: int):
        """
        Создает и сохраняет новую запись в salary за факт сдачи одной темы.
        """
        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return None

        commission_sum, commission_comment = self._calculate_amount_auto(
            student=student,  # ❗ ПЕРЕДАЕМ СТУДЕНТА
            mentor_id=mentor_id,
            amount=1.0
        )
        final_comment = f"Принял {topic_name} у {telegram}. {commission_comment}"
        new_salary_entry = Salary(
            payment_id=None,
            mentor_id=mentor_id,
            calculated_amount=commission_sum,
            comment=final_comment,
        )

        session.add(new_salary_entry)
        return new_salary_entry

    def calculate_bonus_dir(self, session, mentor_id: int, telegram: str, student_id: int):

        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return 0.0, "Ошибка: Студент не найден."

        # Определяем, фуллстек это или нет
        is_fullstack = (student.mentor_id is not None) and (student.auto_mentor_id is not None)

        if is_fullstack:
            # total_price_manual = config.Config.FULLSTACK_MANUAL_COURSE_COST
            total_price_manual = student.total_cost
            total_price_auto = student.total_cost
            # total_price_auto = config.Config.FULLSTACK_AUTO_COURSE_COST
        elif student.total_cost:
            total_price_manual = float(student.total_cost)  # Используем общую стоимость для расчета бонуса
            total_price_auto = float(student.total_cost)
        else:
            total_price_manual = config.Config.FULLSTACK_MANUAL_COURSE_COST
            total_price_auto = config.Config.FULLSTACK_AUTO_COURSE_COST

        if mentor_id == 1:
            # Расчет для MANUAL_COURSE_COST
            try:
                bonus_amount = (total_price_manual * 0.06)
            except ZeroDivisionError:
                bonus_amount = 0

            comment = (
                f"Бонус директору 6% за старт обучения ученика {telegram} по ручному направлению"
            )

        else:  # mentor_id != 1 (предполагаем, что это ID=3)
            # Расчет для AUTO_COURSE_COST
            try:
                bonus_amount = (total_price_auto * 0.06)
            except ZeroDivisionError:
                bonus_amount = 0

            comment = (
                f"Бонус директору 6% за старт обучения ученика {telegram} по автоматическому направлению"
            )

        # --- Создание записи о комиссии в БД ---
        if bonus_amount > 0:
            new_commission = Salary(
                mentor_id=mentor_id,
                calculated_amount=bonus_amount,
                comment=comment,
                is_paid=False,
            )
            session.add(new_commission)

        return bonus_amount, comment
    def _calculate_commission_curator_fullstack(self, session: Session, mentor_id: int, telegram: str, ):
        pass

    def _calculate_commission_dir(self, session: Session, mentor_id: int, telegram: str, ):
        pass

    def _calculate_commission_dir_fullstack(self, session: Session, mentor_id: int, telegram: str, ):
        pass