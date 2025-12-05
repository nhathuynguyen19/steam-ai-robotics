from fastapi import FastAPI, Request
from routers.api import admin, auth, events, users
import models, schemas, routers.api.auth as auth, database
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_redoc_html
from routers.api import users
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from helpers.limiter import limiter
from typing import Annotated
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_redoc_html
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import helpers.security as security
from routers.pages import auth as auth_page
from routers.pages import base as base_page
from routers.pages import partials as partials_page
from routers.pages import events as events_page
from routers.pages import admin as pages_admin
from routers.pages import profile
from utils import alembic_config

app = FastAPI(docs_url="/docs", 
              redoc_url=None,
              lifespan=alembic_config.lifespan
              )
app.mount("/static", StaticFiles(directory="static"), name="static")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SessionMiddleware, secret_key=security.SECRET_KEY)


# api routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(admin.router)

# pages routers
app.include_router(auth_page.router)
app.include_router(base_page.router)
app.include_router(partials_page.router)
app.include_router(events_page.router)
app.include_router(pages_admin.router)
app.include_router(profile.router)

# ============================
# CUSTOM REDOC
# ============================
@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/js/redoc.standalone.js",
    )
    
# Tạo bảng DB
models.Base.metadata.create_all(bind=database.engine)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Cấu hình CSP:
    # - script-src: Thêm 'unsafe-eval' để sửa lỗi bạn gặp.
    # - Thêm các domain CDN (jsdelivr, unpkg) để load thư viện.
    # - style-src/font-src: Cho phép Bootstrap và Google Fonts.
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "worker-src 'self' blob:;"
    )
    
    response.headers["Content-Security-Policy"] = csp_policy
    return response

    
# @app.get("/", response_class=HTMLResponse)
# async def page_home(request: Request, user: models.User | None = Depends(security.get_user_from_cookie)):
#     # Kiểm tra: Nếu chưa đăng nhập -> Đá về trang signin
#     if not user:
#         return RedirectResponse(url="/signin", status_code=302)
    
#     return RedirectResponse(url="/events", status_code=302)
                    
#     # 5. Nếu không có token hợp lệ -> Hiện trang đăng nhập
#     return templates.TemplateResponse("auth/signin.html", {"request": request})

# # ============================
# # AUTH HTML PAGES
# # ============================

# @app.get("/signin/", response_class=HTMLResponse)
# def page_signin(request: Request,
#                 user: models.User | None = Depends(security.get_user_from_cookie)):
#     if user:
#         return RedirectResponse(url="/events", status_code=302)
#     return templates.TemplateResponse("auth/signin.html", {"request": request})

# @app.get("/forgot-password/", response_class=HTMLResponse)
# def page_forgot_password(request: Request):
#     return templates.TemplateResponse("auth/forgot_password.html", {"request": request})

# @app.post("/forgot-password/")
# def forgot_password(email: str = Form(...), request: Request = None):
#     """Demo UI, không gửi mail thật."""
#     return templates.TemplateResponse(
#         "partials/success.html",
#         {"request": request, "message": f"Đã gửi hướng dẫn đặt lại mật khẩu đến {email}"},
#     )


# @app.get("/verify-email/", response_class=HTMLResponse)
# async def verify_email(request: Request, token: str, db: Session = Depends(database.get_db)):
#     """Xác thực email."""
#     try:
#         payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
#         email = payload.get("sub")
#     except:
#         return templates.TemplateResponse(
#             "partials/error.html",
#             {"request": request, "message": "Token hết hạn hoặc không hợp lệ"},
#         )

#     user = db.query(models.User).filter(models.User.email == email).first()
#     if not user:
#         return templates.TemplateResponse(
#             "partials/error.html",
#             {"request": request, "message": "User không tồn tại"},
#         )

#     if user.status:
#         return templates.TemplateResponse(
#             "partials/success.html",
#             {"request": request, "message": "Tài khoản đã được kích hoạt trước đó"},
#         )

#     user.status = True
#     db.commit()

#     return templates.TemplateResponse(
#         "partials/success.html",
#         {"request": request, "message": "Kích hoạt thành công – bạn có thể đăng nhập"},
#     )


# # ============================
# # USER PAGES (HTML)
# # ============================

