# laradock-cli

My CLI wrapper for [Laradock](https://github.com/Laradock/laradock).

## Requirements
- Docker
- Python3
- python-dotenv (`$ pip3 install python-dotenv`)

## Installation
```
$ curl -fsSL https://github.com/Tarik02/laradock-cli/raw/master/install.sh | bash
# here, restart your shell or reload your configuration
$ laradock init
```

## Usage

#### `$ laradock init [patch url]`

Initialize laradock environment. If specified, a patch will be downloaded and applied to Laradock.

#### `$ laradock upgrade`

Replace current cli with the latest version.

#### `$ laradock start`

Start default services (as for now, it is nginx, mysql and workspace).

#### `$ laradock stop`

Stop all services.

#### `$ laradock restart`

Stop all services, start default services.

#### `$ laradock enter [container]`

Enter into running workspace container. If container name is not specified, it fallbacks to `LARADOCK_WORKSPACE` from project's .env and to just `workspace` then.

#### `$ laradock up [services...]`

Start the specified services. If the services are not specified, `LARADOCK_SERVICES` variable as a comma-separated list from project's .env is used.

#### `$ laradock down [services...]`

Stop the specified services.

#### `$ laradock reup [services...]`

Stop and then start the specified services.

#### `$ laradock reload`

Reload nginx configuration.

#### `$ laradock run <command>`

Execute the specified command inside workspace.

#### `$ laradock <...command>`

Run specified command inside laradock's folder using docker-compose.

## Troubleshooting

#### `ERROR: Setting workdir for exec is not supported in API < 1.35 (1.25)`
Specify `version: 3.7` in your `docker-compose.yml` file.

## License

The project is released under the MIT license. Read the [license](https://github.com/Tarik02/laradock-cli/blob/master/LICENSE.md) for more information.
