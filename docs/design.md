Design
======


Request Lifetime
----------------

```

    +------------+                               +------------+
    |HTTP Request|                               |HTTP Reponse|
    +-----+------+                               +------------+
          |                                            ^
          |                                            |
          v                                            |
    +------------+                               +-----+------+
    |   VIEW     |                               |   VIEW     |
    |------------|                               |------------|
    |Decode data |                               |Encode the  |
    |from JSON or|                               |response to |
    |XML into    |                               |the correct |
    |Python      |                               |format      |
    +-----+------+                               +------------+
          |                                            ^
          |                                            |
          v                                            |
    +------------+         +-----------+         +-----+------+
    | RESOURCE   |         |    CORE   |         | RESOURCE   |
    |------------|         |-----------|         |------------|
    |Process data|         |Perform the|         |Convert the |
    |into format +-------->|actual call+-------->|response to |
    |suitable for|         |to         |         |a suitable  |
    |libtorrent  |         |libtorrent |         |format      |
    +------------+         +-----------+         +------------+
```
