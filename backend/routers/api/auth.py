from datetime import datetime, timedelta
from typing import Annotated
from fastapi import Depends, HTTPException, status, APIRouter, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
# from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import models, schemas, database
from dotenv import load_dotenv
import os
from utils.email_utils import send_verification_email
import core.security as security
import re
from core.limiter import limiter

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)

# Lấy limiter từ app state (trick để tránh circular import nếu khai báo limiter ở file riêng)
def get_limiter(request: Request):
    return request.app.state.limiter


@router.post("/signin/", response_model=schemas.Token)
@limiter.limit("5/minute")
async def signin_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(database.get_db)
):
    
    # 1. Tìm user theo Email
    # Mặc dù biến tên là form_data.username (do chuẩn OAuth2 bắt buộc), 
    # nhưng người dùng sẽ nhập Email vào đây.
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    # 2. Xử lý logic: Chưa có user VÀ Hệ thống đang rỗng (Lần đầu tiên chạy)
    if not user:
        # Đếm tổng số user đang có
        user_count = db.query(models.User).count()
        
        if user_count == 0:
            # 1. Validate Gmail
            if not form_data.username.endswith("@gmail.com"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admin đầu tiên phải sử dụng tài khoản Gmail (@gmail.com)"
                )

            # 2. Validate độ khó mật khẩu
            password = form_data.password
            if len(password) < 8:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Mật khẩu khởi tạo phải có ít nhất 8 ký tự"
                )
            if not re.search(r"\d", password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Mật khẩu khởi tạo phải chứa ít nhất một chữ số"
                )
            if not re.search(r"[a-zA-Z]", password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Mật khẩu khởi tạo phải chứa ít nhất một chữ cái"
                )
            # === AUTO REGISTER ADMIN ===
            # Đây là người dùng đầu tiên của hệ thống
            hashed_password = security.get_password_hash(form_data.password)
            
            user = models.User(
                email=form_data.username,
                hashed_password=hashed_password,
                role=schemas.UserRole.ADMIN.value, # Set quyền Admin cao nhất
                status=False,                 
                full_name="Super Admin"      # Tên mặc định (tùy chọn)
            )
            try:
                db.add(user)
                db.commit()
                db.refresh(user)
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=400, detail="Error creating admin user: " + str(e))
            # Sau bước này, 'user' đã tồn tại và hợp lệ, code sẽ chạy tiếp xuống dưới để tạo token
            
            # verify email for first admin
            verification_token = security.create_access_token(
                data={"sub": user.email, "type": "verification"},
                expires_delta=timedelta(hours=24) # Token có hạn trong 24 giờ
            )
            background_tasks = BackgroundTasks()
            background_tasks.add_task(
                send_verification_email, 
                to_email=user.email, 
                token=verification_token
            )
            await background_tasks()
        else:
            # User không tồn tại và hệ thống đã có người khác rồi -> Lỗi đăng nhập
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # 3. Nếu user đã tồn tại -> Verify password
        if not security.verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    # check user status
    if not user.status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not activated. Please verify your email.",
        )
    
    # SINGLE SESSION LOGIC:
    # Tăng version lên 1 mỗi khi đăng nhập thành công
    # Điều này làm các token cũ (chứa version cũ) bị vô hiệu hóa ngay lập tức
    try:
        user.token_version = (user.token_version or 0) + 1
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error during login")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    # Tạo token chứa version mới
    access_token = security.create_access_token(
        data={"sub": user.email, "v": user.token_version}, 
        expires_delta=timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# send verification email
@router.post("/send-verification-email/")
async def send_verification_email_endpoint(
    background_tasks: BackgroundTasks,
    email_request: schemas.EmailRequest,
    db: Session = Depends(database.get_db)
):
    # Tìm user theo email
    user = db.query(models.User).filter(models.User.email == email_request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.status:
        return {"message": "Account is already activated"}
    
    # Tạo token verification
    verification_token = security.create_access_token(
        data={"sub": user.email, "type": "verification"},
        expires_delta=timedelta(hours=24) # Token có hạn trong 24 giờ
    )
    
    # Gửi email trong background
    background_tasks.add_task(
        send_verification_email, 
        to_email=user.email, 
        token=verification_token
    )
    
    return {"message": "Verification email sent"}

@router.get("/verify/")
async def verify_email(token: str, db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Could not validate credentials or token expired",
    )
    
    try:
        # token decode
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "verification":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Tìm user trong DB
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Check if already activated
    if user.status:
        return {"message": "Account already activated"}
    
    # activate user
    user.status = True
    db.commit()
    
    return {"message": "Account activated successfully. You can now login."}

