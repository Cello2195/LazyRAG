"""Theme-aware HTML deck rendering utilities for LazyRAG.

This package implements the visual route:
    deck_schema -> theme-aware fixed-size HTML slides -> screenshots -> image-based PPTX

It is intentionally parallel to chat.pptx so the existing editable PPTX route
remains unchanged.
"""

from .renderer import create_html_deck_from_schema
from .screenshot import render_html_deck_screenshots
from .export_pptx import create_pptx_from_slide_images
from .qa import run_html_deck_qa
from .themes import available_html_themes, resolve_html_theme

__all__ = [
    'create_html_deck_from_schema',
    'render_html_deck_screenshots',
    'create_pptx_from_slide_images',
    'run_html_deck_qa',
    'available_html_themes',
    'resolve_html_theme',
]
