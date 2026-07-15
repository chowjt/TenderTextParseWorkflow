# TenderTextParseWorkflow

烟草招采公告文本解析服务，基于 LangChain 1.0 LTS + LangGraph 一比一重构原始 FastGPT/Dify 工作流，对外提供 HTTP API 接口。

---

## 一、功能概述

本项目解析烟草行业招采公告文本，支持以下 4 种公告类型：

| 公告类型 | 说明 |
|----------|------|
| 招标公告 | 提取项目名称、项目编号、招标人、项目规模、招标内容、投标截止日期等 |
| 变更公告 | 提取变更内容（终止/流标/澄清/更正） |
| 中标候选人公示 | 提取候选人列表、排名、投标报价等 |
| 结果公告 | 提取中标人列表、排名、中标金额等 |

解析结果以结构化 JSON 返回，同时完整记录每次请求日志到本地 SQLite 数据库，并提供 Web 页面查看日志和 Token 消耗统计。

---

## 二、技术栈

- **LangChain 1.0 LTS** + **LangGraph 1.0**
- **FastAPI** 提供 HTTP 服务
- **Pydantic v2** 结构化输出校验
- **SQLite** 本地日志存储
- **ECharts** 前端图表展示

---

## 三、项目结构

```
TenderTextParseWorkflow/
├── .env                          # 敏感配置（API 密钥、模型参数、服务端口）
├── .gitignore                    # Git 忽略配置
├── requirements.txt              # Python 依赖
├── main.py                       # 服务启动入口
├── 解析招采公告文本.json          # 原始 FastGPT/Dify 工作流 JSON
├── data/                         # SQLite 数据库目录
│   └── logs.db                   # 请求日志数据库（运行后自动生成）
├── logs/                         # 日志文件目录
└── app/                          # 应用核心代码
    ├── __init__.py
    ├── auth.py                   # Bearer Token 鉴权
    ├── config.py                 # 配置读取（.env + 日志配置）
    ├── prompts.py                # 4 种公告类型的完整提示词
    ├── schemas.py                # Pydantic 输入/输出模型
    ├── workflow.py               # LangGraph 工作流核心
    ├── server.py                 # FastAPI 服务与接口实现
    ├── api_logger.py             # API 文件日志中间件
    ├── db.py                     # SQLite 数据库模型与查询
    ├── log_api.py                # 日志查询与统计 API
    └── templates/
        └── logs.html             # 日志展示前端页面
```

---

## 四、环境配置

复制 `.env.example` 为 `.env` 并填写以下配置（如没有 example 文件，直接新建 `.env`）：

```env
# 服务配置
SERVER_PORT=26715
API_KEYS=your_api_key_1,your_api_key_2

# DeepSeek 模型配置（统一使用 DeepSeek）
MODEL_NAME=deepseek-ai/DeepSeek-V3
MODEL_BASE_URL=https://api.siliconflow.cn/v1
MODEL_API_KEY=sk-your-siliconflow-api-key
MODEL_TEMPERATURE=0.4
MODEL_MAX_TOKEN=8192
```

> 当前通过硅基流动（SiliconFlow）OpenAI 兼容接口调用 DeepSeek 模型。

---

## 五、安装与启动

### 方式一：本地启动

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 启动服务

```bash
python main.py
```

服务启动后访问：

- API 接口：`http://localhost:26715/api/v1/chat/completions`
- 日志页面：`http://localhost:26715/api/v1/logs`
- 健康检查：`http://localhost:26715/api/v1/health`

### 方式二：Docker 启动

#### 1. 构建镜像

```bash
docker build -t beijingshiye-tender-text-parse:latest .
```

如果构建环境访问 PyPI 较慢或无法访问，可指定国内镜像源：

```bash
docker build \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
  -t beijingshiye-tender-text-parse:latest .
```

#### 2. 运行容器

```bash
docker run -d -p 26715:26715 --name beijingshiye-tender-text-parse --env-file .env beijingshiye-tender-text-parse:latest
```

### 方式三：Docker Compose 启动（推荐）

本项目提供 [docker-compose.yml](docker-compose.yml)，适配 Docker Compose v2.20.3+，并已将 `data/` 和 `logs/` 目录挂载到本地实现持久化。

```bash
# 启动服务（后台运行）
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

> 注意：使用 Docker Compose v2 时，命令为 `docker compose`（无连字符）。

---

## 六、API 使用说明

### 接口地址

```
POST http://localhost:26715/api/v1/chat/completions
```

### 请求头

```http
Authorization: Bearer your_api_key
Content-Type: application/json
```

### 请求体示例

```json
{
  "chatId": "my_chat_id",
  "stream": false,
  "detail": false,
  "responseChatItemId": "my_response_id",
  "variables": {
    "id": "17",
    "dupUid": "5bebd68698c639a6b375ff0d65c92b6d",
    "procureMethod": "公开招标",
    "noticeType": "招标公告",
    "content": "公告招标项目所在地区：江苏省淮安市...",
    "spare1": "",
    "spare2": "",
    "spare3": ""
  },
  "messages": [
    {
      "role": "user",
      "content": "江苏中烟工业有限责任公司淮阴卷烟厂2025年购置4台在线烟支综合测试台项目-公开招标公告"
    }
  ]
}
```

### 响应示例

```json
{
  "id": "my_chat_id",
  "model": "deepseek-v3-2-251201",
  "usage": {
    "prompt_tokens": 138,
    "completion_tokens": 891,
    "total_tokens": 1029
  },
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "```json\n{...}\n```"
      },
      "finish_reason": "stop",
      "index": 0
    }
  ]
}
```

---

## 七、日志与统计

### 数据库字段

每次请求会记录到 `data/logs.db`，字段包括：

- **请求 Header**：Authorization（脱敏）、Content-Type
- **请求 Body**：chatId、responseChatItemId、stream、detail、variables 子字段、messages
- **响应 Body**：resp_id、model、prompt_tokens、completion_tokens、total_tokens、choices、status_code

### 日志页面

访问 `http://localhost:26715/api/v1/logs` 可查看：

- 请求日志列表（支持按公告类型筛选、分页）
- 单条请求详情（请求头、请求体、响应体完整展示）
- Token 消耗统计面板：
  - 近 1 天 / 近 1 周 / 近 1 月 / 本年度分月 / 全部分年 / 全部总量
  - 总 Token、输入 Token、输出 Token、请求数
  - 按公告类型分布饼图
  - Token 消耗趋势图

### 统计接口

```
GET /api/v1/logs/stats?range_type=1d
```

`range_type` 可选值：`1d`、`7d`、`30d`、`month`、`year`、`all`

---

## 八、注意事项

1. 修改数据库表结构后，建议删除 `data/logs.db` 重新启动服务，新表会自动创建。
2. `.env` 文件包含敏感信息，已加入 `.gitignore`，请勿提交到代码仓库。
3. 当前仅支持非流式返回（`stream=false`）。
4. 使用 Docker 部署时，`.env` 文件不会被复制到镜像中，请通过 `docker run --env-file .env` 或 `docker compose` 的方式传入环境变量。
5. `data/` 和 `logs/` 目录已通过 Docker Compose 挂载到本地，容器删除后数据不会丢失。
6. 如果 Docker 构建时出现 `Network is unreachable` 警告，说明构建环境无法访问 PyPI，可通过 `--build-arg PIP_INDEX_URL=...` 指定国内镜像源。

---

## 九、License

MIT
