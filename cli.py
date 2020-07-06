#!/usr/bin/env python3

###############################################################################
# laradock-cli: https://github.com/Tarik02/laradock-cli                       #
###############################################################################

import sys
import subprocess
import os
import urllib.request
import shutil
import re
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


def apply_env(laradock_env: dict, project_dir: Path, project_env: dict, result_env: dict):
    project_name = project_dir.name

    if 'APP_URL' in project_env:
        result_env['APP_URL'] = f'http://{project_name}.test'

    if project_env.get('DB_CONNECTION') == 'mysql':
        result_env['DB_HOST'] = 'mysql'
        result_env['DB_PORT'] = 3306
        result_env['DB_DATABASE'] = project_name
        result_env['DB_USERNAME'] = 'root'
        result_env['DB_PASSWORD'] = laradock_env['MYSQL_ROOT_PASSWORD']

    if 'REDIS_HOST' in project_env:
        result_env['REDIS_HOST'] = 'redis'
        result_env['REDIS_PASSWORD'] = None
        result_env['REDIS_PORT'] = 6379

    if 'MAIL_DRIVER' in project_env:
        result_env['MAIL_HOST'] = 'mailhog'
        result_env['MAIL_PORT'] = 1025
        result_env['MAIL_USERNAME'] = None
        result_env['MAIL_PASSWORD'] = None
        result_env['MAIL_ENCRYPTION'] = None

    if (LARADOCK_ROOT/'env.py').exists():
        with open(LARADOCK_ROOT/'env.py') as f:
            exec(f.read(), {
                'laradock_env': laradock_env,
                'project_dir': project_dir,
                'project_env': project_env,
                'result_env': result_env,
            })


RESTRICTED_ENV_STRINGS = [
    'true', 'TRUE', 'True',
    'false', 'FALSE', 'False',
    'on', 'ON', 'On',
    'off', 'OFF', 'Off',
    'yes', 'YES', 'Yes',
    'no', 'NO', 'NO',

    'null',
]


def stringify_env_value(val, quotes: bool = True) -> str:
    if isinstance(val, Path):
        val = str(val.absolute())

    if val is True:
        return 'true'

    if val is False:
        return 'false'

    if val is None:
        return 'null'

    if isinstance(val, int) or isinstance(val, float):
        return str(val)

    if isinstance(val, str):
        should_be_quoted = re.search(r'["\'%!`, ]', val) or \
            re.match(r'^[0-9\.]', val) or \
            val in RESTRICTED_ENV_STRINGS
        if should_be_quoted:
            val = val\
                .replace('"', '\\"')\
                .replace('\n', '\\n')\
                .replace(',', '\\,')
        if should_be_quoted and quotes:
            val = f'"{val}"'
        return val

    if isinstance(val, list):
        return '"' + ','.join(map(lambda s: stringify_env_value(s, False), val)) + '"'

    raise ValueError(f'Don\'t know how to stringify "{val}"')


if action == 'env':
    project_dir = Path.cwd()
    env_file = project_dir/'.env'

    if not env_file.exists():
        print('Env file does not exist. Trying to create...')

        if (project_dir/'.env.example').exists():
            shutil.copy(project_dir/'.env.example', env_file)
        elif (project_dir/'env.example').exists():
            shutil.copy(project_dir/'env.example', env_file)
        else:
            print('Can\'t create .env file: neither .env.example nor env.example exist.')
            exit(1)

        print('.env file created successfully.')

    print('Preparing new .env file...')
    project_env = dotenv_values(env_file)
    result_env = {}

    apply_env(env, project_dir, project_env, result_env)

    with env_file.open('r') as inf, (project_dir/'.env.tmp').open('w') as outf:
        while True:
            line = inf.readline()
            if not line:
                break

            match = re.match(r'^([a-zA-Z0-9_]+)=', line)
            if not match:
                outf.write(line)
                continue

            key = match.group(1)
            if key not in result_env:
                outf.write(line)
                continue

            outf.write(f'{key}={stringify_env_value(result_env[key])}\n')

    print('Replacing an old .env file with the new one...')
    (project_dir/'.env.tmp').rename(env_file)
    print('Done!')
elif action == 'start':
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
        f'clear && bash -c \\$SHELL',
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
        f'clear && bash -c \\$SHELL',
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
