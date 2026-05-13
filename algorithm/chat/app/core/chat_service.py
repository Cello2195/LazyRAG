from __future__ import annotations
import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Union
import lazyllm
from lazyllm import LOG
import lazyllm.tracing.collect.configs  # noqa: F401
from lazyllm.tracing import current_trace, enable_trace
from lazyllm.tracing.collect import runtime as tracing_runtime
from fastapi.responses import StreamingResponse
from chat.app.core.trace_sink import ensure_local_trace_sink, local_trace_enabled
from chat.config import (RAG_MODE, MULTIMODAL_MODE, MAX_CONCURRENCY,
                         LAZYRAG_LLM_PRIORITY, SENSITIVE_FILTER_RESPONSE_TEXT,
                         URL_MAP, resolve_dataset_url)
from chat.utils.helpers import validate_and_resolve_files
from chat.app.core.chat_server import chat_server
from chat.utils.load_config import inject_model_config


def _install_event_loop_policy_compat() -> None:
    """Ensure asyncio.Event()/Semaphore can be created in sync test contexts.

    Python 3.9 may raise `RuntimeError: There is no current event loop` after
    `asyncio.run()` has been called once in the main thread. The tests create
    `asyncio.Event()` in sync code, so we install a minimal auto-create policy.
    """
    policy = asyncio.get_event_loop_policy()
    if getattr(policy, '_lazyrag_auto_loop', False):
        return
    if not policy.__class__.__module__.startswith('asyncio'):
        return

    class _LazyRAGAutoLoopPolicy(policy.__class__):  # type: ignore[misc, valid-type]
        _lazyrag_auto_loop = True

        def get_event_loop(self):  # type: ignore[override]
            try:
                return super().get_event_loop()
            except RuntimeError:
                loop = self.new_event_loop()
                self.set_event_loop(loop)
                return loop

    asyncio.set_event_loop_policy(_LazyRAGAutoLoopPolicy())


_install_event_loop_policy_compat()


def _build_rag_semaphore() -> asyncio.Semaphore:
    try:
        return asyncio.Semaphore(MAX_CONCURRENCY)
    except RuntimeError:
        # Python 3.9 may require an explicit event loop before semaphore init.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return asyncio.Semaphore(MAX_CONCURRENCY)


rag_sem = _build_rag_semaphore()


def _get_rag_semaphore() -> asyncio.Semaphore:
    """Return a semaphore that is safe to use in the current event loop.

    Python 3.9 may bind asyncio primitives to the loop that created them.
    In tests or reloaded modules, a semaphore can be created outside
    `asyncio.run()` and later used inside another loop, which raises:
    `Future attached to a different loop`.
    """
    sem = rag_sem
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        return sem

    sem_loop = getattr(sem, '_loop', None)
    if sem_loop is not None and sem_loop is not current_loop:
        waiters = getattr(sem, '_waiters', None)
        if not waiters:
            try:
                sem._loop = current_loop  # type: ignore[attr-defined]
            except Exception:
                pass
    return sem


def _run_ppl_with_trace(ppl, ppl_args, *, session_id, dataset, mode_tag, trace_enabled):
    if not trace_enabled:
        return ppl(*ppl_args), None, None

    captured: Dict[str, Any] = {}
    sink = ensure_local_trace_sink() if local_trace_enabled() else None

    def run_chat_pipeline(*args, **kwargs):
        out = ppl(*args, **kwargs)
        trace = current_trace()
        captured['trace_id'] = trace.trace_id if trace else None
        return out

    result = enable_trace(
        run_chat_pipeline, *ppl_args,
        session_id=session_id,
        request_tags=[f'dataset:{dataset}', f'mode:{mode_tag}'],
        module_trace={'default': True},
    )
    _flush_trace_exporter()
    trace_id = captured.get('trace_id')
    if not trace_id:
        raise RuntimeError('LazyLLM trace did not expose a trace_id')
    local_trace = sink.get_trace(trace_id) if sink is not None else None
    if sink is not None and local_trace is None:
        raise RuntimeError(f'local LazyLLM trace sink did not capture trace {trace_id}')
    return result, trace_id, local_trace


