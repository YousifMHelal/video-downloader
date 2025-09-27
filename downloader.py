import os
import sys
import urllib.request
import zipfile
import shutil
import yt_dlp
import re


# =============================
# 🔸 AUTO-INSTALL FFMPEG (Windows)
# =============================
def ensure_ffmpeg():
    ffmpeg_dir = os.path.join(os.path.dirname(__file__), "ffmpeg", "bin")
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")

    if not os.path.exists(ffmpeg_exe):
        print("[INFO] ffmpeg not found. Downloading...")
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        zip_path = os.path.join(os.path.dirname(__file__), "ffmpeg.zip")

        urllib.request.urlretrieve(url, zip_path)
        print("[INFO] Download complete. Extracting...")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("ffmpeg_temp")

        extracted_folder = [f for f in os.listdir("ffmpeg_temp") if os.path.isdir(os.path.join("ffmpeg_temp", f))][0]
        bin_src = os.path.join("ffmpeg_temp", extracted_folder, "bin")

        os.makedirs(ffmpeg_dir, exist_ok=True)
        for file in os.listdir(bin_src):
            shutil.move(os.path.join(bin_src, file), ffmpeg_dir)

        shutil.rmtree("ffmpeg_temp")
        os.remove(zip_path)
        print("[INFO] ffmpeg installed successfully!")

    return ffmpeg_dir


# =============================
# 🔸 SAFE FOLDER NAME
# =============================
def sanitize_folder_name(name: str) -> str:
    """Remove invalid characters from folder names."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


# =============================
# 🔸 GET PLAYLIST TITLE IF URL IS PLAYLIST
# =============================
def get_playlist_title(video_url):
    ydl_opts = {
        'extract_flat': True,
        'dump_single_json': True,
        'playlistend': 1  # only need metadata of playlist
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if info.get('_type') == 'playlist':
                title = info.get('title') or info.get('id')
                return sanitize_folder_name(title)
    except Exception:
        pass
    return None


# =============================
# 🔸 DOWNLOAD FUNCTION
# =============================
def download_video(video_url, quality_option, format_option, output_dir, ffmpeg_path):
    format_map = {
        "1": f"bestvideo[height<=1080][ext={format_option}]+bestaudio/best[height<=1080][ext={format_option}]",
        "2": f"bestvideo[height<=720][ext={format_option}]+bestaudio/best[height<=720][ext={format_option}]",
        "3": f"bestvideo[height<=480][ext={format_option}]+bestaudio/best[height<=480][ext={format_option}]",
        "4": f"bestvideo[ext={format_option}]+bestaudio/best[ext={format_option}]",
        "5": "bestaudio/best"
    }

    format_string = format_map.get(
        quality_option,
        f"bestvideo[ext={format_option}]+bestaudio/best[ext={format_option}]"
    )

    # 🧠 Check if URL is a playlist
    playlist_folder = get_playlist_title(video_url)
    if playlist_folder:
        if output_dir:
            final_dir = os.path.join(output_dir, playlist_folder)
        else:
            final_dir = playlist_folder
    else:
        final_dir = output_dir or ""

    if final_dir:
        os.makedirs(final_dir, exist_ok=True)
        output_path = os.path.join(final_dir, "%(title)s.%(ext)s")
    else:
        output_path = "%(title)s.%(ext)s"

    ydl_opts = {
        'format': format_string,
        'outtmpl': output_path,
        'merge_output_format': format_option if quality_option != "5" else None,
        'postprocessors': [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}] if quality_option == "5" else [],
        'ffmpeg_location': ffmpeg_path
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])


# =============================
# 🔸 MAIN PROGRAM
# =============================
if __name__ == "__main__":
    print("===== Video Downloader =====")

    ffmpeg_path = ensure_ffmpeg()

    video_url = input("Enter the video or playlist URL: ").strip()
    if not video_url:
        print("Error: URL cannot be empty.")
        sys.exit(1)

    print("\nChoose Video Quality:")
    print("1. 1080p (High Quality)")
    print("2. 720p (Medium Quality)")
    print("3. 480p (Low Quality)")
    print("4. Best Available")
    print("5. Audio Only (MP3)")
    quality_option = input("Select quality option (1-5): ").strip()

    if quality_option != "5":
        print("\nChoose Format:")
        print("1. MP4")
        print("2. WebM")
        print("3. MKV")
        format_choice = input("Select format (1-3): ").strip()
        format_map_choice = {"1": "mp4", "2": "webm", "3": "mkv"}
        format_option = format_map_choice.get(format_choice, "mp4")
    else:
        format_option = "mp3"

    output_dir = input("\nEnter download directory (press Enter for current directory): ").strip()

    print("\nStarting download...")
    try:
        download_video(video_url, quality_option, format_option, output_dir, ffmpeg_path)
        print("\n✅ Download complete!")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
