from fastapi import APIRouter
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
import models, schemas, database
import core.security as security

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
)

# get all user
@router.get("/", response_model=list[schemas.UserResponse])
def read_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_user)
):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@router.get("/me/", response_model=schemas.UserResponse)
async def read_users_me(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db)
):
    # current_user từ dependency thường chưa join bảng events (lazy load).
    # Để tối ưu (tránh N+1 khi Pydantic serialize field 'events'), ta query lại với joinedload.
    # Hoặc đơn giản là trả về current_user nếu lazy load là chấp nhận được (với SQLite/ít data).
    # Dưới đây là cách query tối ưu:
    
    user_with_events = db.query(models.User)\
        .options(joinedload(models.User.events))\
        .filter(models.User.user_id == current_user.user_id)\
        .first()
        
    return user_with_events

@router.put("/change-password/", status_code=200)
async def change_password(
    password_data: schemas.ChangePasswordRequest,
    current_user: Annotated[models.User, Depends(security.get_current_user)],
    db: Session = Depends(database.get_db)
):
    # 1. Kiểm tra mật khẩu hiện tại
    if not security.verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    # 2. Cập nhật mật khẩu mới
    current_user.hashed_password = security.get_password_hash(password_data.new_password)
    db.add(current_user)
    db.commit()
    
    return {"message": "Password changed successfully"}