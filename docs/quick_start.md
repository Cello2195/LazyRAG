# Quick Start

This document covers two things only:

- How to configure environment variables
- How to start the services

All commands are run from the repository root by default.

## Prerequisites

- Docker and Docker Compose installed
- You are in the repository root
- If using a public cloud API model, have the corresponding API key ready
- If using an on-premises model, ensure the current machine can reach the internal service

## Environment Variables

### 1. Model configuration

Select a model config via `LAZYRAG_MODEL_CONFIG_PATH`. Three built-in shorthand values:

| Value | Description |
|-------|-------------|
| `online` | Public cloud API (default when not set) |
| `inner` | On-premises / intranet deployment |
| `dynamic` | Key injected per request |

An explicit file path is also accepted.

For public cloud APIs, export the corresponding API key. The variable name must match the placeholder used in the config file. For example, if the config references `${LAZYLLM_SILICONFLOW_API_KEY}`, export that variable:

```bash
export LAZYLLM_SILICONFLOW_API_KEY=your-key
export LAZYRAG_MODEL_CONFIG_PATH=online
```

If the config references multiple providers, export all the corresponding keys at once. `docker-compose.yml` already passes through common LLM API key variables (`LAZYLLM_OPENAI_API_KEY`, `LAZYLLM_DEEPSEEK_API_KEY`, `LAZYLLM_SILICONFLOW_API_KEY`, etc.).

For on-premises models:

```bash
export LAZYRAG_MODEL_CONFIG_PATH=inner
```

### 2. OCR

OCR is disabled by default (built-in PDFReader is used):

```bash
export LAZYRAG_OCR_SERVER_TYPE=none   # default, can be omitted
```

To enable local MinerU:

```bash
export LAZYRAG_OCR_SERVER_TYPE=mineru
# LAZYRAG_OCR_SERVER_URL is auto-derived to http://mineru:8000 when not set
```

To reuse an existing MinerU deployed on ECS / intranet:

```bash
export LAZYRAG_OCR_SERVER_TYPE=mineru
export LAZYRAG_OCR_SERVER_URL=http://your-inner-mineru:port
```

When `LAZYRAG_OCR_SERVER_URL` points to an external address, `make up` will not start the local `mineru` profile.

To enable PaddleOCR (GPU required):

```bash
export LAZYRAG_OCR_SERVER_TYPE=paddleocr
# LAZYRAG_OCR_SERVER_URL is auto-derived to http://paddleocr:8080 when not set
```

### 3. Vector / segment stores

By default, Milvus and OpenSearch are deployed in-stack. To use external services:

```bash
export LAZYRAG_MILVUS_URI=http://your-milvus:19530
export LAZYRAG_OPENSEARCH_URI=https://your-opensearch:9200
export LAZYRAG_OPENSEARCH_USER=admin
export LAZYRAG_OPENSEARCH_PASSWORD=your-password
```

When the URIs stay at `http://milvus:19530` and `https://opensearch:9200`, the built-in services are deployed automatically.

### 4. Frontend port

The frontend defaults to port **8090**. Override if the port is occupied:

```bash
export LAZYRAG_FRONTEND_PORT=8080
```

### 5. Auth credentials (production)

Change these before deploying to production:

```bash
export LAZYRAG_JWT_SECRET=your-strong-secret
export LAZYRAG_BOOTSTRAP_ADMIN_USERNAME=admin
export LAZYRAG_BOOTSTRAP_ADMIN_PASSWORD=your-password
```

### 6. Using a `.env` file

All variables above can be placed in a `.env` file at the repository root. The Makefile loads it automatically:

```bash
# .env
LAZYRAG_MODEL_CONFIG_PATH=online
LAZYLLM_SILICONFLOW_API_KEY=your-key
LAZYRAG_OCR_SERVER_TYPE=none
LAZYRAG_FRONTEND_PORT=8090
```

---

## Starting Services

### Standard startup

```bash
make up
```

Starts all services in the background. Milvus and OpenSearch are deployed automatically.

### Build images and start

```bash
make up-build
```

Use this on first run or after changing Dockerfiles / dependencies.

### Start with specific services only

```bash
make up SERVICES=chat,core
```

### Start with MinerU OCR

