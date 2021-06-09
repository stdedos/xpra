#!/usr/bin/env python3

__doc__ = '''
XPRA bash completion testing

Inspired from:
* https://github.com/lacostej/unity3d-bash-completion/blob/master/lib/completion.py
* http://stackoverflow.com/questions/9137245/unit-test-for-bash-completion-script

Separate from main module, since this will use a module-wide fixture, which will change completion.
'''

__author__ = 'Ntentos Stavros <133706+stdedos@users.noreply.github.com>'

import sys
import textwrap

import pytest

from subprocess import Popen, PIPE, run

# The magics I need to do to hack these tests ...
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))
from test_xpra_completion import xpra_complete, FLAG_NO

# Including it will auto-run it
# noinspection PyUnresolvedReferences
from test_xpra_completion import preconditions

xpra_display_funcs = [
    'upgrade',
    'upgrade-desktop', 'recover', 'shadow', 'attach', 'detach',
    'info', 'version', 'stop', 'exit', 'clean-sockets', 'clean-displays',
    'screenshot filename', 'shell', 'print',
]


@pytest.fixture(scope="module")
def start_xpra_display():
    import pexpect

    obj = Popen(['xpra', 'start', '--daemon=no'],
                stdout=PIPE, stderr=PIPE, universal_newlines=True)

    with obj as proc:
        while True:
            if proc.poll() is not None:
                print(proc.communicate())
                assert False, 'xpra start failed to start and keep alive a display!'

            child = pexpect.spawn('xpra', ['list-sessions'])
            try:
                child.expect([r'\s+:\d+\s+'])
                yield child.match.group(0).decode('UTF-8').strip()
                break
            except (pexpect.EOF, pexpect.TIMEOUT):
                pass  # Try again...

        proc.terminate()
        if proc.wait(10) is None:
            proc.kill()

        # Verify xpra death
        xpra_list = run(['xpra', 'list'], stdout=PIPE,
                        universal_newlines=True, check=True)

        clean_xpra = 'No xpra sessions found' not in xpra_list.stdout
        if clean_xpra:
            message = [
                'xpra screen did not die nicely!',
                textwrap.indent(xpra_list.stdout.strip(), prefix='  > '),
                'You may want to run `xpra clean-displays` afterwards!',
            ]
            assert False, '\n'.join(message)


@pytest.mark.parametrize('cmd', xpra_display_funcs, ids=[f'xpra {x} DISPLAY' for x in xpra_display_funcs])
def test_xpra_complete_display(cmd, start_xpra_display):
    proc = xpra_complete(f'{cmd} ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == [start_xpra_display]

    # After writing the display, then only the flags get completed
    proc = xpra_complete(f'{cmd} {start_xpra_display} ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert len(completions) == FLAG_NO

    # ... but can do it out of order
    flag = '--webcam='
    proc = xpra_complete(f'{cmd} {flag[0:6]}')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == [flag]

    # # Failing right now
    # proc = xpra_complete(f'{cmd} {flag} ')
    # streams = proc.communicate()
    # stdout = streams[0].strip()
    # completions = stdout.split(' ')
    # assert completions == [start_xpra_display]


def test_xpra_control(start_xpra_display):
    proc = xpra_complete(f'control ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == [start_xpra_display]

    proc = xpra_complete(f'control {start_xpra_display} ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == ['client', 'debug']

    proc = xpra_complete(f'control {start_xpra_display} client ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')
    assert completions == ['debug']

    same_completions = [f'control {start_xpra_display} client debug ',
                        f'control {start_xpra_display} debug ']
    for c in same_completions:
        proc = xpra_complete(c)
        streams = proc.communicate()
        stdout = streams[0].strip()
        completions = stdout.split(' ')
        assert completions == ['enable', 'disable']


@pytest.mark.parametrize('cmd', ['start', 'start-desktop'])
def test_xpra_not_display(cmd, start_xpra_display):
    """
    Assert that completion *does not* offer existing xpra displays
    (... should've been like that i-if `--use-display=no`, but shhhh ...)
    """
    proc = xpra_complete(f'{cmd} ')
    streams = proc.communicate()
    stdout = streams[0].strip()
    completions = stdout.split(' ')

    # No display numbers shown, ...
    assert any([start_xpra_display not in x for x in completions])

    # ... instead, flags are shown, ...
    assert len(completions) == FLAG_NO

    # ... and all good
    assert proc.returncode == 0


if __name__ == '__main__':
    # Running tests via PyCharm gives erroneous results (see main file)
    pytest.main([__file__, *sys.argv[1:]])
