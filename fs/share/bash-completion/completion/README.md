# XPRA Autocomplete

## ToDo
* Test against the git version, and not against a maybe-installed one
* Fully testing whether the display is autocompleted only once
  (or out of order e.g. `xpra attach --webcam= `, expecting display again)
* Fuller testing `xpra control :1 ...` completion
  (ofc, I need to first find the arguments to that ...)

## Developement Notes
Test with e.g.:

```bash
'bashsb' '-c' ' if shopt -oq posix; then      >&2 echo "Cannot load completions! (?)" ;     exit 125 ; else      if [ -f /usr/share/bash-completion/bash_completion ]; then         . /usr/share/bash-completion/bash_completion;     elif [ -f /etc/bash_completion ]; then         . /etc/bash_completion;     fi ; fi ; source /home/stdedos/Documents/projects/ATracking/xpra/tests/xpra/test_apps/../../../fs/share/bash-completion/completion/xpra-autocomplete.sh; xpra-config() { echo ; }; export -f xpra-config; COMP_LINE="xpra"; COMP_WORDS=(xpra); COMP_CWORD=1; COMP_POINT=4; "$(complete -p xpra | sed "s/.*-F \\([^ ]*\\) .*/\\1/")" && echo ${COMPREPLY[*]} '
```
