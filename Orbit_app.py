from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import datetime
import hashlib
import secrets
import os

# =========================================================
# 1. セキュリティ：パスワード暗号化の仕組み
# =========================================================
def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(8)
    key = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    )
    return f"{salt}:{key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, key = hashed_password.split(':')
        new_key = hashlib.pbkdf2_hmac(
            'sha256', 
            plain_password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        )
        return new_key.hex() == key
    except Exception:
        return False

# =========================================================
# 2. データベースの初期設定
# =========================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./orbit.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)
Base = declarative_base()

# =========================================================
# 3. データベースのテーブル設計
# =========================================================
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    is_admin = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)

class BoardDB(Base):
    __tablename__ = "boards"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)

class ColumnDB(Base):
    __tablename__ = "columns"
    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, index=True)
    title = Column(String, index=True)
    color = Column(String, default="#0b0d22")
    order_idx = Column(Integer, default=0)

class TaskDB(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, index=True)
    title = Column(String, index=True)
    column_id = Column(Integer)
    description = Column(String, default="")
    is_archived = Column(Boolean, default=False)
    due_date = Column(String, default="")
    order_idx = Column(Integer, default=0)

class ChecklistItemDB(Base):
    __tablename__ = "checklist_items"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True)
    title = Column(String)
    is_checked = Column(Boolean, default=False)

class CommentDB(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True)
    content = Column(String)
    author = Column(String, default="Unknown")
    created_at = Column(DateTime, default=datetime.now)

Base.metadata.create_all(bind=engine)

try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN order_idx INTEGER DEFAULT 0"))
except Exception:
    pass

app = FastAPI()

# =========================================================
# 4. データの受け渡し用ルール
# =========================================================
class UserAuth(BaseModel):
    username: str
    password: str

class AdminToggle(BaseModel):
    is_admin: bool

class ApprovalToggle(BaseModel):
    is_approved: bool

class PasswordReset(BaseModel):
    new_password: str

# ★追加：ユーザー自身によるパスワード変更用
class SelfPasswordChange(BaseModel):
    username: str
    current_password: str
    new_password: str

class BoardCreate(BaseModel):
    title: str

class BoardUpdate(BaseModel):
    title: str

class ColumnCreate(BaseModel):
    board_id: int
    title: str

class ColumnUpdate(BaseModel):
    title: Optional[str] = None
    color: Optional[str] = None
    order_idx: Optional[int] = None

class ColumnOrderUpdate(BaseModel):
    id: int
    order_idx: int

class TaskCreate(BaseModel):
    board_id: int
    column_id: int
    title: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    column_id: Optional[int] = None
    description: Optional[str] = None
    is_archived: Optional[bool] = None
    due_date: Optional[str] = None

class TaskOrderUpdate(BaseModel):
    id: int
    order_idx: int
    column_id: int

class ChecklistItemCreate(BaseModel):
    title: str

class ChecklistItemUpdate(BaseModel):
    is_checked: bool

class CommentCreate(BaseModel):
    content: str
    author: str

class CommentUpdate(BaseModel):
    content: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================================================
# 5. APIエンドポイント
# =========================================================
@app.get("/")
def read_root():
    return FileResponse("index.html")

# --- 認証 & ユーザー管理 ---
@app.post("/api/register")
def register_user(user: UserAuth, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.username == user.username).first()
    
    if existing:
        return {"error": "このユーザー名は既に使われています"}
    
    is_first_user = db.query(UserDB).count() == 0
    hashed_pw = get_password_hash(user.password)
    
    new_user = UserDB(
        username=user.username,
        password=hashed_pw,
        is_admin=is_first_user,
        is_approved=is_first_user
    )
    
    db.add(new_user)
    db.commit()
    
    if is_first_user:
        default_board = BoardDB(title="ミッション・コントロール")
        db.add(default_board)
        db.commit()
        
    return {
        "message": "Success",
        "is_approved": is_first_user
    }

@app.post("/api/login")
def login_user(user: UserAuth, db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.username == user.username).first()
    
    if not target or not verify_password(user.password, target.password):
        return {"error": "ユーザー名かパスワードが間違っています"}
        
    if not target.is_approved:
        return {"error": "管理者の承認待ちです。"}
        
    return {
        "message": "Success",
        "username": target.username,
        "is_admin": target.is_admin
    }