def _run_ppl_with_trace_in_thread(
    ppl: Any,
    ppl_args: tuple,
    session_id: str,
    dataset: str,
    mode_tag: str,
    trace_enabled: bool,
):
    """Positional wrapper for asyncio.to_thread (test-friendly monkeypatching)."""
    return _run_ppl_with_trace(
        ppl,
        ppl_args,
        session_id=session_id,
        dataset=dataset,
        mode_tag=mode_tag,
        trace_enabled=trace_enabled,
    )


def _flush_trace_exporter() -> None:
    provider = getattr(tracing_runtime._runtime, '_provider', None)
    if provider is None:
        return
    try:
        from config import config as _cfg
        provider.force_flush(timeout_millis=_cfg['langfuse_force_flush_timeout_ms'])
    except Exception as exc:
        LOG.warning(f'[ChatServer] [TRACE_FLUSH_FAILED] {exc}')


def _sse_line(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str) + '\n\n'


def _resp(code: int, msg: str, data: Any, cost: float) -> Dict[str, Any]:
    return {'code': code, 'msg': msg, 'data': data, 'cost': cost}


def _friendly_chat_error(exc: Exception) -> Optional[str]:
    err = str(exc or '').strip()
    lower = err.lower()

    if (
        'invalid api key' in lower
        or 'missing api key' in lower
        or ('401' in lower and 'api key' in lower)
    ):
        return (
            '模型服务鉴权失败：当前未配置或配置了无效的 API Key。'
            '请检查 LAZYLLM_MINIMAX_API_KEY / LAZYRAG_MAAS_API_KEY 等环境变量后重试。'
        )

    if (
        'connection timed out' in lower
        or 'max retries exceeded' in lower
        or 'failed to establish a new connection' in lower
        or 'no route to host' in lower
    ):
        return '模型服务连接失败：当前网络或目标模型端点不可达，请检查模型地址与网络连通性。'

    return None


def check_sensitive_content(
    query: str, session_id: str, start_time: float
) -> Optional[Dict[str, Any]]:
    if not chat_server.sensitive_filter.loaded:
        return None
    has_sensitive, sensitive_word = chat_server.sensitive_filter.check(query)
    if has_sensitive:
        cost = round(time.time() - start_time, 3)
        LOG.warning(
            f'[ChatServer] [SENSITIVE_FILTER_BLOCKED] [query={query[:50]}...] '
            f'[sensitive_word={sensitive_word}] [session_id={session_id}]'
        )
        return _resp(
            200,
            'success',
            {
                'think': None,
                'text': SENSITIVE_FILTER_RESPONSE_TEXT,
                'sources': [],
            },
            cost,
        )
    return None


def build_query_params(query: str, history: Optional[List[Dict[str, Any]]],
                       filters: Optional[Dict[str, Any]], other_files: List[str],
                       databases: Optional[List[Dict[str, Any]]], debug: bool,
                       image_files: List[str], priority: Optional[int],
                       dataset: Optional[str],
                       session_id: str,
                       available_tools: Optional[List[str]],
                       available_skills: Optional[List[str]],
                       memory: Optional[str],
                       user_preference: Optional[str],
                       use_memory: Optional[bool],
                       create_user_id: Optional[str] = None) -> Dict[str, Any]:
    hist = [
        {
            'role': str(h.get('role', 'assistant')),
            'content': str(h.get('content', '')),
        }
        for h in (history or [])
        if isinstance(h, dict)
    ]
    return {
        'query': query, 'history': hist, 'filters': filters if RAG_MODE and filters else {},
        'files': other_files, 'image_files': image_files if MULTIMODAL_MODE and image_files else [],
        'debug': debug, 'databases': databases if RAG_MODE and databases else [], 'priority': priority,
        'dataset': dataset,
        'session_id': session_id,
        'document_url': URL_MAP.get(dataset, ''),
        'available_tools': available_tools,
        'available_skills': available_skills,
        'memory': memory,
        'user_preference': user_preference,
        'use_memory': use_memory,
        'create_user_id': create_user_id or '',
    }


