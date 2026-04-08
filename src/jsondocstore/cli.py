from __future__ import annotations

import cmd
import json
import shlex
import sys
from pathlib import Path

try:
    import readline  # noqa: F401
except ImportError:
    readline = None

from .core import JsonDocStore, _json_dump


def _parse_query_value(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _configure_readline() -> None:
    if readline is None:
        return
    doc = getattr(readline, "__doc__", "") or ""
    if "libedit" in doc:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")


class JsonDocStoreShell(cmd.Cmd):
    intro = "JsonDocStore interactive shell. Type 'help' for commands."
    prompt = "jsondocstore> "

    def __init__(self, store: JsonDocStore):
        super().__init__()
        self.store = store

    def get_names(self):
        return [name for name in super().get_names() if name != "do_EOF"]

    def emptyline(self):
        return None

    def _print_json(self, value):
        print(_json_dump(value))

    def _complete_from_options(self, text, options):
        return sorted(option for option in options if option.startswith(text))

    def _document_keys(self):
        root = getattr(self.store, "root", None)
        if root is None:
            return []
        return sorted(
            path.stem
            for path in Path(root).glob("*.json")
            if path.name != "index.json"
        )

    def _document_fields(self):
        fields = set()
        root = getattr(self.store, "root", None)
        if root is None:
            return []
        for path in Path(root).glob("*.json"):
            if path.name == "index.json":
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                fields.update(doc.keys())
            except Exception:
                continue
        return sorted(field for field in fields if isinstance(field, str))

    def _query_fields(self):
        try:
            indexes = self.store.list_indexes()
        except Exception:
            return []
        return indexes or self._document_fields()

    def complete_queryby(self, text, line, begidx, endidx):
        args = shlex.split(line[:begidx])
        if len(args) <= 1:
            return self._complete_from_options(text, self._query_fields())
        return []

    def complete_createindex(self, text, line, begidx, endidx):
        indexed = set(self.store.list_indexes())
        fields = [field for field in self._document_fields() if field not in indexed]
        return self._complete_from_options(text, fields)

    def complete_deleteindex(self, text, line, begidx, endidx):
        return self._complete_from_options(text, self.store.list_indexes())

    def complete_delete(self, text, line, begidx, endidx):
        return self._complete_from_options(text, self._document_keys())

    def do_list(self, arg):
        """List all documents."""
        self._print_json(self.store.list_all())

    def do_listindexes(self, arg):
        """List indexed fields."""
        self._print_json(self.store.list_indexes())

    def do_queryby(self, arg):
        """queryby FIELD VALUE"""
        try:
            field, value = shlex.split(arg)
        except ValueError:
            print("Usage: queryby FIELD VALUE")
            return

        try:
            self._print_json(self.store.query_by(field, _parse_query_value(value)))
        except Exception as e:
            print(f"Error: {e}")

    def do_createindex(self, arg):
        """createindex FIELD"""
        field = arg.strip()
        if not field:
            print("Usage: createindex FIELD")
            return

        try:
            self.store.create_index(field)
            print(f"Created index {field}")
        except Exception as e:
            print(f"Error: {e}")

    def do_deleteindex(self, arg):
        """deleteindex FIELD"""
        field = arg.strip()
        if not field:
            print("Usage: deleteindex FIELD")
            return

        try:
            deleted = self.store.delete_index(field)
            if deleted:
                print(f"Deleted index {field}")
            else:
                print(f"Index not found: {field}")
        except Exception as e:
            print(f"Error: {e}")

    def do_insert(self, arg):
        """insert KEY JSON_DOCUMENT"""
        if not arg.strip():
            print("Usage: insert KEY JSON_DOCUMENT")
            return

        try:
            parts = shlex.split(arg)
            if len(parts) < 2:
                raise ValueError
            key = parts[0]
            json_text = " ".join(parts[1:])
        except ValueError:
            print("Usage: insert KEY JSON_DOCUMENT")
            return

        try:
            self._print_json(self.store.insert(key, json.loads(json_text)))
        except Exception as e:
            print(f"Error: {e}")

    def do_update(self, arg):
        """update KEY JSON_DOCUMENT"""
        if not arg.strip():
            print("Usage: update KEY JSON_DOCUMENT")
            return

        try:
            parts = shlex.split(arg)
            if len(parts) < 2:
                raise ValueError
            key = parts[0]
            json_text = " ".join(parts[1:])
        except ValueError:
            print("Usage: update KEY JSON_DOCUMENT")
            return

        try:
            self._print_json(self.store.update(key, json.loads(json_text)))
        except Exception as e:
            print(f"Error: {e}")

    def do_delete(self, arg):
        """delete PK"""
        pk = arg.strip()
        if not pk:
            print("Usage: delete PK")
            return

        try:
            self.store.delete(pk)
            print(f"Deleted {pk}")
        except Exception as e:
            print(f"Error: {e}")

    def do_exit(self, arg):
        """Exit the shell."""
        return True

    def do_EOF(self, arg):
        """Exit on Ctrl-D."""
        print()
        return True


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m jsondocstore /path/to/db", file=sys.stderr)
        return 1

    _configure_readline()
    root = Path(sys.argv[1])
    try:
        store = JsonDocStore(root, create=True)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        JsonDocStoreShell(store).cmdloop()
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