```bash
export LAZYRAG_OCR_SERVER_TYPE=mineru
make up
```

### Start with PaddleOCR (GPU)

```bash
export LAZYRAG_OCR_SERVER_TYPE=paddleocr
make up
```

### Start with external Milvus / OpenSearch

```bash
make up \
  LAZYRAG_MILVUS_URI=http://your-milvus:19530 \
  LAZYRAG_OPENSEARCH_URI=https://your-opensearch:9200
```

### Enable store dashboards

```bash
make up LAZYRAG_ENABLE_STORE_DASHBOARDS=1
```

- Attu (Milvus): http://127.0.0.1:3000
- OpenSearch Dashboards: http://127.0.0.1:5601 (login: `admin` / `LAZYRAG_OPENSEARCH_PASSWORD`)

Dashboards bind to `127.0.0.1` only and are not started if the corresponding store is external.

---

## After Startup

| URL | Description |
|-----|-------------|
| http://localhost:8090 | Frontend (default port) |
| http://localhost:8000 | Kong API Gateway |
| http://localhost:8090/docs.html | Unified Swagger UI |
| http://localhost:8048 | evo API (self-evolution service) |

Default credentials: `admin` / `admin`

---

## Common Operations

Restart containers without rebuilding:

```bash
docker compose up -d --force-recreate
```

Stop services:

```bash
make down
```

Stop specific services:

```bash
make down SERVICES=chat,core
```

View service status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs --tail=200 -f
```

---

## Data Reset

### Reset knowledge base only

Wipes Milvus, OpenSearch, uploads, and KB-related PostgreSQL tables. User accounts, auth tokens, Redis, conversations, and prompts are **preserved**.

```bash
make reset-kb
make up LAZYRAG_RESET_ALGO_ON_STARTUP=true
```

`LAZYRAG_RESET_ALGO_ON_STARTUP=true` is required after `reset-kb` so the algo service rebuilds its schema tables on next startup.

### Fresh start (standard clean restart)

Equivalent to `reset-kb` + rebuild + start with algo reset:

```bash
make fresh-start
```

### Full reset (wipe everything)

Removes all persistent data including user accounts, auth tokens, Redis, and all volumes. Equivalent to a clean first-run state:

```bash
make reset-all
make up-build
```

### Clear containers and volumes

Stop services, remove all volumes, and clear Python cache (keeps built images):

```bash
make clear
make up-build
```

---

## Complete Startup Examples

### Public cloud API model

```bash
export LAZYLLM_SILICONFLOW_API_KEY=your-key
export LAZYRAG_MODEL_CONFIG_PATH=online
export LAZYRAG_OCR_SERVER_TYPE=none

make up-build
```

### On-premises model + local MinerU

```bash
export LAZYRAG_MODEL_CONFIG_PATH=inner
export LAZYRAG_OCR_SERVER_TYPE=mineru

make up-build
```

### On-premises model + external MinerU

```bash
export LAZYRAG_MODEL_CONFIG_PATH=inner
export LAZYRAG_OCR_SERVER_TYPE=mineru
export LAZYRAG_OCR_SERVER_URL=http://your-inner-mineru:port

make up-build
```

### On-premises model + external Milvus / OpenSearch

```bash
export LAZYRAG_MODEL_CONFIG_PATH=inner
export LAZYRAG_MILVUS_URI=http://your-milvus:19530
export LAZYRAG_OPENSEARCH_URI=https://your-opensearch:9200
export LAZYRAG_OPENSEARCH_USER=admin
export LAZYRAG_OPENSEARCH_PASSWORD=your-password

make up-build
```

## 无 sudo 服务器（本地 Mac 常驻监听，服务器侧操作）

本节默认你已经在本地 Mac 跑了常驻程序，反向隧道保持在线。  
也就是服务器上执行 `ssh mymac-via-tunnel 'docker --version'` 能通。

以下命令是 2026-05-07 在当前环境实测通过的流程。

### 1. 服务器侧准备（一次性）

```bash
export PATH="$HOME/.local/bin:$PATH"

# 1) 验证隧道和本机 Docker 可达
ssh -o BatchMode=yes -o ConnectTimeout=6 mymac-via-tunnel 'docker --version'

