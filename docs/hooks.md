Hooks
=====

Spritzle is made highly extensible by the use of hooks. Hooks can currently
be executed in one way:

 * simple executables stored in a hooks directory, run once per hook fire

Future possibilities may include:

 * in-process hooks loaded from python modules in a plugins directory
 * long running processes that communicate with the daemon

This allows for a very flexible extension and simple system.


Defined Hooks
-------------

Hooks are run when a corresponding [libtorrent alert](https://libtorrent.org/reference-Alerts.html) fires. Currently, all torrent alerts that belong to the `status_notification` category activate hooks.

Common hookable alerts include:
* `torrent_finished_alert`: Fires when a torrent finishes downloading.
* `state_changed_alert`: Fires when torrent state transitions (e.g. from downloading to seeding or checking).
* `torrent_added_alert`: Fires when a new torrent is added.
* `torrent_removed_alert`: Fires when a torrent is removed from the session.
* `torrent_error_alert`: Fires when a torrent encounters an I/O or storage error.
* `tracker_reply_alert`: Fires when a tracker announce succeeds.

See the [libtorrent alerts documentation](https://libtorrent.org/reference-Alerts.html) for all possible alerts.

These hooks will be passed the following positional command-line arguments:

* `info_hash` ($1): 40-character hex string of the torrent's info-hash.
* `tags` ($2): Comma-delimited string of tags associated with this torrent (e.g. `linux,iso`).

Writing Hooks
-------------

When a hookable alert fires, Spritzle runs matching hook executables in the following manner:

* Searches files in `<config_dir>/hooks/` whose filename ends in the alert name (e.g. `*torrent_finished_alert`).
  * Files starting with a non-alphanumeric character (e.g. `.`, `_`, `#`) are ignored.
  * Files without the executable permission bit set are ignored.
* Matching hook scripts are executed in alphanumeric sort order.

As an example, let's write hooks for `torrent_finished_alert`.

The default directory for hooks is `~/.config/spritzle/hooks/`.

To have multiple hooks run in a deterministic order when this alert fires, prepend filenames with an ordering number:

```bash
touch ~/.config/spritzle/hooks/100_torrent_finished_alert
touch ~/.config/spritzle/hooks/200_torrent_finished_alert
touch ~/.config/spritzle/hooks/300_torrent_finished_alert
```

Edit these files with whatever logic you wish to run. Use the `spritzle` CLI inside hooks to interact with `spritzled`. Here is what the beginning of a bash hook script looks like:

```bash
#!/bin/bash
#
# 100_torrent_finished_alert
#

info_hash=$1
tags=$2

#<...do something...>

```

Remember that every hook script must have its execute bit set:

```bash
chmod +x ~/.config/spritzle/hooks/*_torrent_finished_alert
```

Examples
--------

`torrent_finished_alert` - move storage of data for a torrent after it completes based on a tag:

```bash
#!/bin/bash

info_hash=$1
tags=$2

contains() {
	local i
	for i in "${@:2}"; do
		[[ "${i}" == "${1}" ]] && return 0
	done
}

IFS=, read -a tags <<< "${tags}"

if contains "linuxiso" "${tags}"; then
	spritzle move-storage "${info_hash}" "/my/linuxiso/storage"
fi

```

