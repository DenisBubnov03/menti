#!/usr/bin/env python3
"""
Скрипт для анализа и исправления расчетов зарплат менторов
"""

from datetime import datetime, date
from decimal import Decimal
from data_base.db import session
from data_base.models import Student, Mentor, Payment

def analyze_salary_calculation():
    """Анализирует расчеты зарплат менторов"""
    
    print("🔍 Анализ расчетов зарплат менторов...")
    
    # Период для анализа
    start_date = date(2025, 7, 16)
    end_date = date(2025, 7, 31)
    
    print(f"📅 Период: {start_date} - {end_date}")
    
    # Получаем всех менторов
    mentors = session.query(Mentor).all()
    
    total_commission = 0
    mentor_salaries = {}
    
    print("\n👥 Анализ по менторам:")
    
    for mentor in mentors:
        print(f"\n--- {mentor.full_name} (@{mentor.telegram}) ---")
        
        # Получаем студентов ментора
        students = session.query(Student).filter_by(mentor_id=mentor.id).all()
        auto_students = session.query(Student).filter_by(auto_mentor_id=mentor.id).all()
        all_students = students + auto_students
        
        print(f"📚 Студентов: {len(all_students)}")
        
        mentor_commission = 0
        
        for student in all_students:
            print(f"  👨‍🎓 {student.fio} (@{student.telegram})")
            print(f"     💰 Зарплата: {student.salary} руб.")
            print(f"     📊 Комиссия: {student.commission}")
            print(f"     💸 Выплачено комиссии: {student.commission_paid} руб.")
            
            # Рассчитываем комиссию
            if student.commission and student.salary:
                try:
                    parts, percent = map(lambda x: x.strip().replace('%', ''), student.commission.split(","))
                    total_parts = int(parts)
                    percent = float(percent)
                    
                    total_commission_for_student = round((student.salary or 0) * (percent / 100) * total_parts, 2)
                    remaining_commission = total_commission_for_student - float(student.commission_paid or 0)
                    
                    print(f"     📈 Общая комиссия: {total_commission_for_student} руб.")
                    print(f"     📌 Осталось: {remaining_commission} руб.")
                    
                    mentor_commission += remaining_commission
                    
                except Exception as e:
                    print(f"     ❌ Ошибка расчета комиссии: {e}")
        
        mentor_salaries[mentor.telegram] = mentor_commission
        total_commission += mentor_commission
        
        print(f"  💰 Итого комиссия ментора: {mentor_commission} руб.")
    
    print(f"\n📊 ИТОГО:")
    print(f"💰 Общая сумма комиссии: {total_commission} руб.")
    
    # Проверяем платежи за период
    payments = session.query(Payment).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date,
        Payment.status == "подтвержден"
    ).all()
    
    total_payments = sum(float(p.amount) for p in payments)
    print(f"💵 Подтвержденные платежи за период: {total_payments} руб.")
    
    # Анализируем платежи по менторам
    mentor_payments = {}
    for payment in payments:
        mentor = session.query(Mentor).filter_by(id=payment.mentor_id).first()
        if mentor:
            mentor_payments[mentor.telegram] = mentor_payments.get(mentor.telegram, 0) + float(payment.amount)
    
    print(f"\n💸 Платежи по менторам:")
    for mentor_telegram, amount in mentor_payments.items():
        mentor = session.query(Mentor).filter_by(telegram=mentor_telegram).first()
        print(f"  {mentor.full_name} (@{mentor_telegram}): {amount} руб.")
    
    return mentor_salaries, total_commission, mentor_payments

def fix_salary_calculations():
    """Исправляет расчеты зарплат"""
    
    print("\n🔧 Исправление расчетов зарплат...")
    
    # Получаем все подтвержденные платежи
    confirmed_payments = session.query(Payment).filter_by(status="подтвержден").all()
    
    # Сбрасываем комиссии
    students = session.query(Student).all()
    for student in students:
        student.commission_paid = 0
    
    # Пересчитываем комиссии на основе подтвержденных платежей
    for payment in confirmed_payments:
        if payment.comment == "Комиссия":
            student = session.query(Student).filter_by(id=payment.student_id).first()
            if student:
                student.commission_paid = (student.commission_paid or 0) + float(payment.amount)
    
    session.commit()
    print("✅ Комиссии пересчитаны")

if __name__ == "__main__":
    mentor_salaries, total_commission, mentor_payments = analyze_salary_calculation()
    
    print(f"\n🎯 РЕКОМЕНДАЦИИ:")
    print("1. Проверьте правильность расчета комиссий в коде")
    print("2. Убедитесь, что все платежи правильно привязаны к менторам")
    print("3. Проверьте, что процент комиссии корректно применяется")
    
    # Спрашиваем пользователя, хочет ли он исправить расчеты
    response = input("\n❓ Хотите исправить расчеты зарплат? (y/n): ")
    if response.lower() == 'y':
        fix_salary_calculations()
        print("✅ Расчеты исправлены!")
    else:
        print("❌ Расчеты не изменены") 