from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Annotated, Optional
from datetime import date

import database
import models
import schemas
import helpers.security as security

# Định nghĩa đường dẫn tới thư mục templates
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(
    prefix="/events",
    tags=["pages_events"] 
)

# 1. GET: Hiển thị trang tạo sự kiện (Chỉ Admin)
@router.get("/create")
async def get_event_create_page(
    request: Request,
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user # Trả về RedirectResponse nếu bị redirect
    
    return templates.TemplateResponse(
        "pages/create_event.html",  # Bạn cần tạo file template này
        {
            "request": request,
            "user": current_user,
            "error": None
        }
    )

# 2. POST: Xử lý form tạo sự kiện (Chỉ Admin)
@router.post("/create")
async def create_event_action(
    request: Request,
    name: Annotated[str, Form()],
    day_start: Annotated[date, Form()],
    start_period: Annotated[int, Form()],
    end_period: Annotated[int, Form()],
    number_of_student: Annotated[int, Form()],
    max_user_joined: Annotated[int, Form()],
    school_name: Annotated[Optional[str], Form()] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    try:
        # Sử dụng Schema để validate dữ liệu (logic start < end period đã có trong schema)
        event_data = schemas.EventCreate(
            name=name,
            day_start=day_start,
            start_period=start_period,
            end_period=end_period,
            number_of_student=number_of_student, # Map vào schema
            max_user_joined=max_user_joined,
            school_name=school_name
        )
        
        # Tạo model và lưu vào DB
        new_event = models.Event(**event_data.model_dump())
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        
        # Thành công: Redirect về trang danh sách sự kiện (hoặc trang chi tiết)
        # 303 See Other là chuẩn cho redirect sau khi POST
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    except ValueError as e:
        # Lỗi Validate (VD: tiết kết thúc < tiết bắt đầu): Trả lại form kèm thông báo lỗi
        return templates.TemplateResponse(
            "pages/create_event.html",
            {
                "request": request,
                "user": current_user,
                "error": str(e), # Hiển thị lỗi ra template
                # Có thể trả lại các giá trị đã nhập để user không phải gõ lại (optional)
            }
        )
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            "pages/create_event.html",
            {
                "request": request,
                "user": current_user,
                "error": "Đã xảy ra lỗi hệ thống: " + str(e)
            }
        )