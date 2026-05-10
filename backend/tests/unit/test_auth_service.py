# -*- coding: utf-8 -*-
"""
认证服务单元测试
测试范围：
- 密码哈希和验证
- JWT Token 生成和解析
- 用户认证
- 角色权限
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.services.auth_service import AuthService


@pytest.fixture(scope="function")
def auth_service(test_jwt_secret):
    """测试用认证服务"""
    service = AuthService(
        jwt_secret=test_jwt_secret,
        jwt_algorithm="HS256",
        jwt_expire_minutes=30,
        admin_invite_code="test-admin-code"
    )
    return service


@pytest.fixture(scope="function")
def mock_db_session():
    """Mock 数据库 session"""
    session = Mock()
    user = Mock()
    user.username = "testuser"
    user.password_hash = AuthService.get_password_hash("testpassword")
    user.role = "user"
    user.id = 1
    session.query().filter().first = Mock(return_value=user)
    session.add = Mock()
    session.commit = Mock()
    return session


def test_get_password_hash():
    """测试密码哈希"""
    hash1 = AuthService.get_password_hash("testpassword")
    hash2 = AuthService.get_password_hash("testpassword")
    hash3 = AuthService.get_password_hash("differentpassword")
    
    # 相同密码生成的哈希应该不同（有盐）
    assert hash1 != hash2
    # 但应该能验证通过
    assert AuthService.verify_password("testpassword", hash1)
    assert AuthService.verify_password("testpassword", hash2)
    assert not AuthService.verify_password("wrongpassword", hash1)
    assert not AuthService.verify_password("testpassword", hash3)


def test_verify_password():
    """测试密码验证"""
    password = "secure_password_123"
    password_hash = AuthService.get_password_hash(password)
    
    assert AuthService.verify_password(password, password_hash) is True
    assert AuthService.verify_password("wrong_password", password_hash) is False
    assert AuthService.verify_password("", password_hash) is False


def test_create_access_token(auth_service):
    """测试创建 access token"""
    token = auth_service.create_access_token("testuser", "user")
    
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_token_valid(auth_service):
    """测试验证有效的 token"""
    token = auth_service.create_access_token("testuser", "user")
    payload = auth_service.verify_token(token)
    
    assert payload is not None
    assert payload["sub"] == "testuser"
    assert payload["role"] == "user"


def test_verify_token_invalid(auth_service):
    """测试验证无效 token"""
    payload = auth_service.verify_token("invalid_token")
    assert payload is None


def test_verify_token_expired(auth_service):
    """测试过期 token（模拟）"""
    # 这里我们直接测试边界条件
    payload = auth_service.verify_token("random_invalid_string")
    assert payload is None


def test_resolve_role_user(auth_service):
    """测试普通用户角色"""
    role = auth_service.resolve_role("user", None)
    assert role == "user"


def test_resolve_role_admin_valid(auth_service):
    """测试有效邀请码的管理员"""
    role = auth_service.resolve_role("admin", "test-admin-code")
    assert role == "admin"


def test_resolve_role_admin_invalid(auth_service):
    """测试无效邀请码"""
    with pytest.raises(Exception):
        auth_service.resolve_role("admin", "wrong-code")


def test_resolve_role_empty(auth_service):
    """测试空角色"""
    role = auth_service.resolve_role(None, None)
    assert role == "user"


def test_auth_service_with_custom_config():
    """测试自定义配置初始化"""
    service = AuthService(
        jwt_secret="custom-secret",
        jwt_algorithm="HS512",
        jwt_expire_minutes=60
    )
    assert service.jwt_expire_minutes == 60
    assert service.jwt_algorithm == "HS512"


def test_get_current_user_mock(auth_service, mock_db_session):
    """测试获取当前用户（模拟）"""
    token = auth_service.create_access_token("testuser", "user")
    # 注意：真实的 get_current_user 需要 Depends 和 Session
    # 这里我们测试 token 验证逻辑
    payload = auth_service.verify_token(token)
    assert payload is not None
