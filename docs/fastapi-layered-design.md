# FastAPI Layered Architecture - Design Document

## 📋 Mục Lục
1. [Giới Thiệu](#giới-thiệu)
2. [Tổng Quan Kiến Trúc](#tổng-quan-kiến-trúc)
3. [Chi Tiết Từng Lớp](#chi-tiết-từng-lớp)
4. [Cấu Trúc Thư Mục](#cấu-trúc-thư-mục)
5. [Mô Tả Từng File](#mô-tả-từng-file)
6. [Luồng Dữ Liệu](#luồng-dữ-liệu)
7. [Ví Dụ Cụ Thể](#ví-dụ-cụ-thể)

---

## 🎯 Giới Thiệu

**Layered Architecture** (Kiến trúc Phân Lớp) là mô hình thiết kế phần mềm chia ứng dụng thành các lớp ngang hàng, mỗi lớp có trách nhiệm riêng:

- **Presentation Layer** (API Layer): Tiếp nhận request từ client
- **API Router Layer**: Định tuyến và validation
- **Service Layer** (Business Logic): Xử lý logic kinh doanh
- **Data Access Layer** (Repository/DAO): Giao tiếp với cơ sở dữ liệu
- **Database Layer**: Lưu trữ dữ liệu

### Lợi Ích:
✅ Dễ bảo trì và test  
✅ Tách biệt trách nhiệm (Separation of Concerns)  
✅ Dễ mở rộng (Scalable)  
✅ Code tái sử dụng  
✅ Dễ collaboration giữa các team  

---

## 🏗️ Tổng Quan Kiến Trúc

```
┌─────────────────────────────────────────────────────┐
│         CLIENT (Web Browser / Mobile App)           │
└────────────────────┬────────────────────────────────┘
                     │ HTTP Request/Response
                     ▼
┌─────────────────────────────────────────────────────┐
│      PRESENTATION LAYER (FastAPI, Endpoints)        │
│  • Nhận request từ client                          │
│  • Validate input                                   │
│  • Return response (JSON)                          │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│      ROUTER/API LAYER (APIRouter, DTOs)             │
│  • Định tuyến request                              │
│  • Dependency Injection                            │
│  • Request/Response schema validation              │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│    SERVICE LAYER (Business Logic Layer)             │
│  • Xử lý logic kinh doanh                          │
│  • Tính toán, validate business rules              │
│  • Orchestrate multiple operations                 │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  DATA ACCESS LAYER (Repository Pattern)             │
│  • CRUD operations                                  │
│  • Query database                                   │
│  • Data transformation (ORM ↔ Models)              │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│          DATABASE LAYER (PostgreSQL, etc)           │
│  • Persistent data storage                         │
│  • Data integrity constraints                      │
└─────────────────────────────────────────────────────┘
```

---

## 📦 Chi Tiết Từng Lớp

### 1. **Presentation/API Layer (API Endpoint)**
**File:** `api/v1/endpoints/*.py`  
**Trách nhiệm:**
- Tiếp nhận HTTP requests
- Gọi service layer để xử lý
- Format response (JSON)
- Handle exceptions và return appropriate status codes

**Ví dụ:**
```python
@router.get("/users/{user_id}")
async def get_user(user_id: int, service: UserService = Depends()):
    user = await service.get_user_by_id(user_id)
    return user
```

---

### 2. **Router/API Layer (APIRouter)**
**File:** `api/v1/api.py`  
**Trách nhiệm:**
- Combine tất cả các routers
- Set common prefix, tags, dependencies

**Ví dụ:**
```python
from fastapi import APIRouter
from .endpoints import users, items

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
```

---

### 3. **Service Layer (Business Logic)**
**File:** `services/*.py`  
**Trách nhiệm:**
- Xử lý logic kinh doanh phức tạp
- Validate business rules
- Orchestrate calls đến repository
- Transform data
- Handle transactions

**Ví dụ:**
```python
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        # Business logic: check if email already exists
        existing = await self.repo.get_by_email(user_data.email)
        if existing:
            raise BusinessException("Email already registered")
        
        # Hash password
        hashed_pwd = hash_password(user_data.password)
        
        # Save to DB
        user = await self.repo.create({
            **user_data.dict(),
            "password": hashed_pwd
        })
        return UserResponse.from_orm(user)
```

---

### 4. **Data Access Layer (Repository Pattern)**
**File:** `repositories/*.py`  
**Trách nhiệm:**
- CRUD operations
- Query database
- Abstraction của database
- ORM mapping (SQLAlchemy ORM Models → Pydantic Schemas)

**Ví dụ:**
```python
class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    async def get_by_id(self, user_id: int) -> UserModel:
        return self.db.query(UserModel).filter(
            UserModel.id == user_id
        ).first()
    
    async def create(self, user_data: dict) -> UserModel:
        user = UserModel(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    async def update(self, user_id: int, data: dict) -> UserModel:
        user = self.get_by_id(user_id)
        for key, value in data.items():
            setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user
```

---

### 5. **Schema Layer (Pydantic Models)**
**File:** `schemas/*.py`  
**Trách nhiệm:**
- Define request/response models
- Input validation
- API documentation (OpenAPI)
- Data serialization

**Ví dụ:**
```python
class UserBase(BaseModel):
    email: str
    first_name: str
    last_name: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True  # Support ORM model conversion
```

---

### 6. **Model Layer (Database Models)**
**File:** `models/*.py`  
**Trách nhiệm:**
- Define database table structure (SQLAlchemy)
- Database constraints
- Relationships

**Ví dụ:**
```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class UserModel(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

### 7. **Core/Config Layer**
**File:** `core/*.py`  
**Trách nhiệm:**
- Environment variables
- Settings/Configuration
- Security (JWT, passwords)
- Constants

**Ví dụ:**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "My FastAPI App"
    DATABASE_URL: str = "postgresql://user:password@localhost/dbname"
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

### 8. **Database Layer**
**File:** `db/database.py`  
**Trách nhiệm:**
- Database connection setup
- Session management
- Connection pooling

**Ví dụ:**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=True  # Log SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 📁 Cấu Trúc Thư Mục

```
my_fastapi_project/
│
├── app/                                    # Main application package
│   ├── __init__.py
│   ├── main.py                            # Entry point - create FastAPI instance
│   │
│   ├── api/                               # API routes layer
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── api.py                     # Combine all routers
│   │       └── endpoints/                 # Endpoint definitions
│   │           ├── __init__.py
│   │           ├── users.py               # User endpoints
│   │           ├── items.py               # Item endpoints
│   │           └── auth.py                # Auth endpoints
│   │
│   ├── core/                              # Core config & settings
│   │   ├── __init__.py
│   │   ├── config.py                      # Settings (env variables)
│   │   ├── security.py                    # JWT, password hashing
│   │   └── constants.py                   # Constants
│   │
│   ├── db/                                # Database layer
│   │   ├── __init__.py
│   │   ├── database.py                    # Database connection setup
│   │   └── session.py                     # Session dependency
│   │
│   ├── models/                            # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── item.py
│   │
│   ├── schemas/                           # Pydantic models (DTOs)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── item.py
│   │   └── common.py                      # Common schemas
│   │
│   ├── services/                          # Business logic layer
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   └── item_service.py
│   │
│   ├── repositories/                      # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py                        # Base repository
│   │   ├── user_repository.py
│   │   └── item_repository.py
│   │
│   ├── dependencies.py                    # Shared dependencies
│   │
│   └── utils/                             # Utility functions
│       ├── __init__.py
│       ├── validators.py
│       └── helpers.py
│
├── tests/                                  # Tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_users.py
│   └── test_items.py
│
├── .env                                    # Environment variables
├── .gitignore
├── requirements.txt                       # Dependencies
├── docker-compose.yml                     # Local development
└── README.md
```

---

## 📄 Mô Tả Chi Tiết Từng File

### `app/main.py` - Entry Point
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.db.database import engine
from app.models import user, item

# Create tables
user.Base.metadata.create_all(bind=engine)
item.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

---

### `app/api/v1/api.py` - Router Aggregator
```python
from fastapi import APIRouter
from app.api.v1.endpoints import users, items, auth

api_router = APIRouter()

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)
api_router.include_router(
    items.router,
    prefix="/items",
    tags=["items"]
)
```

---

### `app/api/v1/endpoints/users.py` - User Endpoints
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService
from app.db.database import get_db

router = APIRouter()

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db)
):
    service = UserService(db)
    try:
        user = await service.create_user(user_in)
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    service = UserService(db)
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db)
):
    service = UserService(db)
    user = await service.update_user(user_id, user_in)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    service = UserService(db)
    success = await service.delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return None
```

---

### `app/services/user_service.py` - Business Logic
```python
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserUpdate
from app.repositories.user_repository import UserRepository
from app.core.security import hash_password

class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)
    
    async def create_user(self, user_data: UserCreate):
        # Business logic: check if email already exists
        existing = await self.repo.get_by_email(user_data.email)
        if existing:
            raise ValueError("Email already registered")
        
        # Hash password
        hashed_password = hash_password(user_data.password)
        
        # Create user
        db_user = await self.repo.create({
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "password": hashed_password
        })
        return db_user
    
    async def get_user_by_id(self, user_id: int):
        return await self.repo.get_by_id(user_id)
    
    async def get_user_by_email(self, email: str):
        return await self.repo.get_by_email(email)
    
    async def update_user(self, user_id: int, user_data: UserUpdate):
        update_data = user_data.dict(exclude_unset=True)
        return await self.repo.update(user_id, update_data)
    
    async def delete_user(self, user_id: int):
        return await self.repo.delete(user_id)
```

---

### `app/repositories/user_repository.py` - Data Access
```python
from sqlalchemy.orm import Session
from app.models.user import UserModel

class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    async def get_by_id(self, user_id: int) -> UserModel:
        return self.db.query(UserModel).filter(
            UserModel.id == user_id
        ).first()
    
    async def get_by_email(self, email: str) -> UserModel:
        return self.db.query(UserModel).filter(
            UserModel.email == email
        ).first()
    
    async def create(self, user_data: dict) -> UserModel:
        user = UserModel(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    async def update(self, user_id: int, update_data: dict) -> UserModel:
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        for key, value in update_data.items():
            setattr(user, key, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    async def delete(self, user_id: int) -> bool:
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        self.db.delete(user)
        self.db.commit()
        return True
```

---

### `app/models/user.py` - Database Model
```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class UserModel(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

### `app/schemas/user.py` - Pydantic Models
```python
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: EmailStr = None
    first_name: str = None
    last_name: str = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
```

---

## 🔄 Luồng Dữ Liệu (Data Flow)

### Ví dụ: Tạo User Mới

```
1. CLIENT
   ├─ POST /api/v1/users
   └─ Body: {"email": "user@example.com", "first_name": "John", ...}

2. ENDPOINT (app/api/v1/endpoints/users.py)
   ├─ Receive request
   ├─ FastAPI validates UserCreate schema
   └─ Call UserService.create_user()

3. SERVICE (app/services/user_service.py)
   ├─ Check business rules (email duplicate check)
   ├─ Hash password
   └─ Call UserRepository.create()

4. REPOSITORY (app/repositories/user_repository.py)
   ├─ Create UserModel instance
   ├─ db.add(user)
   ├─ db.commit()
   └─ Return UserModel

5. SERVICE → Return UserModel

6. ENDPOINT
   ├─ Convert UserModel to UserResponse (Pydantic)
   └─ Return JSON response

7. CLIENT
   └─ Receive {"id": 1, "email": "user@example.com", ...}
```

---

## 💡 Ví Dụ Cụ Thể: Complete User CRUD Flow

### Step 1: Create User
```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "password": "securepassword123"
  }'
```

**Response:**
```json
{
  "id": 1,
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

### Step 2: Get User
```bash
curl -X GET http://localhost:8000/api/v1/users/1
```

### Step 3: Update User
```bash
curl -X PUT http://localhost:8000/api/v1/users/1 \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jonathan"
  }'
```

### Step 4: Delete User
```bash
curl -X DELETE http://localhost:8000/api/v1/users/1
```

---

## 🧪 Testing Example

```python
# tests/test_users.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_user():
    response = client.post(
        "/api/v1/users",
        json={
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "password": "password123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_get_user():
    # First create user
    response = client.post(...)
    user_id = response.json()["id"]
    
    # Then get it
    response = client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["id"] == user_id
```

---

## 🔐 Best Practices

| Praktik | Penjelasan |
|---------|-----------|
| **Single Responsibility** | Setiap class/function punya 1 tanggung jawab |
| **Dependency Injection** | Inject dependencies melalui constructor/function params |
| **No Logic in Endpoints** | Endpoints hanya route, service handle logic |
| **Repository Pattern** | Abstrak database access, mudah ganti DB |
| **Schema Validation** | Gunakan Pydantic untuk validate input/output |
| **Error Handling** | Handle exceptions di service, return meaningful errors |
| **Type Hints** | Selalu gunakan type hints untuk clarity |
| **Async/Await** | Gunakan untuk I/O operations (DB, API calls) |
| **Environment Variables** | Config via .env, bukan hardcoded |
| **Logging** | Log penting events untuk debugging |

---

## 📚 Dependency Injection Pattern

```python
# app/dependencies.py
from sqlalchemy.orm import Session
from fastapi import Depends
from app.db.database import get_db
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)

# Usage di endpoint
@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    return await service.get_user_by_id(user_id)
```

---

## 🚀 Deployment Checklist

- [ ] Database migrations setup (Alembic)
- [ ] Environment variables configured
- [ ] Security: JWT tokens, password hashing
- [ ] Logging configured
- [ ] Error handling & validation
- [ ] CORS properly configured
- [ ] Rate limiting added
- [ ] Database connection pooling
- [ ] Tests passing
- [ ] Docker image built
- [ ] Health check endpoint working

---

## 📖 Summary

Layered Architecture untuk FastAPI:

1. **Presentation**: Handle HTTP requests
2. **Router**: Route requests to endpoints
3. **Service**: Business logic & orchestration
4. **Repository**: Data access abstraction
5. **Model**: Database structure
6. **Schema**: Data validation & serialization

Setiap layer hanya berkomunikasi dengan layer dibawahnya, tidak langsung ke DB atau client.

Ini membuat code **maintainable, testable, dan scalable**! 🎯
