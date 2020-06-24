#!/usr/bin/env python3

###############################################################################
# laradock-cli: https://github.com/Tarik02/laradock-cli                       #
###############################################################################

import sys
import subprocess
import os
import urllib.request
from pathlib import Path
from typing import Optional
from dotenv import dotenv_values


UPGRADE_URL = 'https://raw.githubusercontent.com/Tarik02/laradock-cli/master/cli.py'

HELP = '''
Usage: laradock <command> <...args>

laradock init [patch url]
    Initialize laradock environment. If specified, a patch will be downloaded and applied to Laradock.

laradock upgrade
    Replace current cli with the latest version.

laradock start
    Start default services (as for now, it is nginx, mysql and workspace).

laradock stop
    Stop all services.

laradock restart
    Stop all services, start default services.

laradock enter
    Enter into running workspace container.

laradock up [services...]
    Start the specified services.

laradock down [services...]
    Stop the specified services.

laradock reup [services...]
    Stop and then start the specified services.

laradock reload
    Reload nginx configuration.

laradock run <command>
    Execute the specified command inside workspace.

laradock <...command>
    Run specified command inside laradock's folder using docker-compose.
'''.strip() + '\n'


LARADOCK_ROOT = Path(os.environ['LARADOCK_ROOT'])

if len(sys.argv) == 1:
    sys.stdout.write(HELP)
    exit(1)

action = sys.argv[1]
args = sys.argv[2:]

if action == 'help':
    print(HELP)
    exit(1)
elif action == 'init':
    with (LARADOCK_ROOT/'.laradock'/'env-example').open('r') as f:
        env = f.read()
    env = env.replace('APP_CODE_PATH_CONTAINER=/var/www', f'APP_CODE_PATH_CONTAINER={LARADOCK_ROOT}')
    with (LARADOCK_ROOT/'.laradock'/'.env').open('w') as f:
        f.write(env)
    exit(0)
elif action == 'upgrade':
    response = urllib.request.urlopen(UPGRADE_URL)
    data = response.read().decode('utf-8')
    with open(__file__, 'w') as f:
        f.write(data)
    print('Upgrade successfull.')
    exit(0)

env = dotenv_values(LARADOCK_ROOT/'.laradock'/'.env')

APP_CODE_PATH = (LARADOCK_ROOT/'.laradock'/env['APP_CODE_PATH_HOST']).resolve()
APP_CODE_PATH_HOST = env['APP_CODE_PATH_HOST']
APP_CODE_PATH_CONTAINER = env['APP_CODE_PATH_CONTAINER']


def path_host_to_container(host: Path) -> Optional[str]:
    try:
        return Path(APP_CODE_PATH_CONTAINER)/host.relative_to(APP_CODE_PATH)
    except ValueError:
        return None


def path_container_to_host(container: str) -> Optional[Path]:
    if container.startswith(APP_CODE_PATH_CONTAINER):
        return APP_CODE_PATH/container[len(APP_CODE_PATH_CONTAINER) + 1:]
    else:
        return None


def compose(*args):
    code = subprocess.run(
        [
            'docker-compose',
            *args,
        ],
        cwd=LARADOCK_ROOT/'.laradock',
    ).returncode
    if code != 0:
        exit(code)


def start_services(services):
    return compose(
        'up',
        '-d',
        *services,
    )


def shellquote(s):
    return "'" + s.replace("'", "'\\''") + "'"


if action == 'start':
    start_services([
        'nginx',
        'mysql',
        'workspace',
    ])
elif action == 'stop':
    compose('down')
elif action == 'restart':
    compose('down')
    start_services([
        'nginx',
        'workspace',
    ])
elif action == 'enter':
    compose(
        'exec',
        '--user=laradock',
        '--env',
        f'LARADOCK_ROOT={APP_CODE_PATH_CONTAINER}',
        '--workdir',
        path_host_to_container(Path.cwd()) or APP_CODE_PATH_CONTAINER,
        'workspace',
        'sh',
        '-c',
        f'clear && bash -c $SHELL',
    )
elif action == 'sudo':
    compose(
        'exec',
        '--env',
        f'LARADOCK_ROOT={APP_CODE_PATH_CONTAINER}',
        '--workdir',
        path_host_to_container(Path.cwd()) or APP_CODE_PATH_CONTAINER,
        'workspace',
        'sh',
        '-c',
        f'clear && bash -c $SHELL',
    )
elif action == 'up':
    start_services(args)
elif action == 'down':
    compose('stop', *args)
elif action == 'reup':
    compose('stop', *args)
    start_services(args)
elif action == 'reload':
    compose('exec', 'nginx', 'nginx', '-s', 'reload')
elif action == 'run':
    command = shellquote(' '.join(args))
    compose(
        'exec',
        '--user=laradock',
        '--env',
        f'LARADOCK_ROOT={APP_CODE_PATH_CONTAINER}',
        '--workdir',
        path_host_to_container(Path.cwd()) or APP_CODE_PATH_CONTAINER,
        'workspace',
        'sh',
        '-c',
        f'bash -c {command}',
    )
else:
    compose(action, *args)
