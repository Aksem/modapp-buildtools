import re
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from platform import system
from shutil import copyfile
from sys import exit
from typing import Optional, List, Tuple

from command_runner import command_runner
from loguru import logger

from modapp_buildtools.file_utils import is_executable, is_shared_library
from modapp_buildtools.rpath_utils import get_rpaths


def _parse_ldd_output(output: str) -> Tuple[List[str], List[str]]:
    p = re.compile(r"\t(?P<lib>.*) => not found")
    not_found_libs = p.findall(output)

    p2 = re.compile(r"=> (?P<lib>.*) \(0x")
    linked_libs = p2.findall(output)
    # ldd returns always absolute paths, but it can also return path with relative parts like
    # '/dir/./../lib.so', normalize them. Path.resolve() cannot be used here,
    # because it resolves symlinks as well and name of linked library would be lost
    linked_libs = [os.path.normpath(p) for p in linked_libs]
    return (linked_libs, not_found_libs)


def _try_fix(
    file_to_fix: Path,
    external_libs: List[Path],
    not_found_libs: List[Path],
    available_libs: List[Path],
    app_path: Path,
) -> bool:
    commands_by_system = {
        "Linux": {
            "change_link": (
                'patchelf --replace-needed "{old_link}" "{new_link}" "{file_to_fix}"'
            ),
            "add_rpath": 'patchelf --add-rpath "{rpath}" "{file_to_fix}"',
        },
        "Darwin": {
            "change_link": (
                'install_name_tool -change "{old_link}" "{new_link}" "{file_to_fix}"'
            ),
            "add_rpath": 'install_name_tool -add_rpath "{rpath}" "{file_to_fix}"',
        },
    }
    fixed = True
    current_system = system()
    if current_system == "":
        logger.error("Failed to recognize OS")
        return False

    commands = commands_by_system[current_system]

    for problem_lib in external_libs + not_found_libs:
        try:
            local_lib = next(
                lib for lib in available_libs if lib.name == problem_lib.name
            )
        except StopIteration:
            logger.error(
                f"Cannot fix {str(problem_lib)}: local library with the same name not"
                " found"
            )
            fixed = False
            continue

        # copy lib to app if it's outside
        lib_in_app_path = local_lib.resolve()
        if not str(local_lib.absolute()).startswith(str(app_path.absolute())):
            # use name of linked library as name of library in app, because resolved
            # name of the library can differ from linked one. Example: linked libQt5Core.5,
            # but it resolves to libQt5Core.5.15.3
            # TODO: support of other platforms? Now supports only linux
            lib_in_app_path = app_path / 'lib' / problem_lib.name
            if not lib_in_app_path.exists():
                # if library is not in app yet (it could be copied as dependency for another
                # library earlier)
                copyfile(local_lib, lib_in_app_path)

        change_command = commands["change_link"].format(
            old_link=str(problem_lib),
            new_link=str(lib_in_app_path.name),
            file_to_fix=file_to_fix,
        )
        command_runner(change_command)
        # TODO: error handling

        rpaths = get_rpaths(file_to_fix)
        relative_path = Path(os.path.relpath(local_lib, file_to_fix))
        needed_rpath = f"{str(relative_path)}"
        if needed_rpath not in rpaths:
            # TODO: use add_rpath()
            add_rpath_command = commands["add_rpath"].format(
                rpath=needed_rpath, file_to_fix=file_to_fix
            )
            command_runner(add_rpath_command)
            # TODO: error handling

    return fixed


def check_file_linking_task(
    file_to_check: Path,
    app_path: Path,
    allowed_libs: Optional[List[str]] = None,
    available_libs: Optional[List[Path]] = None,
    fix: bool = False,
) -> bool:
    file_relative_path_str = str(file_to_check.relative_to(app_path))
    lib_linking_is_ok = True
    logger.info(f'Checking "{file_relative_path_str}"')

    command = f'ldd "{str(file_to_check)}"'
    exit_code, output = command_runner(command)
    if exit_code != 0:
        if exit_code == 1 and "not a dynamic executable" in str(output):
            logger.info(f"Skip {file_relative_path_str}, not a dynamic executable")
            return True
        raise Exception(
            f'Command "{command}" failed with status code {exit_code}, output: {output}'
        )
    if output is None:
        raise Exception(f'Command "{command}" produced no output')
    linked_libs, not_found_libs = _parse_ldd_output(str(output))
    if len(not_found_libs) > 0:
        lib_linking_is_ok = False

    external_libs: List[Path] = []
    for linked_lib in linked_libs:
        if not linked_lib.startswith(str(app_path.absolute())) and (
            allowed_libs is not None and linked_lib not in allowed_libs
        ):
            linked_lib_path = Path(linked_lib)
            try:
                if allowed_libs is None:
                    raise StopIteration()
                next(
                    allowed_lib
                    for allowed_lib in allowed_libs
                    if linked_lib_path.name.startswith(allowed_lib)
                )
            except StopIteration:
                external_libs.append(linked_lib_path)

    if len(external_libs) > 0:
        logger.info(
            f"{file_relative_path_str} has external dependencies:\n    "
            + "\n    ".join([str(p) for p in external_libs])
        )
        lib_linking_is_ok = False

    if fix:
        if available_libs is None:
            raise Exception("Dependencies cannot be fixed without local libs")

        lib_linking_is_ok |= _try_fix(
            file_to_fix=file_to_check,
            available_libs=available_libs,
            external_libs=external_libs,
            not_found_libs=[Path(p) for p in not_found_libs],
            app_path=app_path,
        )

    return lib_linking_is_ok


def check_linking_in_files(
    files: List[Path],
    app_path: Path,
    allowed_libs: Optional[List[str]] = None,
    available_libs: Optional[List[Path]] = None,
    fix: bool = False,
) -> bool:
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                check_file_linking_task,
                file_to_check,
                app_path,
                allowed_libs,
                available_libs,
                fix,
            )
            for file_to_check in files
        ]
        results = [f.result() for f in futures]

    linking_is_ok = all(results)
    return linking_is_ok


def check_linking(
    bin_path: Path,
    allowed_libs: Optional[List[str]] = None,
    fix: bool = False,
) -> None:
    app_path = bin_path
    files_to_check: List[Path] = []
    available_libs: List[Path] = []
    if bin_path.is_file():
        files_to_check.append(bin_path)
        app_path = bin_path.parent
    elif bin_path.is_dir():
        for app_file in bin_path.rglob("*"):
            if is_executable(app_file) or is_shared_library(app_file):
                files_to_check.append(app_file)
                if is_shared_library(app_file):
                    available_libs.append(app_file.absolute())

    logger.info(f"Working directory: {app_path}")
    linking_is_ok = check_linking_in_files(
        files_to_check,
        allowed_libs=allowed_libs,
        available_libs=available_libs,
        fix=fix,
        app_path=app_path,
    )

    if not linking_is_ok:
        logger.error("Linking check failed, see logs above")
        exit(1)
    else:
        logger.success("Linking is correct")
