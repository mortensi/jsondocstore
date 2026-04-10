from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
import re
import tempfile
from typing import Any


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


_VALID_KEY_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SCHEMA_FILENAME = "index.json"


class JsonDocStore:
    """Store JSON documents as individual files in a directory.

    Document identity is the filename stem. Optional indexes are stored in
    ``index.json`` and support exact-match queries on top-level fields.
    """

    def __init__(self, root: str | Path, create: bool = False):
        """Open a document store rooted at ``root``.

        If ``create`` is true, the directory is created when missing.
        ``index.json`` is optional and is only needed for indexed queries.
        """
        self.root = Path(root)
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        elif not self.root.exists():
            raise ValueError(f"Directory does not exist: {self.root}")
        if not self.root.is_dir():
            raise ValueError(f"Path is not a directory: {self.root}")

        self.schema_path = self.root / _SCHEMA_FILENAME
        self.schema = self._load_schema() if self.schema_path.exists() else None
        self.index_fields = list(self.schema.get("index_fields", [])) if self.schema else []
        self.indexes: dict[str, dict[Any, set[str]]] = {field: defaultdict(set) for field in self.index_fields}
        if self.schema is not None:
            self._rebuild_index()

    def _load_schema(self) -> dict[str, Any]:
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        if "index_fields" not in schema:
            raise ValueError("index.json must contain 'index_fields'")
        if not isinstance(schema["index_fields"], list):
            raise ValueError("'index_fields' must be a list")
        if not all(isinstance(field, str) for field in schema["index_fields"]):
            raise ValueError("'index_fields' entries must be strings")
        if not all(field for field in schema["index_fields"]):
            raise ValueError("'index_fields' entries must not be empty")
        return schema

    def _doc_path(self, pk: str) -> Path:
        return self.root / f"{pk}.json"

    def _validate_key(self, pk: str) -> None:
        if not pk:
            raise ValueError("Document key must not be empty")
        if pk in {".", ".."}:
            raise ValueError(f"Invalid document key: {pk}")
        if pk == Path(_SCHEMA_FILENAME).stem:
            raise ValueError(f"Document key '{Path(_SCHEMA_FILENAME).stem}' is reserved")
        if not _VALID_KEY_RE.fullmatch(pk):
            raise ValueError(
                "Invalid document key. Use only letters, digits, dot, underscore, or hyphen"
            )

    def _validate_field_name(self, field: str) -> None:
        if not isinstance(field, str):
            raise ValueError("Indexed field name must be a string")
        if not field:
            raise ValueError("Indexed field name must not be empty")

    def _rebuild_index(self) -> None:
        for field in self.index_fields:
            self.indexes[field].clear()
        for path in sorted(self.root.glob("*.json")):
            if path.name == _SCHEMA_FILENAME:
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            self._add_indexes(path.stem, doc)

    def _list_doc_names(self) -> list[str]:
        return [
            path.name
            for path in sorted(self.root.glob("*.json"))
            if path.name != _SCHEMA_FILENAME
        ]

    def _add_indexes(self, pk: str, doc: dict[str, Any]) -> None:
        for field in self.index_fields:
            if field in doc:
                self.indexes[field][doc[field]].add(pk)

    def _remove_indexes(self, pk: str, doc: dict[str, Any]) -> None:
        for field in self.index_fields:
            if field in doc:
                value = doc[field]
                bucket = self.indexes[field].get(value)
                if bucket is not None:
                    bucket.discard(pk)
                    if not bucket:
                        del self.indexes[field][value]

    def _write_json_atomic(self, path: Path, obj: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(self.root), delete=False
        ) as tmp:
            tmp.write(_json_dump(obj))
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)

    def list_all(self) -> list[str]:
        """Return all document filenames in the store."""
        return self._list_doc_names()

    def get(self, pk: str) -> dict[str, Any]:
        """Return the document stored under ``pk``.

        Raises ``KeyError`` if the document does not exist.
        """
        self._validate_key(pk)
        path = self._doc_path(pk)
        if not path.exists():
            raise KeyError(f"Document not found: {pk}")
        return json.loads(path.read_text(encoding="utf-8"))

    def query_by(self, field: str, value: Any) -> dict[str, dict[str, Any]]:
        """Return documents whose indexed ``field`` exactly matches ``value``.

        The result is a mapping of ``key -> document``. Raises ``ValueError`` if
        no index exists or if ``field`` is not indexed.
        """
        self._validate_field_name(field)
        if self.schema is None:
            raise ValueError("Cannot query without an index. Create an index first")
        if field not in self.indexes:
            raise ValueError(f"Field is not indexed: {field}")
        return {pk: self.get(pk) for pk in sorted(self.indexes[field].get(value, ()))}

    def create_index(self, field: str) -> None:
        """Create an exact-match index for a top-level field.

        Creates ``index.json`` when needed. Raises ``ValueError`` if the index
        already exists.
        """
        self._validate_field_name(field)
        if self.schema is None:
            self.schema = {"index_fields": []}
            self.index_fields = []
            self.indexes = {}
        if field in self.indexes:
            raise ValueError(f"Index already exists: {field}. Delete it before recreating")
        self.index_fields.append(field)
        self.indexes[field] = defaultdict(set)
        self.schema["index_fields"] = list(self.index_fields)
        self._write_json_atomic(self.schema_path, self.schema)
        self._rebuild_index()

    def list_indexes(self) -> list[str]:
        """Return the sorted list of indexed fields."""
        return sorted(self.index_fields)

    def delete_index(self, field: str) -> bool:
        """Delete an index by field name.

        Returns ``True`` if an index was deleted, ``False`` if it did not
        exist. Raises ``ValueError`` if no ``index.json`` exists.
        """
        self._validate_field_name(field)
        if self.schema is None:
            raise ValueError("Cannot delete an index without an index.json")
        if field not in self.indexes:
            return False
        self.index_fields = [name for name in self.index_fields if name != field]
        del self.indexes[field]
        self.schema["index_fields"] = list(self.index_fields)
        self._write_json_atomic(self.schema_path, self.schema)
        return True

    def insert(self, pk: str, doc: dict[str, Any]) -> dict[str, Any]:
        """Insert a new document under ``pk`` and return it.

        Raises ``ValueError`` if the key is invalid or already exists.
        """
        self._validate_key(pk)
        path = self._doc_path(pk)
        if path.exists():
            raise ValueError(f"Primary key already exists: {pk}")
        if self.schema is not None:
            self._add_indexes(pk, doc)
        self._write_json_atomic(path, doc)
        return doc

    def update(self, pk: str, doc: dict[str, Any]) -> dict[str, Any]:
        """Replace the existing document stored under ``pk`` and return it.

        Raises ``KeyError`` if the document does not exist.
        """
        self._validate_key(pk)
        path = self._doc_path(pk)
        if not path.exists():
            raise KeyError(f"Document not found: {pk}")
        if self.schema is not None:
            old_doc = self.get(pk)
            self._remove_indexes(pk, old_doc)
            self._add_indexes(pk, doc)
        self._write_json_atomic(path, doc)
        return doc

    def delete(self, pk: str) -> None:
        """Delete the document stored under ``pk``.

        Raises ``KeyError`` if the document does not exist.
        """
        self._validate_key(pk)
        path = self._doc_path(pk)
        if not path.exists():
            raise KeyError(f"Document not found: {pk}")
        if self.schema is not None:
            doc = self.get(pk)
            self._remove_indexes(pk, doc)
        path.unlink()
