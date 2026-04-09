from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jsondocstore import cli
from jsondocstore.core import JsonDocStore


class JsonDocStoreTests(unittest.TestCase):
    def make_store(
        self,
        *,
        index_fields: list[str] | None = None,
        docs: list[dict[str, object] | tuple[str, dict[str, object]]] | None = None,
    ) -> tuple[Path, JsonDocStore]:
        root = Path(tempfile.mkdtemp())
        schema = {"index_fields": index_fields or []}
        (root / "index.json").write_text(json.dumps(schema), encoding="utf-8")
        for item in docs or []:
            if isinstance(item, tuple):
                key, doc = item
            else:
                doc = item
                key = str(doc["id"])
            doc_path = root / f"{key}.json"
            doc_path.write_text(json.dumps(doc), encoding="utf-8")
        return root, JsonDocStore(root)

    def test_create_index_only_when_missing(self) -> None:
        _, store = self.make_store(
            docs=[
                ("doc-1", {"age": 42}),
                ("doc-2", {"age": 7}),
            ]
        )

        store.create_index("age")
        with self.assertRaisesRegex(ValueError, "Index already exists: age"):
            store.create_index("age")
        self.assertEqual(store.query_by("age", 42), {"doc-1": {"age": 42}})

    def test_create_index_bootstraps_schema_when_missing(self) -> None:
        root = Path(tempfile.mkdtemp())
        store = JsonDocStore(root, create=True)
        (root / "user-1.json").write_text(json.dumps({"role": "admin"}), encoding="utf-8")
        (root / "user-2.json").write_text(json.dumps({"role": "user"}), encoding="utf-8")
        store = JsonDocStore(root)

        store.create_index("role")

        self.assertEqual(
            json.loads((root / "index.json").read_text(encoding="utf-8")),
            {"index_fields": ["role"]},
        )
        self.assertEqual(store.query_by("role", "user"), {"user-2": {"role": "user"}})

    def test_query_by_requires_index(self) -> None:
        root = Path(tempfile.mkdtemp())
        (root / "doc-1.json").write_text(json.dumps({"name": "alice"}), encoding="utf-8")
        store = JsonDocStore(root)

        with self.assertRaisesRegex(ValueError, "Cannot query without an index"):
            store.query_by("name", "alice")

    def test_delete_index_only_when_present(self) -> None:
        _, store = self.make_store(
            index_fields=["age"],
            docs=[
                ("doc-1", {"age": 42}),
            ],
        )

        self.assertTrue(store.delete_index("age"))
        self.assertFalse(store.delete_index("age"))
        with self.assertRaisesRegex(ValueError, "Field is not indexed: age"):
            store.query_by("age", 42)

    def test_list_indexes_returns_sorted_fields(self) -> None:
        _, store = self.make_store(index_fields=["zeta", "alpha"])

        self.assertEqual(store.list_indexes(), ["alpha", "zeta"])

    def test_query_by_rejects_non_indexed_field_when_schema_exists(self) -> None:
        _, store = self.make_store(
            index_fields=["age"],
            docs=[
                ("doc-1", {"name": "alice", "age": 42}),
            ],
        )

        with self.assertRaisesRegex(ValueError, "Field is not indexed: name"):
            store.query_by("name", "alice")

    def test_list_all_returns_document_filenames(self) -> None:
        _, store = self.make_store(
            docs=[
                ("doc-1", {"name": "alice"}),
                ("doc-2", {"name": "bob"}),
            ],
        )

        self.assertEqual(store.list_all(), ["doc-1.json", "doc-2.json"])

    def test_filename_identity_is_independent_from_document_fields(self) -> None:
        _, store = self.make_store(
            index_fields=["name"],
            docs=[
                ("a", {"id": "1", "name": "alice"}),
                ("b", {"id": "1", "name": "bob"}),
            ],
        )

        self.assertEqual(store.get("a"), {"id": "1", "name": "alice"})
        self.assertEqual(store.get("b"), {"id": "1", "name": "bob"})

    def test_get_raises_for_missing_document(self) -> None:
        _, store = self.make_store()

        with self.assertRaisesRegex(KeyError, "Document not found: missing"):
            store.get("missing")

    def test_delete_raises_for_missing_document(self) -> None:
        _, store = self.make_store()

        with self.assertRaisesRegex(KeyError, "Document not found: missing"):
            store.delete("missing")

    def test_insert_uses_explicit_key_not_document_pk_field(self) -> None:
        root, store = self.make_store()

        inserted = store.insert("customer-1", {"id": "different", "name": "alice"})

        self.assertEqual(inserted, {"id": "different", "name": "alice"})
        self.assertEqual(
            json.loads((root / "customer-1.json").read_text(encoding="utf-8")),
            {"id": "different", "name": "alice"},
        )
        self.assertEqual(store.get("customer-1"), {"id": "different", "name": "alice"})

    def test_update_replaces_existing_document(self) -> None:
        root, store = self.make_store(docs=[("customer-1", {"name": "alice", "role": "user"})])

        updated = store.update("customer-1", {"name": "alice", "role": "admin"})

        self.assertEqual(updated, {"name": "alice", "role": "admin"})
        self.assertEqual(
            json.loads((root / "customer-1.json").read_text(encoding="utf-8")),
            {"name": "alice", "role": "admin"},
        )
        self.assertEqual(store.get("customer-1"), {"name": "alice", "role": "admin"})

    def test_update_refreshes_indexes(self) -> None:
        _, store = self.make_store(
            index_fields=["role"],
            docs=[("customer-1", {"name": "alice", "role": "user"})],
        )

        store.update("customer-1", {"name": "alice", "role": "admin"})

        self.assertEqual(store.query_by("role", "user"), {})
        self.assertEqual(
            store.query_by("role", "admin"),
            {"customer-1": {"name": "alice", "role": "admin"}},
        )

    def test_update_requires_existing_document(self) -> None:
        _, store = self.make_store()

        with self.assertRaisesRegex(KeyError, "Document not found: missing"):
            store.update("missing", {"name": "alice"})

    def test_insert_rejects_invalid_key(self) -> None:
        _, store = self.make_store()

        with self.assertRaisesRegex(ValueError, "Invalid document key"):
            store.insert("bad key", {"name": "alice"})

    def test_key_validation_rejects_empty_dot_and_dotdot(self) -> None:
        _, store = self.make_store()

        with self.assertRaisesRegex(ValueError, "Document key must not be empty"):
            store.get("")
        with self.assertRaisesRegex(ValueError, r"Invalid document key: \."):
            store.get(".")
        with self.assertRaisesRegex(ValueError, r"Invalid document key: \.\."):
            store.get("..")

    def test_key_validation_rejects_reserved_index_name(self) -> None:
        _, store = self.make_store()

        with self.assertRaisesRegex(ValueError, "Document key 'index' is reserved"):
            store.insert("index", {"name": "alice"})

    def test_delete_index_requires_index_json(self) -> None:
        root = Path(tempfile.mkdtemp())
        store = JsonDocStore(root, create=True)

        with self.assertRaisesRegex(ValueError, "Cannot delete an index without an index.json"):
            store.delete_index("age")

    def test_invalid_schema_missing_index_fields_raises(self) -> None:
        root = Path(tempfile.mkdtemp())
        (root / "index.json").write_text(json.dumps({"wrong": []}), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "index.json must contain 'index_fields'"):
            JsonDocStore(root)

    def test_invalid_schema_malformed_json_raises(self) -> None:
        root = Path(tempfile.mkdtemp())
        (root / "index.json").write_text("{not json", encoding="utf-8")

        with self.assertRaises(json.JSONDecodeError):
            JsonDocStore(root)

    def test_invalid_schema_index_fields_must_be_list(self) -> None:
        root = Path(tempfile.mkdtemp())
        (root / "index.json").write_text(json.dumps({"index_fields": "age"}), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "'index_fields' must be a list"):
            JsonDocStore(root)

    def test_interactive_cli_starts_without_schema_file(self) -> None:
        root = Path(tempfile.mkdtemp())

        with patch.object(cli.JsonDocStoreShell, "cmdloop", return_value=None):
            with patch("sys.argv", ["cli.py", str(root)]):
                rc = cli.main()

        self.assertEqual(rc, 0)
        self.assertFalse((root / "index.json").exists())

    def test_interactive_cli_exits_cleanly_on_keyboard_interrupt(self) -> None:
        root = Path(tempfile.mkdtemp())
        stdout = io.StringIO()

        with patch.object(cli.JsonDocStoreShell, "cmdloop", side_effect=KeyboardInterrupt):
            with patch("sys.argv", ["cli.py", str(root)]), redirect_stdout(stdout):
                rc = cli.main()

        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), "\n")

    def test_cli_main_requires_root_argument(self) -> None:
        stderr = io.StringIO()

        with patch("sys.argv", ["cli.py"]), contextlib.redirect_stderr(stderr):
            rc = cli.main()

        self.assertEqual(rc, 1)
        self.assertIn("Usage: python -m jsondocstore /path/to/db", stderr.getvalue())

    def test_shell_completes_command_names(self) -> None:
        _, store = self.make_store()
        shell = cli.JsonDocStoreShell(store)

        matches = shell.completenames("cr")

        self.assertEqual(matches, ["createindex"])

    def test_shell_does_not_complete_command_arguments(self) -> None:
        _, store = self.make_store(
            index_fields=["role"],
            docs=[("user-1", {"role": "admin"})],
        )
        shell = cli.JsonDocStoreShell(store)

        matches = shell.completedefault("r", "queryby r", 8, 9)

        self.assertEqual(matches, [])


