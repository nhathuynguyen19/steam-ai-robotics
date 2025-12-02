# husc-ai-robotics/routers/pages/admin.py

from fastapi import APIRouter, Request, Depends, Form, status, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Annotated, Optional
from pydantic import ValidationError

import database
import models
import schemas
import helpers.security as security

from sqlalchemy import or_
from math import ceil

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(
    prefix="/admin",
    tags=["pages_admin"]
)

# 1. GET: Hiển thị form tạo tài khoản
@router.get("/users/create")
async def get_create_user_page(
    request: Request,
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    # Nếu dependency trả về RedirectResponse (chưa login hoặc không phải admin), return luôn
    if isinstance(current_user, RedirectResponse):
        return current_user
        
    return templates.TemplateResponse(
        "pages/admin/create_user.html",
        {
            "request": request,
            "user": current_user,
            "error": None,
            "success": None
        }
    )

@router.post("/users/create")
async def create_user_action(
    request: Request,
    email: Annotated[str, Form()],
    role: Annotated[str, Form()],
    # Cập nhật: Cho phép None hoặc chuỗi rỗng
    full_name: Annotated[str, Form()] = None, 
    phone: Annotated[str, Form()] = None,
    # Cập nhật: Mặc định là husc1234 nếu form không gửi lên (dù form html đã có value sẵn)
    password: Annotated[str, Form()] = "husc1234", 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    
    try:
        if not password or password.strip() == "":
            password = "husc1234"
        
        # Validate dữ liệu
        user_data = schemas.UserCreateAdmin(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            phone=phone,
            status=True
        )
        
        # Check email trùng
        if db.query(models.User).filter(models.User.email == user_data.email).first():
            raise ValueError("Email này đã được sử dụng.")
        
        # [FIX 5] Kiểm tra trùng Số điện thoại (Bắt buộc vì models.py yêu cầu unique)
        if db.query(models.User).filter(models.User.phone == user_data.phone).first():
            raise ValueError("Số điện thoại này đã được sử dụng.")

        # Tạo User
        new_user = models.User(
            email=user_data.email,
            hashed_password=security.get_password_hash(user_data.password),
            full_name=user_data.full_name,
            phone=user_data.phone,
            role=user_data.role,
            status=user_data.status
        )
        db.add(new_user)
        db.commit()
        
        return templates.TemplateResponse(
            "pages/admin/create_user.html",
            {
                "request": request,
                "user": current_user,
                "success": f"Đã tạo tài khoản {user_data.email} thành công!",
                "form_data": None # Reset form sau khi thành công
            }
        )

    except ValidationError as e:
        db.rollback()
        # Xử lý thông báo lỗi hiển thị cho đẹp
        error_msg = str(e.errors()[0].get("msg")).replace("Value error, ", "")
        return templates.TemplateResponse(
            "pages/admin/create_user.html",
            {
                "request": request,
                "user": current_user,
                "error": error_msg,
                "form_data": { # Giữ lại dữ liệu cũ khi lỗi
                    "email": email,
                    "full_name": full_name,
                    "phone": phone,
                    "role": role
                }
            }
        )
    except ValueError as e: # Catch lỗi trùng email/phone
        db.rollback()
        return templates.TemplateResponse(
            "pages/admin/create_user.html",
            {
                "request": request,
                "user": current_user,
                "error": str(e), # Hiển thị lỗi rõ ràng cho user
                "form_data": {
                    "email": email,
                    "full_name": full_name,
                    "phone": phone,
                    "role": role
                }
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "pages/admin/create_user.html",
            {
                "request": request,
                "user": current_user,
                "error": e,
                "form_data": { # Giữ lại dữ liệu cũ khi lỗi
                    "email": email,
                    "full_name": full_name,
                    "phone": phone,
                    "role": role
                }
            }
        )
        
# --- [MỚI] 1. Trang danh sách User (Có Search + Pagination) ---
@router.get("/users")
async def list_users(
    request: Request,
    search: str = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user

    LIMIT = 10
    query = db.query(models.User).filter(models.User.is_deleted == False)

    # Logic Tìm kiếm
    if search:
        query = query.filter(
            or_(
                models.User.email.ilike(f"%{search}%"),
                models.User.full_name.ilike(f"%{search}%")
            )
        )

    # Logic Phân trang
    total_users = query.count()
    total_pages = ceil(total_users / LIMIT)
    offset = (page - 1) * LIMIT
    
    users = query.order_by(models.User.user_id.desc()).offset(offset).limit(LIMIT).all()

    context = {
        "request": request,
        "user": current_user,
        "users": users,
        "search": search,
        "page": page,
        "total_pages": total_pages,
        "total_users": total_users
    }

    # Nếu là HTMX request (Search/Phân trang) -> Chỉ trả về Table partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/admin_users_table.html", context)
    
    # Nếu là request thường -> Trả về Full page
    return templates.TemplateResponse("pages/admin/users.html", context)


# --- [MỚI] 2. Trang Edit User (GET) ---
@router.get("/users/{user_id}/edit")
async def edit_user_page(
    request: Request,
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user

    target_user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("pages/admin/edit_user.html", {
        "request": request,
        "user": current_user,
        "target_user": target_user
    })


# --- [MỚI] 3. Xử lý Edit User (POST) ---
@router.post("/users/{user_id}/edit")
async def edit_user_action(
    request: Request,
    user_id: int,
    full_name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    user_status: Annotated[bool, Form(alias="status")] = False,
    password: Annotated[Optional[str], Form()] = None, # Mật khẩu mới (optional)
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user

    target_user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update info
    target_user.full_name = full_name
    target_user.role = role
    target_user.status = True if user_status else False # Checkbox HTML logic

    # Update password nếu có nhập
    if password and len(password.strip()) > 0:
        target_user.hashed_password = security.get_password_hash(password)

    db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)