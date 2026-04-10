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
    intro = "JsonDocStore shell. Type 'help' or 'help COMMAND'."
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

    def completedefault(self, text, line, begidx, endidx):
        return []

    def do_list(self, arg):
        """list: print document filenames"""
        self._print_json(self.store.list_all())

    def do_listindexes(self, arg):
        """listindexes: print indexed fields"""
        self._print_json(self.store.list_indexes())

    def do_get(self, arg):
        """get KEY: print a document by key"""
        pk = arg.strip()
        if not pk:
            print("Usage: get KEY")
            return

        try:
            self._print_json(self.store.get(pk))
        except Exception as e:
            print(f"Error: {e}")

    def do_queryby(self, arg):
        """queryby FIELD VALUE: exact-match query on an indexed field"""
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
        """createindex FIELD: create an index on a top-level field"""
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
        """deleteindex FIELD: delete an index"""
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
        """insert KEY JSON_DOCUMENT: insert a new document"""
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
        """update KEY JSON_DOCUMENT: replace an existing document"""
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
        """delete KEY: delete a document by key"""
        pk = arg.strip()
        if not pk:
            print("Usage: delete KEY")
            return

        try:
            self.store.delete(pk)
            print(f"Deleted {pk}")
        except Exception as e:
            print(f"Error: {e}")

    def do_exit(self, arg):
        """exit: leave the shell"""
        return True

    def do_EOF(self, arg):
        """Ctrl-D: leave the shell"""
        print()
        return True


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m jsondocstore /path/to/db", file=sys.stderr)
        return 1

    _configure_readline()
    root = Path(sys.argv[1])
    try:
        store = JsonDocStore(root)
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