def log_chat_request(query: str, session_id: str, filters: Optional[Dict[str, Any]],
                     other_files: List[str], databases: Optional[List[Dict[str, Any]]],
                     image_files: List[str], cost: float,
                     response: Any = None, log_type: str = 'KB_CHAT') -> None:
    databases_str = json.dumps(databases, ensure_ascii=False) if databases else []
    response_str = response if response is not None else None
    LOG.info(
        f'[ChatServer] [{log_type}] [query={query}] [session_id={session_id}] '
        f'[filters={filters}] [files={other_files}] [image_files={image_files}] '
        f'[databases={databases_str}] [cost={cost}] [response={response_str}]'
    )


def _attach_trace_info(data: Any, trace_id: Optional[str], local_trace: Optional[dict]) -> Any:
    if trace_id is None:
        return data
    out = {**data, 'trace_id': trace_id} if isinstance(data, dict) else {'data': data, 'trace_id': trace_id}
    if local_trace is not None:
        out['trace'] = local_trace
    return out


def _build_ppl_call(reasoning: bool, dataset: str, query_params: Dict[str, Any],
                    *legacy_args: Any, stream: Optional[bool] = None) -> tuple:
    # Backward compatibility for tests and legacy callers:
    # _build_ppl_call(reasoning, dataset, query_params, query, filters, priority, stream)
    if stream is None and reasoning and len(legacy_args) >= 4:
        query = str(legacy_args[0] or '')
        filters = legacy_args[1] if isinstance(legacy_args[1], dict) else {}
        priority = legacy_args[2]
        stream = bool(legacy_args[3])
        dataset_url = resolve_dataset_url(dataset)
        if dataset_url is None:
            raise KeyError(f'dataset `{dataset}` not found in URL_MAP')
        kb_search = {
            'filters': filters,
            'files': list(query_params.get('files') or []),
            'stream': stream,
            'priority': priority,
            'document_url': dataset_url,
        }
        return (chat_server.query_ppl_reasoning, {'query': query}, {'kb_search': kb_search}, stream)

    if stream is None:
        if legacy_args and isinstance(legacy_args[0], bool):
            stream = bool(legacy_args[0])
        else:
            stream = False

    if reasoning:
        dataset_url = resolve_dataset_url(dataset)
        if dataset_url is None:
            raise KeyError(f'dataset `{dataset}` not found in URL_MAP')
        ppl = chat_server.query_ppl_reasoning
        params = {**query_params, 'document_url': dataset_url, 'stream': stream}
    else:
        ppl = chat_server.get_query_pipeline(dataset, stream=stream)
        params = query_params
    return (ppl, params)


