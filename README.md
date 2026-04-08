# JsonDocStore

Simple JSON document storage on disk.

Each document is stored as one file named `<key>.json`. The document key is the filename stem, not a field inside the JSON body.

If you want to organize documents into different folders, use one `JsonDocStore` instance per folder. Each instance manages only the JSON files in its own directory.

## What It Does

- Stores one JSON document per file.
- Reads documents directly by filename.
- Uses optional in-memory indexes defined in `index.json`.
- Provides an interactive CLI in `cli.py`.

## Data Model

- `get(key)` reads `<key>.json`.
- `insert(key, doc)` writes `<key>.json`.
- Valid keys may contain letters, digits, `.`, `_`, and `-`. No whitespace.

## Schema

`index.json` is optional.

- `create=True` creates the directory if needed. It does not create `index.json`.
- `index_fields` defines which fields are indexed in memory.
- `get()`, `insert()`, `delete()`, and `list_all()` work without `index.json`.
- `query_by()` only works when an index exists. Querying without an index, or on a non-indexed field, raises an error.
- Indexes work only on top-level document fields, not nested paths.

Example:

```json
{
  "index_fields": ["email", "status"]
}
```

For example, this works:

```json
{
  "email": "alice@example.com",
  "profile": {
    "city": "Rome"
  }
}
```

- you can index `email`
- you cannot index `profile.city`

## CLI

Start the interactive shell:

```bash
python3 cli.py /path/to/store
```

Commands:

- `list` prints document filenames only
- `listindexes` prints indexed fields, or `[]` if there is no `index.json`
- `queryby FIELD VALUE`
- `createindex FIELD`
- `deleteindex FIELD`
- `insert KEY JSON_DOCUMENT`
- `update KEY JSON_DOCUMENT`
- `delete KEY`
- `exit`

Example session:

```text
$ python3 cli.py ./data
jsondocstore> insert user-1 '{"username": "alice", "password": "secret1", "role": "admin"}'
jsondocstore> insert user-2 '{"username": "bob", "password": "secret2", "role": "user"}'
jsondocstore> insert user-3 '{"username": "carol", "password": "secret3", "role": "user"}'
jsondocstore> update user-2 '{"username": "bob", "password": "secret2", "role": "admin"}'
jsondocstore> list
[
  "user-1.json",
  "user-2.json",
  "user-3.json"
]
jsondocstore> createindex role
jsondocstore> queryby role user
[
  {
    "password": "secret2",
    "role": "user",
    "username": "bob"
  },
  {
    "password": "secret3",
    "role": "user",
    "username": "carol"
  }
]
```

## Library

```python
from core import JsonDocStore

store = JsonDocStore("./data", create=True)
store.insert("user-1", {"username": "alice", "password": "secret1", "role": "admin"})
store.insert("user-2", {"username": "bob", "password": "secret2", "role": "user"})
store.insert("user-3", {"username": "carol", "password": "secret3", "role": "user"})
store.update("user-2", {"username": "bob", "password": "secret2", "role": "admin"})
names = store.list_all()
store.create_index("role")
admins = store.query_by("role", "admin")
doc = store.get("user-1")
```
