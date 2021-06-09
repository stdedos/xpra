#!/bin/bash
#
# XPRA autocomplete commands
#
# Author: "Ntentos, Stavros" <stdedos@gmail.com>

# # shellcheck source=/home/stdedos/Documents/projects/ATracking/bash-oo-framework/your-script.sh
# . "${HOME}/Documents/projects/ATracking/bash-oo-framework/your-script.sh"

# import util/exception

join_by() { local d=$1; shift; echo -n "$1"; shift; printf "%s" "${@/#/$d}"; }

echoErr() { >&2 printf '%s\n' "$*" ; }

# FIXME: Should be replaced by a real `xpra config x.y` function
if ! declare -F "xpra-config" &> /dev/null; then
  xpra-config() { :; }
  export -f xpra-config
fi

trap-error() {
	{
		echo
		# for arg; do echoErr "- '${arg}'" ; done
		echo "Error at ${BASH_SOURCE[1]##*/}:${FUNCNAME[1]}[${BASH_LINENO[0]}]: $1"
		echo "Call stack (first call last):"
		for arg in "${FUNCNAME[@]}" ; do echo "- '${arg}'" ; done

		test -e "${BASH_SOURCE[1]}" || return
		echo
		grep -nFC2 "$1" "${BASH_SOURCE[1]}"
	} > /dev/tty
}

xpra-is-it-display-time() {
	if [ "${#}" -le 3 ] ; then
		echoErr "Illegal number of parameters."
		echoErr "Usage: $(basename "${BASH_SOURCE[0]}")(${FUNCNAME[0]}) 'words[1]' 'cword' 'commands' '[cur]'"
		echoErr
		echoErr "Gave:"
		for arg; do echoErr "'${arg}'" ; done

		return 125
	fi

	local words_1 cword commands cur DISPLAY_COL

	words_1="$1"
	cword="$2"
	commands="$3"
	cur="$4"

	# if it's the first word after xpra, an empty string
	# means we have yet to pick operation - it's not display time
	[ -z "${words_1}" ] && return 1
	# if the current text does not look like a display
	# (i.e. /:?\d+/ or empty) - it's not display time
	# (Maybe it could've been, but a smart user opted to ignore it)
	grep -qP '^(:?\d*|$)' <<< "${cur:-}" || return 1

	commands="$(grep -Fe "${words_1} " <<< "${commands}")"

	# No heuristics for non-unique command!
	if [ "$(wc -l <<< "${commands}")" -ne 1 ] ; then
		echoErr "Non-unique '${words_1}' for:"
		echoErr "${commands}"
		echoErr "-------------------------"
		return 124
	fi

	if grep -qviF "DISPLAY" <<< "${commands}" ; then
		return 1
	fi

	DISPLAY_COL="$(awk -v b="DISPLAY" '{for (i=1;i<=NF;i++) { if ($i ~ b) { print i } }}' <<< "${commands}")"
	# Must be a number
	case ${DISPLAY_COL} in
		''|*[!0-9]*) return 1 ;;
		*) :;;
	esac

	[ "${DISPLAY_COL}" -ge "${cword}" ] || return $?

	xpra-return-displays "${cur}"
	[ -n "${COMPREPLY[*]}" ] || return $?
}

xpra-return-displays() {
	local displays
	# Or `displays`, but that means we may ask xpra to connect to :0
	# (shadow sessions are usually meant to be `start`ed, not e.g. `attach`ed to)
	displays="$(xpra list-sessions | grep -ivP '^Found' | grep -iFe "${1:-}" | awk '{print $1}' | tr '\n' ' ')"
	mapfile -t COMPREPLY <<< "$(compgen -W "${displays}" -- "${1:-}")"
}

