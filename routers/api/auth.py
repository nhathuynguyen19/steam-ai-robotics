from datetime import datetime, timedelta
from typing import Annotated
from fastapi import Depends, HTTPException, status, APIRouter, BackgroundTasks, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import models, schemas, database
from dotenv import load_dotenv
import os
from utils.email_utils import send_verification_email
import helpers.security as security
import re
from helpers.limiter import limiter

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)

# --- HELPER FUNCTION: Validate & Create First Admin ---
def create_first_super_admin(db: Session, form_data: OAuth2PasswordRequestForm, background_tasks: BackgroundTasks):
    """
    Hàm này chỉ chạy duy nhất 1 lần khi hệ thống chưa có User nào.
    Nó sẽ tạo tài khoản Super Admin và gửi email xác thực.
    """
    # 1. Validate Email & Password
    if not form_data.username.endswith("@gmail.com"):
        raise HTTPException(status_code=400, detail="Admin đầu tiên phải sử dụng tài khoản Gmail (@gmail.com)")
    
    password = form_data.password
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mật khẩu khởi tạo phải có ít nhất 8 ký tự")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Mật khẩu khởi tạo phải chứa ít nhất một chữ số")
    if not re.search(r"[a-zA-Z]", password):
        raise HTTPException(status_code=400, detail="Mật khẩu khởi tạo phải chứa ít nhất một chữ cái")

    # 2. Create User Logic
    hashed_password = security.get_password_hash(password)
    new_admin = models.User(
        email=form_data.username,
        hashed_password=hashed_password,
        role=schemas.UserRole.ADMIN.value,
        status=False, # Chưa kích hoạt, cần verify email
        full_name="Super Admin",
        phone="0900000000"
    )
    
    try:
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Lỗi tạo admin: {str(e)}")

    # 3. Send Verification Email
    verification_token = security.create_access_token(
        data={"sub": new_admin.email, "type": "verification"},
        expires_delta=timedelta(hours=24)
    )
    
    # Inject task gửi mail vào background
    background_tasks.add_task(
        send_verification_email, 
        email=new_admin.email, 
        token=verification_token
    )
    
    # Dừng quy trình đăng nhập, trả về 201 Created
    raise HTTPException(
        status_code=status.HTTP_201_CREATED,
        detail="Hệ thống đã khởi tạo tài khoản Admin. Vui lòng kiểm tra email để kích hoạt trước khi đăng nhập."
    )

# --- MAIN AUTH ROUTES ---

@router.post("/signin/", response_model=schemas.Token)
@limiter.limit("5/minute")
async def signin_for_access_token(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks, # Inject BackgroundTasks vào đây
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(database.get_db)
):
    # 1. Tìm user theo Email
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    # 2. Xử lý trường hợp User chưa tồn tại
    if not user:
        # Nếu DB rỗng -> Tạo Admin đầu tiên
        user_count = db.query(models.User).count()
        if user_count == 0:
            # Hàm này sẽ raise Exception để kết thúc request luôn nếu tạo thành công
            create_first_super_admin(db, form_data, background_tasks)
        
        # Nếu DB không rỗng mà tìm không thấy user -> Lỗi đăng nhập
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. User tồn tại -> Verify Password
    if not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
            
    # 4. Check Status (Account Activation)
    if not user.status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not activated. Please verify your email.",
        )
    
    # 5. SINGLE SESSION LOGIC
    # Tăng version lên 1 mỗi khi đăng nhập thành công
    try:
        user.token_version = (user.token_version or 0) + 1
        # db.add(user) # Không cần thiết vì object đang được session track
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error during login")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    # 6. Tạo Token & Set Cookie
    access_token = security.create_access_token(
        data={"sub": user.email, "v": user.token_version}, 
        expires_delta=timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=False,  
        max_age=1800,   # 30 phút
        samesite="lax", 
        secure=False    # Đặt True nếu chạy HTTPS production
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/signout/")
async def signout(response: Response):
    """
    Đăng xuất người dùng bằng cách xóa cookie access_token.
    """
    response.delete_cookie(key="access_token")
    # Thêm header này để HTMX tự động chuyển hướng về trang đăng nhập
    response.headers["HX-Redirect"] = "/auth/signin"
    return {"message": "Signed out successfully"}


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
        expires_delta=timedelta(hours=24)
    )
    
    # Gửi email trong background
    background_tasks.add_task(
        send_verification_email, 
        email=user.email, 
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