"""Package the app as a Windows executable and (optionally) add shortcuts.

    python tools/build_exe.py                 # one-file exe + Desktop/Start menu
    python tools/build_exe.py --onedir        # folder build, starts faster
    python tools/build_exe.py --no-shortcuts  # just build

The result is dist/Video Downloader.exe. ffmpeg is not bundled: the app fetches
it on first use into %LOCALAPPDATA%\\VideoDownloader.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "Video Downloader"
ENTRY = ROOT / "gui.py"
ICON = ROOT / "assets" / "icon.ico"
DIST = ROOT / "dist"


def run(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)


def ensure_tooling() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is missing - installing it now...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    if not ICON.exists():
        run([sys.executable, str(ROOT / "tools" / "make_icon.py")])


def build(onedir: bool) -> Path:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--onedir" if onedir else "--onefile",
        "--name", NAME,
        "--icon", str(ICON),
        "--add-data", f"{ROOT / 'assets'}{os.pathsep}assets",
        "--collect-data", "customtkinter",
        # yt-dlp ships its own PyInstaller hook that pulls in the extractors;
        # collecting its submodules by hand only makes the build crawl.
        "--exclude-module", "tkinter.test",
        str(ENTRY),
    ]
    run(args)
    exe = DIST / (f"{NAME}/{NAME}.exe" if onedir else f"{NAME}.exe")
    if not exe.exists():
        raise SystemExit(f"Build finished but {exe} is missing.")
    return exe


def publish(exe: Path) -> Path:
    """Copy a one-file build next to the source, so anyone who downloads the
    project finds a runnable app without building it first."""
    if exe.parent != DIST:  # a --onedir build needs its whole folder
        return exe
    target = ROOT / exe.name
    shutil.copy2(exe, target)
    print(f"  copied to {target}")
    return target


def make_shortcut(exe: Path, folder: Path, name: str) -> None:
    """Create a .lnk via the Windows scripting host — no extra packages."""
    folder.mkdir(parents=True, exist_ok=True)
    link = folder / f"{name}.lnk"
    script = (
        "$s = (New-Object -ComObject WScript.Shell)."
        f"CreateShortcut('{link}'); "
        f"$s.TargetPath = '{exe}'; "
        f"$s.WorkingDirectory = '{exe.parent}'; "
        f"$s.IconLocation = '{exe}'; "
        "$s.Description = 'Download videos, audio and playlists'; "
        "$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)
    print(f"  shortcut: {link}")


def add_shortcuts(exe: Path) -> None:
    home = Path(os.path.expanduser("~"))
    desktop = Path(os.environ.get("USERPROFILE", home)) / "Desktop"
    start_menu = (Path(os.environ.get("APPDATA", home))
                  / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    for folder in (desktop, start_menu):
        try:
            make_shortcut(exe, folder, NAME)
        except Exception as exc:
            print(f"  could not write a shortcut in {folder}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Windows app.")
    parser.add_argument("--onedir", action="store_true",
                        help="folder build instead of a single file "
                             "(starts noticeably faster)")
    parser.add_argument("--no-shortcuts", action="store_true",
                        help="skip Desktop and Start menu shortcuts")
    parser.add_argument("--shortcuts-only", action="store_true",
                        help="don't build; just point Desktop and Start menu "
                             "shortcuts at the exe already in this folder")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("This build script targets Windows.")
        return 1

    if args.shortcuts_only:
        existing = ROOT / f"{NAME}.exe"
        if not existing.exists():
            print(f"{existing} does not exist yet — build it first.")
            return 1
        add_shortcuts(existing)
        return 0

    ensure_tooling()
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    exe = build(args.onedir)

    print(f"\nBuilt {exe}")
    exe = publish(exe)
    if not args.no_shortcuts:
        add_shortcuts(exe)
    print("\nDone. Double-click the shortcut, or the exe itself, to start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