_xpra() {
	local c cur words cword cur opts
	local COMMANDS flag
	local -a TRICKY_COMMANDS

	local shortcut_verbs='-h --help help --version'
	local COMPLETION_DEBUG="${XPRA_COMPLETION_DEBUG:-false}"
	local COMPLETION_DEBUG_HEAVY="${XPRA_COMPLETION_DEBUG_HEAVY:-false}"

	if [ "$(type -t _get_comp_words_by_ref)" != function ]; then
		return 1
	fi

	COMPREPLY=()
	TRICKY_COMMANDS=(clean-sockets clean-displays shell exit)

	# # Ignore ':' as a word-splitter
	# __get_cword_at_cursor_by_ref ":" words cword cur
	_get_comp_words_by_ref -n ":=" -w words -i cword -c cur

	if "${COMPLETION_DEBUG}" ; then
		BASH_XTRACEFD="19"
		exec 19> "$(dirname "${BASH_SOURCE[0]}")/xtrace_bash_${FUNCNAME[0]}.log"

		trap 'trap-error "${BASH_COMMAND}"' ERR
		{
			echo
			printf 'words(%d): ' "${#words[@]}"
			join_by ',' "${words[@]}"
			echo
			echo "cur=${cur}"
			echo "cword=${cword}"
			echo "prev=${words[${#words}-1]}"
			echo "words[1]=${words[1]}"
			echo
			echo "COMP_LINE=${COMP_LINE}"
			echo "COMP_WORDS=(${COMP_WORDS[*]})"
			echo "COMP_CWORD=${COMP_CWORD}"
			echo "COMP_POINT=${COMP_POINT}"
		} >&19

		if "${COMPLETION_DEBUG_HEAVY}" ; then
			# Find the file, use tail
			export PS4='+ $(basename "$BASH_SOURCE"):$FUNCNAME:$LINENO> '
			set -x
		fi
	fi

	COMMANDS="$(xpra tell-me-the-subcommandz | /bin/grep -P '(?<=^\s)\s*xpra' | perl -pe 's/\s*xpra\s*//g')"
	if [ "${cword}" -eq 1 ] ; then
		# Mask commands we perceive that they are not for the common user, but
		# allow them if we are asked to (ala `git config completion.commands`)
		for c in "${TRICKY_COMMANDS[@]}" ; do
			if xpra-config get autocomplete.allow | grep -qFe "$c" ; then
				"${COMPLETION_DEBUG}" && >&19 echo "* Allowing ignored command '$c'"
				continue
			fi
			COMMANDS="$(grep -vFe "$c" <<< "${COMMANDS}")"
		done

		opts="$(grep -ie "${cur}" <<< "${COMMANDS}" | cut -f1 -d' ' | tr '\n' ' ')"

		# No commands - no problem
		[ -z "${opts}" ] && return 1

		mapfile -t COMPREPLY <<< "$(compgen -W "${opts} ${shortcut_verbs}" -- "${cur}")"
		return 0
	fi

	# No need to complete after these
	if [[ " ${shortcut_verbs} " = *" ${words[1]} "* ]] ; then
		return 0
	fi

	# Shouldn't it require `grep -vP ' :\d+ ' <<< "${words[*]} " &&`?
	if [[ "${words[1]}" != *"start"* ]] && xpra-is-it-display-time "${words[1]}" "${cword}" "${COMMANDS}" "${cur}" ; then
		: xpra-is-it-display-time alreay set the result
	elif [ "${words[1]}" == "control" ] ; then
		# `xpra control X ...` does not seem kind enough to expose API ...

		# `xpra control X ...` and `xpra control X client ...`
		# seem to share any '...' command ...
		[ "${words[3]}" == "client" ] && cword="$((cword - 1))"
		case "${cword}" in
			3) opts='client debug';;
			4) opts='enable disable';;
			*) COMPREPLY=() ; return 0 ;;
		esac
		[ "${words[3]}" == "client" ] && opts="${opts//client/}"

		mapfile -t COMPREPLY <<< "$(compgen -W "${opts}" -- "${cur}")"
	else
		COMMANDS="$(xpra --help | grep -P '^\s*--?' | perl -pe 's/^\s+//' | perl -pe 's/,\s+/\n/' | grep -P '^\s*--?' | awk '{print $1}' | grep -ve '--close-stderr')"
		# From xpra --help:
		# * Keep only lines starting with --?
		# * Trim whitespace
		# * Some flags have shorthand options, split at ', '
		# * ... but also explanations have ', ', so filter again
		# * `--close-stderr` manages to elude filtering :-p

		# Filter against cur
		COMMANDS="$(grep -Fe "${cur/=*}" <<< "${COMMANDS}")" || true

		# No commands - no problem
		[ -z "${COMMANDS}" ] && return 1

		# More than one
		if [ "$(wc -l <<< "${COMMANDS}")" -ne 1 ] ; then
			"${COMPLETION_DEBUG}" && >&19 echo "cur='${cur}'"
		  COMMANDS="$(grep -iFe "${cur}" <<< "${COMMANDS}")"
			"${COMPLETION_DEBUG}" && >&19 echo "COMMANDS='${COMMANDS}'"

			opts="$(tr '\n' ' ' <<< "${COMMANDS}")"
			if [ "$(wc -l <<< "${COMMANDS}")" -gt 1 ] && [ -n "${cur}" ] ; then
				opts="${opts} ${cur}..."
			fi
			mapfile -t COMPREPLY <<< "$(compgen -W "${opts}")"
			return 0
		elif grep -qF '=' <<< "${COMMANDS}" && [[ "${cur}" != *'='* ]] ; then
			# "Not more than one and has something" (i.e. exactly 1), but has options
			compopt -o nospace

			# Same logic as ahead - keeping as-is for tracking purposes
		  flag="$(cut -f1 -d'=' <<< "${COMMANDS}")"
			COMPREPLY=("${flag}=")

			return 0
		fi

		# Just one with =-options: Need to complete without appending a space
		# https://unix.stackexchange.com/a/212308/266638
		flag="$(cut -f1 -d'=' <<< "${COMMANDS}")"
		if grep -qF '=' <<< "${cur}" && grep -qF '|' <<< "${COMMANDS}"  ; then
			# If the flag has a set of options, and user started completing them, autocomplete
			compopt -o nosort
			# Good example of that --opengl=(yes|no|auto)[:backends]
			opts="$(cut -f2 -d'=' <<< "${COMMANDS}" | tr '|' ' ' | perl -pe 's/[()]//g')"
			mapfile -t COMPREPLY <<< "$(compgen -W "${opts}" -- "${cur#*=}")"
		else
			# Otherwise, present them and wait for the user to fill in the option

			if [ "${flag}=" == "${cur}" ] ; then
				# Hacky way to print argument help in bash:
				#
				# compgen -W cannot contain `=`.
				# Therefore, we have to -S (suffix) / compopt -o nospace it
				#
				# Next, we press "Tab" again; curr now is --arg=
				# However, flag can only be --arg
				#
				# Thus, we get into a loop that we are trying to
				# compgen -W '--arg' -- '--arg=', which is impossible*
				# However, compgen has to tell us this _eventually_.
				#
				# Which leads into us being able to printf _and_ our prompt is
				# getting re-generated from the second time onwards.
				#
				# *= `-P/S` flags are applied *after* compgen returns matches for cur!
				printf '\n%s' "${COMMANDS}"
			fi

			compopt -o nospace
			mapfile -t COMPREPLY <<< "$(compgen -S'=' -W "${flag}" -- "${cur}")"
		fi
	fi

	return $?
}

complete -F _xpra xpra
# complete -F _xpra -o filenames xpra
