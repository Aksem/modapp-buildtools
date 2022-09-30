from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
from os import mkdir, makedirs
from os.path import relpath
from shutil import copy, rmtree
from string import Template

from command_runner import command_runner
from loguru import logger

from modapp_buildtools.file_utils import is_executable, is_shared_library

if TYPE_CHECKING:
    from typing import List


BIN_REL_PATH = Path("bin")
LIB_REL_PATH = Path("lib")
RESOURCE_REL_PATH = Path("share")


def prepare_output_dir(output_path: Path, app_dir_name: str) -> Path:
    # TODO: handle other OS
    res_app_path = output_path / app_dir_name
    if res_app_path.exists():
        if res_app_path.is_dir():
            rmtree(res_app_path)
        else:
            res_app_path.unlink()
    makedirs(res_app_path)
    return res_app_path


def add_rpath(file_path: Path, new_rpath: str) -> None:
    # patchlelf has also --add-rpath subcommand, but it's supported since v0.14,
    # that cannot be built on old systems with C++ standard lower C++17
    # use --print-rpath and --set-rpath instead, that are supported in all versions
    exit_code, output = command_runner(
        f"patchelf --print-rpath {str(file_path.absolute())}", shell=True
    )
    if exit_code != 0:
        logger.error(f"Failed to get rpath of {str(file_path)}: {output}")

    current_rpath = str(output).strip("\n")
    rpaths = set(current_rpath.split(":"))
    rpaths.add(new_rpath)
    updated_rpath = ":".join(rpaths)

    exit_code, output = command_runner(
        f"patchelf --set-rpath '{updated_rpath}' {str(file_path.absolute())}",
        shell=True,
    )
    if exit_code != 0:
        logger.error(f"Failed to set rpath of {str(file_path)}: {output}")


def handle_executables(executables: List[Path], res_app_path: Path) -> None:
    destination = res_app_path / BIN_REL_PATH
    mkdir(destination)

    lib_path = res_app_path / LIB_REL_PATH
    # Path.relative_to cannot be used here, because it cannot compute relative path
    # between relative pathes. It's a case if output path is relative
    bin_to_lib_rel_path = relpath(lib_path, start=destination)

    for executable in executables:
        app_executable_path = destination / executable.name
        copy(executable, app_executable_path)
        # all libs will be placed in lib dir, add rpath to it
        add_rpath(app_executable_path, f"$ORIGIN/{bin_to_lib_rel_path}")


def handle_libraries(libraries: List[Path], app_path: Path, res_app_path: Path) -> None:
    destination = res_app_path / LIB_REL_PATH
    mkdir(destination)
    for library in libraries:
        library_rel_path = library.relative_to(app_path)
        library_res_path = destination / library_rel_path
        makedirs(library_res_path.parent, exist_ok=True)
        copy(library, library_res_path)


def handle_other_files(
    other_files: List[Path], app_path: Path, res_app_path: Path
) -> None:
    destination = res_app_path / RESOURCE_REL_PATH
    mkdir(destination)
    for other_file in other_files:
        other_file_rel_path = other_file.relative_to(app_path)
        other_file_res_path = destination / other_file_rel_path
        makedirs(other_file_res_path.parent, exist_ok=True)
        copy(other_file, other_file_res_path)


def predeploy_app(app_path: Path, output_path: Path, app_dir_name: str = "AppDir"):
    """Predeploy application.

    Args:
        app_path (Path): path to application directory
        output_path (Path): output directory. If application exists inside, it
                            will be overwritten
        app_dir_name (str): name of app directory. 'AppDir' by default.
    """
    executables: List[Path] = []
    libraries: List[Path] = []
    other_files: List[Path] = []

    for app_file in app_path.rglob("*"):
        if is_executable(app_file):
            executables.append(app_file)
        elif is_shared_library(app_file):
            libraries.append(app_file)
        elif app_file.is_file():
            other_files.append(app_file)

    res_app_path = prepare_output_dir(output_path, app_dir_name)
    handle_executables(executables, res_app_path)
    handle_libraries(libraries, app_path, res_app_path)
    handle_other_files(other_files, app_path, res_app_path)

    if len(executables) == 0:
        raise Exception("No executables found")
    app_name = executables[0].stem

    # icon
    icon_src_path = Path(__file__).parent / "resources" / "app.png"
    # go-appimage requires icon on the same level as AppDir
    icon_dst_path = output_path / "app.png"
    copy(icon_src_path, icon_dst_path)

    # .desktop file
    desktop_file_template_path = Path(__file__).parent / "resources" / "app.desktop"
    desktop_file_dst_path = (
        res_app_path / "share" / "applications" / f"{app_name}.desktop"
    )
    with open(desktop_file_template_path) as template_file:
        desktop_template = Template(template_file.read())

    desktop_file_content = desktop_template.safe_substitute(
        {
            "name": app_name,
            "exec": app_name,
        }
    )
    makedirs(desktop_file_dst_path.parent)
    with open(desktop_file_dst_path, "w") as output_file:
        output_file.write(desktop_file_content)
