Hooks
=====

Spritzle is made highly extensible by the use of hooks. Hooks can be
executed in a couple of ways:

 * in-process hooks loaded from python modules in a plugins directory
 * simple executables stored in a hooks directory, run once per hook fire
 * long running processes that communicate with the daemon

This allows for a very flexible extension system, allowing plugins to vary
from the extremely simple:

```sh
#!/bin/sh
#
# 01-email-notification.sh
#

echo "Subject: Spritzle notification

Something happened" | sendmail joe@example.org
```

to a fullblown plugin utilising all the hooks via python in process.


- *encode_data*
  - format, string, the format of the encoding
  - data, string, the data to encode
  - Returns the encoded data

- *decode_data*
  - format, stribng, the format of the encoding
  - data, string, the data to decode
  - Returns the decoded data