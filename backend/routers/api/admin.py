from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import database, models, schemas
import core.security as security 

# Tạo Router riêng, prefix là /admin
# dependencies=[Depends(auth.get_current_admin_user)] đảm bảo TẤT CẢ các API trong này đều bắt buộc quyền Admin
router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Management"],
    dependencies=[Depends(security.get_current_admin_user)] 
)

# xem 1 user chi tiết (Admin)
@router.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user_by_id(user_id: int, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 1. Lấy danh sách tất cả Users
@router.get("/users", response_model=List[schemas.UserResponse])
def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(database.get_db)
):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

# 2. Admin tạo User mới (Set được Role & Status luôn)
@router.post("/users", response_model=schemas.UserResponse)
def create_user_by_admin(
    user: schemas.UserCreateAdmin, 
    db: Session = Depends(database.get_db)
):
    # Check email trùng
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user = models.User(
        email=user.email,
        hashed_password=security.get_password_hash(user.password),
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        status=user.status # Admin set true/false tùy ý
    )
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating user: " + str(e))

    return db_user

# 3. Admin cập nhật thông tin User (VD: Đổi quyền, Khóa tài khoản)
@router.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user_by_admin(
    user_id: int, 
    user_update: schemas.UserUpdateAdmin, 
    db: Session = Depends(database.get_db)
):
    db_user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update dynamic: Chỉ update những trường user gửi lên (khác None)
    update_data = user_update.model_dump(exclude_unset=True) # Pydantic v2 dùng model_dump, v1 dùng dict(exclude_unset=True)
    # Nếu bạn dùng Pydantic v1 cũ thì dùng: update_data = user_update.dict(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

# 4. Admin xóa User
@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    return {"detail": "User deleted successfully"}