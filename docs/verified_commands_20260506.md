# LazyRAG 可执行命令（已实测）

验证日期：2026-05-06  
验证机器：`/home/mnt/xiongyida`  
说明：以下命令均已在本机实跑，包含通过项与已知失败项。

## 0) 进入环境

```bash
source /home/mnt/xiongyida/project/agentic_rag/.venv/bin/activate
cd /home/mnt/xiongyida/project/LazyRAG
python -V
```

实测结果：通过（Python 3.10.9）

## 1) 安装本次测试所需最小依赖

```bash
/home/mnt/xiongyida/project/agentic_rag/.venv/bin/python -m pip install pytest -q
cd /home/mnt/xiongyida/project/LazyRAG
python -m pip install -r backend/auth-service/requirements.txt -r tests/backend/auth-service/requirements-test.txt -q
python -m pip install python-multipart python-dotenv jsonschema scikit-learn -q
```

实测结果：通过

## 2) CLI 可用性检查

```bash
cd /home/mnt/xiongyida/project/LazyRAG
./lazyrag --help
./lazyrag status --json
./lazyrag config list --json
```

实测结果：通过（命令可正常执行并返回 JSON）

## 3) 主要功能测试（已通过）

建议先关闭自动加载插件（避免沙箱里 pytest 插件建 socket 失败）：

```bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
```

### 3.1 CLI 单测（覆盖注册/登录/建库/上传/检索等命令逻辑）

```bash
python -m pytest tests/test_cli.py -q
```

实测结果：`84 passed`

### 3.2 auth-service 核心能力

```bash
python -m pytest tests/backend/auth-service/core -q --import-mode=importlib
python -m pytest tests/backend/auth-service/services/test_auth_service.py -q --import-mode=importlib
python -m pytest tests/backend/auth-service/test_schemas.py -q --import-mode=importlib
```

实测结果：`39 passed` + `6 passed` + `19 passed`

### 3.3 algorithm/processor（文档处理主流程单测）

```bash
python -m pytest tests/algorithm/processor -q
```

实测结果：`66 passed, 1 failed`  
唯一失败用例：`tests/algorithm/processor/test_worker.py::test_worker_constructs_document_processor_worker_from_env`

### 3.4 algorithm/chat 健康路由

```bash
python -m pytest tests/algorithm/chat/test_chat_api_health_routes.py -q
```

实测结果：`2 passed`

### 3.5 文档检查

```bash
python -m pytest tests/doc_check/test_docs.py -q
```

实测结果：`2 passed`

## 4) 已知失败/受限项（本机实测）

### 4.1 整体容器栈无法在当前机器验证

```bash
docker --version
docker compose version
```

实测结果：失败（本机无 `docker` 命令）

### 4.2 auth-service 部分测试存在断言/执行问题

```bash
python -m pytest tests/backend/auth-service/test_models.py -q --import-mode=importlib
python -m pytest tests/backend/auth-service/test_repositories.py -q --import-mode=importlib
python -m pytest tests/backend/auth-service/test_services.py -q --import-mode=importlib
```

实测结果：均有失败（主要是 `__all__` 导出断言与当前代码不一致）

### 4.3 evo 测试大量失败（代码与测试/数据约定不一致）

```bash
python -m pytest tests/evo -q
```

实测结果：大量失败（例如缺 `evo/data/eval_mock.json`，以及结构化调用签名与测试 stub 不一致）

### 4.4 algorithm/chat 大部分测试依赖当前 LazyLLM 版本不满足

```bash
python -m pytest tests/algorithm/chat -q
```

实测结果：大量失败（典型报错：`No module named lazyllm.tools.fs.client`）

## 5) 你在有 Docker 的机器上可执行的全栈启动命令（未在本机验证）

```bash
cd /home/mnt/xiongyida/project/LazyRAG
make up-build
docker compose ps
```

说明：这是项目官方启动路径；当前这台机器因缺少 Docker 无法实测该部分。
