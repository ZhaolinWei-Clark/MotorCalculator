"""Generate build-only metadata from the authoritative version module."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from motor_calculator.deployment.release import write_build_metadata
from motor_calculator.version import (
    APPLICATION_DISPLAY_NAME_ZH_CN,
    APPLICATION_NAME,
    APPLICATION_PUBLISHER,
    APPLICATION_VERSION,
    windows_version_tuple,
)


def render_windows_version_info() -> str:
    tuple_version = str(windows_version_tuple())
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tuple_version}, prodvers={tuple_version}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('080404b0', [
    StringStruct('CompanyName', '{APPLICATION_PUBLISHER}'),
    StringStruct('FileDescription', '{APPLICATION_DISPLAY_NAME_ZH_CN}'),
    StringStruct('FileVersion', '{APPLICATION_VERSION}'),
    StringStruct('InternalName', '{APPLICATION_NAME}'),
    StringStruct('OriginalFilename', 'MotorCalculator.exe'),
    StringStruct('ProductName', '{APPLICATION_NAME}'),
    StringStruct('ProductVersion', '{APPLICATION_VERSION}')
  ])]), VarFileInfo([VarStruct('Translation', [2052, 1200])])]
)\n"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    arguments = parser.parse_args()
    root = arguments.repository_root.resolve()
    write_build_metadata(root / "packaging" / "build_info.json", git_commit=arguments.git_commit)
    (root / "packaging" / "windows_version_info.txt").write_text(
        render_windows_version_info(), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
