from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List
from datetime import date
import enum
import re

# ==========================================
# 1. ENUMS
# ==========================================

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    
class EventRole(str, enum.Enum):
    INSTRUCTOR = "instructor"
    TA = "teaching_assistant"
    
class EventStatus(str, enum.Enum):
    ONGOING = "ongoing"
    FINISHED = "finished"
    DELETED = "deleted"


# ==========================================
# 2. TOKEN & AUTH SCHEMAS
# ==========================================

class Token(BaseModel):
    access_token: str
    token_type: str
    
    class Config:
        from_attributes = True

class TokenData(BaseModel):
    email: str | None = None
    
    class Config:
        from_attributes = True

class EmailRequest(BaseModel):
    email: EmailStr
    
    @field_validator('email')
    @classmethod
    def validate_gmail(cls, v: str):
        if not v.endswith("@gmail.com"):
            raise ValueError("Hệ thống chỉ chấp nhận tài khoản Gmail (@gmail.com)")
        return v
    
    class Config:
        from_attributes = True

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)
    
    @field_validator('new_password')
    def validate_password_strength(cls, v: str):
        if len(v) < 8:
             raise ValueError('Mật khẩu phải có ít nhất 8 ký tự')
        if not re.search(r"\d", v):
            raise ValueError('Mật khẩu phải chứa ít nhất một chữ số')
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError('Mật khẩu phải chứa ít nhất một chữ cái')
        return v
    
    class Config:
        from_attributes = True


# ==========================================
# 3. USER SCHEMAS
# ==========================================

class UserBase(BaseModel):
    full_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = Field(None, pattern=r"^0\d{9}$") # Regex: Bắt đầu bằng 0, 10 số
    status: bool = True
    role: str = UserRole.USER
    name_bank: Optional[str] = None
    bank_number: Optional[str] = None

    @field_validator('role')
    def role_must_be_valid(cls, v):
        if v not in [UserRole.USER, UserRole.ADMIN]:
            raise ValueError('Role must be user or admin')
        return v
    
    class Config:
        from_attributes = True
        str_strip_whitespace = True

class UserCreateAdmin(BaseModel):
    """Schema dùng cho Admin tạo User"""
    email: EmailStr
    password: str = "husc1234"
    full_name: Optional[str] = None
    role: str = UserRole.USER.value
    status: bool = True 
    phone: Optional[str] = None

    @field_validator('role')
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in [UserRole.USER, UserRole.ADMIN]:
             raise ValueError('Role must be user or admin')
        return v
    
    @field_validator('email')
    @classmethod
    def validate_gmail(cls, v: str):
        if not v.endswith("@gmail.com"):
            raise ValueError("Hệ thống chỉ chấp nhận tài khoản Gmail (@gmail.com)")
        return v
    
    @field_validator('password')
    def validate_password_strength(cls, v: str):
        if len(v) < 8:
             raise ValueError('Mật khẩu phải có ít nhất 8 ký tự')
        if not re.search(r"\d", v):
            raise ValueError('Mật khẩu phải chứa ít nhất một chữ số')
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError('Mật khẩu phải chứa ít nhất một chữ cái')
        return v
    
    class Config:
        from_attributes = True
        str_strip_whitespace = True

class UserUpdateAdmin(BaseModel):
    """Schema dùng cho Admin cập nhật User"""
    full_name: Optional[str] = None
    phone: Optional[str] = Field(None, pattern=r"^0\d{9}$")
    role: Optional[str] = None
    status: Optional[bool] = None
    name_bank: Optional[str] = None
    bank_number: Optional[str] = None
    
    @field_validator('role')
    @classmethod
    def role_must_be_valid(cls, v):
        if v is not None and v not in [UserRole.USER, UserRole.ADMIN]:
            raise ValueError('Role must be user or admin')
        return v
    
    class Config:
        from_attributes = True

class UserResponse(UserBase):
    user_id: int
    
    class Config:
        from_attributes = True    
        
class UserRequestProfile(BaseModel):
    full_name: str = None
    # email: EmailStr
    phone: str = Field(None, pattern=r"^0\d{9}$") # Regex: Bắt đầu bằng 0, 10 số
    name_bank: Optional[str] = None
    bank_number: Optional[str] = None
    password: str = Field(..., min_length=8)
    re_password: str = Field(..., min_length=8)
    
    # @field_validator('email')
    # @classmethod
    # def validate_gmail(cls, v: str):
    #     if not v.endswith("@gmail.com"):
    #         raise ValueError("Hệ thống chỉ chấp nhận tài khoản Gmail (@gmail.com)")
    #     return v
    
    @field_validator('password')
    def validate_password_strength(cls, v: str | None):
        # Nếu không nhập gì hoặc là None thì bỏ qua (nghĩa là không đổi pass)
        if not v or v.strip() == "":
            return None
            
        if len(v) < 8:
             raise ValueError('Mật khẩu phải có ít nhất 8 ký tự')
        if not re.search(r"\d", v):
            raise ValueError('Mật khẩu phải chứa ít nhất một chữ số')
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError('Mật khẩu phải chứa ít nhất một chữ cái')
        return v
    
    class Config:
        from_attributes = True

# ==========================================
# 4. EVENT SCHEMAS
# ==========================================

class EventBase(BaseModel):
    name: str
    day_start: date
    start_period: int = Field(..., ge=1, le=12, description="Tiết bắt đầu (1-12)")
    end_period: int = Field(..., ge=1, le=12, description="Tiết kết thúc (1-12)")
    number_of_student: int = Field(0, ge=0)
    max_user_joined: int = Field(..., ge=1)
    status: str = EventStatus.ONGOING.value
    school_name: Optional[str] = None
    is_locked: bool = False
    
    @model_validator(mode='after')
    def check_period_logic(self):
        if self.end_period < self.start_period:
            raise ValueError('Tiết kết thúc phải lớn hơn hoặc bằng tiết bắt đầu')
        return self
    
    @field_validator('status')
    def validate_status(cls, v):
        if v not in [EventStatus.ONGOING.value, EventStatus.FINISHED.value, EventStatus.DELETED.value]:
            raise ValueError('Status must be one of: ongoing, finished, deleted')
        return v
    
    class Config:
        from_attributes = True
        str_strip_whitespace = True

class EventCreate(EventBase):
    pass

class JoinEventRequest(BaseModel):
    event_id: int
    role: str = EventRole.TA
    
    @field_validator('role')
    def validate_role(cls, v):
        if v not in [EventRole.INSTRUCTOR, EventRole.TA]:
            raise ValueError('Role must be instructor or ta')
        return v
    
    class Config:
        from_attributes = True

class UserEventLink(BaseModel):
    """Schema thể hiện thông tin User trong Event"""
    user_id: int
    role: str = "participant"
    
    class Config:
        from_attributes = True

class EventResponse(EventBase):
    event_id: int
    # UserEventLink được định nghĩa ở trên nên có thể dùng trực tiếp không cần dấu ''
    participants: List[UserEventLink] = []
    
    class Config:
        from_attributes = True