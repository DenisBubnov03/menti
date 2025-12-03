# salary_manager.py
from sqlalchemy.orm import Session

import config
# Вам нужно будет изменить этот импорт, чтобы он указывал на ваш файл:
from data_base.models import Salary, Student


class SalaryManager:
    """
    Класс отвечает за расчет комиссии и создание записи в таблице salary.
    """
    def _calculate_amount_manual(self, mentor_id: int, amount: float) -> tuple[float, str]:
        base_rate_kurator = config.Config.MANUAL_CURATOR_RESERVE_PERCENT
        count_calls_total = config.Config.MANUAL_CALLS_TOTAL
        course_cost = config.Config.FULLSTACK_MANUAL_COURSE_COST
        base_rate_dir = config.Config.MANUAL_DIR_RESERVE_PERCENT

        if mentor_id != 1:
            try:
                calls_price = (course_cost * base_rate_kurator) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = (
                "Оплата за 1 принятую тему ручного направления куратору. "
            )

            return calls_price, comment
        else:
            try:
                calls_price = (course_cost * base_rate_dir) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = (
                "Оплата за 1 принятую тему ручного направления директору."
            )

            return calls_price, comment


    def create_salary_for_manual_task(self, session: Session, mentor_id: int, telegram: str, topic_name: str):
        """
        Создает и сохраняет новую запись в salary за факт сдачи одной темы.
        """
        commission_sum, commission_comment = self._calculate_amount_manual(
            mentor_id=mentor_id,
            amount=1.0  # Это фиктивное значение, т.к. оно не влияет на calls_price
        )
        final_comment = f"Принял {topic_name} у {telegram}. {commission_comment}"
        new_salary_entry = Salary(
            # ВНИМАНИЕ: payment_id должен быть NULL, если он не связан с конкретным платежом!
            # Если payment_id обязателен, то нужно создать "фиктивный" payment_id (не рекомендуется)
            payment_id=None,  # Предполагаем, что поле может быть NULL
            mentor_id=mentor_id,
            calculated_amount=commission_sum,
            comment=final_comment,
            # is_paid по умолчанию FALSE
        )

        # 4. Добавляем в сессию
        session.add(new_salary_entry)

        return new_salary_entry

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

            comment = (
                "Оплата за 1 принятую тему авто направления куратору. "
            )

            return calls_price, comment
        else:
            try:
                calls_price = (course_cost * base_rate_dir) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = (
                f"Оплата за 1 принятую тему авто направления директору. "
            )

            return calls_price, comment

    def create_salary_for_auto_task(self, session: Session, mentor_id: int, telegram: str, topic_name: str):
        """
        Создает и сохраняет новую запись в salary за факт сдачи одной темы.
        """
        commission_sum, commission_comment = self._calculate_amount_auto(
            mentor_id=mentor_id,
            amount=1.0  # Это фиктивное значение, т.к. оно не влияет на calls_price
        )
        final_comment = f"Принял {topic_name} у {telegram}. {commission_comment}"
        new_salary_entry = Salary(
            # ВНИМАНИЕ: payment_id должен быть NULL, если он не связан с конкретным платежом!
            # Если payment_id обязателен, то нужно создать "фиктивный" payment_id (не рекомендуется)
            payment_id=None,  # Предполагаем, что поле может быть NULL
            mentor_id=mentor_id,
            calculated_amount=commission_sum,
            comment=final_comment,
            # is_paid по умолчанию FALSE
        )

        # 4. Добавляем в сессию
        session.add(new_salary_entry)

        return new_salary_entry

    # В классе SalaryManager:
    def calculate_bonus_dir(self, session, mentor_id: int, telegram: str):  # Убрали amount, т.к. он не используется
        # Импортируем модель Salary, если она нужна
        total_price_manual = config.Config.FULLSTACK_MANUAL_COURSE_COST
        total_price_auto = config.Config.FULLSTACK_AUTO_COURSE_COST

        if mentor_id == 1:
            # Расчет для MANUAL_COURSE_COST
            try:
                bonus_amount = (total_price_manual * 0.1)
            except ZeroDivisionError:
                bonus_amount = 0

            comment = (
                f"Бонус директору 10% за старт обучения фуллстак ученика {telegram} по ручному направлению"
            )

        else:  # mentor_id != 1
            # Расчет для AUTO_COURSE_COST
            try:
                bonus_amount = (total_price_auto * 0.1)
            except ZeroDivisionError:
                bonus_amount = 0

            comment = (
                f"Бонус директору 10% за старт обучения фуллстак ученика {telegram} по автоматическому направлению"
            # Исправляем комментарий
            )

        # --- Создание записи о комиссии в БД ---
        if bonus_amount > 0:
            new_commission = Salary(
                mentor_id=mentor_id,  # Директор - постоянный получатель бонуса
                calculated_amount=bonus_amount,
                comment=comment,
                # Дополнительные поля, которые могут быть Not Null (например, is_paid, payment_id)
                # Если payment_id не может быть NULL:
                # payment_id=some_default_payment_id,
                is_paid=False,
            )
            session.add(new_commission)
            # ВАЖНО: session.commit() будет вызван в вызывающей функции submit_topic_students

        return bonus_amount, comment

    @staticmethod  # <--- ДОБАВИТЬ ЭТОТ ДЕКОРАТОР
    def count_all_completed_tasks(session: Session, student_id: int, is_manual_flow: bool) -> dict:
        """
        Считает общее количество сданных тем/модулей для ОДНОГО ученика,
        используя student_id как первичный ключ.
        """
        # 🌟 Локальный импорт моделей
        from data_base.models import ManualProgress, AutoProgress

        # 1. Определяем модель и список полей
        if is_manual_flow:
            ProgressModel = ManualProgress
            TASK_FIELDS = [
                'm1_submission_date', 'm2_1_2_2_submission_date',
                'm2_3_3_1_submission_date', 'm3_2_submission_date',
                'm3_3_submission_date', 'm4_1_submission_date',
                'm4_2_4_3_submission_date', 'm4_mock_exam_passed_date'
            ]
        else:  # Авто-флоу
            ProgressModel = AutoProgress
            TASK_FIELDS = [
                'm2_exam_passed_date', 'm3_exam_passed_date',
                'm4_topic_passed_date', 'm5_topic_passed_date',
                'm6_topic_passed_date', 'm7_topic_passed_date'
            ]

        # 2. Находим запись прогресса по первичному ключу (самый простой запрос)
        progress = session.query(ProgressModel).filter_by(student_id=student_id).first()

        total_completed_tasks = 0

        if progress:
            completed_count = 0

            # 3. Цикл по заранее известным полям
            for field_name in TASK_FIELDS:
                # Получаем значение поля. Если None, то None
                submission_date = getattr(progress, field_name, None)

                # Если дата сдачи ЕСТЬ (не None), считаем тему сданной
                if submission_date is not None:
                    completed_count += 1

            total_completed_tasks = completed_count
        print('start count')
        print('total completed tasks: ', total_completed_tasks)
        return {
            'total_tasks': total_completed_tasks,
            'details': {student_id: total_completed_tasks}
        }

    def _calculate_commission_curator(self, session: Session,student_id: int, payment_amount: float) -> tuple[
        float, str]:
        """
                Рассчитывает комиссию, которая должна быть выплачена куратору за счет
                поступившего платежа. Применяется для ручного направления.

                Аргументы:
                    session (Session): Сессия БД.
                    student_id (int): ID студента, который произвел платеж.
                    payment_amount (float): Сумма поступившего платежа.

                Возвращает:
                    tuple[float, str]: Фактическая сумма к выплате и комментарий.
                """

        # 1. Находим студента и ответственного куратора
        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return 0.0, "Ошибка: Студент не найден."
        mentor_id = student.mentor_id  # Берем ID ментора ручного направления
        if not mentor_id:
            return 0.0, "Ошибка: Ментор ручного направления не закреплен."

        # 2. Определяем стоимость одной темы (используем существующий метод расчета)
        # Важно: Считаем, что _calculate_amount_manual теперь STATIC
        theme_price, _ = self._calculate_amount_manual(mentor_id=mentor_id, amount=1.0)
        print('theme price: ', theme_price)
        if theme_price <= 0:
            return 0.0, "Ошибка: Расчетная стоимость темы равна нулю."

        # 3. Подсчитываем общее количество сданных тем (ручной флоу)
        # Важно: Считаем, что count_all_completed_tasks теперь STATIC
        progress_data = SalaryManager.count_all_completed_tasks(session, student_id=student_id, is_manual_flow=True)
        total_themes = progress_data['total_tasks']

        # 4. Получаем данные об уже выплаченной комиссии
        # Поле commission_paid из модели Student
        already_paid = student.commission_paid if student.commission_paid else 0.0

        # 5. Финальный Расчет

        # Общая сумма, которую куратор заработал (накоплено)
        total_accrued_commission = theme_price * total_themes

        # Максимальная сумма, которую можно выплатить сейчас (разница)
        commission_difference = total_accrued_commission - already_paid

        # Сумма к выплате: не больше, чем разница, И не больше, чем текущий платеж
        commission_to_pay = min(payment_amount, commission_difference)

        if commission_to_pay <= 0:
            comment = f"Начисление: 0.00. Накоплено: {total_accrued_commission:.2f}, Оплачено ранее: {already_paid:.2f}."
            return 0.0, comment

        comment = (
            f"Выплата комиссии куратору  за платеж {payment_amount:.2f}. "
            f"Накоплено: {total_accrued_commission:.2f} ({total_themes} тем * {theme_price:.2f}). "
            f"Оплачено ранее: {already_paid:.2f}. Выплачено сейчас: {commission_to_pay:.2f}."
        )

        return commission_to_pay, comment

    def create_salary_entry_from_payment(self, session: Session, payment_id: int, student_id: int,
                                         payment_amount: float):
        """
                Логика распределения входящего платежа 'Комиссия':
                1. Директор: 10% от суммы платежа (сразу).
                2. Куратор: 20% от суммы платежа * Коэффициент прогресса (но не больше остатка долга).
                """
        from data_base.models import Student, Salary, CuratorCommission
        import config

        payment_amount = float(payment_amount)
        student = session.query(Student).filter_by(id=student_id).first()
        if not student: return

        # ==========================================
        # 1. РАСЧЕТ ДИРЕКТОРА (10% от входящих денег)
        # ==========================================
        # 0. Расчет суммы бонуса директора (10%)
        DIRECTOR_PERCENT = 0.10
        director_payout = payment_amount * DIRECTOR_PERCENT

        # 1. Определяем поток студента и соответствующие ID
        curator_id = None  # ID фактического куратора студента
        director_payout_id = None  # ID директора, который должен получить бонус (1 или 3)
        comment_suffix = ""

        if student.mentor_id:
            # Ручной поток
            curator_id = student.mentor_id
            director_payout_id = 1  # ID Директора ручного направления
            comment_suffix = "ручного направления"
        elif student.auto_mentor_id:
            # Авто поток
            curator_id = student.auto_mentor_id
            director_payout_id = 3  # ID Директора авто направления (пример)
            comment_suffix = "авто направления"

        # ==========================================
        # 2. РАСЧЕТ ДИРЕКТОРА (10% от входящих денег)
        # ==========================================

        if director_payout > 0 and director_payout_id is not None:

            # ❗ КОРРЕКЦИЯ ЛОГИКИ: Платим 10% ТОЛЬКО если Директор НЕ является Куратором
            if curator_id != director_payout_id:

                session.add(Salary(
                    payment_id=payment_id,
                    mentor_id=director_payout_id,
                    calculated_amount=director_payout,
                    comment=f"Директор {comment_suffix}: 10% от платежа {payment_amount:.2f}",
                    is_paid=False
                ))
            else:
                # Если ID куратора совпадает с ID директора, бонус 10% пропускаем.
                print(
                    f"DEBUG: Директор ID {director_payout_id} является куратором студента {student_id}. Бонус 10% не начислен.")

        # ==========================================
        # 2. РАСЧЕТ КУРАТОРА
        # ==========================================

        # Ищем запись о долге по student_id
        debt_record = session.query(CuratorCommission).filter_by(student_id=student_id).first()

        # Если записи нет — значит долг не был инициализирован (студент не трудоустроен?), платить нечего.
        if debt_record:

            # А. Базовая доля куратора от ЭТОГО платежа (20%)
            # Пример: Платеж 50 000 -> База 10 000
            CURATOR_PAYMENT_SHARE = 0.20
            base_curator_share = payment_amount * CURATOR_PAYMENT_SHARE

            # Б. Считаем Прогресс (Коэффициент 0.0 - 1.0)
            IS_MANUAL = bool(student.mentor_id)
            TOTAL_CALLS = config.Config.MANUAL_CALLS_TOTAL if IS_MANUAL else config.Config.AUTO_CALLS_TOTAL

            # Используем статический метод подсчета (он должен быть у вас реализован корректно)
            progress_data = SalaryManager.count_all_completed_tasks(session, student_id, IS_MANUAL)
            completed_themes = progress_data['total_tasks']

            try:
                progress_ratio = completed_themes / TOTAL_CALLS
            except ZeroDivisionError:
                progress_ratio = 0.0

            # Ограничиваем прогресс 100% (чтобы не заплатить лишнего за перевыполнение)
            if progress_ratio > 1.0: progress_ratio = 1.0

            # В. Реальная сумма к выплате (База * Прогресс)
            # Пример: 10 000 * 0.5 (50% тем) = 5 000 руб.
            curator_payout = base_curator_share * progress_ratio

            # Г. Проверка Лимита (Остаток общего долга)
            # Сколько осталось выплатить всего по контракту? (Total - Paid)
            remaining_debt = float(debt_record.total_amount) - float(debt_record.paid_amount)
            if remaining_debt < 0: remaining_debt = 0

            # Платим MIN(расчетная выплата, остаток долга)
            final_curator_payout = min(curator_payout, remaining_debt)

            if final_curator_payout > 0:
                # 1. Создаем запись в Salary (конкретная выплата)
                session.add(Salary(
                    payment_id=payment_id,
                    mentor_id=debt_record.curator_id,
                    calculated_amount=final_curator_payout,
                    comment=(f"Куратор: 20% от {payment_amount} * Прогресс {progress_ratio:.2f}. "
                             f"Остаток долга: {remaining_debt:.2f}"),
                    is_paid=False
                ))

                # 2. Обновляем таблицу долгов (увеличиваем выплаченное)
                debt_record.paid_amount = float(debt_record.paid_amount) + final_curator_payout
                session.add(debt_record)

                # 3. Обновляем статистику в студенте (для истории)
                current_paid = float(student.commission_paid) if student.commission_paid else 0.0
                student.commission_paid = current_paid + final_curator_payout
                session.add(student)

        # Важно: session.commit() вызывается во внешней функции (confirm_payment)

    def _calculate_commission_curator_fullstack(self, session: Session, mentor_id: int, telegram: str,):
        pass

    def _calculate_commission_dir(self, session: Session, mentor_id: int, telegram: str,):
        pass

    def _calculate_commission_dir_fullstack(self, session: Session, mentor_id: int, telegram: str,):
        pass


