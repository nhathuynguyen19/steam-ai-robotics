from fastapi import APIRouter, Request, Depends, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
import models
import helpers.security as security
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import database
from sqlalchemy.orm import Session  # [Thêm] Để khai báo kiểu dữ liệu Session
from datetime import date           # [Thêm] Để lấy ngày hiện tại
import database
from datetime import date, datetime, time


BASE_DIR = Path(__file__).resolve().parent.parent.parent

router = APIRouter(
    prefix="",
    tags=["pages"],
)

# --------------------------
# CẤU HÌNH THỜI GIAN TIẾT HỌC
# --------------------------
PERIOD_START_TIMES = {
    1:  (7, 0), 2:  (8, 0), 3:  (9, 0), 4:  (10, 0),
    5:  (13, 0), 6:  (14, 0), 7:  (15, 0), 8:  (16, 0),
    9:  (17, 30), 10: (18, 25), 11: (19, 25), 12: (20, 25),
}

PERIOD_END_TIMES = {
    1:  (8, 0), 2:  (9, 0), 3:  (10, 0), 4:  (11, 0),
    5:  (14, 0), 6:  (15, 0), 7:  (16, 0), 8:  (17, 0),
    9:  (18, 25), 10: (19, 25), 11: (20, 25), 12: (21, 25),
}

def get_event_times(event_day: date, start_period: int, end_period: int):
    """Tính toán thời gian bắt đầu và kết thúc cụ thể của sự kiện."""
    # Lấy giờ/phút từ cấu hình, mặc định tiết 1 (7:00) và tiết 12 (21:25) nếu không tìm thấy
    sh, sm = PERIOD_START_TIMES.get(start_period, (7, 0))
    eh, em = PERIOD_END_TIMES.get(end_period, (21, 25))
    
    start_dt = datetime.combine(event_day, time(sh, sm))
    end_dt = datetime.combine(event_day, time(eh, em))
    return start_dt, end_dt

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/ping")
async def ping():
    return {"status": "OK"}

@router.get("/")
async def root(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User | None = Depends(security.get_user_from_cookie),
):
    if user:
        now = datetime.now()
        today = now.date()
        
        # 1. Đếm sự kiện ở các NGÀY KHÁC (Dùng SQL cho nhanh)
        # - Sự kiện ở tương lai (ngày mai trở đi)
        future_events_count = db.query(models.Event).filter(models.Event.day_start > today).count()
        # - Sự kiện ở quá khứ (hôm qua trở về trước)
        past_events_count = db.query(models.Event).filter(models.Event.day_start < today).count()

        # 2. Xử lý sự kiện trong HÔM NAY (Phải check từng tiết)
        today_events = db.query(models.Event).filter(models.Event.day_start == today).all()
        
        today_upcoming_count = 0
        today_past_count = 0
        
        # dem so user
        query = db.query(models.User).filter(models.User.is_deleted == False)
        total_users = query.count()
        
        # Danh sách tạm chứa các sự kiện hôm nay đã kết thúc
        today_finished_events = []
        
        for event in today_events:
            # Tính thời gian thực tế dựa trên tiết
            start_dt, end_dt = get_event_times(event.day_start, event.start_period, event.end_period)
            
            if start_dt > now:
                # Chưa bắt đầu -> Sắp diễn ra
                today_upcoming_count += 1
            elif end_dt < now:
                # Đã kết thúc -> Đã qua
                today_past_count += 1
                today_finished_events.append(event) # Lưu lại để xử lý "mới nhất"
            # (Trường hợp còn lại là Đang diễn ra, không cộng vào đâu cả)

        # 3. Tổng hợp kết quả
        total_upcoming = future_events_count + today_upcoming_count
        total_past = past_events_count + today_past_count
        
        # --- 2. LẤY 2 SỰ KIỆN ĐÃ QUA MỚI NHẤT ---
        
        # Bước A: Lấy thêm sự kiện từ những ngày trước (Backup nếu hôm nay không đủ 2 sự kiện)
        # Sắp xếp giảm dần theo ngày và tiết để lấy cái gần nhất
        older_past_events = db.query(models.Event)\
            .filter(models.Event.day_start < today)\
            .order_by(models.Event.day_start.desc(), models.Event.end_period.desc())\
            .limit(2)\
            .all()
            
        # Bước B: Gộp danh sách "Hôm nay đã xong" và "Ngày cũ"
        # Ưu tiên: Hôm nay xong > Ngày cũ
        all_past_candidates = today_finished_events + older_past_events
        
        # Bước D: Lấy 2 cái đầu tiên
        recent_past_events = all_past_candidates[:2]
        
        return templates.TemplateResponse("/pages/dashboard.html", {
            "request": request, 
            "user": user,
            "total_users": total_users,
            "upcoming_count": total_upcoming,
            "past_count": total_past,
            "recent_past_events": recent_past_events # [New] Truyền biến này sang template
            })
    
    return RedirectResponse(url="/auth/signin", status_code=status.HTTP_302_FOUND)

@router.get("/events", response_class=HTMLResponse)
def get_events(request: Request, 
             tab: str = Query("upcoming", enum=["upcoming", "ongoing", "finished"]),
             user: models.User | None = Depends(security.get_user_from_cookie)
):
    if user:
        return templates.TemplateResponse("/pages/events.html", {
            "request": request, 
            "user": user,
            "tab": tab
            })
    return RedirectResponse(url="/auth/signin", status_code=302)