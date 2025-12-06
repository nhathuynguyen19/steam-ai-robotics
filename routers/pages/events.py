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
from fastapi import HTTPException
from routers.api.events import PERIOD_START_TIMES, PERIOD_END_TIMES

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
        return current_user 
    
    return templates.TemplateResponse(
        "pages/create_event.html",
        {
            "request": request,
            "user": current_user,
            "error": None,
            # [MỚI] Truyền danh sách giờ xuống template
            "period_start_times": PERIOD_START_TIMES,
            "period_end_times": PERIOD_END_TIMES
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
    # max_user_joined: Annotated[int, Form()],
    max_instructor: Annotated[int, Form()],
    max_teaching_assistant: Annotated[int, Form()],
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
            max_user_joined=max_instructor + max_teaching_assistant,
            school_name=school_name,
            max_instructor=max_instructor,
            max_teaching_assistant=max_teaching_assistant,
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
        
# 3. GET: Hiển thị trang cập nhật sự kiện
@router.get("/{event_id}/edit")
async def get_event_edit_page(
    request: Request,
    event_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user 

    # Tìm sự kiện theo ID
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện")

    return templates.TemplateResponse(
        "pages/edit_event.html", # File template này sẽ tạo ở bước 3
        {
            "request": request,
            "user": current_user,
            "event": event,
            "error": None,
            # [MỚI] Truyền danh sách giờ xuống template
            "period_start_times": PERIOD_START_TIMES,
            "period_end_times": PERIOD_END_TIMES
        }
    )

# 4. POST: Xử lý cập nhật sự kiện
@router.post("/{event_id}/edit")
async def update_event_action(
    request: Request,
    event_id: int,
    name: Annotated[str, Form()],
    day_start: Annotated[date, Form()],
    start_period: Annotated[int, Form()],
    end_period: Annotated[int, Form()],
    number_of_student: Annotated[int, Form()],
    # [THAY ĐỔI] Thay max_user_joined bằng 2 trường riêng biệt
    max_instructor: Annotated[int, Form()],
    max_teaching_assistant: Annotated[int, Form()],
    school_name: Annotated[Optional[str], Form()] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user

    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện")

    try:
        # Tự động tính tổng max_user_joined
        calculated_max_joined = max_instructor + max_teaching_assistant
        
        # Validate dữ liệu bằng Schema
        event_data = schemas.EventCreate(
            name=name,
            day_start=day_start,
            start_period=start_period,
            end_period=end_period,
            number_of_student=number_of_student,
            max_user_joined=calculated_max_joined, # Gán giá trị tính toán
            max_instructor=max_instructor,         # Gán giá trị riêng
            max_teaching_assistant=max_teaching_assistant, # Gán giá trị riêng
            school_name=school_name
        )

        # Cập nhật các trường vào DB
        event.name = event_data.name
        event.day_start = event_data.day_start
        event.start_period = event_data.start_period
        event.end_period = event_data.end_period
        event.number_of_student = event_data.number_of_student
        
        event.max_instructor = event_data.max_instructor
        event.max_teaching_assistant = event_data.max_teaching_assistant
        event.max_user_joined = event_data.max_user_joined
        
        event.school_name = event_data.school_name
        
        db.commit()
        db.refresh(event)
        
        # Redirect về trang chủ hoặc trang chi tiết
        return RedirectResponse(url="/events", status_code=status.HTTP_303_SEE_OTHER)

    except ValueError as e:
        return templates.TemplateResponse(
            "pages/edit_event.html",
            {
                "request": request,
                "user": current_user,
                "event": event, # Trả lại event cũ để fill form
                "error": str(e),
                "period_start_times": PERIOD_START_TIMES,
                "period_end_times": PERIOD_END_TIMES
            }
        )
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            "pages/edit_event.html",
            {
                "request": request,
                "user": current_user,
                "event": event,
                "error": "Lỗi hệ thống: " + str(e),
                "period_start_times": PERIOD_START_TIMES,
                "period_end_times": PERIOD_END_TIMES
            }
        )