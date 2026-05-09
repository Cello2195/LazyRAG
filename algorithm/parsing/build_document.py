import os
import inspect
from urllib.parse import urlparse

from lazyllm.tools.rag import Document, MineruPDFReader, PDFReader
from lazyllm.tools.rag.doc_impl import NodeGroupType
from lazyllm.tools.rag.parsing_service import DocumentProcessor
from lazyllm.tools.rag.readers import PaddleOCRPDFReader

from chat.pipelines.builders.get_models import get_automodel
from chat.utils.load_config import get_retrieval_settings
from parsing.transform import GeneralParser, LineSplitter

ALGO_ID = 'general_algo'


def _parse_bool_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip().lower()
    if value == '':
        return None
    if value in ('1', 'true', 'yes', 'on'):
        return True
    if value in ('0', 'false', 'no', 'off'):
        return False
    raise ValueError(f'{name} must be a boolean string, got: {value!r}')


def _default_mineru_upload_mode(ocr_url: str) -> bool:
    hostname = (urlparse(ocr_url).hostname or '').lower()
    # Only the in-network MinerU service can resolve the same container path.
    return hostname != 'mineru'


def get_algo_server_port() -> int:
    return int(os.getenv('LAZYRAG_ALGO_SERVER_PORT', os.getenv('LAZYRAG_DOCUMENT_SERVER_PORT', '8000')))


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f'{name} is required')
    return value


def _build_store_config(index_kwargs):
    milvus_uri = _require_env('LAZYRAG_MILVUS_URI')
    opensearch_uri = _require_env('LAZYRAG_OPENSEARCH_URI')
    return {
        'vector_store': {
            'type': 'milvus',
            'kwargs': {
                'uri': milvus_uri,
                'index_kwargs': index_kwargs,
            },
        },
        'segment_store': {
            'type': 'opensearch',
            'kwargs': {
                'uris': opensearch_uri,
                'client_kwargs': {
                    'http_compress': True,
                    'use_ssl': True,
                    'verify_certs': False,
                    'user': os.getenv('LAZYRAG_OPENSEARCH_USER', 'admin'),
                    'password': os.getenv('LAZYRAG_OPENSEARCH_PASSWORD', 'LazyRAG_OpenSearch123!'),
                },
            },
        },
    }


def _build_pdf_reader():
    ocr_type = os.getenv('LAZYRAG_OCR_SERVER_TYPE', 'none')
    ocr_url = os.getenv('LAZYRAG_OCR_SERVER_URL', 'http://localhost:8000').rstrip('/')
    patch_applied = _parse_bool_env('LAZYRAG_OCR_PATCH_APPLIED') or False
    service_variant = os.getenv('LAZYRAG_OCR_SERVICE_VARIANT', 'online')
    if ocr_type in ('none', None, ''):
        return PDFReader()
    if ocr_type == 'mineru':
        upload_mode = _parse_bool_env('LAZYRAG_MINERU_UPLOAD_MODE')
        if upload_mode is None:
            upload_mode = _default_mineru_upload_mode(ocr_url)
        return MineruPDFReader(
            url=ocr_url,
            backend=os.getenv('LAZYRAG_MINERU_BACKEND', 'pipeline'),
            upload_mode=upload_mode,
            timeout=3600,
            patch_applied=patch_applied,
            service_variant=service_variant,
            image_cache_dir='/app/uploads/.image_cache'
        )
    if ocr_type == 'paddleocr':
        return PaddleOCRPDFReader(
            url=ocr_url,
            service_variant=service_variant,
            images_dir='/app/uploads/.image_cache'
        )
    raise ValueError(f'Unsupported LAZYRAG_OCR_SERVER_TYPE: {ocr_type!r}')


def _document_processor_accepts_store_conf() -> bool:
    """Return whether current LazyLLM expects store_conf on DocumentProcessor."""
    try:
        params = inspect.signature(DocumentProcessor.__init__).parameters
    except (TypeError, ValueError):
        return False
    return 'store_conf' in params


def _build_document_processor(processor_url: str, store_conf: dict) -> tuple[DocumentProcessor, bool]:
    """Create DocumentProcessor for both old/new LazyLLM APIs.

    Returns:
        (processor, store_conf_bound_to_processor)
    """
    if _document_processor_accepts_store_conf():
        return DocumentProcessor(url=processor_url, store_conf=store_conf), True
    return DocumentProcessor(url=processor_url), False


def build_document() -> Document:
    processor_url = os.getenv('LAZYRAG_DOCUMENT_PROCESSOR_URL', 'http://localhost:8000')
    server_port = get_algo_server_port()
    settings = get_retrieval_settings()
    embed = {k: get_automodel(k) for k in settings.embed_keys}
    store_conf = _build_store_config(settings.index_kwargs)
    processor, store_conf_bound_to_processor = _build_document_processor(processor_url, store_conf)

    document_kwargs = {
        'dataset_path': None,
        'name': ALGO_ID,
        'embed': embed,
        'manager': processor,
        'doc_fields': [],
        'server': server_port,
    }
    if not store_conf_bound_to_processor:
        document_kwargs['store_conf'] = store_conf

    try:
        docs = Document(**document_kwargs)
    except ValueError as exc:
        error_text = str(exc)
        # LazyLLM new API: store_conf must be bound to DocumentProcessor.
        if 'must not be passed to Document' in error_text and 'DocumentProcessor' in error_text:
            processor = DocumentProcessor(url=processor_url, store_conf=store_conf)
            document_kwargs['manager'] = processor
            document_kwargs.pop('store_conf', None)
            docs = Document(**document_kwargs)
        # LazyLLM old API: store_conf must be passed to Document.
        elif 'store_conf' in error_text and 'required' in error_text and 'DocumentProcessor' in error_text:
            document_kwargs['store_conf'] = store_conf
            docs = Document(**document_kwargs)
        else:
            raise

    docs.add_reader('*.pdf', _build_pdf_reader())
    docs.create_node_group(name='block', display_name='paragraph slice',
                           group_type=NodeGroupType.CHUNK, transform=GeneralParser(max_length=2048, split_by='\n'))
    docs.create_node_group(name='line', display_name='sentence slice',
                           group_type=NodeGroupType.CHUNK, transform=LineSplitter, parent='block')
    docs.activate_group('block', embed_keys=settings.embed_keys)
    docs.activate_group('line', embed_keys=settings.embed_keys)
    return docs
