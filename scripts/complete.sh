_get_commands() {
	n=$(spritzle --help | grep -n 'Commands:' | cut -d ':' -f 1)
	let n=n+1
	cmds=$(spritzle --help | tail -n+$n |cut -d ' ' -f 3|xargs)
}

_spritzle() {
	local cur=${COMP_WORDS[COMP_CWORD]}
	local cmd=${COMP_WORDS[COMP_CWORD-1]}
	if [[ $COMP_CWORD -eq 1 ]]; then
		_get_commands
		COMPREPLY=($(compgen -W "${cmds}" -- "${cur}"))
		return 0
	fi
	case "$cmd" in
		remove)
			w=$(spritzle list --no-header -f info_hash | xargs)
			COMPREPLY=($(compgen -W "${w}" -- "${cur}"))
			return 0
			;;
	esac
}
complete -F _spritzle spritzle
