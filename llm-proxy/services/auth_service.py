"""
认证服务
"""

from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

from models.user import User
from repositories.user_repo import UserRepository
from services.email_service import EmailService
from services.apikey_service import ApiKeyService
from core.security import hash_password, verify_password, create_session_id
from core.verifier import validate_email, validate_password_strength, validate_username
from core.limiter import rate_limiter
from app.config import settings
from log.logger import get_logger
from utils.redis_client import RedisClient

logger = get_logger(__name__)
redis_client = RedisClient()


class AuthService:
    """认证服务"""

    def __init__(self):
        self.user_repo = UserRepository()
        self.email_service = EmailService()
        self.apikey_service = ApiKeyService()

    def send_register_code(self, email: str, db: Session) -> Tuple[bool, str]:
        """
        发送注册验证码
        检查: 邮箱是否已注册、请求频率限制
        """
        # 检查邮箱格式
        if not validate_email(email):
            return False, "邮箱格式错误"

        # 检查请求频率
        allowed, _ = rate_limiter.check_rate_limit(
            "verify", email, settings.rate_limit.verify_code_per_minute, 60
        )
        if not allowed:
            return False, "验证码发送过于频繁，请稍后再试"

        # 检查邮箱是否已注册
        if self.user_repo.get_by_email(email, db):
            return False, "邮箱已注册"

        # 生成并发送验证码
        from utils.token import generate_verify_code
        code = generate_verify_code()

        # 将验证码存入 Redis
        redis_client.set_verify_code(email, code)

        if not self.email_service.send_verify_code(email, code):
            return False, "验证码发送失败"

        rate_limiter.increment("verify", email, 60)
        return True, "验证码已发送"

    def register(
        self, email: str, code: str, username: str, password: str, db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        用户注册
        1. 验证验证码
        2. 验证密码强度
        3. 创建用户
        4. 创建Session
        5. 设置Cookie
        """
        # 验证验证码
        valid, msg = redis_client.verify_code(email, code)
        if not valid:
            return False, msg, {}

        # 验证密码强度
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            return False, error_msg, {}

        # 验证用户名
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            return False, error_msg, {}

        # 创建用户
        password_hash = hash_password(password)
        user = self.user_repo.create(
            email=email,
            username=username,
            password_hash=password_hash,
            db=db,
        )

        # 创建 Session
        session_id = create_session_id()
        # 将 Session 存入 Redis
        redis_client.set_session(session_id, user.id)

        return True, "注册成功", {
            "user_id": user.id,
            "session_id": session_id,
        }

    def login(self, identifier: str, password: str, db: Session) -> Tuple[bool, str, Optional[User]]:
        """
        用户登录
        1. 验证账号密码
        2. 检查登录错误次数
        3. 创建Session
        4. 设置Cookie
        """
        # 检查登录错误次数
        allowed, remaining = rate_limiter.check_rate_limit(
            "login_fail", identifier, settings.rate_limit.login_max_attempts, 900
        )
        if not allowed:
            return False, f"登录失败次数过多，请{settings.rate_limit.login_lockout_minutes}分钟后重试", None

        # 查找用户
        user = self.user_repo.get_by_email(identifier, db) or self.user_repo.get_by_username(identifier, db)
        if not user:
            rate_limiter.increment("login_fail", identifier, 900)
            return False, "账号或密码错误", None

        # 验证密码
        if not verify_password(password, user.password_hash):
            rate_limiter.increment("login_fail", identifier, 900)
            return False, "账号或密码错误", None

        # 重置登录错误次数
        rate_limiter.reset("login_fail", identifier)

        # 创建 Session
        session_id = create_session_id()
        # 将 Session 存入 Redis
        redis_client.set_session(session_id, user.id)

        user.session_id = session_id
        return True, "登录成功", user

    def logout(self, session_id: str) -> bool:
        """
        退出登录
        1. 删除Session
        2. 清除Cookie
        """
        # 从 Redis 删除 Session
        redis_client.delete_session(session_id)
        return True

    def delete_account(
        self, user_id: int, email: str, code: str, password: str, db: Session
    ) -> Tuple[bool, str]:
        """
        注销账户
        1. 验证验证码和密码
        2. 软删除用户
        3. 删除所有Session
        4. 发送通知邮件
        """
        # 验证验证码
        valid, msg = redis_client.verify_code(email, code)
        if not valid:
            return False, msg

        # 获取用户
        user = self.user_repo.get_by_id(user_id, db)
        if not user:
            return False, "用户不存在"

        # 验证密码
        if not verify_password(password, user.password_hash):
            return False, "密码错误"

        # 软删除用户
        self.user_repo.soft_delete(user_id, db)

        # 删除所有 Session
        redis_client.delete_user_sessions(user_id)

        # 发送通知邮件
        self.email_service.send_account_deleted_notice(email)

        return True, "账户已注销"

    def validate_session(self, session_id: str, db: Session) -> Optional[User]:
        """
        验证Session有效性
        有效则自动续期
        """
        # 从 Redis 获取 Session
        session_data = redis_client.get_session(session_id)
        if not session_data:
            return None

        user_id = session_data.get("user_id")
        if not user_id:
            return None

        # 获取用户信息
        user = self.user_repo.get_by_id(user_id, db)
        if not user:
            return None

        # 续期 Session
        redis_client.refresh_session(session_id)

        user.session_id = session_id
        return user

    def refresh_session(self, session_id: str) -> bool:
        """
        刷新Session有效期 (续期1天)
        """
        # 刷新 Redis 中的 Session TTL
        return redis_client.refresh_session(session_id)
