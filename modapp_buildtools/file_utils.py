from pathlib import Path
from os import access, X_OK


def is_executable(path: Path) -> bool:
    # TODO: handle other OS
    return path.is_file() and path.suffix == "" and access(path, mode=X_OK)


def is_shared_library(path: Path) -> bool:
    # TODO: handle other OS
    # on linux libraries can have unversioned file name 'lib.so' and versioned
    # 'lib.so.1' or even 'lib.so.1.1'. Library name can also includes dotes:
    # 'libpython3.10.so'
    return "so" in path.name.split(".")
