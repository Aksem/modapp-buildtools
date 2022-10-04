#!/bin/sh

poetry config virtualenvs.in-project true

cd /app/

LINUX_APPIMAGE_PATH=./buildtools_Linux/modapp_buildtools/resources/linux_appimage

echo "Create venv"
sh $LINUX_APPIMAGE_PATH/create_venv.sh

echo "Change load path"
poetry run python $LINUX_APPIMAGE_PATH/replace_load_path.py

poetry run python -m nuitka \
            --standalone \
            --follow-imports \
            --assume-yes-for-downloads \
            --plugin-enable="pylint-warnings" \
            --warn-unusual-code \
            --warn-implicit-exceptions \
            --show-memory \
            --show-modules \
            --include-data-dir=modapp_buildtools/resources=modapp_buildtools/resources \
            modapp_buildtools/cli.py
