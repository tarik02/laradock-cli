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
import grp
import importlib.util
from collections import namedtuple
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

laradock env
    Setup project's .env file automagically.

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
LARADOCK_CONTAINERS_ROOT = LARADOCK_ROOT/'.laradock'

if len(sys.argv) == 1:
    sys.stdout.write(HELP)
    exit(1)

action = sys.argv[1]
args = sys.argv[2:]

try:
    if action == 'help':
        print(HELP)
        exit(1)
    elif action == 'init':
        env_file = LARADOCK_CONTAINERS_ROOT/'.env'
        if not env_file.exists:
            env_file = LARADOCK_CONTAINERS_ROOT/'env-example'
        with env_file.open('r') as f:
            env = f.read()

        DOCKER_GID = grp.getgrnam('docker').gr_gid
        env = re.sub(r'APP_CODE_PATH_CONTAINER=[^\n]*', f'APP_CODE_PATH_CONTAINER={LARADOCK_ROOT}', env)
        env = re.sub(r'DOCKER_GID=[^\n]*', f'DOCKER_GID={DOCKER_GID}', env)

        with (LARADOCK_CONTAINERS_ROOT/'.env').open('w') as f:
            f.write(env)
        exit(0)
    elif action == 'upgrade':
        response = urllib.request.urlopen(UPGRADE_URL)
        data = response.read().decode('utf-8')
        with open(__file__, 'w') as f:
            f.write(data)
        print('Upgrade successfull.')
        exit(0)
except KeyboardInterrupt:
    print('Interrupted')
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)


env = dotenv_values(LARADOCK_CONTAINERS_ROOT/'.env')

APP_CODE_PATH = (LARADOCK_CONTAINERS_ROOT/env['APP_CODE_PATH_HOST']).resolve()
APP_CODE_PATH_HOST = env['APP_CODE_PATH_HOST']
APP_CODE_PATH_CONTAINER = env['APP_CODE_PATH_CONTAINER']
LARADOCK_CLI_DEFAULT_CONTAINERS = (env.get('LARADOCK_CLI_DEFAULT_CONTAINERS') or 'nginx,mysql,workspace').split(',')
LARADOCK_CLI_DEFAULT_WORKSPACE = env.get('LARADOCK_CLI_DEFAULT_WORKSPACE') or 'workspace'
LARADOCK_CLI_WORKSPACE_PREFIX = env.get('LARADOCK_CLI_WORKSPACE_PREFIX') or 'workspace'


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
            *[i for i in args if i is not None],
        ],
        cwd=LARADOCK_CONTAINERS_ROOT,
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


def find_project_root_dir(start: Path = Path.cwd()) -> Optional[Path]:
    if LARADOCK_CONTAINERS_ROOT in (start, *start.parents):
        return None

    for path in [start, *start.parents]:
        if path == LARADOCK_ROOT:
            break

        if (path/'.env').exists or (path/'.env.example').exists:
            return path

    return None


def find_project_env_file(start: Path = Path.cwd()) -> Optional[Path]:
    project_dir = find_project_root_dir(start)
    if project_dir is None:
        return None

    env_file = project_dir/'.env'

    if env_file.exists:
        return env_file

    return None


def load_project_env(start: Path = Path.cwd()) -> dict:
    env_file = find_project_env_file(start)
    if env_file is None:
        return {}

    return dotenv_values(env_file)


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


try:
    if action == 'env':
        project_dir = find_project_root_dir()
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
        if len(LARADOCK_CLI_DEFAULT_CONTAINERS) == 0:
            print('No containers to start')
        else:
            start_services(LARADOCK_CLI_DEFAULT_CONTAINERS)
    elif action == 'stop':
        compose('down')
    elif action == 'restart':
        if len(LARADOCK_CLI_DEFAULT_CONTAINERS) == 0:
            print('No containers to start')
        else:
            compose('down')
            start_services(LARADOCK_CLI_DEFAULT_CONTAINERS)
    elif action == 'enter':
        container_name = args[0] if len(args) >= 1 else load_project_env().get('LARADOCK_CLI_WORKSPACE', LARADOCK_CLI_DEFAULT_WORKSPACE)
        compose(
            'exec',
            '--user=laradock' if container_name.startswith(LARADOCK_CLI_WORKSPACE_PREFIX) else None,
            '--env',
            f'LARADOCK_ROOT={APP_CODE_PATH_CONTAINER}',
            '--workdir',
            path_host_to_container(Path.cwd()) or APP_CODE_PATH_CONTAINER,
            container_name,
            'sh',
            '-c',
            f'clear && bash -c \\$SHELL',
        )
    elif action == 'sudo':
        container_name = load_project_env().get('LARADOCK_CLI_WORKSPACE', LARADOCK_CLI_DEFAULT_WORKSPACE_CONTAINER)
        compose(
            'exec',
            '--user=root',
            '--env',
            f'LARADOCK_ROOT={APP_CODE_PATH_CONTAINER}',
            '--workdir',
            path_host_to_container(Path.cwd()) or APP_CODE_PATH_CONTAINER,
            container_name,
            'sh',
            '-c',
            f'clear && bash -c \\$SHELL',
        )
    elif action == 'up':
        if len(args) == 0:
            project_env = load_project_env()

            if 'LARADOCK_CLI_SERVICES' in project_env:
                args = project_env['LARADOCK_CLI_SERVICES'].split(',')
            else:
                print('Specify LARADOCK_CLI_SERVICES variable in your project .env file.')
                exit(-1)

        start_services(args)
    elif action == 'down':
        compose('stop', *args)
    elif action == 'reup':
        compose('stop', *args)
        start_services(args)
    elif action == 'reload':
        compose('exec', 'nginx', 'nginx', '-s', 'reload')
    elif action == 'run':
        container_name = load_project_env().get('LARADOCK_CLI_WORKSPACE', LARADOCK_CLI_DEFAULT_WORKSPACE_CONTAINER)
        command = shellquote(' '.join(args))
        compose(
            'exec',
            '--user=laradock' if container_name.startswith(LARADOCK_CLI_WORKSPACE_PREFIX) else None,
            '--env',
            f'LARADOCK_ROOT={APP_CODE_PATH_CONTAINER}',
            '--workdir',
            path_host_to_container(Path.cwd()) or APP_CODE_PATH_CONTAINER,
            container_name,
            'sh',
            '-c',
            f'bash -c {command}',
        )
    else:
        if (LARADOCK_ROOT/'commands.py').exists():
            spec = importlib.util.spec_from_file_location('commands', LARADOCK_ROOT/'commands.py')
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            project_dir = find_project_root_dir()
            project_env = None

            if project_dir is not None and (project_dir/'.env').exists():
                project_env = dotenv_values(project_dir/'.env')

            if hasattr(mod, action):
                sys.exit(getattr(mod, action)(
                    namedtuple('Context', ['compose', 'laradock_env', 'project_dir', 'project_env', 'args'])(
                        compose,
                        env,
                        project_dir,
                        project_env,
                        args,
                    )
                ))

        compose(action, *args)
except KeyboardInterrupt:
    print('Interrupted')
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