@app.get("/api/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(UserDB).all()

@app.put("/api/users/{username}/admin")
def toggle_admin(username: str, toggle: AdminToggle, db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.username == username).first()
    if target:
        target.is_admin = toggle.is_admin
        db.commit()
        return {"message": "Success"}
    return {"error": "Not found"}

@app.put("/api/users/{username}/approve")
def toggle_approve(username: str, toggle: ApprovalToggle, db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.username == username).first()
    if target:
        target.is_approved = toggle.is_approved
        db.commit()
        return {"message": "Success"}
    return {"error": "Not found"}

@app.put("/api/users/{username}/password")
def reset_password(username: str, pwd_data: PasswordReset, db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.username == username).first()
    if target:
        target.password = get_password_hash(pwd_data.new_password)
        db.commit()
        return {"message": "Success"}
    return {"error": "Not found"}

# ★追加：自分自身でのパスワード変更
@app.put("/api/users/me/password")
def change_own_password(pwd_data: SelfPasswordChange, db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.username == pwd_data.username).first()
    
    if not target or not verify_password(pwd_data.current_password, target.password):
        return {"error": "現在のパスワードが間違っています"}
        
    target.password = get_password_hash(pwd_data.new_password)
    db.commit()
    return {"message": "Success"}

@app.delete("/api/users/{username}")
def delete_user(username: str, db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.username == username).first()
    if target:
        db.delete(target)
        db.commit()
        return {"message": "Deleted"}
    return {"error": "Not found"}

# --- ボード (Board) ---
@app.get("/api/boards")
def get_boards(db: Session = Depends(get_db)):
    return db.query(BoardDB).all()

@app.post("/api/boards")
def create_board(board: BoardCreate, db: Session = Depends(get_db)):
    new_board = BoardDB(title=board.title)
    db.add(new_board)
    db.commit()
    db.refresh(new_board)
    return new_board

@app.put("/api/boards/{board_id}")
def update_board(board_id: int, board: BoardUpdate, db: Session = Depends(get_db)):
    target = db.query(BoardDB).filter(BoardDB.id == board_id).first()
    if target:
        target.title = board.title
        db.commit()
        return target
    return {"error": "Not found"}

@app.delete("/api/boards/{board_id}")
def delete_board(board_id: int, db: Session = Depends(get_db)):
    target = db.query(BoardDB).filter(BoardDB.id == board_id).first()
    if target:
        db.query(ColumnDB).filter(ColumnDB.board_id == board_id).delete()
        db.query(TaskDB).filter(TaskDB.board_id == board_id).delete()
        db.delete(target)
        db.commit()
        return {"message": "Deleted"}
    return {"error": "Not found"}

# --- 列 (Column) ---
@app.get("/api/boards/{board_id}/columns")
def get_columns(board_id: int, db: Session = Depends(get_db)):
    return db.query(ColumnDB).filter(ColumnDB.board_id == board_id).order_by(ColumnDB.order_idx).all()

@app.post("/api/columns")
def create_column(column: ColumnCreate, db: Session = Depends(get_db)):
    count = db.query(ColumnDB).filter(ColumnDB.board_id == column.board_id).count()
    new_column = ColumnDB(
        board_id=column.board_id, 
        title=column.title,
        order_idx=count
    )
    db.add(new_column)
    db.commit()
    db.refresh(new_column)
    return new_column

@app.put("/api/columns/{column_id}")
def update_column(column_id: int, column: ColumnUpdate, db: Session = Depends(get_db)):
    target = db.query(ColumnDB).filter(ColumnDB.id == column_id).first()
    if target:
        if column.title is not None:
            target.title = column.title
        if column.color is not None:
            target.color = column.color
        db.commit()
        return target
    return {"error": "Not found"}

@app.put("/api/columns/reorder/batch")
def reorder_columns(orders: List[ColumnOrderUpdate], db: Session = Depends(get_db)):
    for order in orders:
        target = db.query(ColumnDB).filter(ColumnDB.id == order.id).first()
        if target:
            target.order_idx = order.order_idx
    db.commit()
    return {"message": "Success"}

@app.delete("/api/columns/{column_id}")
def delete_column(column_id: int, db: Session = Depends(get_db)):
    target = db.query(ColumnDB).filter(ColumnDB.id == column_id).first()
    if target:
        db.delete(target)
        db.commit()
        return {"message": "Deleted"}
    return {"error": "Not found"}

# --- タスク (Task) ---
@app.get("/api/boards/{board_id}/tasks")
def get_tasks(board_id: int, db: Session = Depends(get_db)):
    return db.query(TaskDB).filter(TaskDB.board_id == board_id).order_by(TaskDB.order_idx).all()

@app.post("/api/tasks")
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    count = db.query(TaskDB).filter(TaskDB.column_id == task.column_id).count()
    new_task = TaskDB(
        board_id=task.board_id,
        column_id=task.column_id,
        title=task.title,
        order_idx=count
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@app.put("/api/tasks/{task_id}")
def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)):
    target = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if target:
        if task_update.title is not None:
            target.title = task_update.title
        if task_update.column_id is not None:
            target.column_id = task_update.column_id
        if task_update.description is not None:
            target.description = task_update.description
        if task_update.is_archived is not None:
            target.is_archived = task_update.is_archived
        if task_update.due_date is not None:
            target.due_date = task_update.due_date
        db.commit()
        db.refresh(target)
        return target
    return {"error": "Not found"}

