# LLM Proxy - 大模型 API 中转站

## 项目简介

LLM Proxy 是一个基于 FastAPI 的大模型 API 中转站项目，支持 OpenAI、Claude、Gemini 等多种大模型接口的统一接入和管理。

## 功能特性

- 用户认证系统（注册、登录、Session管理）
- API-Key 管理
- 代理转发（OpenAI Chat Completions、Claude Messages、Gemini、OpenAI Responses）
- 计费系统
- 充值系统（PayPal）
- 限流保护

## 项目结构

```
llm-proxy/
├── app/                    # 应用核心
├── api/                    # API 接口
├── core/                   # 核心模块
├── models/                 # 数据模型
├── schemas/                # Pydantic 模型
├── services/               # 业务服务
├── repositories/           # 数据访问层
├── utils/                  # 工具函数
├── middleware/             # 中间件
├── log/                    # 日志
├── scripts/                # 脚本
└── tests/                  # 测试
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制 `config.yaml` 并修改配置项：

```yaml
database:
  host: "localhost"
  port: 3306
  username: "root"
  password: "your-password"
  name: "llm_proxy"

redis:
  host: "localhost"
  port: 6379
```

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

### 4. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API 文档

启动服务后访问：`http://localhost:8000/docs`

## 测试

```bash
pytest tests/
```
