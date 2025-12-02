from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from pathlib import Path
import schemas

import database
import models
import helpers.security as security

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(
    tags=["pages_profile"]
)

# 1. GET: Hiển thị trang Profile
@router.get("/profile")
async def view_profile(
    request: Request,
    user: models.User | None = Depends(security.get_user_from_cookie)
):
    # Nếu chưa đăng nhập -> đá về trang login
    if not user:
        return RedirectResponse(url="/auth/signin", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        "pages/profile.html", 
        {
            "request": request, 
            "user": user,
            "success": None,
            "error": None
        }
    )

# 2. POST: Xử lý cập nhật thông tin
@router.post("/profile")
async def update_profile(
    request: Request,
    # Nhận dữ liệu từ Form HTML (tên biến phải khớp name="" trong HTML)
    full_name: str = Form(...),
    phone: str = Form(...),
    name_bank: str = Form(None),   # Cho phép None
    bank_number: str = Form(None), # Cho phép None
    password: str = Form(None),    # Cho phép None
    re_password: str = Form(None), # Cho phép None
    db: Session = Depends(database.get_db),
    current_user: models.User | None = Depends(security.get_user_from_cookie)
):
    if not current_user:
        return RedirectResponse(url="/auth/signin", status_code=status.HTTP_302_FOUND)
    
    user_phone = db.query(models.User).filter(models.User.phone == phone).first()

    error = None
    success = None

    try:
        # --- BƯỚC 1: KIỂM TRA SỐ ĐIỆN THOẠI TỒN TẠI ---
        # Chỉ kiểm tra nếu số điện thoại mới khác số điện thoại hiện tại
        if current_user.phone != phone:
            existing_user = db.query(models.User).filter(
                models.User.phone == phone,
                models.User.user_id != current_user.user_id # Loại trừ chính user đang update
            ).first()

            if existing_user:
                error = "Số điện thoại này đã được sử dụng bởi một tài khoản khác."
                
        # Kiểm tra lỗi ở Bước 1 trước khi tiếp tục
        if error is None:
            # Cập nhật Họ tên
            current_user.full_name = full_name
            current_user.phone = phone
            current_user.name_bank = name_bank
            current_user.bank_number = bank_number

            # 2. Xử lý đổi mật khẩu (chỉ khi người dùng nhập vào ô password)
            if password and password.strip():
                # Validate thủ công hoặc dùng schema ở đây
                if len(password) < 8:
                    error = "Mật khẩu mới phải có ít nhất 8 ký tự."
                elif password != re_password:
                    error = "Mật khẩu xác nhận không khớp."
                else:
                    # Hash mật khẩu và lưu
                    current_user.hashed_password = security.get_password_hash(password)
        
        if not error:
            db.commit()
            db.refresh(current_user)
            error = None
            success = "Cập nhật thông tin thành công!"
            
    except Exception as e:
        db.rollback()
        error = f"Đã xảy ra lỗi hệ thống: {str(e)}"
        
    # Render lại trang profile với thông báo
    return templates.TemplateResponse(
        "pages/profile.html", 
        {
            "request": request, 
            "user": current_user,
            "error": error,
            "success": success
        }
    )