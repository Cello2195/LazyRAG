from __future__ import annotations

# ruff: noqa: E402

import asyncio
import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Dict, Mapping, Optional

import lazyllm
from lazyllm import loop, once_wrapper
from lazyllm.tools.agent.functionCall import FunctionCall
from lazyllm.tools.fs.client import FS
from lazyllm.tools.sandbox.sandbox_base import create_sandbox  # noqa: F401

from config import config as _cfg


from chat.components.agentic.config import (  # noqa: E402
    _augment_skills_for_request,
    _build_runtime_system_prompt,
    _filter_tools_for_request,
    _get_runtime_agent_defaults,
    _normalize_available_skills,
    _normalize_available_tools,
    _sync_request_context,
)
from chat.components.lclm.detector import normalize_lclm_mode, should_use_lclm  # noqa: E402
from chat.components.agentic.history import (  # noqa: E402
    _build_stream_citation_scanner,
    _count_tool_turns,
    _count_user_turns,
    _format_non_stream_result,
    _normalize_history_for_agent,
    _reset_citation_state,
)
from chat.components.agentic.review import (  # noqa: E402
    _build_review_decision,
    _spawn_background_review,
)
from chat.components.agentic.tool_stream import (  # noqa: E402
    _STREAM_CHUNK_SIZE,
    _format_tool_stream_frame,
    _iter_text_chunks,
    _normalize_tool_call,
    _stream_frame,
    _tool_call_id,
)
from lazyllm import AutoModel  # noqa: E402


