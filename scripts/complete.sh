_spritzle_info_hashes() {
    spritzle list --no-header -f info_hash 2>/dev/null
}

_spritzle_flags() {
    echo "apply_ip_filter auto_managed duplicate_is_error override_trackers override_web_seeds paused seed_mode sequential_download share_mode stop_when_ready super_seeding update_subscribe upload_mode"
}

_spritzle() {
    local cur prev cmd
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local global_opts="-c --config -h --host -p --port -t --token --help"
    local commands="add auth config flags list move_storage pause remove resume settings stats"

    # Find the subcommand if already provided
    cmd=""
    local i
    for ((i = 1; i < COMP_CWORD; i++)); do
        local word="${COMP_WORDS[i]}"
        case "${word}" in
            -c|--config|-h|--host|-p|--port|-t|--token)
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
                COMPREPLY=($(compgen -W "--help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "$(_spritzle_info_hashes)" -- "${cur}"))
            fi
            ;;
        remove)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--delete-files --help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "$(_spritzle_info_hashes)" -- "${cur}"))
            fi
            ;;
        move_storage)
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
                COMPREPLY=($(compgen -W "-s --sets -u --unsets --header --no-header --help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "$(_spritzle_info_hashes)" -- "${cur}"))
            fi
            ;;
        add)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--tag --file --url --info-hash --help" -- "${cur}"))
            else
                COMPREPLY=($(compgen -f -- "${cur}"))
            fi
            ;;
        list)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-q --query -f --field -s --sort --header --no-header --help" -- "${cur}"))
            fi
            ;;
        settings)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "-s --sets --header --no-header --help" -- "${cur}"))
            fi
            ;;
        stats)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--header --no-header --help" -- "${cur}"))
            fi
            ;;
        auth)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--password --help" -- "${cur}"))
            fi
            ;;
        config)
            if [[ "${cur}" == -* ]]; then
                COMPREPLY=($(compgen -W "--help" -- "${cur}"))
            fi
            ;;
    esac
}

complete -F _spritzle spritzle
