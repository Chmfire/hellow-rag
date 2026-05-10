# -*- coding: utf-8 -*-
"""
认证 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.requests import LoginRequest, RegisterRequest
from app.models.responses import AuthResponse, CurrentUserResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    resolve_role,
    get_current_user,
)
from app.db.user_repository import get_user_repository, UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    用户注册
    """
    username = (request.username or "").strip()
    password = (request.password or "").strip()

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名和密码不能为空",
        )

    # 检查用户名是否已存在
    existing_user = user_repo.get_by_username(username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    # 解析角色
    role = resolve_role(request.role, request.admin_code)

    # 创建用户
    user = user_repo.create(
        username=username,
        password_hash=get_password_hash(password),
        role=role,
    )

    # 生成访问令牌
    access_token = create_access_token(username=user["username"], role=user["role"])

    return AuthResponse(
        access_token=access_token,
        username=user["username"],
        role=user["role"],
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    用户登录
    """
    user = authenticate_user(request.username, request.password, user_repo)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(username=user["username"], role=user["role"])

    return AuthResponse(
        access_token=access_token,
        username=user["username"],
        role=user["role"],
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
):
    """
    获取当前登录用户信息
    """
    return CurrentUserResponse(
        username=current_user["username"],
        role=current_user["role"],
    )
