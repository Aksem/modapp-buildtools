import os
import re
from typing import List
from pathlib import Path
from platform import system

from command_runner import command_runner
from loguru import logger


def get_rpaths(filepath: Path) -> List[str]:
    current_system = system()
    if current_system == "Linux":
        command = f"patchelf --print-rpath {filepath}"
        exit_code, output = command_runner(command)
        if exit_code != 0:
            ...  # TODO
        return str(output).split(":")
    elif current_system == "Darwin":
        command = f"otool -l {filepath}"
        exit_code, output = command_runner(command)
        if exit_code != 0:
            ...  # TODO
        p2 = re.compile(
            r"cmd LC_RPATH\n      cmdsize \d+\n         path (?P<lib>.*) \("
        )
        return p2.findall(str(output))
    return []


def add_relative_rpath_if_needed(file_path: Path, to_path: Path) -> None:
    # from file to directory
    relative_path = Path(os.path.relpath(to_path, file_path.parent))
    rpath = f"$ORIGIN/{str(relative_path)}"
    add_rpath_if_needed(file_path, rpath)


def add_rpath_if_needed(file_path: Path, rpath: str) -> None:
    rpaths = get_rpaths(file_path)
    if rpath not in rpaths:
        add_rpath(file_path, rpath)


def add_rpath(file_path: Path, rpath: str) -> None:
    # add new rpath. If it exists, it'll be duplicated(check before)
    current_system = system()
    if current_system == "":
        logger.error("Failed to recognize OS")
        return

    commands_by_system = {
        # Older systems that are often used for build include patchelf 0.9 which doesn't support
        # --add-rpath. It was introduced in patchelf 0.14 that cannot be built for old systems,
        # because it requires C++17. Use set + print instead of add.
        "Linux": (
            'patchelf --set-rpath "$(patchelf --print-rpath \'{file_to_fix}\'):{rpath}"'
            ' "{file_to_fix}"'
        ),
        "Darwin": 'install_name_tool -add_rpath "{rpath}" "{file_to_fix}"',
    }

    add_rpath_command = commands_by_system[current_system].format(
        rpath=rpath, file_to_fix=file_path
    )
    exit_code, output = command_runner(add_rpath_command)
    if exit_code != 0:
        logger.error(f"Failed to add rpath '{rpath}' to '{file_path}': {output}")
    else:
        logger.trace(f"Added rpath '{rpath}' to '{file_path}'")
