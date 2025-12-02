from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import database, models, schemas
import helpers.security as security 
from datetime import datetime
import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def now_vn():
    return datetime.now(VN_TZ)

# Tạo Router riêng, prefix là /admin
# dependencies=[Depends(auth.get_current_admin_user)] đảm bảo TẤT CẢ các API trong này đều bắt buộc quyền Admin
router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Management"],
    dependencies=[Depends(security.get_current_admin_from_cookie)]
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
    # Thêm filter(models.User.is_deleted == False)
    users = db.query(models.User).filter(models.User.is_deleted == False).offset(skip).limit(limit).all()
    return users

# 2. Admin tạo User mới (Set được Role & Status luôn)
@router.post("/users", response_model=schemas.UserResponse)
def create_user_by_admin(
    user: schemas.UserCreateAdmin, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
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
        status=user.status, # Admin set true/false tùy ý
        created_by=current_user.user_id
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
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    
    user_to_edit = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user_to_edit:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 1. LOGIC CHẶN TỰ HẠ QUYỀN (Self-Role Modification)
    # Nếu đang sửa chính mình VÀ cố tình đổi role khác role hiện tại
    if current_user.user_id == user_to_edit.user_id:
        if 'role' in update_data:
            # Cách 2: Softcore (Khuyên dùng) - Chỉ cần xóa key role đi, update các cái khác bình thường
            del update_data['role']

    # 2. LOGIC BẢO VỆ NGƯỜI TẠO (Creator Protection)
    # Nếu user đang bị sửa là người đã tạo ra current_user (người cha)
    if current_user.created_by == user_to_edit.user_id:
        raise HTTPException(
            status_code=403,
            detail="Bạn không được phép chỉnh sửa tài khoản của người đã cấp quyền cho bạn."
        )
        
    # Update dynamic: Chỉ update những trường user gửi lên (khác None)
    update_data = user_update.model_dump(exclude_unset=True) # Pydantic v2 dùng model_dump, v1 dùng dict(exclude_unset=True)
    # Nếu bạn dùng Pydantic v1 cũ thì dùng: update_data = user_update.dict(exclude_unset=True)

    for key, value in update_data.items():
        setattr(user_to_edit, key, value)
    
    db.commit()
    db.refresh(user_to_edit)
    return user_to_edit

# 4. Admin xóa User
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    user_to_delete = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")
     
    # Kiểm tra tồn tại và chưa bị xóa
    if not user_to_delete or user_to_delete.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")
     
    # Không cho phép tự xóa chính mình
    if user_to_delete.user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Không thể xóa tài khoản đang đăng nhập")
    
    # 2. LOGIC BẢO VỆ NGƯỜI TẠO
    # Nếu user bị xóa là người đã tạo ra current_user
    if current_user.created_by == user_to_delete.user_id:
        raise HTTPException(
            status_code=403, 
            detail="Bạn không được phép xóa tài khoản của người đã tạo ra bạn."
        )

    # [THAY ĐỔI] Thay vì db.delete(), ta update trạng thái
    user_to_delete.is_deleted = True
    user_to_delete.email += str(now_vn())
    user_to_delete.phone += str(now_vn())
    user_to_delete.status = False # Tắt kích hoạt luôn để không đăng nhập được
    
    db.commit()
    
    return