@app.put("/api/tasks/reorder/batch")
def reorder_tasks(orders: List[TaskOrderUpdate], db: Session = Depends(get_db)):
    for order in orders:
        target = db.query(TaskDB).filter(TaskDB.id == order.id).first()
        if target:
            target.order_idx = order.order_idx
            target.column_id = order.column_id
    db.commit()
    return {"message": "Success"}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    target = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if target:
        db.delete(target)
        db.commit()
        return {"message": "Deleted"}
    return {"error": "Not found"}

# --- チェックリスト ---
@app.get("/api/tasks/{task_id}/checklist")
def get_checklist(task_id: int, db: Session = Depends(get_db)):
    return db.query(ChecklistItemDB).filter(ChecklistItemDB.task_id == task_id).all()

@app.post("/api/tasks/{task_id}/checklist")
def create_checklist_item(task_id: int, item: ChecklistItemCreate, db: Session = Depends(get_db)):
    new_item = ChecklistItemDB(
        task_id=task_id, 
        title=item.title
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@app.put("/api/checklist/{item_id}")
def update_checklist_item(item_id: int, item_update: ChecklistItemUpdate, db: Session = Depends(get_db)):
    target = db.query(ChecklistItemDB).filter(ChecklistItemDB.id == item_id).first()
    if target:
        target.is_checked = item_update.is_checked
        db.commit()
        db.refresh(target)
        return target
    return {"error": "Not found"}

@app.delete("/api/checklist/{item_id}")
def delete_checklist_item(item_id: int, db: Session = Depends(get_db)):
    target = db.query(ChecklistItemDB).filter(ChecklistItemDB.id == item_id).first()
    if target:
        db.delete(target)
        db.commit()
        return {"message": "Deleted"}
    return {"error": "Not found"}

# --- コメント ---
@app.get("/api/tasks/{task_id}/comments")
def get_comments(task_id: int, db: Session = Depends(get_db)):
    return db.query(CommentDB).filter(CommentDB.task_id == task_id).all()

@app.post("/api/tasks/{task_id}/comments")
def create_comment(task_id: int, comment: CommentCreate, db: Session = Depends(get_db)):
    new_comment = CommentDB(
        task_id=task_id, 
        content=comment.content, 
        author=comment.author
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

@app.put("/api/comments/{comment_id}")
def update_comment(comment_id: int, comment_update: CommentUpdate, db: Session = Depends(get_db)):
    target = db.query(CommentDB).filter(CommentDB.id == comment_id).first()
    if target:
        target.content = comment_update.content
        db.commit()
        db.refresh(target)
        return target
    return {"error": "Not found"}

@app.delete("/api/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    target = db.query(CommentDB).filter(CommentDB.id == comment_id).first()
    if target:
        db.delete(target)
        db.commit()
        return {"message": "Deleted"}
    return {"error": "Not found"}