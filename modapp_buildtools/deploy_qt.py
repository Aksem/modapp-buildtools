from pathlib import Path
from typing import Optional, List
from sys import exit
from shutil import copytree
from os import makedirs
from string import Template

from loguru import logger

from modapp_buildtools.file_utils import is_executable, is_shared_library
from modapp_buildtools.check_linking import check_linking_in_files
from modapp_buildtools.rpath_utils import add_relative_rpath_if_needed


def create_qt_conf(destination: Path, prefix: str) -> None:
    template_path = Path(__file__).parent / "resources" / "linux_qt" / "qt.conf.template"
    with open(template_path) as template_file:
        qt_conf_template = Template(template_file.read())

    qt_conf_content = qt_conf_template.safe_substitute(
        {
            "Prefix": prefix,
        }
    )

    with open(destination / 'qt.conf', "w") as output_file:
        output_file.write(qt_conf_content)


def deploy_qt(
    bin_path: Path,
    qt_path: Path,
    allowed_libs: Optional[List[str]] = None,
    fix: bool = False,
    plugins: Optional[List[str]] = None,
    qml_dir: Optional[Path] = None,
) -> None:
    app_path = bin_path
    app_lib_path = app_path / "lib"

    create_qt_conf(app_path / "bin", "../lib/")

    if plugins is not None:
        app_plugins_path = app_lib_path / "plugins"
        if not app_plugins_path.exists():
            makedirs(app_plugins_path)
        for plugin in plugins:
            copytree(qt_path / "plugins" / plugin, app_plugins_path / plugin, dirs_exist_ok=True)
            # in default qt installation plugins dir is on the same level with lib dir, we
            # place plugins inside lib, rpath should be updated
            # TODO: make parallel
            for file in (app_plugins_path / plugin).rglob("*"):
                if is_shared_library(file):
                    add_relative_rpath_if_needed(file, app_lib_path)

    if qml_dir is not None:
        # temporary solution: copy all default qml modules
        # TODO: copy only needed
        app_qml_dir = app_lib_path / "qml"
        copytree(qt_path / "qml", app_qml_dir, dirs_exist_ok=True)
        # in default qt installation qml dir is on the same level with lib dir, we
        # place qml inside lib, rpath should be updated
        # TODO: make parallel
        for file in (app_qml_dir).rglob("*"):
            if is_shared_library(file):
                add_relative_rpath_if_needed(file, app_lib_path)

    files_to_check: List[Path] = []
    available_libs: List[Path] = []
    if bin_path.is_file():
        files_to_check.append(bin_path)
        app_path = bin_path.parent
        # TODO
        print(app_path.name)
        if app_path.name == "lib":
            app_path = app_path.parent
    elif bin_path.is_dir():
        for app_file in bin_path.rglob("*"):
            if is_executable(app_file) or is_shared_library(app_file):
                files_to_check.append(app_file)
                if is_shared_library(app_file):
                    available_libs.append(app_file.absolute())

    qt_lib_path = qt_path / "lib"
    if not qt_lib_path.exists():
        raise Exception()
    for qt_file in qt_lib_path.rglob("*"):
        if is_shared_library(qt_file):
            available_libs.append(qt_file.absolute())

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


def appimage_post_deploy(app_run_dir_path: Path) -> None:
    create_qt_conf(app_run_dir_path / "lib64", "../usr/lib/")
