"""DEPRECATED: This module has been replaced by app.gemini_analysis.

The project now uses Google's Gemini API (default model: gemini-2.5-flash-lite)
for LLM augmentation. This file is kept only to avoid stale-import errors and
will be removed in a future change.
"""
from app.gemini_analysis import analyze_with_gemini as analyze_with_openai  # noqa: F401
