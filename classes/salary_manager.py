# salary_manager.py

from sqlalchemy.orm import Session

import config
# Вам нужно будет изменить этот импорт, чтобы он указывал на ваш файл:
from data_base.models import Salary
from typing import Dict, Any
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


    def create_commission_for_manual_task(self, session: Session, mentor_id: int, telegram: str, topic_name: str):
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

    def create_commission_for_auto_task(self, session: Session, mentor_id: int, telegram: str, topic_name: str):
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
        from data_base.models import Salary  # Предполагаем, что у вас есть такая модель

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

        return bonus_amount, comment  # Возвращаем рассчитанную сумму и комментарий