class JsonDocStoreShellTests(unittest.TestCase):
    def make_shell(self) -> tuple[MagicMock, cli.JsonDocStoreShell]:
        store = MagicMock()
        shell = cli.JsonDocStoreShell(store)
        return store, shell

    def test_list_uses_store_api(self) -> None:
        store, shell = self.make_shell()
        store.list_all.return_value = ["doc-1.json"]

        with redirect_stdout(io.StringIO()):
            shell.do_list("")

        store.list_all.assert_called_once_with()

    def test_listindexes_uses_store_api(self) -> None:
        store, shell = self.make_shell()
        store.list_indexes.return_value = ["age"]

        with redirect_stdout(io.StringIO()):
            shell.do_listindexes("")

        store.list_indexes.assert_called_once_with()

    def test_get_uses_store_api(self) -> None:
        store, shell = self.make_shell()
        store.get.return_value = {"id": "1"}

        with redirect_stdout(io.StringIO()):
            shell.do_get("1")

        store.get.assert_called_once_with("1")

    def test_queryby_uses_store_api_with_parsed_value(self) -> None:
        store, shell = self.make_shell()
        store.query_by.return_value = {"doc-1": {"id": "1", "age": 42}}

        with redirect_stdout(io.StringIO()):
            shell.do_queryby("age 42")

        store.query_by.assert_called_once_with("age", 42)

    def test_createindex_uses_store_api(self) -> None:
        store, shell = self.make_shell()

        with redirect_stdout(io.StringIO()):
            shell.do_createindex("age")

        store.create_index.assert_called_once_with("age")

    def test_deleteindex_uses_store_api(self) -> None:
        store, shell = self.make_shell()
        store.delete_index.return_value = True

        with redirect_stdout(io.StringIO()):
            shell.do_deleteindex("age")

        store.delete_index.assert_called_once_with("age")

    def test_insert_uses_store_api(self) -> None:
        store, shell = self.make_shell()
        store.insert.return_value = {"id": "1"}

        with redirect_stdout(io.StringIO()):
            shell.do_insert('doc-1 "{\\"id\\": \\"1\\"}"')

        store.insert.assert_called_once_with("doc-1", {"id": "1"})

    def test_update_uses_store_api(self) -> None:
        store, shell = self.make_shell()
        store.update.return_value = {"id": "1"}

        with redirect_stdout(io.StringIO()):
            shell.do_update('doc-1 "{\\"id\\": \\"1\\"}"')

        store.update.assert_called_once_with("doc-1", {"id": "1"})

    def test_delete_uses_store_api(self) -> None:
        store, shell = self.make_shell()

        with redirect_stdout(io.StringIO()):
            shell.do_delete("1")

        store.delete.assert_called_once_with("1")

    def test_help_hides_eof_command(self) -> None:
        _, shell = self.make_shell()
        output = io.StringIO()

        with redirect_stdout(output):
            shell.onecmd("help")

        self.assertNotIn("EOF", output.getvalue())

    def test_emptyline_does_not_repeat_last_command(self) -> None:
        store, shell = self.make_shell()

        with redirect_stdout(io.StringIO()):
            shell.onecmd("delete 1")
            shell.emptyline()

        store.delete.assert_called_once_with("1")


if __name__ == "__main__":
    unittest.main()
