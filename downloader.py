"""Command-line front end. The download logic itself lives in app/core.py."""

import os
import sys
import threading

from app.core import (CONTAINERS, QUALITIES, Engine, Job, Status, human_eta,
                      human_size, human_speed)

# Keep box-drawing output readable on non-UTF-8 consoles (Windows cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass


def print_header():
    print()
    print("+--------------------------------------+")
    print("|          Video Downloader            |")
    print("+--------------------------------------+")
    print()


def ask(prompt, valid=None):
    """Ask the user a question, optionally validating against a set of choices."""
    while True:
        answer = input(prompt).strip()
        if valid is None or answer in valid:
            return answer
        print(f"  Please enter one of: {', '.join(valid)}")


def draw_bar(job: Job):
    filled = int(job.percent * 50)
    detail = f"{human_speed(job.speed)}  ETA: {human_eta(job.eta)}"
    if job.total:
        detail += f"  {human_size(job.downloaded)}/{human_size(job.total)}"
    if job.is_playlist and job.item_count:
        detail += f"  [{job.item_index or 1}/{job.item_count}]"
    print(f"\r  [{'#' * filled}{'.' * (50 - filled)}] "
          f"{job.percent * 100:5.1f}%  {detail}   ", end='', flush=True)


def main():
    print_header()

    url = input("Enter the video or playlist URL: ").strip()
    if not url:
        print("Error: URL cannot be empty.")
        return 1

    print()
    print("Choose Video Quality:")
    for index, quality in enumerate(QUALITIES, start=1):
        print(f"  {index}. {quality.label}  ({quality.hint})")
    choice = ask(f"Select quality (1-{len(QUALITIES)}): ",
                 valid={str(i) for i in range(1, len(QUALITIES) + 1)})
    quality = QUALITIES[int(choice) - 1]

    container = "mp4"
    if not quality.audio_only:
        print()
        print("Choose Format:")
        for index, name in enumerate(CONTAINERS, start=1):
            print(f"  {index}. {name.upper()}")
        format_choice = ask(f"Select format (1-{len(CONTAINERS)}): ",
                            valid={str(i) for i in range(1, len(CONTAINERS) + 1)})
        container = CONTAINERS[int(format_choice) - 1]

    print()
    output_dir = input("Download directory (Enter = current folder): ").strip()
    output_dir = output_dir or os.getcwd()

    done = threading.Event()
    state = {"job": None}

    def emit(event, payload):
        if event == "job":
            job: Job = payload
            state["job"] = job
            if job.status is Status.DOWNLOADING:
                draw_bar(job)
            elif job.status is Status.PROBING:
                print("Reading link details...")
            elif job.status is Status.PROCESSING:
                print("\r" + " " * 100, end="")
                print("\r  Merging and tagging...", flush=True)
            elif job.status.is_final:
                done.set()
        elif event == "log":
            _job_id, line = payload
            print(f"\r{line}")
        elif event == "ffmpeg":
            message, _percent = payload
            print(f"\r[ffmpeg] {message}")

    engine = Engine(emit)
    engine.start()
    engine.submit(Job(url=url, quality_id=quality.id, container=container,
                      output_dir=output_dir))

    print("\nStarting download...\n")
    try:
        while not done.wait(0.2):
            pass
    except KeyboardInterrupt:
        job = state["job"]
        if job:
            engine.cancel(job.id)
        print("\n\nDownload cancelled by user.")
        return 0

    job = state["job"]
    engine.shutdown()

    if job.status is Status.DONE:
        print(f"\nAll done! Saved to {job.dest_dir}")
        return 0
    if job.status is Status.CANCELLED:
        print("\nCancelled.")
        return 0
    print(f"\nFinished with errors: {job.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
