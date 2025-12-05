from sqlalchemy import Boolean, Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
import enum
from schemas import *

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    status = Column(Boolean, default=False) # True: Active
    role = Column(String, default='user')  # 'user', 'admin'
    name_bank = Column(String, nullable=True)
    bank_number = Column(String, nullable=True)
    token_version = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    # Lưu ID của người đã tạo ra user này (Self-referencing Foreign Key)
    created_by = Column(Integer, ForeignKey("users.user_id"), nullable=True) 
    
    # Relationship để truy cập object người tạo dễ dàng (optional)
    creator = relationship("User", remote_side=[user_id]) 
    # ---------------------

    # Quan hệ ngược lại bảng user_event
    events = relationship("UserEvent", back_populates="user")

class Event(Base):
    __tablename__ = "events"

    event_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    day_start = Column(Date, nullable=False)
    start_period = Column(Integer, nullable=False) 
    end_period = Column(Integer, nullable=False)
    number_of_student = Column(Integer, default=0)
    status = Column(String, default=EventStatus.ONGOING.value) # ongoing, finished, deleted
    school_name = Column(String, nullable=True)
    max_user_joined = Column(Integer, nullable=False)
    is_locked = Column(Boolean, default=False)
    
    max_instructor = Column(Integer, nullable=False)
    max_teaching_assistant = Column(Integer, nullable=False)

    # Quan hệ ngược lại bảng user_event
    participants = relationship("UserEvent", back_populates="event")
    

class UserEvent(Base):
    __tablename__ = "user_event"

    # Composite Primary Key (user_id + event_id)
    event_id = Column(Integer, ForeignKey("events.event_id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    
    role = Column(String, default=EventRole.TA.value)  # instructor, ta
    status = Column(String, default="registered") # registered, attended, cancelled

    user = relationship("User", back_populates="events")
    event = relationship("Event", back_populates="participants")