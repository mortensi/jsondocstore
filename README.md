# JsonDocStore

Simple JSON document storage on disk. 

- A Python library to organize and query JSON documents on disk, basically, with no running process.
- Each document is stored as one file named `<key>.json`. The document key is the filename stem.
- If you want to organize documents into different folders, use one `JsonDocStore` instance per folder. Each instance manages only the JSON files in its own directory.
- If you want to query by a field, create an index on it. This will create an `index.json` file in the store directory. It is not required for basic operations like `insert`, `update`, `delete`, and `get`.

## Installation

```bash
pip install jsondocstore
```

## Using from the terminal

Start the interactive shell:

```bash
jsondocstore /path/to/store
```

Commands:

- `list` prints document filenames only
- `listindexes` prints indexed fields, or `[]` if there is no `index.json`
- `get KEY`
- `queryby FIELD VALUE`
- `createindex FIELD`
- `deleteindex FIELD`
- `insert KEY JSON_DOCUMENT`
- `update KEY JSON_DOCUMENT`
- `delete KEY`
- `exit`

Example session:

```text
$ jsondocstore ./data
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
jsondocstore> get user-1
{
  "password": "secret1",
  "role": "admin",
  "username": "alice"
}
jsondocstore> createindex role
jsondocstore> queryby role user
{
  "user-3": {
    "password": "secret3",
    "role": "user",
    "username": "carol"
  }
}
```

## Using from your Python application

```python
from jsondocstore import JsonDocStore

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

## Data Model

- `get(key)` reads `<key>.json`.
- `insert(key, doc)` writes `<key>.json`.
- Valid keys may contain letters, digits, `.`, `_`, and `-`. No whitespace.

## Schema

`index.json` is optional.

- `create=True` creates the directory if needed. It does not create `index.json`.
- `index_fields` defines which fields are indexed in memory.
- `get()`, `insert()`, `delete()`, and `list_all()` work without `index.json`.
- `query_by()` only works when an index exists. It returns a mapping of `key -> document`. Querying without an index, or on a non-indexed field, raises an error.
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
