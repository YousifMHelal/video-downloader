# Video Downloader

A desktop app for downloading videos, audio and playlists with `yt-dlp`, plus the
original command-line script. Windows-first.

![queue](assets/icon.png)

## What it does

- A download table with live columns: name, format, size, progress, speed, ETA
  and status — select a row to see its details underneath
- Menu bar, toolbar, right-click menus and keyboard shortcuts throughout
- Playlists are detected automatically and saved into their own numbered folder
- Cancel a running download at any point, including mid-playlist
- Filter the queue or the history as you type
- Copy a link anywhere and the app offers to queue it when you switch back
- Progress mirrored in the window title, totals in the status bar
- History of everything fetched, with "open folder" and "download again"
- Remembers your folder, quality, format, theme and window size
- Downloads and installs `ffmpeg` on first use — nothing to set up by hand

### Keyboard

| Shortcut | Action |
| --- | --- |
| `Ctrl+N` | Add download |
| `Ctrl+V` | Add the link on the clipboard |
| `Ctrl+F` | Filter the list |
| `Ctrl+1/2/3` | Queue · History · Settings |
| `Ctrl+J` | Activity log |
| `Esc` | Cancel the selected download |
| `Del` | Remove the selected row |
| `Ctrl+Shift+C` | Copy the selected link |
| `Ctrl+Q` | Quit |

## Just run it

`Video Downloader.exe` sits in this folder — double-click it. No Python, no
install; it fetches `ffmpeg` by itself the first time you download something.

To put it on the Desktop and in the Start menu:

```sh
python tools/build_exe.py --shortcuts-only
```

…or right-click the exe → *Send to* → *Desktop*, and *Pin to Start*.

## Run it from source on any PC

Clone the repository and **double-click `start.bat`**. On its first run it
creates a virtual environment, installs the requirements, and starts the app;
after that it just starts the app. Nothing else to install except Python itself.

Prefer the terminal, or already have the packages?

```sh
pip install -r requirements.txt
python gui.py          # desktop app
python downloader.py   # the original prompt-based CLI
```

`python gui.py` also installs anything missing from `requirements.txt` on its
own before starting, so a fresh clone works either way.

### No Python on that PC?

Every push builds a Windows executable in GitHub Actions
(`.github/workflows/build.yml`). Open the latest run and download the
**video-downloader-windows** artifact, or push a `v*` tag and the exe is
attached to the release automatically.

## Build a desktop executable

```sh
python tools/build_exe.py
```

This produces `dist/Video Downloader.exe` and places a shortcut on the Desktop
and in the Start menu, so the app can be started like any other program.

| Option | Effect |
| --- | --- |
| *(no flags)* | one-file exe, shortcuts created |
| `--onedir` | folder build — larger on disk, starts noticeably faster |
| `--no-shortcuts` | build only |

The icon is generated from `tools/make_icon.py`; run it to regenerate
`assets/icon.ico` after changing the design.

## Where things are stored

| | Source checkout | Packaged exe |
| --- | --- | --- |
| settings & history | `.config/` | `%LOCALAPPDATA%\VideoDownloader\.config\` |
| ffmpeg | `ffmpeg/bin/` | `%LOCALAPPDATA%\VideoDownloader\ffmpeg\bin\` |

Downloaded files go wherever you point "Save to" — your `Downloads` folder by
default.

## Layout

```
app/
  core.py      download engine: queue, worker thread, yt-dlp options, ffmpeg bootstrap
  store.py     settings and history persistence
  theme.py     design tokens — every colour, size and font in one place
  widgets.py   reusable components (cards, pills, toolbar, table, rows)
  views.py     the Queue, History and Settings screens
  dialogs.py   the add-download and about windows
  main.py      window shell, menus, shortcuts, controller wiring
gui.py         desktop entry point
downloader.py  command-line entry point
tools/         icon generator and the build script
```

`core.py` never prints or prompts and knows nothing about Tk, so the CLI and the
desktop app drive exactly the same engine.

## Quality options

| Option | Result |
| --- | --- |
| 1080p / 720p / 480p | best stream at or below that height, merged to your chosen container |
| Best available | highest the source offers |
| Audio only | MP3 at 192 kbps (the format choice no longer applies) |

Containers: MP4, MKV, WebM.

## Troubleshooting

- **A download fails or a site stopped working** — update yt-dlp:
  `pip install --upgrade yt-dlp`
- **Part of a playlist is missing** — unavailable items are skipped on purpose;
  the activity log lists each one.
- **A cancelled download left a `.part` file** — that is the resume data; start
  the same link again and it continues from there.
- **ffmpeg will not install** — check the activity log, then drop an `ffmpeg.exe`
  into the `ffmpeg/bin` folder listed above.
