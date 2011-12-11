Design
======

Files
-----
Spritzle will have to read/write a number of files, namely configuration,
spritzle state and libtorrent state. By default these will all be stored
in a .spritzle directory in the user's home directory.

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
