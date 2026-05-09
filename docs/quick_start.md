# Quick Start

这份文档只包含两件事：

- 如何配置环境变量
- 如何启动服务

所有命令都默认在仓库根目录执行。

## 前置条件

- 已安装 Docker / Docker Compose
- 已在仓库根目录
- 如需使用线上 API 模型，提前准备好对应 API key
- 如需使用内网模型，确保当前机器能访问对应内网服务

## 环境变量

### 1. 线上 API 模型

使用 [`algorithm/chat/runtime_models.yaml`](../algorithm/chat/runtime_models.yaml)：

```bash
export LAZYLLM_SILICONFLOW_API_KEY=你的key
export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.yaml
```

这里的环境变量名必须和 yaml 里使用的占位符一致。例如 yaml 中写的是 `${LAZYLLM_SILICONFLOW_API_KEY}`，那就必须 export `LAZYLLM_SILICONFLOW_API_KEY`。
如果一份 yaml 同时引用多个 provider 的 key，也可以同时 export 多个环境变量。`docker-compose.yml` 已经透传常见的在线模型环境变量。

### 2. 内网已部署模型

```bash
export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.inner.yaml
```

对应配置文件是 [`algorithm/chat/runtime_models.inner.yaml`](../algorithm/chat/runtime_models.inner.yaml)。

### 3. OCR 相关

默认不启用 OCR 服务：

```bash
export LAZYRAG_OCR_SERVER_TYPE=none
```

如果要启用本地 MinerU：

```bash
export LAZYRAG_OCR_SERVER_TYPE=mineru
export LAZYRAG_OCR_SERVER_URL=http://mineru:8000
export LAZYRAG_MINERU_BACKEND=pipeline
export LAZYRAG_MINERU_UPLOAD_MODE=true
```

如果要复用 ECS / 内网已经部署好的 MinerU：

```bash
export LAZYRAG_OCR_SERVER_TYPE=mineru
export LAZYRAG_OCR_SERVER_URL=http://your-inner-mineru:port
export LAZYRAG_MINERU_UPLOAD_MODE=true
```

`http://mineru:8000` 表示使用当前 `docker compose` 启动的本地 MinerU。
如果 `LAZYRAG_OCR_SERVER_URL` 指向外部地址，服务会复用外部 MinerU，`make up-build` 也不会自动启动本地 `mineru` profile。

如果使用外部 Milvus / OpenSearch，也在启动前 export 对应变量：

```bash
export LAZYRAG_MILVUS_URI=http://your-milvus:19530
export LAZYRAG_OPENSEARCH_URI=https://your-opensearch:9200
export LAZYRAG_OPENSEARCH_USER=admin
export LAZYRAG_OPENSEARCH_PASSWORD=your-password
```

## 启动服务

### 1. 默认启动

```bash
make up-build
```

### 2. 使用线上 API 模型启动

```bash
export LAZYLLM_SILICONFLOW_API_KEY=你的key
export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.yaml
export LAZYRAG_OCR_SERVER_TYPE=none

make up-build
```

### 3. 使用内网 runtime 配置启动

```bash
export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.inner.yaml
export LAZYRAG_OCR_SERVER_TYPE=none

make up-build
```

### 4. 启用 MinerU 启动

```bash
export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.inner.yaml
export LAZYRAG_OCR_SERVER_TYPE=mineru
export LAZYRAG_OCR_SERVER_URL=http://mineru:8000
export LAZYRAG_MINERU_BACKEND=pipeline
export LAZYRAG_MINERU_UPLOAD_MODE=true

make up-build
```

## 常用运维命令

只重启容器，不重新 build：

```bash
docker compose up -d --force-recreate
```

停止服务：

```bash
make down
```

清理容器和卷后重新启动：

```bash
make clear
make up-build
```

查看服务状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs --tail=200
```

## 完整启动示例

### 1. 线上 API 模型

```bash
export LAZYLLM_SILICONFLOW_API_KEY=你的key
export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.yaml
export LAZYRAG_OCR_SERVER_TYPE=none

make up-build
```

如果 yaml 里同时引用了多个 provider 的 key，就把对应环境变量一并 export，变量名要和 yaml 中的占位符保持一致。

### 2. 内网已部署模型

使用新的内网 runtime 配置 + 本地 MinerU：

```bash
export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.inner.yaml
export LAZYRAG_OCR_SERVER_TYPE=mineru
export LAZYRAG_OCR_SERVER_URL=http://mineru:8000
export LAZYRAG_MINERU_BACKEND=pipeline
export LAZYRAG_MINERU_UPLOAD_MODE=true

make up-build
```

如果要复用 ECS / 内网已经部署好的 MinerU：

```bash
export LAZYRAG_MODEL_CONFIG_PATH=/app/chat/runtime_models.inner.yaml
export LAZYRAG_OCR_SERVER_TYPE=mineru
export LAZYRAG_OCR_SERVER_URL=http://your-inner-mineru:port
export LAZYRAG_MINERU_UPLOAD_MODE=true

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
