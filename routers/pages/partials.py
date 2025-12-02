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

import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def now_vn():
    return datetime.now(VN_TZ)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
PERIOD_START_TIMES = {
    1:  (7, 0),
    2:  (8, 0),
    3:  (9, 0),
    4:  (10, 0),
    5:  (13, 0),
    6:  (14, 0),
    7:  (15, 0),
    8:  (16, 0),
    9:  (17, 30),
    10: (18, 25),
    11: (19, 25),
    12: (20, 25),
}

PERIOD_END_TIMES = {
    1:  (8, 0),
    2:  (9, 0),
    3:  (10, 0),
    4:  (11, 0),
    5:  (14, 0),
    6:  (15, 0),
    7:  (16, 0),
    8:  (17, 0),
    9:  (18, 25),
    10: (19, 25),
    11: (20, 25),
    12: (21, 25),
}

TAB_TITLES = {
    "upcoming": "Sự Kiện Sắp Diễn Ra",
    "ongoing": "Sự Kiện Đang Diễn Ra",
    "finished": "Sự Kiện Đã Kết Thúc"
}

# Hàm helper chuyển tiết học sang giờ (7h - 13h) để dùng trong template
def format_period(period: int) -> str:
    hour = 7 + (period - 1) if period <= 4 else 13 + (period - 5)
    return f"{hour}h00"

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

    filtered_events = []
    now = now_vn()

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

    # 4. Build View Model (Giữ nguyên logic cũ của bạn)
    events_view = []
    for event in filtered_events:
        instructors = [p.user.full_name 
                       for p in event.participants 
                       if p.role == 'instructor' and p.user and p.user.full_name]
        tas = [p.user.full_name 
               for p in event.participants 
               if p.role == 'ta' and p.user and p.user.full_name]
        
        current_participant = next((p for p in event.participants if p.user_id == current_user.user_id), None)
        is_joined = current_participant is not None
        
        # Logic is_ended dùng chính biến real_end_dt đã tính ở trên
        is_ended = now > event.real_end_dt
        
        is_full = len(event.participants) >= event.max_user_joined

        events_view.append({
            "event_id": event.event_id,
            "day_str": event.day_start.strftime("%d/%m/%Y"),
            "time_str": f"{format_period(event.start_period)} - {format_period(event.end_period + 1)}",
            "period_detail": f"(Tiết {event.start_period}-{event.end_period})",
            "school_name": event.school_name,
            "name": event.name,
            "student_count": event.number_of_student,
            "instructors": ", ".join(instructors) if instructors else "---",
            "tas": ", ".join(tas) if tas else "---",
            
            "is_joined": is_joined,
            "user_role": current_participant.role if is_joined else None,
            "attendance_status": current_participant.status if is_joined else None,
            "is_ended": is_ended,
            "is_full": is_full,
            "is_locked": event.is_locked,
            "status": event.status
        })
        
    current_title = TAB_TITLES.get(tab, "Danh Sách Sự Kiện")

    return templates.TemplateResponse(
        "partials/events_table.html", 
        {
            "request": request, 
            "events": events_view,
            "user": current_user,
            "current_tab": tab, # Truyền tab xuống view để active button nếu cần
            "title": current_title # Truyền tiêu đề xuống template
        }
    )