"""Entry point for the desktop app.

    python gui.py          # with a console window
    pythonw gui.py         # without one
    start.bat              # sets up a virtual environment first, then launches

If a dependency is missing (a fresh clone, for instance) it is installed from
requirements.txt and the app is started again.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"
REQUIRED = ("customtkinter", "yt_dlp", "PIL")
INSTALL_FLAG = "--deps-installed"


def missing_packages() -> list[str]:
    import importlib.util
    return [name for name in REQUIRED if importlib.util.find_spec(name) is None]


def install_requirements() -> None:
    print("Installing requirements, this only happens once…", flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-r",
                    str(REQUIREMENTS)], check=True)


def main() -> int:
    frozen = getattr(sys, "frozen", False)
    missing = [] if frozen else missing_packages()
    if missing and INSTALL_FLAG not in sys.argv:
        if not REQUIREMENTS.exists():
            print(f"Missing packages: {', '.join(missing)}")
            return 1
        try:
            install_requirements()
        except subprocess.CalledProcessError:
            print("\nCould not install the requirements automatically.\n"
                  f"Run:  {sys.executable} -m pip install -r {REQUIREMENTS}")
            return 1
        # Re-exec so the freshly installed packages are importable.
        return subprocess.run([sys.executable, __file__, INSTALL_FLAG]).returncode

    from app.main import run
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
