_spritzle_info_hashes() {
    spritzle list --plain --no-header -f info_hash 2>/dev/null
}

_spritzle_flags() {
    echo "apply_ip_filter auto_managed duplicate_is_error override_trackers override_web_seeds paused seed_mode sequential_download share_mode stop_when_ready super_seeding update_subscribe upload_mode"
}

_spritzle_remote_subcommands() {
    echo "add list use remove show status set-key"
}

_spritzle_remotes() {
    spritzle remote list --plain 2>/dev/null | awk '{print $1}' | sed 's/^\*//'
}

_spritzle() {
    local cur prev cmd
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local global_opts="-c --config -r --remote --color --no-color --help"
    local commands="add completion config daemon-config flags help info list move-storage pause remote remove resume settings stats status top"

    # Find the subcommand if already provided
    cmd=""
    local i
    for ((i = 1; i < COMP_CWORD; i++)); do
        local word="${COMP_WORDS[i]}"
        case "${word}" in
            -c|--config|-r|--remote)
                ((i++)) # skip option argument
                ;;
            -*)
                ;;
            *)
                cmd="${word}"
                break
                ;;
        esac
    done

    # If no subcommand found yet
    if [[ -z "${cmd}" ]]; then
        if [[ "${cur}" == -* ]]; then
            COMPREPLY=($(compgen -W "${global_opts}" -- "${cur}"))
        else
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
        fi
        return 0
    fi

    # Subcommand-specific completion
    case "${cmd}" in
        pause|resume)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-q --query --all -Q --quiet --help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "$(_spritzle_info_hashes)" -- "${cur}"))
            fi
            ;;
        remove)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--delete-files -q --query --all -Q --quiet --help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "$(_spritzle_info_hashes)" -- "${cur}"))
            fi
            ;;
        info)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--json --plain --help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "$(_spritzle_info_hashes)" -- "${cur}"))
            fi
            ;;
        move-storage)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--help" -- "${cur}"))
            elif [[ ${COMP_CWORD} -eq $((i+1)) ]]; then
                COMPREPLY=($(compgen -W "$(_spritzle_info_hashes)" -- "${cur}"))
            else
                COMPREPLY=($(compgen -d -- "${cur}"))
            fi
            ;;
        flags)
            case "${prev}" in
                -s|--sets|-u|--unsets)
                    COMPREPLY=($(compgen -W "$(_spritzle_flags)" -- "${cur}"))
                    return 0
                    ;;
            esac
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-s --sets -u --unsets -q --query --all --header --no-header --json --plain --help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "$(_spritzle_info_hashes)" -- "${cur}"))
            fi
            ;;
        add)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-t --tag -o --option -Q --quiet -w --watch --json --plain --help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -f -- "${cur}"))
            fi
            ;;
        list)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-q --query -f --fields --header --no-header --json --plain --raw -w --watch -i --interval --help" -- "${cur}"))
            fi
            ;;
        top)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-i --interval -q --query --plain --help" -- "${cur}"))
            fi
            ;;
        settings)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-s --set -r --reset --reset-all -m --modified -d --defaults --json --plain --help" -- "${cur}"))
            fi
            ;;
        stats)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-a --all --raw --json --plain --help" -- "${cur}"))
            fi
            ;;
        status)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--json --plain --help" -- "${cur}"))
            fi
            ;;
        completion)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "bash zsh fish" -- "${cur}"))
            fi
            ;;
        config)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-s --set -u --unset --reset --json --plain --help" -- "${cur}"))
            fi
            ;;
        daemon-config)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-s --set --json --plain --help" -- "${cur}"))
            fi
            ;;
        remote)
            local subcmd="${COMP_WORDS[i+1]}"
            if [[ ${COMP_CWORD} -eq $((i+1)) ]]; then
                if [[ "${cur}" == -* ]]; then
                    COMPREPLY=($(compgen -W "--help" -- "${cur}"))
                else
                    COMPREPLY=($(compgen -W "$(_spritzle_remote_subcommands)" -- "${cur}"))
                fi
            else
                case "${subcmd}" in
                    status)
                        if [[ "${cur}" == -* ]]; then
                            COMPREPLY=($(compgen -W "-t --timeout --json --plain --help" -- "${cur}"))
                        else
                            COMPREPLY=($(compgen -W "$(_spritzle_remotes)" -- "${cur}"))
                        fi
                        ;;
                    list)
                        if [[ "${cur}" == -* ]]; then
                            COMPREPLY=($(compgen -W "--json --plain --help" -- "${cur}"))
                        fi
                        ;;
                    use|remove|show|set-key)
                        if [[ "${cur}" == -* ]]; then
                            COMPREPLY=($(compgen -W "--help" -- "${cur}"))
                        else
                            COMPREPLY=($(compgen -W "$(_spritzle_remotes)" -- "${cur}"))
                        fi
                        ;;
                    add)
                        if [[ "${cur}" == -* ]]; then
                            COMPREPLY=($(compgen -W "-k --key -f --force --insecure --ca-cert --fingerprint --help" -- "${cur}"))
                        fi
                        ;;
                esac
            fi
            ;;
        help)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
            ;;
    esac
}

complete -F _spritzle spritzle