# @app.get("/events", response_class=HTMLResponse)
# def page_events(request: Request, user: models.User | None = Depends(security.get_user_from_cookie)):
#     # Kiểm tra: Nếu chưa đăng nhập -> Đá về trang signin
#     if not user:
#         return RedirectResponse(url="/signin", status_code=302)
    
#     # Nếu đã đăng nhập -> Hiện trang Events và truyền user vào template
#     return templates.TemplateResponse("user/events.html", {
#         "request": request,
#         "user": user  # Truyền user để hiển thị tên, avatar...
#     })

# @app.get("/events/partial", response_class=HTMLResponse)
# async def view_events_table(
#     request: Request,
#     tab: str = "ongoing",
#     db: Session = Depends(database.get_db),
#     # [FIX] Đổi từ get_current_user sang get_user_from_cookie
#     current_user: models.User | None = Depends(security.get_user_from_cookie)
# ):
#     # [THÊM] Kiểm tra nếu không có user (cookie hết hạn) thì trả về lỗi hoặc redirect
#     if not current_user:
#         # Trả về header để HTMX tự redirect về trang đăng nhập
#         response = HTMLResponse(content="Unauthorized", status_code=401)
#         response.headers["HX-Redirect"] = "/signin"
#         return response
    
#     today = date.today()
#     now = datetime.now()
    
#     # Query cơ bản: không lấy sự kiện đã xóa
#     query = db.query(models.Event).filter(models.Event.status != models.EventStatus.DELETED.value)
    
#     # 1. Logic phân chia Tab
#     if tab == "upcoming":
#         # Sự kiện chưa diễn ra: Ngày bắt đầu > Hôm nay
#         query = query.filter(models.Event.day_start > today)
#     elif tab == "finished":
#         # Sự kiện đã hoàn thành: Ngày bắt đầu < Hôm nay (Giản lược logic)
#         # Hoặc chính xác hơn là kết hợp logic giờ kết thúc, nhưng để đơn giản theo ngày:
#         query = query.filter(models.Event.day_start < today)
#     else: # ongoing
#         # Sự kiện đang diễn ra: Ngày bắt đầu == Hôm nay
#         query = query.filter(models.Event.day_start == today)
    
#     events = query.order_by(models.Event.day_start, models.Event.start_period).all()
    
#     # 2. Xử lý dữ liệu hiển thị (Decorate data)
#     events_data = []
#     for e in events:
#         # Lấy thông tin tham gia của user hiện tại
#         user_event = db.query(models.UserEvent).filter_by(
#             user_id=current_user.user_id, 
#             event_id=e.event_id
#         ).first()
        
#         is_joined = user_event is not None
#         user_role = user_event.role if is_joined else None
#         has_checked_in = (user_event.status == 'attended') if is_joined else False
        
#         # Logic tính thời gian kết thúc cụ thể của sự kiện
#         end_hour, end_minute = PERIOD_END_TIMES.get(e.end_period, (23, 59))
#         event_end_dt = datetime.combine(e.day_start, time(hour=end_hour, minute=end_minute))
        
#         # Kiểm tra sự kiện đã kết thúc về mặt thời gian chưa (để mở khóa checkbox)
#         is_time_finished = now > event_end_dt
        
#         # Logic Tag "Finished": Tất cả người tham gia đều đã check-in
#         total_participants = len(e.participants)
#         checked_in_count = sum(1 for p in e.participants if p.status == 'attended')
#         # Tag hiện khi: có người tham gia VÀ tất cả đều đã check-in
#         show_finished_tag = (total_participants > 0) and (total_participants == checked_in_count)
        
#         events_data.append({
#             "obj": e,
#             "is_joined": is_joined,
#             "user_role": user_role,
#             "has_checked_in": has_checked_in,
#             "is_time_finished": is_time_finished,
#             "show_finished_tag": show_finished_tag,
#             "participant_count": total_participants
#         })
        
#     return templates.TemplateResponse(
#         "user/_events_table.html", 
#         {
#             "request": request, 
#             "events_data": events_data,
#             "current_tab": tab,
#             "current_user": current_user
#         }
#     )


# # ============================
# # ADMIN PAGES (HTML)
# # ============================

# @app.get("/admin/events", response_class=HTMLResponse)
# def admin_events_page(request: Request):
#     return templates.TemplateResponse("admin/events.html", {"request": request})

