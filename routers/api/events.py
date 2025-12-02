from fastapi import APIRouter, Form, Response, Query
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
import models, schemas, database
import helpers.security as security
from schemas import EventRole
from datetime import datetime, date, time
from pathlib import Path
from fastapi.templating import Jinja2Templates

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

router = APIRouter(
    prefix="/api/events",
    tags=["events"],
)

# --- Helper function để lấy datetime thực tế ---
def get_event_times(event_day: date, start_period: int, end_period: int):
    sh, sm = PERIOD_START_TIMES.get(start_period, (7, 0))
    eh, em = PERIOD_END_TIMES.get(end_period, (21, 0))
    start_dt = datetime.combine(event_day, time(sh, sm))
    end_dt = datetime.combine(event_day, time(eh, em))
    return start_dt, end_dt

# --- EVENT ENDPOINTS (Admin Create) ---

# xem su kien by id
@router.get("/{event_id}", response_model=schemas.EventResponse)
def read_event(event_id: int, db: Session = Depends(database.get_db), current_user = Depends(security.get_current_user)):
    event = db\
        .query(models.Event)\
        .options(joinedload(models.Event.participants))\
        .filter(models.Event.event_id == event_id)\
        .first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.get("", response_model=list[schemas.EventResponse])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db), current_user = Depends(security.get_current_user)):
    events = db\
        .query(models.Event)\
        .options(joinedload(models.Event.participants))\
        .offset(skip)\
        .limit(limit)\
        .all()
    return events

@router.get("/partials/events_table")
async def render_events_table(
    request: Request,
    db: Session = Depends(database.get_db),
    current_user = Depends(security.get_current_user)
):
    if not current_user:
        return templates.TemplateResponse(
            "partials/events_table.html", 
            {"request": request, "events": [], "error": "Vui lòng đăng nhập để xem lịch."}
        )
    


@router.post("", response_model=schemas.EventResponse)
def create_event(
    event: schemas.EventCreate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_user)
):
    new_event = models.Event(**event.dict())
    try:
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating event: " + str(e))
    
    return new_event

# cap nhat su kien
@router.put("/{event_id}/", response_model=schemas.EventResponse)
def update_event(
    event_id: int,
    event_update: schemas.EventCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_user)
):
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    for key, value in event_update.dict().items():
        setattr(event, key, value)
    
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error updating event: " + str(e))
    
    return event

# xoa su kien
@router.delete("/{event_id}/", status_code=204)
def delete_event(
    event_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_user)
):
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Thay vì xoá hẳn, ta chỉ đánh dấu là 'deleted'
    event.status = schemas.EventStatus.DELETED.value
    try:
        db.add(event)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error deleting event: " + str(e))
    
    return


# --- USER-EVENT ACTION (User tham gia sự kiện) ---
@router.post("/{event_id}/join/")
def join_event(
    event_id: int,
    role: str = Form(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_user_from_cookie)
):
    # 1. Check event tồn tại
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # kiem tra event bi xoa
    if event.status == schemas.EventStatus.DELETED.value:
        raise HTTPException(status_code=400, detail="Cannot join a deleted event")
    
    # check event is locked
    if event.is_locked:
        raise HTTPException(status_code=400, detail="Event is locked. Cannot join at this time.")
    
    # 2. Check đã tham gia chưa
    existing_link = db.query(models.UserEvent).filter(
        models.UserEvent.user_id == current_user.user_id,
        models.UserEvent.event_id == event_id
    ).first()
    if existing_link:
        raise HTTPException(status_code=400, detail="User already joined this event")
    
    # kiem tra so luong nguoi tham gia du thi khoa event
    participant_count = db.query(models.UserEvent).filter(
        models.UserEvent.event_id == event_id
    ).count()
    
    if participant_count >= event.max_user_joined:
        raise HTTPException(status_code=400, detail="Event has reached maximum number of participants")

    # 3. Tạo link
    user_event = models.UserEvent(user_id=current_user.user_id, event_id=event_id, role=role)
    
    try:
        db.add(user_event)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error joining event: " + str(e))
    
    return Response(status_code=200, headers={"HX-Trigger": "event_updated"})

# huy tham gia
@router.post("/{event_id}/leave/")
def leave_event(
    event_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_user_from_cookie)
):
    # 1. Check event tồn tại
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # check event is bi xoa
    if event.status == schemas.EventStatus.DELETED.value:
        raise HTTPException(status_code=400, detail="Cannot leave a deleted event")
    
    # check event is locked
    if event.is_locked:
        raise HTTPException(status_code=400, detail="Event is locked. Cannot leave at this time.")
    
    # 2. Check đã tham gia chưa
    existing_link = db.query(models.UserEvent).filter(
        models.UserEvent.user_id == current_user.user_id,
        models.UserEvent.event_id == event_id
    ).first()
    if not existing_link:
        raise HTTPException(status_code=400, detail="User has not joined this event")
    
    # check da hoan thanh su kien chua
    if existing_link.status == "attended":
        raise HTTPException(status_code=400, detail="Cannot leave an event that has been attended")
    
    # 3. Xoá link
    try:
        db.delete(existing_link)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error leaving event: " + str(e))
    
    return Response(status_code=200, headers={"HX-Trigger": "event_updated"})

# danh dau da tham gia
@router.post("/{event_id}/attend/")
def attend_event(
    event_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_user_from_cookie)
):
    # 1. Check event tồn tại
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # 2. Check đã tham gia chưa
    existing_link = db.query(models.UserEvent).filter(
        models.UserEvent.user_id == current_user.user_id,
        models.UserEvent.event_id == event_id
    ).first()
    if not existing_link:
        raise HTTPException(status_code=400, detail="User has not joined this event")
    
    # kiem tra su kien ket thuc chua
    now = datetime.now()
    
    # Lấy giờ, phút kết thúc dựa trên end_period của event
    # (Giả sử bạn đã đổi tên trường to_time -> end_period trong models.py như hướng dẫn trước)
    # Nếu chưa đổi trong DB thì thay event.end_period bằng event.to_time (nếu to_time đang lưu số tiết)
    end_hour, end_minute = PERIOD_END_TIMES.get(event.end_period, (23, 59))
    
    event_end_time = datetime.combine(event.day_start, time(hour=end_hour, minute=end_minute))   
     
    if now < event_end_time:
        raise HTTPException(status_code=400, detail="Event has not ended yet. Cannot mark attendance.")
    
    # 3. Cập nhật trạng thái tham gia
    existing_link.status = "attended"
    db.add(existing_link)
    db.commit()
    
    return Response(status_code=200, headers={"HX-Trigger": "event_updated"})

@router.post("/{event_id}/lock")
async def lock_event(
    event_id: int,
    response: Response,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie) # Chỉ Admin được phép
):
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện")
    
    event.is_locked = True
    db.commit()
    
    # Gửi tín hiệu để HTMX refresh lại bảng
    response.headers["HX-Trigger"] = "event_updated"
    return {"message": "Đã khóa sự kiện"}

# --- 2. API Mở khóa sự kiện ---
@router.post("/{event_id}/unlock")
async def unlock_event(
    event_id: int,
    response: Response,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện")
    
    event.is_locked = False
    db.commit()
    
    response.headers["HX-Trigger"] = "event_updated"
    return {"message": "Đã mở khóa sự kiện"}