"""Helpers for converting the shared PostgreSQL URL into LazyLLM SqlManager db_config."""
import os
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

from psycopg2 import connect
from psycopg2.extensions import connection as PGConnection


SHARED_DB_ENV_KEY = 'LAZYRAG_DATABASE_URL'


def parse_db_url(url: Optional[str]) -> Optional[Dict[str, Any]]:
    """Convert postgresql+psycopg://user:password@host:port/dbname into SqlManager kwargs."""
    if not url or not url.strip():
        return None
    try:
        u = urlparse(url)
        db_type = (u.scheme or 'postgresql').split('+')[0]
        if db_type != 'postgresql':
            raise ValueError(f'unsupported database scheme: {u.scheme or db_type}')
        if not u.hostname:
            raise ValueError('database host is required')
        return {
            'db_type': 'postgresql',
            'user': unquote(u.username) if u.username else '',
            'password': unquote(u.password) if u.password else '',
            'host': u.hostname or '',
            'port': u.port or 5432,
            'db_name': (u.path or '/').lstrip('/') or 'app',
        }
    except (AttributeError, TypeError) as exc:
        raise ValueError('invalid database url') from exc


def get_shared_database_url() -> Optional[str]:
    """Return the shared PostgreSQL URL configured by docker-compose."""
    value = os.getenv(SHARED_DB_ENV_KEY)
    return value if value and value.strip() else None


def get_shared_db_config() -> Optional[Dict[str, Any]]:
    """Get db_config for DocServer / DocumentProcessor / Worker from the shared DB env."""
    database_url = get_shared_database_url()
    return parse_db_url(database_url) if database_url else None


def require_shared_db_config(service_name: str) -> Dict[str, Any]:
    """Return shared db_config or raise a clear error when it is missing."""
    database_url = get_shared_database_url()
    if database_url is None:
        raise RuntimeError(
            f'{service_name} requires a shared database configuration. '
            f'Set {SHARED_DB_ENV_KEY} to a valid PostgreSQL URL.'
        )
    try:
        db_config = parse_db_url(database_url)
    except ValueError as exc:
        raise RuntimeError(
            f'{service_name} requires a valid PostgreSQL URL in {SHARED_DB_ENV_KEY}: {exc}'
        ) from exc
    if db_config is None:
        raise RuntimeError(
            f'{service_name} requires a shared database configuration. '
            f'Set {SHARED_DB_ENV_KEY} to a valid PostgreSQL URL.'
        )
    return db_config


def get_doc_task_db_config() -> Optional[Dict[str, Any]]:
    """Backward-compatible alias for the shared database config."""
    return get_shared_db_config()


def _connect_postgres(db_config: Dict[str, Any]) -> PGConnection:
    return connect(
        dbname=db_config.get('db_name') or 'app',
        user=db_config.get('user') or '',
        password=db_config.get('password') or '',
        host=db_config.get('host') or 'localhost',
        port=int(db_config.get('port') or 5432),
    )


def ensure_parsing_service_schema_compat(db_config: Dict[str, Any], *, service_name: str = 'DocumentProcessor') -> None:
    """Apply lightweight forward-compatible schema patches for LazyLLM parsing tables.

    New LazyLLM builds read ``lazyllm_algorithm.node_group_ids``. Older deployments
    may have tables created before this column existed, causing startup failure.
    """
    if not db_config:
        return
    conn: Optional[PGConnection] = None
    try:
        conn = _connect_postgres(db_config)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'lazyllm_algorithm'
                    ) THEN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'lazyllm_algorithm'
                              AND column_name = 'node_group_ids'
                        ) THEN
                            ALTER TABLE public.lazyllm_algorithm
                            ADD COLUMN node_group_ids TEXT DEFAULT '[]';
                        END IF;
                    END IF;
                END $$;
                """
            )
    except Exception as exc:
        # Non-fatal: keep startup behavior, but make root cause explicit.
        print(f'[{service_name}] schema compatibility check failed: {exc}')
    finally:
        if conn is not None:
            conn.close()