# 2) 同步代码到本机 Mac（容器实际在 Mac 上运行，必须有本地代码目录）
#    注意：排除运行态目录，避免 rsync --delete 影响正在运行的 Redis/Postgres 等状态目录
cd /home/mnt/xiongyida/project
rsync -az --delete \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "data/state/" \
  --exclude "data/core/uploads/" \
  --exclude "data/scan/" \
  --exclude "data/watch/" \
  LazyRAG/ mymac-via-tunnel:/Users/xiongyida/project/LazyRAG/

# 说明：
# 1) 若出现 "data/core: not empty, cannot delete"，通常是因为目标目录仍有运行态文件，属可忽略告警。
# 2) 同步排除了 .git，所以后续若看到 "fatal: not a git repository"（旧版 Makefile），不影响服务启动。
```

### 2. 生成 Mac 专用模型配置（服务器执行）

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel '
  cd /Users/xiongyida/project/LazyRAG &&
  cp algorithm/chat/runtime_models.inner.yaml algorithm/chat/runtime_models.macproxy.yaml &&
  sed -i "" "s|http://10.119.27.151:2269|http://host.docker.internal:2269|g" algorithm/chat/runtime_models.macproxy.yaml
'
```

### 3. 确保 2269 转发可用（服务器执行）

如果你的本地常驻程序已经把 `10.119.27.151:2269` 转发到了 Mac 本机 `127.0.0.1:2269`，这一步会直接通过。  
否则会自动补一次转发：

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel 'curl -sS --max-time 2 -i http://127.0.0.1:2269/embed >/dev/null' || \
ssh -fNT -o ExitOnForwardFailure=yes -R 127.0.0.1:2269:10.119.27.151:2269 mymac-via-tunnel
```

### 4. 启动 LazyRAG（服务器发起，Mac 执行）

先确保 Mac 侧项目根目录有可用模型 key（推荐写入 `.env`，避免 shell 会话失效）：

```bash
# 在 Mac 上执行（或通过 ssh 执行）
cd /Users/xiongyida/project/LazyRAG
test -f .env || cp .env.example .env

# 至少配置一个可用聊天模型 key（按你的模型网关实际需要填写）
# 例如 Minimax 网关：
# LAZYLLM_MINIMAX_API_KEY=your-real-key
```

如果未配置有效 key，`chat` 服务会返回“模型服务鉴权失败”提示，而不是正常生成内容。

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  export DOCKER_BUILDKIT=1
  export LAZYRAG_OCR_SERVER_TYPE=none
  export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.macproxy.yaml
  export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
  export PIP_DEFAULT_TIMEOUT=1200
  export PIP_RETRIES=30
  cd /Users/xiongyida/project/LazyRAG
  test -f algorithm/chat/runtime_models.macproxy.yaml || \
    (cp algorithm/chat/runtime_models.inner.yaml algorithm/chat/runtime_models.macproxy.yaml && \
     sed -i "" "s|http://10.119.27.151:2269|http://host.docker.internal:2269|g" algorithm/chat/runtime_models.macproxy.yaml)
  make up-build
'
```

### 4.1 修改代码后如何生效

#### 普通代码修改：同步到 Mac + 重启 chat，不 rebuild

```bash
export PATH="$HOME/.local/bin:$PATH"

cd /home/mnt/xiongyida/project
rsync -az --delete \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "data/state/" \
  --exclude "data/core/uploads/" \
  --exclude "data/scan/" \
  --exclude "data/watch/" \
  LazyRAG/ mymac-via-tunnel:/Users/xiongyida/project/LazyRAG/

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  cd /Users/xiongyida/project/LazyRAG
  docker compose restart chat
  docker compose ps chat
'
```

#### 修改后直接跑 HTML/PPTX 调试脚本

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  cd /Users/xiongyida/project/LazyRAG
  docker compose exec chat bash -lc "PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme auto"
'
```

#### 需要真实截图和 visual.pptx 时

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  cd /Users/xiongyida/project/LazyRAG
  docker compose exec chat bash -lc "PYTHONPATH=algorithm python scripts/debug_html_deck_generation.py --theme auto --require-screenshots"
'
```

#### 只看 chat 日志

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  cd /Users/xiongyida/project/LazyRAG
  docker compose logs --tail=200 chat
