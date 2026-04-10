# JsonDocStore

Simple JSON document storage on disk. 

- A Python library to organize and query JSON documents on disk, basically, with no running process.
- You instantiate a `JsonDocStore` object with a root directory where your JSON documents will be stored. If you want to organize documents into different folders, use one `JsonDocStore` instance per folder. Each instance manages only the JSON files in its own directory. E.g. `JsonDocStore("./data/users")` and `JsonDocStore("./data/products")`.
- Each document is stored as a file named `<key>.json`. The document key is the filename stem.
- If you want to query by a field, create an index on it. This will create an `index.json` file in the store directory. Currently, only exact match is supported. It is not required for basic operations like `insert`, `update`, `delete`, and `get`. The index is in-memory, not persisted to disk and is rebuilt when the store is opened. 

## Installation

```bash
pip install jsondocstore
```

API docs are available at:

```text
https://mortensi.github.io/jsondocstore/
```

## Using from the terminal

Start the interactive shell:

```bash
jsondocstore /path/to/store
```

The directory must already exist. The CLI does not create it for you.

Commands:

- `list` prints document filenames only
- `listindexes` prints indexed fields, or `[]` if there is no `index.json`
- `get KEY`
- `queryby FIELD VALUE`
- `createindex FIELD`
- `deleteindex FIELD`
- `insert KEY JSON_DOCUMENT` valid keys may contain letters, digits, `.`, `_`, and `-`. No whitespace.
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

Learn the API by reading the [API reference](https://mortensi.github.io/jsondocstore/api/jsondocstore.html).

Example:

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

## Schema

The schema file `index.json` is optional and required only if you want to use indexes.

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
