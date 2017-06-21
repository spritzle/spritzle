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

Hooks are run when a corresponding [libtorrent alert](http://libtorrent.org/reference-Alerts.html) fires. Currently, all torrent alerts that belong to the status_notification category will activate.  See the [libtorrent alert](http://libtorrent.org/reference-Alerts.html) page for all possible alerts.

These hooks will be passed the following arguments in this order:

* info_hash: a string of the torrent's info_hash
* tags: a comma-delimited string of tags associated with this torrent

Writing Hooks
-------------

When a hookable alert fires, Spritzle will try to run hooks for that alert in the following manner:

 * find files in the hooks directory that name ends in the alert name
   * files that start with a non-alphanumeric character are ignored
   * files that are not set executable are ignored
 * hooks are then run in alphanumeric order

As an example, let's write some hooks for the [torrent_finished_alert](http://libtorrent.org/reference-Alerts.html#torrent-finished-alert).

The default directory for hooks is ~/.config/spritzle/hooks.

We want to have multiple hooks run when this alert fires, so we are going to prepend the hook file names with a number.

```bash
touch ~/.config/spritzle/hooks/100_torrent_finished_alert
touch ~/.config/spritzle/hooks/200_torrent_finished_alert
touch ~/.config/spritzle/hooks/300_torrent_finished_alert
```

Edit these files and put in any you wish to do when the script runs. It's suggested to use the spritzle-cli program if you need to interact with spritzled.  Some examples are in the Examples section, but here is what the beginning of your script may look like if written in bash.

```bash
#!/bin/bash
#
# 100_torrent_finished_alert
#

info_hash=$1
tags=$2

#<...do something...>

```

Remember that any hook that you want executed needs to have it's execute bit set.

```bash
chmod +x ~/.config/spritzle/hooks/*_torrent_finished_alert
```

Examples
--------

torrent_finished_alert - move storage of datas for a torrent after it completes based on a tag.

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
	spritzle move_storage "${info_hash}" "/my/linuxiso/storage"
fi

```