'
```

#### 修改依赖 / Dockerfile / compose / 系统库时才 rebuild

```bash
export PATH="$HOME/.local/bin:$PATH"

cd /home/mnt/xiongyida/project
rsync -az --delete \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "data/state/" \
  --exclude "data/core/uploads/" \
  --exclude "data/scan/" \
  --exclude "data/watch/" \
  LazyRAG/ mymac-via-tunnel:/Users/xiongyida/project/LazyRAG/

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  export DOCKER_BUILDKIT=1
  export LAZYRAG_OCR_SERVER_TYPE=none
  export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.macproxy.yaml
  export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
  export PIP_DEFAULT_TIMEOUT=1200
  export PIP_RETRIES=30
  cd /Users/xiongyida/project/LazyRAG
  make up-build
'
```

#### 如果只想重建 chat 一个服务

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  cd /Users/xiongyida/project/LazyRAG
  docker compose up -d --build chat
  docker compose ps chat
'
```

### 5. 查看状态（服务器执行）

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  cd /Users/xiongyida/project/LazyRAG
  docker compose ps
'
```

### 6. 常用运维（服务器执行）

```bash
export PATH="$HOME/.local/bin:$PATH"

# 查看状态
ssh mymac-via-tunnel 'export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH; cd /Users/xiongyida/project/LazyRAG; docker compose ps'

# 查看日志
ssh mymac-via-tunnel 'export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH; cd /Users/xiongyida/project/LazyRAG; docker compose logs --tail=200'

# 停止
ssh mymac-via-tunnel 'export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH; cd /Users/xiongyida/project/LazyRAG; make down'
```

### 7. 快速健康检查（服务器执行）

```bash
export PATH="$HOME/.local/bin:$PATH"

ssh mymac-via-tunnel '
  export PATH=/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
  cd /Users/xiongyida/project/LazyRAG
  check_url () {
    name="$1"; url6="$2"; url4="$3"
    code="$(curl -g -6 -s -o /dev/null -w "%{http_code}" --max-time 5 "$url6" || true)"
    if [ -z "$code" ] || [ "$code" = "000" ]; then
      code="$(curl -4 -s -o /dev/null -w "%{http_code}" --max-time 5 "$url4" || true)"
    fi
    echo "$name $code"
  }
  check_url "frontend" "http://[::1]:8090" "http://127.0.0.1:8090"
  check_url "scan"     "http://[::1]:18080/healthz" "http://127.0.0.1:18080/healthz"
  check_url "evo"      "http://[::1]:8048/healthz"  "http://127.0.0.1:8048/healthz"
  check_url "core"     "http://[::1]:8001/api/core/health" "http://127.0.0.1:8001/api/core/health"
  echo "redis";        docker compose ps redis
'
```

### 8. 故障快速判断

- `ssh ... mymac-via-tunnel 'docker --version'` 不通：本地常驻隧道程序未运行或已断开。
- `make up-build` 报 mount 路径错误：说明不是在 Mac 本地目录运行 compose，请确认代码已同步到 `/Users/xiongyida/project/LazyRAG`。
- `lazyllm-algo` 启动失败且日志含 `10.119.27.151:2269 timeout`：检查第 3 步端口转发是否成功。
- `lazyllm-algo` 报 `Model config ... runtime_models.macproxy.yaml not found`：按第 4/4.1 步中的 `test -f ... || cp ...` 兜底生成后重试。
- `redis` 变成 `unhealthy` 且日志出现 `Failed opening the temp RDB file ... No such file or directory`：优先检查是否执行了会改动 `data/state/redis` 的同步/清理操作。
- 网页弹 `服务器无响应` 但 `docker compose ps` 全是 `Up(healthy)`：优先检查 VSCode 本地端口转发是否占用了 `127.0.0.1:8090/8001`。  
  现象：`lsof -nP -iTCP:8090 -sTCP:LISTEN` 里同时出现 `Code Helper (Plugin)` 与 `com.docker`。  
  处理：优先访问 `http://[::1]:8090/agent/chat/home`，并在 VSCode Ports 面板关闭 `8090/8001` 的转发（或改成本地其它端口）。
- 首轮 `make up-build` 拉镜像和大依赖耗时较长，常见 10~40 分钟。
