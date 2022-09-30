import typer
from pathlib import Path
from typing import Optional, List

from modapp_buildtools.check_linking import check_linking as _check_linking
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
def predeploy(app_path: Path, output_path: Path) -> None:
    predeploy_app(app_path, output_path)


if __name__ == "__main__":
    app()
