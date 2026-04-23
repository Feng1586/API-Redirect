"""
PayPal 支付服务
封装与 PayPal REST API 的交互（OAuth 认证、创建订单、捕获订单）
"""

import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


class PayPalService:
    """PayPal 支付服务"""

    def __init__(self):
        self.base_url = settings.paypal.paypal_base_url.rstrip("/")
        self.client_id = settings.paypal.client_id
        self.client_secret = settings.paypal.client_secret
        self.proxy = settings.paypal.proxy
        self._access_token: Optional[str] = None

    def _build_client(self, timeout: int = 30) -> httpx.AsyncClient:
        """
        创建 httpx 客户端，自动处理代理配置

        代理优先级:
        1. config.yaml 中的 paypal.proxy 配置
        2. 环境变量 HTTP_PROXY / HTTPS_PROXY
        3. 无代理（直连）
        """
        client_kwargs = {"timeout": timeout}

        # 1. 优先使用配置文件的代理
        if self.proxy:
            client_kwargs["proxy"] = self.proxy
            logger.info(f"使用配置文件代理: {self.proxy}")
        else:
            # 2. 其次检查环境变量
            env_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
            if env_proxy:
                client_kwargs["proxy"] = env_proxy
                logger.info(f"使用环境变量代理: {env_proxy}")

        return httpx.AsyncClient(**client_kwargs)

    # ==================== OAuth 2.0 ====================

    async def get_access_token(self) -> Tuple[bool, str, Optional[str]]:
        """
        获取 OAuth 2.0 Access Token
        使用 Client Credentials 模式

        Returns:
            (success, message, access_token)
        """
        url = f"{self.base_url}/v1/oauth2/token"

        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }

        data = {"grant_type": "client_credentials"}

        try:
            async with self._build_client() as client:
                response = await client.post(
                    url,
                    auth=(self.client_id, self.client_secret),
                    headers=headers,
                    data=data,
                )

                if response.status_code == 200:
                    result = response.json()
                    token = result.get("access_token")
                    self._access_token = token
                    logger.info("PayPal OAuth 获取成功")
                    return True, "获取成功", token
                else:
                    error_msg = f"获取失败: HTTP {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return False, error_msg, None

        except httpx.RequestError as e:
            error_msg = f"请求异常: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    async def _ensure_token(self) -> Tuple[bool, str]:
        """确保有可用的 Access Token"""
        if self._access_token:
            return True, ""

        success, msg, token = await self.get_access_token()
        if not success:
            return False, msg
        return True, ""

    # ==================== 创建订单 ====================

    async def create_order(
        self,
        amount: str,
        currency: str = "USD",
        custom_id: str = "",
        return_url: str = "",
        cancel_url: str = "",
        description: str = "AI API 充值",
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        创建 PayPal 订单（intent=CAPTURE，直接扣款模式）

        Args:
            amount: 金额，如 "10.00"
            currency: 币种，默认 USD
            custom_id: 自定义ID（可用于关联本地订单号）
            return_url: 支付成功后的跳转 URL
            cancel_url: 取消支付后的跳转 URL
            description: 订单描述

        Returns:
            (success, message, order_data)
            order_data 包含: id, status, approve_url 等
        """
        # 1. 确保有 Token
        ok, err = await self._ensure_token()
        if not ok:
            return False, err, None

        # 2. 构建请求体
        purchase_unit = {
            "amount": {
                "currency_code": currency.upper(),
                "value": amount,
            },
            "description": description,
        }
        if custom_id:
            purchase_unit["custom_id"] = custom_id

        order_request = {
            "intent": "CAPTURE",
            "purchase_units": [purchase_unit],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                        "landing_page": "LOGIN",
                        "user_action": "PAY_NOW",
                        "return_url": return_url or "https://example.com/success",
                        "cancel_url": cancel_url or "https://example.com/cancel",
                    }
                }
            },
        }

        # 3. 发送请求
        url = f"{self.base_url}/v2/checkout/orders"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
            "PayPal-Request-Id": f"ORDER-{custom_id or amount}-{__import__('uuid').uuid4().hex[:8]}",
        }

        try:
            async with self._build_client() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=order_request,
                )

                result = response.json()
                logger.info(f"PayPal 创建订单响应: {response.status_code}")

                if response.status_code in (200, 201):
                    # 提取 approve URL
                    approve_url = ""
                    for link in result.get("links", []):
                        if link.get("rel") == "payer-action":
                            approve_url = link.get("href", "")
                            break
                        if link.get("rel") == "approve":
                            approve_url = link.get("href", "")
                            break

                    order_data = {
                        "paypal_order_id": result.get("id", ""),
                        "status": result.get("status", ""),
                        "approve_url": approve_url,
                        "raw_response": result,
                    }
                    return True, "订单创建成功", order_data
                else:
                    error_msg = f"创建订单失败: {response.status_code} - {json.dumps(result, ensure_ascii=False)}"
                    logger.error(error_msg)
                    return False, error_msg, None

        except httpx.RequestError as e:
            error_msg = f"请求异常: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    # ==================== 捕获订单（扣款） ====================

    async def capture_order(
        self, paypal_order_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        捕获订单（真正扣款）
        在用户批准支付后调用此接口完成扣款

        Args:
            paypal_order_id: PayPal 返回的订单 ID

        Returns:
            (success, message, capture_data)
            capture_data 包含: capture_id, status, 金额, 手续费等
        """
        # 1. 确保有 Token
        ok, err = await self._ensure_token()
        if not ok:
            return False, err, None

        # 2. 发送请求
        url = f"{self.base_url}/v2/checkout/orders/{paypal_order_id}/capture"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
            "PayPal-Request-Id": f"CAPTURE-{paypal_order_id}-{__import__('uuid').uuid4().hex[:8]}",
        }

        try:
            async with self._build_client() as client:
                response = await client.post(url, headers=headers, json={})

                result = response.json()
                logger.info(f"PayPal 捕获订单响应: {response.status_code}")

                if response.status_code in (200, 201):
                    # 提取捕获信息
                    captures = []
                    for unit in result.get("purchase_units", []):
                        for cap in unit.get("payments", {}).get("captures", []):
                            captures.append({
                                "capture_id": cap.get("id", ""),
                                "status": cap.get("status", ""),
                                "amount": cap.get("amount", {}).get("value", "0"),
                                "currency": cap.get("amount", {}).get("currency_code", "USD"),
                                "final_capture": cap.get("final_capture", True),
                                "seller_receivable_breakdown": cap.get("seller_receivable_breakdown", {}),
                                "create_time": cap.get("create_time", ""),
                            })

                    capture_data = {
                        "paypal_order_id": result.get("id", ""),
                        "status": result.get("status", ""),
                        "captures": captures,
                        "payer": result.get("payer", {}),
                        "raw_response": result,
                    }
                    return True, "扣款成功", capture_data
                else:
                    error_msg = f"捕获订单失败: {response.status_code} - {json.dumps(result, ensure_ascii=False)}"
                    logger.error(error_msg)
                    return False, error_msg, None

        except httpx.RequestError as e:
            error_msg = f"请求异常: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    # ==================== 查询订单 ====================

    async def get_order(
        self, paypal_order_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        查询 PayPal 订单详情

        Args:
            paypal_order_id: PayPal 订单 ID

        Returns:
            (success, message, order_data)
        """
        ok, err = await self._ensure_token()
        if not ok:
            return False, err, None

        url = f"{self.base_url}/v2/checkout/orders/{paypal_order_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        try:
            async with self._build_client() as client:
                response = await client.get(url, headers=headers)
                result = response.json()

                if response.status_code == 200:
                    return True, "查询成功", result
                else:
                    error_msg = f"查询订单失败: {response.status_code} - {json.dumps(result, ensure_ascii=False)}"
                    return False, error_msg, None

        except httpx.RequestError as e:
            error_msg = f"请求异常: {str(e)}"
            return False, error_msg, None

    # ==================== 查询交易详情 ====================

    async def get_capture_details(
        self, capture_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        查询捕获交易详情（包含手续费信息）

        Args:
            capture_id: 捕获交易 ID

        Returns:
            (success, message, capture_details)
        """
        ok, err = await self._ensure_token()
        if not ok:
            return False, err, None

        url = f"{self.base_url}/v2/payments/captures/{capture_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        try:
            async with self._build_client() as client:
                response = await client.get(url, headers=headers)
                result = response.json()

                if response.status_code == 200:
                    return True, "查询成功", result
                else:
                    error_msg = f"查询失败: {response.status_code} - {json.dumps(result, ensure_ascii=False)}"
                    return False, error_msg, None

        except httpx.RequestError as e:
            error_msg = f"请求异常: {str(e)}"
            return False, error_msg, None

    # ==================== 退款 ====================

    async def refund_capture(
        self, capture_id: str, amount: Optional[str] = None, currency: str = "USD"
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        退款（全额或部分）

        Args:
            capture_id: 捕获交易 ID
            amount: 退款金额，为空则全额退款
            currency: 币种

        Returns:
            (success, message, refund_data)
        """
        ok, err = await self._ensure_token()
        if not ok:
            return False, err, None

        url = f"{self.base_url}/v2/payments/captures/{capture_id}/refund"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
            "PayPal-Request-Id": f"REFUND-{capture_id}-{__import__('uuid').uuid4().hex[:8]}",
        }

        refund_request = {}
        if amount:
            refund_request["amount"] = {
                "value": amount,
                "currency_code": currency.upper(),
            }

        try:
            async with self._build_client() as client:
                response = await client.post(url, headers=headers, json=refund_request)
                result = response.json()

                if response.status_code in (200, 201):
                    return True, "退款成功", result
                else:
                    error_msg = f"退款失败: {response.status_code} - {json.dumps(result, ensure_ascii=False)}"
                    return False, error_msg, None

        except httpx.RequestError as e:
            error_msg = f"请求异常: {str(e)}"
            return False, error_msg, None

    # ==================== Webhook 签名验证 ====================

    async def verify_webhook_signature(
        self,
        webhook_id: str,
        event_body: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Tuple[bool, str]:
        """
        验证 Webhook 签名（POST /v1/notifications/verify-webhook-signature）

        Args:
            webhook_id: Webhook ID
            event_body: 完整的 webhook 事件体
            headers: PayPal 回调的 HTTP 头（需包含 auth_algo、cert_url、transmission_id、transmission_sig、transmission_time）

        Returns:
            (verified, message)
        """
        ok, err = await self._ensure_token()
        if not ok:
            return False, err

        url = f"{self.base_url}/v1/notifications/verify-webhook-signature"
        headers_post = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        verify_request = {
            "auth_algo": headers.get("PAYPAL-AUTH-ALGO", ""),
            "cert_url": headers.get("PAYPAL-CERT-URL", ""),
            "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
            "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
            "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
            "webhook_id": webhook_id,
            "webhook_event": event_body,
        }

        try:
            async with self._build_client() as client:
                response = await client.post(url, headers=headers_post, json=verify_request)
                result = response.json()

                if response.status_code == 200:
                    verification_status = result.get("verification_status", "")
                    if verification_status == "SUCCESS":
                        return True, "签名验证通过"
                    else:
                        return False, f"签名验证失败: {verification_status}"
                else:
                    return False, f"验证请求失败: {response.status_code}"

        except httpx.RequestError as e:
            return False, f"请求异常: {str(e)}"


# 单例
paypal_service = PayPalService()