class _StreamingFunctionCall(FunctionCall):
    def __init__(self, *args: Any, stream_event_callback=None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._stream_event_callback = stream_event_callback
        self._round_index = 0

    def _post_action(self, llm_output: Dict[str, Any]):
        self._round_index += 1
        if (
            isinstance(llm_output, dict)
            and not llm_output.get('tool_calls')
            and isinstance(llm_output.get('content'), str)
        ):
            match = re.search(
                r'Action:\s*Call\s+(\w+)\s+with\s+parameters\s+(\{.*?\})',
                llm_output['content'],
            )
            if match:
                try:
                    llm_output['tool_calls'] = [{
                        'type': 'function',
                        'function': {
                            'name': match.group(1),
                            'arguments': json.loads(match.group(2)),
                        },
                    }]
                except json.JSONDecodeError:
                    pass
        tool_calls = []
        if isinstance(llm_output, dict):
            for idx, tc in enumerate((llm_output.get('tool_calls') or []), start=1):
                if not isinstance(tc, dict):
                    continue
                normalized_tool_call = _normalize_tool_call(tc)
                normalized_tool_call['id'] = _tool_call_id(
                    normalized_tool_call, self._round_index, idx
                )
                tool_calls.append(normalized_tool_call)
            if tool_calls:
                llm_output['tool_calls'] = [
                    {
                        'id': tool_call['id'],
                        'type': 'function',
                        'function': {
                            'name': tool_call.get('name', ''),
                            'arguments': json.dumps(
                                tool_call.get('arguments', {}),
                                ensure_ascii=False,
                            ),
                        },
                    }
                    for tool_call in tool_calls
                ]

        if self._stream_event_callback and isinstance(llm_output, dict) and tool_calls:
            self._stream_event_callback({
                'round': self._round_index,
                'content': llm_output.get('content', ''),
                'tool_calls': tool_calls,
                'tool_results': [],
            })

        result = super()._post_action(llm_output)

        if self._stream_event_callback and isinstance(llm_output, dict) and tool_calls:
            tool_call_trace = (
                lazyllm.locals.get('_lazyllm_agent', {})
                .get('workspace', {})
                .get('tool_call_trace', [])
            )
            self._stream_event_callback({
                'round': self._round_index,
                'content': '',
                'tool_calls': [],
                'tool_results': [
                    {
                        'id': tool_call.get('id', ''),
                        'tool_name': tool_call.get('name', ''),
                        'result': tool_trace.get('tool_call_result'),
                    }
                    for tool_call, tool_trace in zip(tool_calls, tool_call_trace)
                    if isinstance(tool_trace, dict)
                ],
            })
        return result


class _StreamingReactAgent(lazyllm.tools.agent.ReactAgent):
    def __init__(self, *args: Any, stream_event_callback=None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._stream_event_callback = stream_event_callback

    @once_wrapper(reset_on_pickle=True)
    def build_agent(self):
        agent = loop(
            _StreamingFunctionCall(
                llm=self._llm,
                _prompt=self._prompt,
                return_trace=self._return_trace,
                stream=self._stream,
                _tool_manager=self._tools_manager,
                skill_manager=self._skill_manager,
                workspace=self.workspace,
                keep_full_turns=self._keep_full_turns,
                stream_event_callback=self._stream_event_callback,
            ),
            stop_condition=lambda x: isinstance(x, str),
            count=20,
        )
        self._agent = agent


def agentic_forward(
    query: str,
    history: list[dict[str, Any]],
    stream_event_callback=None,
) -> Any:
    config = lazyllm.globals['agentic_config'] or {}
    logger = getattr(lazyllm, 'LOG', None)
    log_warning = getattr(logger, 'warning', None) or getattr(logger, 'info', None)
    if callable(log_warning):
        log_warning(f'config: {config}')
    if not isinstance(config, dict):
        config = {}

    try:
        from chat.utils.load_config import get_config_path
        model_config_path = get_config_path()
    except Exception:
        model_config_path = False
    llm = AutoModel(model='llm', config=model_config_path)
    available_tools = _filter_tools_for_request(
        _normalize_available_tools(config.get('available_tools')),
        config,
    )
    available_skills = _normalize_available_skills(config.get('available_skills'))
    available_skills = _augment_skills_for_request(
        available_skills,
        query=query,
        available_tools=available_tools,
    )
    skills_dir = config.get('skill_fs_url') or ''
    config['available_tools'] = available_tools
    config['available_skills'] = available_skills

    keep_full_turns = config.get('keep_full_turns', 3)
    runtime_prompt = _build_runtime_system_prompt(config, available_tools)
    agent_cls = _StreamingReactAgent if stream_event_callback else lazyllm.tools.agent.ReactAgent
    agent_kwargs = {
        'llm': llm,
        'tools': available_tools,
        'max_retries': _cfg['max_retries'],
        'return_trace': config.get('return_trace', False),
        'stream': bool(stream_event_callback),
        'prompt': runtime_prompt,
        'skills': available_skills,
        'workspace': config.get('workspace', './workspace'),
        'keep_full_turns': keep_full_turns,
        'fs': FS,
        'skills_dir': skills_dir,
        'enable_builtin_tools': False,
        'force_summarize': True,
        'force_summarize_context': query,
    }
    if stream_event_callback:
        agent_kwargs['stream_event_callback'] = stream_event_callback

    react_agent = agent_cls(
        **agent_kwargs,
    )

    request_global_sid = lazyllm.globals._sid
    lazyllm.globals['agentic_config'] = config
    agent_output = react_agent(query, llm_chat_history=history)
    agent_history = lazyllm.locals.get('_lazyllm_agent', {}).get('history', [])
    history_snapshot = agent_history
    if runtime_prompt and (not history_snapshot or history_snapshot[0].get('role') != 'system'):
        history_snapshot = (
            [{'role': 'system', 'content': runtime_prompt}]
            + history_snapshot
            + [{'role': 'assistant', 'content': agent_output}]
        )
    tool_turns = _count_tool_turns(agent_history)
    user_turns = _count_user_turns(history, query)
    memory_review_interval = _cfg['memory_review_interval']
    skill_review_interval = _cfg['skill_review_interval']
    review_decision = _build_review_decision(
        available_tools=available_tools,
        tool_turns=tool_turns,
        user_turns=user_turns,
        memory_review_interval=memory_review_interval,
        skill_review_interval=skill_review_interval,
    )
    print(
        '[bg-review] DECISION '
        f"mode={review_decision.get('mode')} "
        f"memory_due={review_decision.get('memory_due')} "
        f"skill_due={review_decision.get('skill_due')} "
        f"skill_due_by_tool_turns={review_decision.get('skill_due_by_tool_turns')} "
        f"skill_due_by_user_turns={review_decision.get('skill_due_by_user_turns')} "
        f"debug_force_combined={review_decision.get('debug_force_combined')} "
        f'tool_turns={tool_turns} user_turns={user_turns} '
        f'memory_interval={memory_review_interval} skill_interval={skill_review_interval} '
        f'available_tools={available_tools}'
    )
    review_mode = review_decision['mode']
    if review_mode is not None:
        _spawn_background_review(
            config=config,
            llm=llm,
            keep_full_turns=keep_full_turns,
            history_snapshot=history_snapshot,
            review_mode=review_mode,
            request_global_sid=request_global_sid,
        )

    return agent_output


def _lazyllm_queue_db_path() -> Path:
    try:
        from lazyllm.configs import config
        home = Path(os.path.expanduser(config['home']))
    except Exception:
        home = Path(os.path.expanduser('~/.lazyllm_rag'))
    return home / '.lazyllm_filesystem_queue.db'


def _clear_orphaned_lazyllm_queue_lock() -> None:
    db_path = _lazyllm_queue_db_path()
    lock_path = Path(f'{db_path}.lock')
    if lock_path.exists() and not db_path.exists():
        lock_path.unlink(missing_ok=True)


async def _agentic_forward_stream(
    query: str,
    history: list[dict[str, Any]],
    runtime_params: dict[str, Any],
    global_sid: str,
    local_sid: str,
):
    event_queue: Queue = Queue()
    sentinel = object()
    closed = threading.Event()
    streamed_text = False
    text_scanner, citation_plugin = _build_stream_citation_scanner(runtime_params)

    lazyllm.globals._init_sid(global_sid)
    lazyllm.locals._init_sid(local_sid)
    _clear_orphaned_lazyllm_queue_lock()
    lazyllm.FileSystemQueue().clear()
    lazyllm.FileSystemQueue.get_instance('think').clear()

    def _emit_event(event: dict[str, Any]) -> None:
        if not closed.is_set():
            event_queue.put({'type': 'tool_event', 'event': event})

    def _drain_stream_frames() -> list[dict[str, Any]]:
        nonlocal streamed_text
        frames: list[dict[str, Any]] = []

        think_values = lazyllm.FileSystemQueue.get_instance('think').dequeue()
        if think_values:
            think_text = ''.join(think_values)
            if think_text:
                frames.append(_stream_frame(think=think_text))

        text_values = lazyllm.FileSystemQueue().dequeue()
        if text_values:
            text = ''.join(text_values)
            if text:
                for field, seg in text_scanner.feed(text):
                    if not seg:
                        continue
                    if field == 'think':
                        frames.append(_stream_frame(think=seg))
                    else:
                        streamed_text = True
                        frames.append(_stream_frame(text=seg))

        return frames

    def _worker() -> None:
        lazyllm.globals._init_sid(global_sid)
        lazyllm.locals._init_sid(local_sid)
        lazyllm.globals['agentic_config'] = runtime_params
        try:
            result = agentic_forward(
                query=query,
                history=history,
                stream_event_callback=_emit_event,
            )
            if not closed.is_set():
                event_queue.put({'type': 'final', 'result': result})
        except Exception as exc:
            if not closed.is_set():
                event_queue.put(exc)
        finally:
            if not closed.is_set():
                event_queue.put(sentinel)

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()
    final_result = None
    try:
        while True:
            for frame in _drain_stream_frames():
                yield frame

            try:
                event = await asyncio.to_thread(event_queue.get, True, 0.05)
            except Empty:
                continue

            if event is sentinel:
                break
            if isinstance(event, Exception):
                raise event
            if isinstance(event, dict) and event.get('type') == 'final':
                final_result = event.get('result')
            elif isinstance(event, dict) and event.get('type') == 'tool_event':
                for frame in _drain_stream_frames():
                    yield frame
                tool_event = event.get('event') or {}
                frame = _format_tool_stream_frame(tool_event)
                if frame is None:
                    continue
                yield frame

        for frame in _drain_stream_frames():
            yield frame
        for field, seg in text_scanner.flush():
            if not seg:
                continue
            if field == 'think':
                yield _stream_frame(think=seg)
            else:
                streamed_text = True
                yield _stream_frame(text=seg)

        output = _format_non_stream_result(final_result, runtime_params)
        chunk_size = int(runtime_params.get('stream_chunk_size') or _STREAM_CHUNK_SIZE)
        if not streamed_text:
            think = str(output.get('think') or '')
            if think:
                for chunk in _iter_text_chunks(think, chunk_size):
                    yield _stream_frame(think=chunk)
            for chunk in _iter_text_chunks(str(output.get('text') or ''), chunk_size):
                yield _stream_frame(
                    text=chunk,
                )

        sources = output.get('sources') or citation_plugin.collect()
        if sources:
            yield _stream_frame(
                text='',
                sources=sources,
            )
    finally:
        closed.set()
        worker.join(timeout=0)


def _ensure_tools_registered() -> None:
    # Trigger @fc_register side effects once so ReactAgent can resolve tool names.
    from chat.tools import kb, memory, pptx, html_deck, skill_manager, web_search  # noqa: F401


def _log_lclm_exception(message: str, exc: Exception) -> None:
    logger = getattr(lazyllm, 'LOG', None)
    fn = getattr(logger, 'exception', None) or getattr(logger, 'error', None) or getattr(logger, 'info', None)
    if callable(fn):
        fn(f'{message}: {exc}')


def merge_lclm_runtime_params(
    query_params: Optional[Dict[str, Any]],
    kwargs: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    runtime_params: dict[str, Any] = {}
    if isinstance(query_params, dict):
        runtime_params.update(query_params)
    if isinstance(kwargs, dict):
        runtime_params.update(kwargs)

    filters = runtime_params.get('filters')
    if isinstance(filters, dict):
        for key, value in filters.items():
            if isinstance(key, str) and key.startswith('lclm_'):
                runtime_params[key] = value
    return runtime_params


def _log_lclm_runtime_params(runtime_params: Mapping[str, Any]) -> None:
    logger = getattr(lazyllm, 'LOG', None)
    fn = getattr(logger, 'info', None)
    if not callable(fn):
        return
    for key in (
        'lclm_mode',
        'lclm_use_llm',
        'lclm_max_outline_nodes',
        'lclm_max_depth',
        'lclm_node_evidence_topk',
        'lclm_enable_evidence',
        'lclm_enable_arxiv',
        'lclm_enable_web',
        'lclm_max_repair_rounds',
        'lclm_save_artifact',
    ):
        if key in runtime_params:
            fn(f'[LCLM] runtime {key}={runtime_params.get(key)}')


@lru_cache(maxsize=1)
def _get_cwd() -> str:
    return str(Path.cwd())


def get_ppl_agentic():
    return agentic_rag


def _run_lclm_pipeline(
    *,
    query: str,
    history: list[dict[str, Any]],
    runtime_params: dict[str, Any],
    progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    from chat.components.lclm.pipeline import run_outline_longform

    result = run_outline_longform(
        query=query,
        history=history,
        runtime_params=runtime_params,
        progress_callback=progress_callback,
    )
    return result if isinstance(result, dict) else {'text': str(result or '')}


def _lclm_progress_text(event: Mapping[str, Any], elapsed_sec: float) -> str:
    text = str(event.get('text') or '').strip()
    if text:
        return text
    stage = str(event.get('stage') or '').strip().lower()
    if stage == 'planning_start':
        return '正在规划大纲...'
    if stage == 'planning_end':
        nodes = event.get('outline_nodes')
        if isinstance(nodes, int) and nodes > 0:
            return f'已完成大纲规划，共 {nodes} 个章节。'
        return '已完成大纲规划。'
    if stage == 'evidence_start':
        return '正在检索章节证据...'
    if stage == 'evidence_end':
        return '章节证据检索完成。'
    if stage == 'writer_start':
        return '正在撰写章节内容...'
    if stage == 'writer_end':
        return '章节撰写完成。'
    if stage == 'compose_start':
        return '正在合成全文...'
    if stage == 'compose_end':
        return '全文合成完成。'
    if stage == 'artifact_saving':
        return '正在保存可下载文件...'
    if stage == 'artifact_saved':
        return '文件已生成，正在返回下载链接...'
    if stage == 'done':
        return '长文本生成完成。'
    elapsed = int(max(0.0, elapsed_sec))
    return f'正在生成长文本，请稍候...（已耗时约 {elapsed} 秒）'


def _safe_text_chunk(text: Any, fallback: str) -> str:
    chunk = str(text or '').strip()
    return chunk if chunk else fallback


async def _lclm_forward_stream(
    *,
    query: str,
    history: list[dict[str, Any]],
    runtime_params: dict[str, Any],
    global_sid: str,
    local_sid: str,
):
    lclm_mode = normalize_lclm_mode(runtime_params.get('lclm_mode'))
    heartbeat_raw = runtime_params.get('lclm_stream_heartbeat_sec')
    try:
        heartbeat_sec = int(heartbeat_raw)
    except Exception:
        heartbeat_sec = 15
    heartbeat_sec = max(5, min(30, heartbeat_sec))

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    start_ts = loop.time()

    def _publish_event(payload: dict[str, Any]) -> None:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, payload)
        except Exception:
            return

    def _progress_callback(event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        _publish_event({'type': 'progress', 'payload': dict(event)})

    worker = asyncio.create_task(
        asyncio.to_thread(
            _run_lclm_pipeline,
            query=query,
            history=history,
            runtime_params=runtime_params,
            progress_callback=_progress_callback,
        )
    )
    try:
        lazyllm.globals._init_sid(global_sid)
        lazyllm.locals._init_sid(local_sid)
        lazyllm.globals['agentic_config'] = runtime_params
        yield _stream_frame(
            think='LCLM workflow started',
            text='正在启动长文本生成流程...',
            extra={'finish_reason': 'FINISH_REASON_UNSPECIFIED'},
        )

        final_result: Optional[dict[str, Any]] = None
        while True:
            if worker.done():
                result = await worker
                if isinstance(result, dict):
                    final_result = result
                else:
                    final_result = {'text': str(result or '')}
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_sec)
            except asyncio.TimeoutError:
                elapsed = loop.time() - start_ts
                yield _stream_frame(
                    think='LCLM workflow in progress',
                    text=f'正在生成长文本，请稍候...（已耗时约 {int(elapsed)} 秒）',
                    extra={'finish_reason': 'FINISH_REASON_UNSPECIFIED'},
                )
                continue
            if not isinstance(item, dict):
                continue
            if item.get('type') != 'progress':
                continue
            event = item.get('payload')
            if not isinstance(event, dict):
                continue
            elapsed = loop.time() - start_ts
            progress_text = _lclm_progress_text(event, elapsed)
            yield _stream_frame(
                think='LCLM workflow in progress',
                text=_safe_text_chunk(progress_text, '正在生成长文本，请稍候...'),
                extra={
                    'lclm_progress': event,
                    'finish_reason': 'FINISH_REASON_UNSPECIFIED',
                },
            )

        output = _format_non_stream_result(final_result or {}, runtime_params)
        final_think = str(output.get('think') or 'LCLM workflow completed').strip() or 'LCLM workflow completed'
        final_text = str(output.get('text') or '').strip()
        final_sources = output.get('sources') or []

        extra: dict[str, Any] = {}
        for key in ('artifact', 'download_link', 'download_url', 'lclm', 'preview_url'):
            if key in output and output.get(key) is not None:
                extra[key] = output.get(key)

        if not final_text:
            title = ''
            lclm_meta = output.get('lclm')
            if isinstance(lclm_meta, dict):
                title = str(lclm_meta.get('title') or '').strip()
            download_link = str(output.get('download_link') or output.get('download_url') or '').strip()
            lines = ['已生成长文本报告。']
            if title:
                lines.append(f'标题：{title}')
            if download_link:
                lines.append(f'下载：[点击下载]({download_link})')
            lines.append('下面是正文预览：')
            lines.append('请通过下载链接查看完整内容。')
            final_text = '\n'.join(lines)

        final_text = _safe_text_chunk(final_text, '已生成长文本结果，请查看下载链接。')
        yield _stream_frame(
            think=final_think,
            text=final_text,
            sources=final_sources,
            extra={
                **extra,
                'finish_reason': 'FINISH_REASON_STOP',
            },
        )
    except Exception as exc:
        _log_lclm_exception('[LCLM] stream pipeline failed', exc)
        if lclm_mode == 'force':
            raise
        async for frame in _agentic_forward_stream(
            query=query,
            history=history,
            runtime_params=runtime_params,
            global_sid=global_sid,
            local_sid=local_sid,
        ):
            yield frame
    finally:
        if not worker.done():
            worker.cancel()


def agentic_rag(
    global_params: Dict[str, Any],
    tool_params: Optional[Dict[str, Any]] = None,
    stream: bool = False,
    **kwargs: Any,
) -> Any:
    _ensure_tools_registered()

    query = (global_params or {}).get('query', '')
    if not isinstance(query, str) or not query.strip():
        raise ValueError('query is required')

    runtime_params = merge_lclm_runtime_params(_get_runtime_agent_defaults(), global_params or {})
    runtime_params = merge_lclm_runtime_params(runtime_params, kwargs)
    # stream can be passed either as a function arg or inside global_params dict
    stream = stream or bool(runtime_params.get('stream', False))
    runtime_params['stream'] = stream
    _sync_request_context(runtime_params)
    _reset_citation_state(runtime_params)
    _log_lclm_runtime_params(runtime_params)

    history = (global_params or {}).get('history') or []
    if not isinstance(history, list):
        history = []
    history = _normalize_history_for_agent(history, runtime_params)

    lazyllm.globals['agentic_config'] = runtime_params

    use_lclm, lclm_reason = should_use_lclm(query, runtime_params)
    runtime_params['lclm_decision'] = lclm_reason
    if use_lclm:
        lclm_mode = normalize_lclm_mode(runtime_params.get('lclm_mode'))
        if not stream:
            try:
                lclm_result = _run_lclm_pipeline(
                    query=query.strip(),
                    history=history,
                    runtime_params=runtime_params,
                )
                return _format_non_stream_result(lclm_result, runtime_params)
            except Exception as exc:
                _log_lclm_exception('[LCLM] non-stream pipeline failed', exc)
                if lclm_mode == 'force':
                    raise
                result = agentic_forward(query=query.strip(), history=history)
                return _format_non_stream_result(result, runtime_params)
        return _lclm_forward_stream(
            query=query.strip(),
            history=history,
            runtime_params=runtime_params,
            global_sid=lazyllm.globals._sid,
            local_sid=lazyllm.locals._sid,
        )

    if not stream:
        result = agentic_forward(query=query.strip(), history=history)
        return _format_non_stream_result(result, runtime_params)

    return _agentic_forward_stream(
        query=query.strip(),
        history=history,
        runtime_params=runtime_params,
        global_sid=lazyllm.globals._sid,
        local_sid=lazyllm.locals._sid,
    )