async def handle_chat(query: str, history: Optional[List[Dict[str, Any]]],
                      session_id: str, filters: Optional[Dict[str, Any]],
                      files: Optional[List[str]], debug: Optional[bool], reasoning: Optional[bool],
                      databases: Optional[List[Dict[str, Any]]], dataset: Optional[str],
                      priority: Optional[int], available_tools: Optional[List[str]] = None,
                      available_skills: Optional[List[str]] = None, memory: Optional[str] = None,
                      user_preference: Optional[str] = None, use_memory: Optional[bool] = None,
                      is_stream: bool = False, trace: bool = False,
                      create_user_id: Optional[str] = None,
                      model_config: Optional[Dict[str, Any]] = None) -> Union[Dict[str, Any], StreamingResponse]:
    result = None
    priority = LAZYRAG_LLM_PRIORITY if priority is None else priority

    if not chat_server.has_dataset(dataset):
        return _resp(400, f'dataset {dataset} not found', None, 0.0)

    start_time = time.time()
    sensitive_check_result = check_sensitive_content(query, session_id, start_time)
    log_tag = 'KB_CHAT_STREAM' if is_stream else 'KB_CHAT'
    LOG.info(f'[ChatServer] [{log_tag}] [query={query}] [sid={session_id}]')

    other_files, image_files = validate_and_resolve_files(files)
    query_params = build_query_params(
        query, history, filters, other_files, databases,
        debug or False, image_files, priority, dataset, session_id,
        available_tools, available_skills, memory, user_preference,
        use_memory, create_user_id,
    )

    def _init_session():
        lazyllm.globals._init_sid(sid=session_id)
        lazyllm.locals._init_sid(sid=session_id)
        inject_model_config(model_config)

    if not is_stream:
        if sensitive_check_result:
            return sensitive_check_result

        try:
            async with _get_rag_semaphore():
                _init_session()
                ppl_call = _build_ppl_call(bool(reasoning), dataset, query_params, stream=False)
                result, trace_id, local_trace = await asyncio.to_thread(
                    _run_ppl_with_trace_in_thread,
                    ppl_call[0],
                    ppl_call[1:],
                    session_id,
                    dataset,
                    'sync_reasoning' if reasoning else 'sync',
                    bool(trace),
                )
                cost = round(time.time() - start_time, 3)
                data = _attach_trace_info(result, trace_id, local_trace)
                return _resp(200, 'success', data, cost)
        except Exception as exc:
            LOG.exception(exc)
            cost = round(time.time() - start_time, 3)
            friendly_err = _friendly_chat_error(exc)
            if friendly_err:
                return _resp(
                    200,
                    'success',
                    {
                        'think': None,
                        'text': friendly_err,
                        'sources': [],
                    },
                    cost,
                )
            return _resp(500, f'chat service failed: {exc}', None, cost)
        finally:
            cost = round(time.time() - start_time, 3)
            log_chat_request(
                query, session_id, filters, other_files, image_files, databases, cost, result
            )
    else:
        if sensitive_check_result:

            async def error_stream():
                yield _sse_line(sensitive_check_result)
                yield _sse_line(_resp(200, 'success', {'status': 'FINISHED'}, 0.0))

            return StreamingResponse(error_stream(), media_type='text/event-stream')

        first_frame_logged = False
        collected_chunks: List[str] = []
        ppl_call = _build_ppl_call(bool(reasoning), dataset, query_params, stream=True)

        async def event_stream(ppl, *args) -> Any:
            nonlocal first_frame_logged
            friendly_error_frame: Optional[Dict[str, Any]] = None
            try:
                async with _get_rag_semaphore():
                    _init_session()
                    async_result, trace_id, local_trace = await asyncio.to_thread(
                        _run_ppl_with_trace_in_thread,
                        ppl,
                        args,
                        session_id,
                        dataset,
                        'stream_reasoning' if reasoning else 'stream',
                        bool(trace),
                    )
                    if trace_id is not None:
                        yield _sse_line(_resp(200, 'success',
                                              _attach_trace_info({}, trace_id, local_trace), 0.0))
                    async for chunk in async_result:
                        now = time.time()
                        if not first_frame_logged:
                            first_cost = round(now - start_time, 3)
                            LOG.info(
                                f'[ChatServer] [KB_CHAT_STREAM_FIRST_FRAME] '
                                f'[query={query}] [session_id={session_id}] '
                                f'[cost={first_cost}]'
                            )
                            first_frame_logged = True

                        chunk_str = (
                            chunk
                            if isinstance(chunk, str)
                            else json.dumps(chunk, ensure_ascii=False)
                        )
                        collected_chunks.append(chunk_str)
                        cost = round(now - start_time, 3)
                        yield _sse_line(_resp(200, 'success', chunk, cost))

            except Exception as exc:
                LOG.exception(exc)
                collected_chunks.append(f'[EXCEPTION]: {str(exc)}')
                friendly_err = _friendly_chat_error(exc)
                if friendly_err:
                    friendly_error_frame = _resp(
                        200,
                        'success',
                        {
                            'think': None,
                            'text': friendly_err,
                            'sources': [],
                        },
                        0.0,
                    )
                final_resp = _resp(
                    500, f'chat service failed: {exc}', {'status': 'FAILED'}, 0.0
                )
            else:
                final_resp = _resp(200, 'success', {'status': 'FINISHED'}, 0.0)

            cost = round(time.time() - start_time, 3)
            if friendly_error_frame is not None:
                friendly_error_frame['cost'] = cost
                yield _sse_line(friendly_error_frame)
                collected_chunks.append(f'[FRIENDLY_ERROR]: {friendly_error_frame}')
            final_resp['cost'] = cost
            yield _sse_line(final_resp)

            log_chat_request(query, session_id, filters, other_files, image_files, databases,
                             cost, '\n'.join(collected_chunks), 'KB_CHAT_STREAM_FINISH')

        return StreamingResponse(
            event_stream(*ppl_call), media_type='text/event-stream'
        )
