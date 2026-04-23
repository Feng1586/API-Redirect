"""
邮件服务
"""

from typing import Optional

import resend

from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """邮件服务"""

    def __init__(self):
        self.resend = resend
        self.resend.api_key = settings.email.resend_api_key
        self.from_email = settings.email.from_email
        self.from_name = settings.email.from_name

    def send_verify_code(self, to_email: str, code: str) -> bool:
        """
        发送验证码邮件
        邮件格式:
        标题: [LLM Proxy] 您的注册验证码
        内容: 尊敬的用户，您的验证码是：XXXXXX，5分钟内有效。
        """
        try:
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": "[LLM Proxy] 您的注册验证码",
                "html": f"尊敬的用户，您的验证码是：<b>{code}</b>，5分钟内有效。",
            }
            self.resend.Emails.send(params)
            return True
        except Exception as e:
            logger.error(f"发送验证码邮件失败: {e}")
            return False

    def send_account_deleted_notice(self, to_email: str) -> bool:
        """
        发送账户注销通知
        """
        try:
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": "[LLM Proxy] 账户注销通知",
                "html": "您的账户已成功注销。如有疑问，请联系客服。",
            }
            self.resend.Emails.send(params)
            return True
        except Exception as e:
            logger.error(f"发送注销通知失败: {e}")
            return False

    def send_low_balance_warning(self, to_email: str, balance: float) -> bool:
        """
        发送余额不足警告
        """
        try:
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": "[LLM Proxy] 余额不足警告",
                "html": f"您的账户余额已不足，当前余额：{balance}元。请及时充值。",
            }
            self.resend.Emails.send(params)
            return True
        except Exception as e:
            logger.error(f"发送余额警告失败: {e}")
            return False
