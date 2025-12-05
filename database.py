from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()  # Load biến môi trường từ file .env

# Sử dụng SQLite file tên là test.db
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

# 2. Cấu hình connect_args động
connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # Chỉ thêm tham số này nếu đang dùng SQLite
    connect_args = {"check_same_thread": False}

# 3. Tạo engine với connect_args phù hợp
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args=connect_args
)
    
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

from models import *

# Dependency để lấy DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()