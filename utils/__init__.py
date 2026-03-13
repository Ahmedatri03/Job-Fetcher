"""Utility helpers — deduplication, hashing, logging, text extraction."""

from utils.dedupe import compute_hash, normalize
from utils.extract import extract_snippet, extract_techs
from utils.logger import setup_logger

__all__ = ["compute_hash", "normalize", "setup_logger", "extract_techs", "extract_snippet"]
