from fastapi import APIRouter, Query
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
import models, schemas, database
import helpers.security as security
from schemas import EventRole
from datetime import datetime, date, time
from pathlib import Path
from fastapi.templating import Jinja2Templates
from zoneinfo import ZoneInfo
from typing import List 
import models # Đảm bảo đã import models
from utils.constants import PERIOD_START_TIMES, PERIOD_END_TIMES

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def get_vietnamese_weekday(d: date) -> str:
    weekdays = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
    return weekdays[d.weekday()]

TAB_TITLES = {
    "upcoming": "Sự Kiện Sắp Diễn Ra",
    "ongoing": "Sự Kiện Đang Diễn Ra",
    "finished": "Sự Kiện Đã Kết Thúc"
}

def format_period_start_time(period: int) -> str:
    start = PERIOD_START_TIMES.get(period)
    if not start:
        return "N/A"
    h, m = start
    return f"{h}h{m:02d}"

def format_period_end_time(period: int) -> str:
    start = PERIOD_END_TIMES.get(period)
    if not start:
        return "N/A"
    h, m = start
    return f"{h}h{m:02d}"


router = APIRouter(
    prefix="/partials",
    tags=["partials"],
)

@router.get("/events-table")
async def render_events_table(
    request: Request,
    tab: str = Query("upcoming", enum=["upcoming", "ongoing", "finished"]),
    db: Session = Depends(database.get_db), 
    current_user = Depends(security.get_user_from_cookie)
):
    if not current_user:
        return templates.TemplateResponse(
            "partials/events_table.html", 
            {"request": request, "events": [], "error": "Vui lòng đăng nhập để xem lịch."}
        )

    # Lấy sự kiện chưa bị xóa
    all_events = db.query(models.Event)\
        .filter(models.Event.status != "deleted")\
        .options(joinedload(models.Event.participants).joinedload(models.UserEvent.user))\
        .order_by(models.Event.day_start)\
        .limit(20)\
        .all()

    filtered_events: list[models.Event] = []
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None)

    # 2. Lọc sự kiện theo Tab
    for event in all_events:
        # Lấy giờ phút bắt đầu và kết thúc từ dict
        start_h, start_m = PERIOD_START_TIMES.get(event.start_period, (7, 0))
        end_h, end_m = PERIOD_END_TIMES.get(event.end_period, (23, 59))

        # Tạo datetime đầy đủ
        start_dt = datetime.combine(event.day_start, time(start_h, start_m))
        end_dt = datetime.combine(event.day_start, time(end_h, end_m))
        
        # Gán tạm vào object để dùng cho việc sort bên dưới
        event.real_start_dt = start_dt
        event.real_end_dt = end_dt

        # Logic phân loại
        if tab == "upcoming":
            # Sắp diễn ra: Thời gian bắt đầu > hiện tại
            if start_dt > now:
                filtered_events.append(event)
        
        elif tab == "ongoing":
            # Đang diễn ra: Đã bắt đầu nhưng chưa kết thúc
            if start_dt <= now <= end_dt:
                filtered_events.append(event)
        
        elif tab == "finished":
            # Đã kết thúc: Thời gian kết thúc < hiện tại
            if end_dt < now:
                filtered_events.append(event)

    # 3. Sắp xếp danh sách
    if tab == "finished":
        # Sự kiện đã qua: Sự kiện mới nhất (vừa xong) lên đầu
        filtered_events.sort(key=lambda x: x.real_end_dt, reverse=True)
    else:
        # Sắp diễn ra & Đang diễn ra: Sự kiện gần nhất (sắp tới) lên đầu
        filtered_events.sort(key=lambda x: x.real_start_dt)

    # Giới hạn số lượng hiển thị (ví dụ 50) để tránh quá tải view
    filtered_events = filtered_events[:50]

    events_view = []
    for event in filtered_events:
        # 1. Tách danh sách tham gia
        # Lưu ý: check kỹ string role trong DB so với Enum. 
        # Trong schemas.py: INSTRUCTOR = "instructor", TA = "teaching_assistant"
        
        list_instructors = [p for p in event.participants if p.role == EventRole.INSTRUCTOR.value]
        list_tas = [p for p in event.participants if p.role == EventRole.TA.value]
        
        # Lấy tên để hiển thị (như cũ)
        instructor_names = [p.user.full_name for p in list_instructors if p.user]
        ta_names = [p.user.full_name for p in list_tas if p.user]
        
        # 2. Tìm trạng thái của user hiện tại
        current_participant = next((p for p in event.participants if p.user_id == current_user.user_id), None)
        is_joined = current_participant is not None
        user_role = current_participant.role if is_joined else None
        attendance_status = current_participant.status if is_joined else None
        
        # 3. Tính toán Logic từng vai trò
        # Instructor
        count_instructor = len(list_instructors)
        is_instructor_full = count_instructor >= (event.max_instructor or 1) # Default 1 nếu None
        
        # TA
        count_ta = len(list_tas)
        is_ta_full = count_ta >= (event.max_teaching_assistant or 0) # Default 0 nếu None

        # Logic thời gian
        is_ended = now > event.real_end_dt
        
        # [THÊM] Tính thứ
        day_name_str = get_vietnamese_weekday(event.day_start)
        
        events_view.append({
            "event_id": event.event_id,
            "day_str": event.day_start.strftime("%d/%m/%Y"),
            "day_str_month_year": event.day_start.strftime("%m/%Y"), # Thêm trường này cho template
            "time_str": f"{format_period_start_time(event.start_period)} - {format_period_end_time(event.end_period)}",
            "period_detail": f"(Tiết {event.start_period}-{event.end_period})",
            "school_name": event.school_name,
            "name": event.name,
            "student_count": event.number_of_student,
            
            # Thông tin hiển thị cột phân công
            "instructors": ", ".join(instructor_names) if instructor_names else "---",
            "tas": ", ".join(ta_names) if ta_names else "---",
            
            # Thông tin logic hành động
            "is_joined": is_joined,
            "user_role": user_role,              # 'instructor' hoặc 'teaching_assistant'
            "attendance_status": attendance_status, # 'registered' hoặc 'attended'
            
            "is_ended": is_ended,
            "is_locked": event.is_locked,
            "status": event.status,
            
            # Logic riêng cho từng role
            "max_instructor": event.max_instructor,
            "curr_instructor": count_instructor,
            "is_instructor_full": is_instructor_full,
            
            "max_ta": event.max_teaching_assistant,
            "curr_ta": count_ta,
            "is_ta_full": is_ta_full,
            
            "day_name": day_name_str,
        })
        
    current_title = TAB_TITLES.get(tab, "Danh Sách Sự Kiện")

    return templates.TemplateResponse(
        "partials/events_table.html", 
        {
            "request": request, 
            "events": events_view,
            "user": current_user,
            "current_tab": tab, 
            "title": current_title
        }
    )