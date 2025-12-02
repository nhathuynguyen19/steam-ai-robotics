from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from pathlib import Path

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
    full_name: Annotated[str, Form()],
    password: Annotated[Optional[str], Form()] = None,
    confirm_password: Annotated[Optional[str], Form()] = None,
    db: Session = Depends(database.get_db),
    user: models.User | None = Depends(security.get_user_from_cookie)
):
    if not user:
        return RedirectResponse(url="/auth/signin", status_code=status.HTTP_302_FOUND)

    error = None
    success = None

    try:
        # Cập nhật Họ tên
        user.full_name = full_name

        # Cập nhật Mật khẩu (nếu có nhập)
        if password and len(password.strip()) > 0:
            if len(password) < 8:
                error = "Mật khẩu mới phải có ít nhất 8 ký tự."
            elif password != confirm_password:
                error = "Mật khẩu xác nhận không khớp."
            else:
                user.hashed_password = security.get_password_hash(password)
        
        if not error:
            db.commit()
            db.refresh(user)
            success = "Cập nhật thông tin thành công!"
            
    except Exception as e:
        db.rollback()
        error = f"Đã xảy ra lỗi: {str(e)}"

    return templates.TemplateResponse(
        "pages/profile.html", 
        {
            "request": request, 
            "user": user,
            "success": success,
            "error": error
        }
    )