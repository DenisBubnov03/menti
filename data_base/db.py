from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

# Установите уровень логирования для SQLAlchemy

DATABASE_URL = "postgresql://bot_user:denbub0311@localhost/student_tracker"
engine = create_engine(DATABASE_URL, echo=False)


# Создание базы для описания таблиц
Base = declarative_base()

# Настройка сессии
Session = sessionmaker(bind=engine)
session = Session()
