import os
import yt_dlp

def download_video(video_url, quality_option, format_option, output_dir):
    format_map = {
        "1": f"bestvideo[height<=1080][ext={format_option}]+bestaudio/best[height<=1080][ext={format_option}]",
        "2": f"bestvideo[height<=720][ext={format_option}]+bestaudio/best[height<=720][ext={format_option}]",
        "3": f"bestvideo[height<=480][ext={format_option}]+bestaudio/best[height<=480][ext={format_option}]",
        "4": f"bestvideo[ext={format_option}]+bestaudio/best[ext={format_option}]",
        "5": "bestaudio/best"
    }

    format_string = format_map.get(quality_option, f"bestvideo[ext={format_option}]+bestaudio/best[ext={format_option}]")

    # Ensure output directory exists
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "%(playlist_title)s/%(title)s.%(ext)s")
    else:
        output_path = "%(title)s.%(ext)s"

    ydl_opts = {
        'format': format_string,
        'outtmpl': output_path,
        'merge_output_format': format_option if quality_option != "5" else None,
        'postprocessors': [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}] if quality_option == "5" else []
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

# Main script
if __name__ == "__main__":
    print("===== Video Downloader =====")
    video_url = input("Enter the video or playlist URL: ").strip()

    if not video_url:
        print("Error: URL cannot be empty.")
        exit(1)

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
        format_map = {"1": "mp4", "2": "webm", "3": "mkv"}
        format_option = format_map.get(format_choice, "mp4")
    else:
        format_option = "mp3"

    output_dir = input("\nEnter download directory (press Enter for current directory): ").strip()

    print("\nStarting download...")
    download_video(video_url, quality_option, format_option, output_dir)
    print("Download complete!")
