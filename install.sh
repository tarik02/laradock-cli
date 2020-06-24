#!/usr/bin/env bash

set -e

if [ -d $HOME/.bin ]; then
	BIN_FILE=$HOME/.bin/laradock
elif [ -d $HOME/.local/bin ]; then
	BIN_FILE=$HOME/.local/bin/laradock
else
	echo 'Create `$HOME/.bin` or `$HOME/.local/bin` and add it to PATH'
	exit 1
fi

cat << 'EOF' > $BIN_FILE
#!/usr/bin/env bash

###############################################################################
# laradock-cli: https://github.com/Tarik02/laradock-cli                       #
###############################################################################

if [ -z $LARADOCK_ROOT ]; then
	LARADOCK_ROOT=$HOME/Laradock
fi

if ! type python3 > /dev/null; then
	echo "This command requires python3 to be available."
	exit 1
fi

if [[ "$1" == "init" ]]; then
	shift
	if [ "$#" -gt 1 ]; then
		echo "Usage: laradock init [patch url]"
		exit 1
	fi
	(
		set -e
		mkdir -p $LARADOCK_ROOT
		cd $LARADOCK_ROOT
		#curl -o cli.py -fsSL https://github.com/Tarik02/laradock-cli/raw/master/cli.py
		git clone https://github.com/Laradock/laradock.git .laradock
		if [ "$#" -eq 1 ]; then
			cd .laradock
			curl -o laradock.patch "$1"
			git apply laradock.patch
			rm laradock.patch
		fi
		cd ..
		LARADOCK_ROOT="$LARADOCK_ROOT" python3 $LARADOCK_ROOT/cli.py init
	)
	exit $?
fi

if [ ! -d $LARADOCK_ROOT ] || [ ! -f $LARADOCK_ROOT/cli.py ]; then
	echo "Laradock is not initialized. Run \`laradock init\` to initialize laradock."
	exit 1
fi

LARADOCK_ROOT="$LARADOCK_ROOT" python3 $LARADOCK_ROOT/cli.py "$@"
exit $?
EOF

chmod +x $BIN_FILE

echo "laradock-cli was successfully installed to $BIN_FILE"
