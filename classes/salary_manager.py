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
                f"Оплата за 1 принятую тему ручного направления. "
                f"Расчет: ({course_cost} * {base_rate_kurator*100:.0f}%) / {count_calls_total} тем. "
                f"Сумма платежа: {calls_price}."
            )

            return calls_price, comment
        else:
            try:
                calls_price = (course_cost * base_rate_dir) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = (
                f"Оплата за 1 принятую тему ручного направления директору. "
                f"Расчет: ({course_cost} * {base_rate_dir*100:.0f}%) / {count_calls_total} тем. "
                f"Сумма платежа: {calls_price}."
            )

            return calls_price, comment


    def create_commission_for_manual_task(self, session: Session, mentor_id: int, task_id: int, topic_name: str):
        """
        Создает и сохраняет новую запись в salary за факт сдачи одной темы.
        """
        commission_sum, commission_comment = self._calculate_amount_manual(
            mentor_id=mentor_id,
            amount=1.0  # Это фиктивное значение, т.к. оно не влияет на calls_price
        )
        final_comment = f"Тема #{task_id}: {topic_name}. {commission_comment}"
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
                f"Оплата за 1 принятую тему ручного направления. "
                f"Расчет: ({course_cost} * {base_rate_kurator*100:.0f}%) / {count_calls_total} тем. "
                f"Сумма платежа: {calls_price}."
            )

            return calls_price, comment
        else:
            try:
                calls_price = (course_cost * base_rate_dir) / count_calls_total
            except ZeroDivisionError:
                calls_price = 0

            comment = (
                f"Оплата за 1 принятую тему ручного направления. "
                f"Расчет: ({course_cost} * {base_rate_dir * 100:.0f}%) / {count_calls_total} тем. "
                f"Сумма платежа: {calls_price}."
            )

            return calls_price, comment

    def create_commission_for_auto_task(self, session: Session, mentor_id: int, task_id: int, topic_name: str):
        """
        Создает и сохраняет новую запись в salary за факт сдачи одной темы.
        """
        commission_sum, commission_comment = self._calculate_amount_auto(
            mentor_id=mentor_id,
            amount=1.0  # Это фиктивное значение, т.к. оно не влияет на calls_price
        )
        final_comment = f"Тема #{task_id}: {topic_name}. {commission_comment}"
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

