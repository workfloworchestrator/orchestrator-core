# Filter Operators (Reference)

List of **operators** supported by structured filters.

> Programmatic source of truth: `GET api/search/definitions`

---

## Operator matrix (by `value_kind`)

### `string`

| Op     | Meaning    |
| ------ | ---------- |
| `eq`   | equals     |
| `neq`  | not equals |
| `like` | SQL LIKE   |

### `number` (maps to `integer` / `float`)

| Op        | Meaning                                                   |
| --------- | --------------------------------------------------------- |
| `eq`      | equals                                                    |
| `neq`     | not equals                                                |
| `lt`      | less than                                                 |
| `lte`     | less than or equal                                        |
| `gt`      | greater than                                              |
| `gte`     | greater than or equal                                     |
| `between` | inclusive range object `{ "start": <num>, "end": <num> }` |

### `datetime`

| Op        | Meaning                | Value format                             |
| --------- | ---------------------- | ---------------------------------------- |
| `eq`      | equals                 | ISO 8601 string                          |
| `neq`     | not equals             | ISO 8601 string                          |
| `lt`      | before                 | ISO 8601 string                          |
| `lte`     | at or before           | ISO 8601 string                          |
| `gt`      | after                  | ISO 8601 string                          |
| `gte`     | at or after            | ISO 8601 string                          |
| `between` | inclusive range object | `{ "start": "...", "end": "..." }` (ISO) |

### `boolean`

| Op    | Meaning    |
| ----- | ---------- |
| `eq`  | equals     |
| `neq` | not equals |

### Equality on special field types

`eq` / `neq` also apply to fields indexed as **`uuid`**, **`block`**, and **`resource_type`**.

---

## LTree (path) operators

`value_kind: "component"`

Use these to filter on **path structure** (components), not the field value.

| Op                  | Description                       | SQL symbol / pattern            | Example `condition.value`          |
| ------------------- | --------------------------------- | ------------------------------- | ---------------------------------- |
| `matches_lquery`    | lquery wildcard match             | `~` (ltree lquery)              | `subscription.*.name`              |
| `is_ancestor`       | left is ancestor of right         | `@>`                            | `subscription.product`             |
| `is_descendant`     | left is descendant of right       | `<@`                            | `subscription.product.basic_block` |
| `path_match`        | exact path match                  | `=`                             | `subscription.product.name`        |
| `has_component`     | path contains segment             | `~ '*.<seg>.*'`                 | `product`                          |
| `not_has_component` | path does **not** contain segment | NOT EXISTS with `~ '*.<seg>.*'` | `debug`                            |
| `ends_with`         | path ends with segment            | `~ '*.<seg>'`                   | `name`                             |

---
