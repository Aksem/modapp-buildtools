import typer
from pathlib import Path
from typing import Optional, List

from modapp_buildtools.check_linking import check_linking as _check_linking
from modapp_buildtools.deploy_qt import deploy_qt as _deploy_qt, appimage_post_deploy
from modapp_buildtools.predeploy import predeploy_app


app = typer.Typer()


@app.command()
def check_linking(
    bin_path: Path,
    allowed_libs: Optional[List[str]] = None,
    fix: bool = False,
) -> None:
    _check_linking(bin_path, allowed_libs=allowed_libs, fix=fix)


@app.command()
def deploy_qt(
    bin_path: Path,
    qt_path: Path,
    allowed_libs: Optional[List[str]] = None,
    fix: bool = False,
    plugins: Optional[List[str]] = None,
    qml_dir: Optional[Path] = None,
) -> None:
    _deploy_qt(bin_path, qt_path, allowed_libs=allowed_libs, fix=fix, plugins=plugins, qml_dir=qml_dir)


@app.command()
def predeploy(app_path: Path, output_path: Path, app_dir_name: str = "AppDir") -> None:
    predeploy_app(app_path, output_path, app_dir_name=app_dir_name)


@app.command()
def appimage_qt_post_deploy(app_run_dir_path: Path) -> None:
    appimage_post_deploy(app_run_dir_path)


if __name__ == "__main__":
    app()
