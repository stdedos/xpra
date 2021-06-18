#!/usr/bin/env python3

__doc__ = '''
XPRA bash completion testing

Inspired from:
* https://github.com/lacostej/unity3d-bash-completion/blob/master/lib/completion.py
* http://stackoverflow.com/questions/9137245/unit-test-for-bash-completion-script
'''

__author__ = 'Ntentos Stavros <133706+stdedos@users.noreply.github.com>'

import sys
import shlex
import textwrap
import functools

import pytest

from pathlib import Path
from subprocess import Popen, run, PIPE
from typing import Optional, Union

MY_DIR = Path(__file__).parents[0]
COMPLETION_LOCATION = Path('../../../fs/share/bash-completion/completion/xpra-autocomplete.sh')
XPRA_AUTOCOMPLETE_SH = MY_DIR / COMPLETION_LOCATION


@pytest.fixture(scope='session', autouse=True)
def preconditions():
    global XPRA_AUTOCOMPLETE_SH
    check_for_sessions = run(['xpra', 'list-sessions'], stdout=PIPE,
                             universal_newlines=True, check=True).stdout

    # We want to exit with a bang... and two times
    partial_exit = functools.partial(pytest.exit, returncode=pytest.ExitCode.INTERNAL_ERROR)
    if 'Found 0 xpra sessions:' not in check_for_sessions:
        partial_exit('In order to run these tests, xpra must have 0 ongoing displays!')

    if not XPRA_AUTOCOMPLETE_SH.is_file():
        partial_exit(f'Wrong filename to source xpra completions! (Gave: "{XPRA_AUTOCOMPLETE_SH}")')

    XPRA_AUTOCOMPLETE_SH = XPRA_AUTOCOMPLETE_SH.absolute()


# Trying to match Bash naming with COMP_, and FORCE_LOAD_COMPLETIONS is a constant
# noinspection PyPep8Naming
def bash_complete(program: str,
                  command: str = '',
                  pre_execute: Optional[Union[list, str]] = None) -> Popen:
    """
    Start bash completion for program, optionally after sourcing a file, and/or giving arguments.
    To start a new word completion, remember to end the string with a whitespace
    (corner case of empty string i.e. completion after executable is covered)

    :param program: executable to complete against
    :param command: command to complete against (empty for the program itself)
    :param pre_execute: pre-load (source) files to bash
    :return: subprocess.Popen object
    """
    FORCE_LOAD_COMPLETIONS = ' '.join(textwrap.dedent('''
    if shopt -oq posix; then 
        >&2 echo "Cannot load completions! (?)" ;
        exit 125 ;
    else 
        if [ -f /usr/share/bash-completion/bash_completion ]; then
            . /usr/share/bash-completion/bash_completion;
        elif [ -f /etc/bash_completion ]; then
            . /etc/bash_completion;
        fi ;
    fi
    ''').split('\n'))

    COMP_WORDS = [program.rstrip()]
    COMP_WORDS.extend(shlex.split(command))
    COMP_LINE = shlex.join(COMP_WORDS)

    COMP_CWORD = len(COMP_WORDS) - 1
    COMP_POINT = len(COMP_LINE)

    if not command or (command and command[-1] == ' '):
        COMP_WORDS.append(" ")
        COMP_CWORD += 1

    # Prepare the completion, find the autocompletion function, call it, and get the result
    full_cmdline = f'COMP_LINE="{COMP_LINE}"; ' \
                   f'COMP_WORDS=({COMP_LINE}); ' \
                   f'COMP_CWORD={COMP_CWORD}; ' \
                   f'COMP_POINT={COMP_POINT}; ' \
                   f'"$(complete -p {shlex.quote(program)} | sed "s/.*-F \\([^ ]*\\) .*/\\1/")" && ' \
                   f'echo ${{COMPREPLY[*]}} '
    if isinstance(pre_execute, str):
        pre_execute = [pre_execute]
    pre_execute.insert(0, FORCE_LOAD_COMPLETIONS)

    if isinstance(pre_execute, list):
        full_cmdline = '; '.join([*pre_execute, full_cmdline])

    proc = Popen(['timeout', '5', 'bash', '-c', full_cmdline],
                 stdout=PIPE, stderr=PIPE, universal_newlines=True)
    return proc


def xpra_complete(complete: str = '',
                  pre_execute: Optional[Union[list, str]] = None) -> Popen:
    if isinstance(pre_execute, str):
        pre_execute = [pre_execute]
    if pre_execute is None:
        pre_execute = []

    # prepend xpra completion
    pre_execute.insert(0, f'source {shlex.quote(str(XPRA_AUTOCOMPLETE_SH))}')

    return bash_complete('xpra', complete, pre_execute)


