# LLM Proxy — 前端接口文档

> 本文档面向**前端开发者**，说明与后端 API 对接的所有接口规范。
> 后端基于 FastAPI 开发，所有接口返回统一 JSON 格式。

---

## 📋 目录

1. [通用说明](#1-通用说明)
2. [认证接口](#2-认证接口)
3. [用户接口](#3-用户接口)
4. [充值接口（PayPal 支付）](#4-充值接口paypal-支付)
5. [前端对接 PayPal 支付流程](#5-前端对接-paypal-支付流程)
6. [附录：统一响应格式](#6-附录统一响应格式)

---

## 1. 通用说明

### Base URL

| 环境 | URL |
|------|-----|
| **开发环境** | `http://localhost:8000/api/v1` |
| **生产环境** | 待定 |

### 认证方式

本项目使用 **Session Cookie** 进行认证。用户登录后，服务端会通过 `Set-Cookie` 写入 `llm_session` 到浏览器。

| 项目 | 值 |
|------|-----|
| Cookie 名 | `llm_session` |
| HttpOnly | `true`（JS 不可读取） |
| SameSite | `Lax` |
| 有效期 | 24 小时 |

> **前端无需手动处理 Token**，浏览器会自动在每次请求中带上 Cookie。
> 如果使用 Postman 测试，需要手动添加 Cookie 头：`Cookie: llm_session=xxxxxx`

### 响应格式

所有接口返回统一格式（详见 [附录](#6-附录统一响应格式)）：

```json
{
    "code": 0,          // 0=成功，非0=失败
    "message": "success",
    "data": { ... }     // 业务数据，成功时存在
}
```

---

## 2. 认证接口

### 2.1 发送注册验证码

发送验证码到邮箱，用于注册和注销账户。

**请求**

```
POST /auth/send-code
Content-Type: application/json

{
    "email": "user@example.com"
}
```

**响应**

```json
{
    "code": 0,
    "message": "验证码已发送"
}
```

**错误**

```json
{
    "code": 400,
    "message": "邮箱已注册"
}
```

---

### 2.2 用户注册

**请求**

```
POST /auth/register
Content-Type: application/json

{
    "email": "user@example.com",
    "code": "123456",
    "username": "myusername",
    "password": "MyPassword123!"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `email` | string | 邮箱地址 |
| `code` | string | 邮箱收到的 6 位验证码 |
| `username` | string | 用户名（3-20 位字母数字） |
| `password` | string | 密码（至少 8 位，需含字母和数字） |

**响应**

```json
{
    "code": 0,
    "message": "注册成功",
    "data": {
        "user_id": 1
    }
}
```

> **成功后服务端会自动下发 Cookie**，前端无需额外操作。

---

### 2.3 用户登录

支持邮箱或用户名登录。

**请求**

```
POST /auth/login
Content-Type: application/json

{
    "identifier": "user@example.com",
    "password": "MyPassword123!"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `identifier` | string | 邮箱 或 用户名 |
| `password` | string | 密码 |

**响应**

```json
{
    "code": 0,
    "message": "登录成功",
    "data": {
        "user_id": 1
    }
}
```

> **登录成功后服务端自动下发 Cookie**，后续请求自动携带。

**错误**

```json
{
    "code": 401,
    "message": "账号或密码错误"
}
```

---

### 2.4 退出登录

**请求**

```
POST /auth/logout
Cookie: llm_session=xxxxxx
```

**响应**

```json
{
    "code": 0,
    "message": "退出登录成功"
}
```

---

## 3. 用户接口

### 3.1 获取用户信息

**请求**

```
GET /user/profile
Cookie: llm_session=xxxxxx
```

**响应**

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "balance": 99.99,
        "monthly_spending": 10.50,
        "api_keys": [
            {
                "key": "sk-a1b2c3d4e5f6...",
                "name": "默认密钥",
                "is_active": 1
            }
        ]
    }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `balance` | number | 账户余额（USD） |
| `monthly_spending` | number | 本月消费金额（USD） |
| `api_keys` | array | API 密钥列表 |

---

### 3.2 获取账单列表

**请求**

```
GET /user/bill?page=1&page_size=20
Cookie: llm_session=xxxxxx
```

**响应**

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "total": 42,
        "page": 1,
        "page_size": 20,
        "items": [
            {
                "order_no": "ORD20260424120000123456",
                "status": "paid",
                "amount": 10.00,
                "created_at": "2026-04-24T12:00:00"
            }
        ]
    }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `pending` 待支付 / `paid` 已支付 / `failed` 失败 |
| `amount` | number | 金额（USD） |

---

## 4. 充值接口（PayPal 支付）

> 整个充值流程分两步走，详见 [第 5 节](#5-前端对接-paypal-支付流程)。

### 4.1 创建 PayPal 订单（Step 1）

在前端展示 PayPal 按钮时调用，后端会在 PayPal 创建一笔订单并返回支付链接。

**请求**

```
POST /recharge/paypal/create
Cookie: llm_session=xxxxxx
Content-Type: application/json

{
    "amount": 10.00,
    "currency": "USD",
    "return_url": "https://your-frontend.com/success",
    "cancel_url": "https://your-frontend.com/cancel"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `amount` | number | ✅ | 充值金额，大于 0 |
| `currency` | string | ❌ | 货币代码，默认 `USD` |
| `return_url` | string | ❌ | 支付成功后前端跳转地址 |
| `cancel_url` | string | ❌ | 取消支付后前端跳转地址 |

**响应（201 Created）**

```json
{
    "code": 0,
    "message": "订单创建成功",
    "data": {
        "order_no": "ORD20260424120000123456",
        "paypal_order_id": "5OY12345ABC123456X",
        "amount": 10.0,
        "currency": "USD",
        "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=5OY12345ABC123456X",
        "status": "CREATED"
    }
}
```

| 返回字段 | 类型 | 说明 |
|----------|------|------|
| `order_no` | string | **本地订单号**，请保存，下一步捕获要用 |
| `paypal_order_id` | string | PayPal 侧订单 ID |
| `approve_url` | string | **⭐ 关键**：跳转到此 URL 让用户完成支付 |
| `status` | string | 当前订单状态 |

> **前端逻辑**：拿到 `approve_url` 后，用 `window.location.href` 跳转或弹窗让用户前往 PayPal 付款。

---

### 4.2 捕获订单（Step 2）

用户在 PayPal 页面完成支付后调用此接口，后端会：
1. 调用 PayPal API **完成扣款**
2. 将订单状态更新为 `paid`
3. **为用户账户增加余额**

**请求**

```
POST /recharge/paypal/capture
Cookie: llm_session=xxxxxx
Content-Type: application/json

{
    "order_no": "ORD20260424120000123456"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `order_no` | string | ✅ | 创建订单时返回的 `order_no` |

**响应（200 OK）**

```json
{
    "code": 0,
    "message": "充值成功",
    "data": {
        "order_no": "ORD20260424120000123456",
        "paypal_order_id": "5OY12345ABC123456X",
        "capture_id": "9PC12345ABC123456X",
        "status": "paid",
        "amount": 10.0,
        "currency": "USD",
        "paypal_fee": 0.59,
        "net_amount": 9.41,
        "payer_email": "sb-xxxxx@personal.example.com"
    }
}
```

| 返回字段 | 类型 | 说明 |
|----------|------|------|
| `status` | string | 固定为 `paid` |
| `amount` | number | 充值金额（总额） |
| `paypal_fee` | number | PayPal 手续费 |
| `net_amount` | number | 扣除手续费后实际到账 |
| `payer_email` | string | 付款人 PayPal 邮箱 |

**错误示例**

```json
// 订单不存在
{ "code": 404, "message": "订单不存在" }

// 无权操作
{ "code": 403, "message": "无权操作该订单" }

// 已支付过
{ "code": 400, "message": "该订单已支付" }
```

---

### 4.3 查询订单状态

**请求**

```
GET /recharge/{order_no}
Cookie: llm_session=xxxxxx
```

**响应**

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "order_no": "ORD20260424120000123456",
        "status": "paid",
        "amount": 10.00,
        "external_no": "5OY12345ABC123456X",
        "created_at": "2026-04-24T12:00:00",
        "paid_at": "2026-04-24T12:05:00"
    }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `pending` / `paid` / `failed` / `refunded` |
| `paid_at` | string | 支付时间，未支付时为 `null` |

---

## 5. 前端对接 PayPal 支付流程

### 流程图

```
┌────────────────────────────────────────────────────────────────────┐
│  前端（浏览器）                       后端（你的服务器）          │
│                                                                     │
│  ① 用户点击"充值"                                                   │
│     ↓                                                               │
│  ② POST /recharge/paypal/create  ───────────→  ③ 创建 PayPal 订单  │
│     ↑                                                               │
│  ④ ←──── 返回 { order_no, approve_url }       PayPal 返回 approve │
│                                                                     │
│  ⑤ window.location.href = approve_url                              │
│     ↓                                                               │
│  ┌──────────────────────────────────────┐                           │
│  │  PayPal 支付页面                      │                           │
│  │  - 用户登录沙箱/正式账号               │                           │
│  │  - 确认支付                            │                           │
│  └──────────────┬───────────────────────┘                           │
│                 ↓                                                   │
│  ⑥ PayPal 重定向到 return_url（带上 token）                         │
│     ↓                                                               │
│  ⑦ 前端捕获到 return_url 后, 调用                                   │
│     POST /recharge/paypal/capture  ─────→  ⑧ 捕获资金 + 增加余额   │
│     ↑                                                               │
│  ⑨ ←──── 返回 { status: "paid", amount }                           │
│                                                                     │
│  ⑩ 显示"充值成功"提示，刷新余额                                      │
└────────────────────────────────────────────────────────────────────┘
```

### 前端代码示例（伪代码）

```javascript
// ===== Step 1: 用户点击充值按钮 =====

async function handleRecharge(amount) {
  try {
    // 1. 创建订单
    const resp = await fetch("/api/v1/recharge/paypal/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        amount: amount,
        currency: "USD",
        return_url: `${window.location.origin}/payment/success`,
        cancel_url: `${window.location.origin}/payment/cancel`,
      }),
    });

    const result = await resp.json();

    if (result.code !== 0) {
      alert(result.message);
      return;
    }

    const { order_no, approve_url } = result.data;

    // 2. 保存 order_no 到 sessionStorage（跳转后恢复）
    sessionStorage.setItem("pending_order_no", order_no);

    // 3. 跳转到 PayPal 支付页面
    window.location.href = approve_url;

  } catch (err) {
    console.error("创建订单失败:", err);
  }
}


// ===== Step 2: 用户在 PayPal 完成支付后回到 return_url =====

// 在 /payment/success 页面加载时执行
async function handlePaymentSuccess() {
  const order_no = sessionStorage.getItem("pending_order_no");

  if (!order_no) {
    // 没有待处理的订单，可能是直接访问此页面
    return;
  }

  try {
    // 调用捕获接口
    const resp = await fetch("/api/v1/recharge/paypal/capture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_no }),
    });

    const result = await resp.json();

    // 清除缓存
    sessionStorage.removeItem("pending_order_no");

    if (result.code === 0) {
      // 充值成功！刷新用户余额
      showSuccess(`充值成功！到账 $${result.data.amount}`);
      refreshUserBalance();  // 调用 GET /user/profile 刷新余额
    } else {
      showError(result.message);
    }

  } catch (err) {
    console.error("捕获订单失败:", err);
  }
}
```

### 重要提示

| 提示 | 说明 |
|------|------|
| **保存 order_no** | 跳转到 PayPal 前一定要保存 `order_no`（例如 `sessionStorage`） |
| **不要重复捕获** | 一个 `order_no` 只能捕获一次，再次调用会返回错误 |
| **余额自动增加** | 捕获成功后后端会自动为用户增加余额，不需要前端额外调用 |
| **掉单处理** | 如果用户支付成功但网络异常导致 `capture` 失败，可以让用户重试 `capture` |
| **本地测试** | 开发时 `return_url` 和 `cancel_url` 可以留空或用任何 URL |

---

## 6. 附录：统一响应格式

### 成功响应

```json
{
    "code": 0,
    "message": "success",
    "data": { ... }
}
```

### 错误响应

```json
{
    "code": 400,
    "message": "错误描述信息"
}
```

### 常见错误码

| HTTP 状态码 | `code` 字段 | 含义 |
|-------------|-------------|------|
| 201 | 0 | 创建成功 |
| 200 | 0 | 请求成功 |
| 400 | 400 | 参数错误或业务校验失败 |
| 401 | 40101 | 账号/密码错误 |
| 401 | 40102 | 未登录或 Session 失效 |
| 403 | 403 | 无权操作 |
| 404 | 404 | 资源不存在 |
| 429 | 429 | 请求太频繁，被限流 |

### 前端判断逻辑

```javascript
// 统一处理响应
async function apiCall(url, options) {
  const resp = await fetch(url, options);
  const result = await resp.json();

  if (result.code !== 0) {
    // 根据 code 做不同处理
    if (result.code === 40102) {
      // Session 过期，跳转登录页
      redirectToLogin();
    }
    throw new Error(result.message);
  }

  return result.data;
}
```

---

> 文档版本: v1.0 | 最后更新: 2026-04-24
