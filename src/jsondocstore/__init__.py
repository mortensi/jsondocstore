"""JsonDocStore package.

Store JSON documents as individual files and optionally query them through
exact-match indexes on top-level fields.
"""

from .core import JsonDocStore

__all__ = ["JsonDocStore"]
