# from typing import Annotated
from fastapi import FastAPI, Request
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlalchemy.orm import Session, joinedload
from routers.api import admin, auth, events, users
import models, schemas, routers.api.auth as auth, database
# from utils.email_utils import send_verification_email
# from jose import jwt, JWTError
from fastapi.staticfiles import StaticFiles # <--- Import cái này
from fastapi.openapi.docs import get_redoc_html # <--- Import cái này
# from models import EventRole
from routers.api import users
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from core.limiter import limiter
from typing import Annotated
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_redoc_html
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import core.security as security

from sqlalchemy.orm import Session
from jose import jwt, JWTError

# from backend import models, schemas, auth, database
# from backend.models import EventRole
# from backend.email_utils import send_verification_email


# ============================
# PATH & TEMPLATE CONFIG
# ============================

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(docs_url="/docs", redoc_url=None)

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

# Gắn state limiter vào app để dùng trong Router
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SessionMiddleware, secret_key=security.SECRET_KEY)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(admin.router)

# Tạo bảng DB
models.Base.metadata.create_all(bind=database.engine)


# ============================
# CUSTOM REDOC
# ============================
@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )
    

# ============================
# AUTH HTML PAGES
# ============================

@app.get("/", response_class=HTMLResponse)
def page_home(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@app.get("/login/", response_class=HTMLResponse)
def page_login(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@app.get("/register/", response_class=HTMLResponse)
def page_register(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

@app.get("/forgot-password/", response_class=HTMLResponse)
def page_forgot_password(request: Request):
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})

@app.post("/forgot-password/")
def forgot_password(email: str = Form(...), request: Request = None):
    """Demo UI, không gửi mail thật."""
    return templates.TemplateResponse(
        "partials/success.html",
        {"request": request, "message": f"Đã gửi hướng dẫn đặt lại mật khẩu đến {email}"},
    )


@app.get("/verify-email/", response_class=HTMLResponse)
async def verify_email(request: Request, token: str, db: Session = Depends(database.get_db)):
    """Xác thực email."""
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email = payload.get("sub")
    except:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Token hết hạn hoặc không hợp lệ"},
        )

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "User không tồn tại"},
        )

    if user.status:
        return templates.TemplateResponse(
            "partials/success.html",
            {"request": request, "message": "Tài khoản đã được kích hoạt trước đó"},
        )

    user.status = True
    db.commit()

    return templates.TemplateResponse(
        "partials/success.html",
        {"request": request, "message": "Kích hoạt thành công – bạn có thể đăng nhập"},
    )


# ============================
# USER PAGES (HTML)
# ============================

@app.get("/events", response_class=HTMLResponse)
def page_events(request: Request):
    return templates.TemplateResponse("user/events.html", {"request": request})


# ============================
# ADMIN PAGES (HTML)
# ============================

@app.get("/admin/events", response_class=HTMLResponse)
def admin_events_page(request: Request):
    return templates.TemplateResponse("admin/events.html", {"request": request})