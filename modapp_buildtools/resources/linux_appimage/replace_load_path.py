from pathlib import Path

import nuitka


STRING_TO_REPLACE = (
    "        appendStringSafe(filename, getBinaryDirectoryHostEncoded(),"
    " sizeof(filename));"
)
NEW_STRING = """        appendStringSafe(filename, getBinaryDirectoryHostEncoded(), sizeof(filename));
        // new code
        appendCharSafe(filename, SEP, sizeof(filename));
        appendStringSafe(filename, "..", sizeof(filename));
        appendCharSafe(filename, SEP, sizeof(filename));
        appendStringSafe(filename, "usr", sizeof(filename));
        appendCharSafe(filename, SEP, sizeof(filename));
        appendStringSafe(filename, "lib", sizeof(filename));
        // new code end
"""


def replace_load_path():
    nuitka_path = Path(nuitka.__file__).parent
    src_file_path = nuitka_path / "build" / "static_src" / "MetaPathBasedLoader.c"
    with open(src_file_path, "r") as src_file:
        src = src_file.read()

    src = src.replace(STRING_TO_REPLACE, NEW_STRING)

    with open(src_file_path, "w") as src_file:
        src_file.write(src)


if __name__ == "__main__":
    replace_load_path()
