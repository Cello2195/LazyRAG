# Utility layer
# Contains helper functions and various definitions used in the chat flow.
# schema.py - Pydantic data definitions and data classes
# config.py - Configuration management, environment variables and constants
# helpers.py - Helper functions (including tool schema conversion, etc.)
# url.py - URL processing utilities
# stream_scanner.py - Streaming scan utilities

try:
    from chat.utils.schema import (
        BaseMessage, SessionMemory,
        MiddleResults, ToolMemory, ToolCall,
        PlanStep, TaskContext
    )
except Exception:  # pragma: no cover - lightweight test fallback
    BaseMessage = object
    SessionMemory = object
    MiddleResults = object
    ToolMemory = object
    ToolCall = object
    PlanStep = object
    TaskContext = object
try:
    from chat.config import URL_MAP, MAX_CONCURRENCY, LAZYRAG_LLM_PRIORITY
except Exception:  # pragma: no cover - lightweight test fallback
    URL_MAP = {}
    MAX_CONCURRENCY = 1
    LAZYRAG_LLM_PRIORITY = 0

try:
    from chat.utils.helpers import tool_schema_to_string
except Exception:  # pragma: no cover - lightweight test fallback
    def tool_schema_to_string(*_args, **_kwargs):
        return ''

__all__ = [
    'BaseMessage', 'SessionMemory',
    'MiddleResults', 'ToolMemory', 'ToolCall',
    'PlanStep', 'TaskContext',
    'URL_MAP', 'LAZYRAG_LLM_PRIORITY',
    'MAX_CONCURRENCY', 'tool_schema_to_string'
]