shortcut_verbs = ['-h', '--help', 'help', '--version']

# Hacky testing of no-tricky-command-allowance: `''`
tricky_commands = ['', 'shell', 'exit', 'clean-sockets', 'clean-displays']
tricky_commands_ids = [f'''xpra.config get autocomplete.allow "{', '.join(tricky_commands[0:i + 1])}"'''
                       for i in range(len(tricky_commands))]


@pytest.mark.parametrize('verb_no', range(len(tricky_commands)), ids=tricky_commands_ids)
def test_xpra_verbs(verb_no):
    expand_matches = 'xpra-config() { echo %s ; }; export -f xpra-config'
    default_verbs = [
        'start', 'start-desktop', 'upgrade', 'upgrade-desktop', 'recover', 'shadow', 'attach', 'detach', 'info',
        'version', 'stop', 'screenshot', 'control', 'print', 'showconfig', 'list', 'list-sessions', 'list-windows',
        'sessions', 'launcher', 'gui', 'start-gui', 'displays', 'list-mdns', 'mdns-gui', *shortcut_verbs,
    ]

    allowable_verbs = tricky_commands[0:verb_no + 1]
    allow_verbs = expand_matches % shlex.quote(' '.join(allowable_verbs))
    allowable_verbs.pop(0)  # pop the no-arg '', interferes with assertion
    proc = xpra_complete(pre_execute=allow_verbs)
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert sorted(completions) == sorted([*default_verbs, *allowable_verbs])
    assert proc.returncode == 0


@pytest.mark.parametrize('verb', shortcut_verbs)
def test_xpra_no_autocomplete_after_version(verb):
    proc = xpra_complete(f'{verb} ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    assert not stdout
    assert proc.returncode == 0


FLAG_NO = 183


def test_xpra_flags():
    proc = xpra_complete('info ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert len(completions) == FLAG_NO

    # Not an xpra argument
    assert '--close-stderr' not in completions

    # Partial flag completion (i.e. a hack to keep the partial flag matching around)
    # should not be display when there is no parsed argument
    assert any(['...' in x for x in completions])
    assert proc.returncode == 0


def test_xpra_no_partial_matching_on_zero_results():
    proc = xpra_complete(f'attach not-a-flag-argument')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert not [x for x in completions if x]
    assert proc.returncode == 1


def test_xpra_autocomplete_flags_grep():
    partial_completion = 'spla'
    proc = xpra_complete(f'attach {partial_completion}')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    expected = ['--resize-display=yes|no|widthxheight', '--splash=yes|no|auto',
                '--use-display=yes|no|auto', '--displayfd=FD', f'{partial_completion}...']
    assert sorted(completions) == sorted(expected)
    assert proc.returncode == 0

    proc = xpra_complete(f'attach splash')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == ['--splash=']
    assert proc.returncode == 0

    proc = xpra_complete(f'attach --splash=')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == ['yes', 'no', 'auto']
    assert proc.returncode == 0

    proc = xpra_complete(f'info --html=')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == ['on', 'off', '[HOST:]PORT']
    assert proc.returncode == 0

    proc = xpra_complete(f'info --opengl=')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == ['yes', 'no', 'auto[:backends]']
    assert proc.returncode == 0


def test_xpra_autocomplete_debug_opts():
    proc = xpra_complete('attach -d ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert len(completions) == 111
    assert proc.returncode == 0

    proc = xpra_complete('attach -d sc')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert sorted(completions) == sorted(['scaling', 'score', 'screen', 'scroll'])
    assert proc.returncode == 0

    proc = xpra_complete('attach -d sca')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert sorted(completions) == sorted(['scaling'])
    assert proc.returncode == 0
    # But will leave a space - should find a way to assert that

    proc = xpra_complete('attach -d scaling,sc')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert sorted(completions) == sorted(['score', 'screen', 'scroll'])
    assert proc.returncode == 0

    proc = xpra_complete('attach -d scaling,scro')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == ['scaling,scroll']
    assert proc.returncode == 0
    # But won't leave a space - should find a way to assert that


if __name__ == '__main__':
    # # Running tests via PyCharm gives erroneous results:
    # Verb arguments:
    #  'recover',
    #  'start',
    #  'start-desktop',
    #  'upgrade',
    #  'upgrade-desktop',
    # are missing (#test_xpra_verbs), total no of flags are 183 (and not 167, #test_xpra_flags), and flags
    #  '--resize-display=yes|no|widthxheight',
    #  '--splash=yes|no|auto',
    # are missing (#test_xpra_autocomplete_flags_grep)!
    pytest.main([__file__, *sys.argv[1:]])
