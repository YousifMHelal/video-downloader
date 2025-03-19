# Video Downloader - Usage Guide

This script allows you to download videos and playlists from various websites using `yt-dlp`.

## Installation

### Prerequisites
Ensure you have Python installed on your system. You can download it from [python.org](https://www.python.org/).

### Install Required Package
Run the following command to install `yt-dlp`:
```sh
pip install yt-dlp
```

## How to Use

1. **Run the script:**
   ```sh
   python downloader.py
   ```

2. **Enter the video or playlist URL** when prompted.

3. **Select video quality:**
   - `1` - 1080p (High Quality)
   - `2` - 720p (Medium Quality)
   - `3` - 480p (Low Quality)
   - `4` - Best Available
   - `5` - Audio Only (MP3)

4. **Choose video format** (only if downloading video):
   - `1` - MP4
   - `2` - WebM
   - `3` - MKV

5. **Specify output directory** or press Enter to save in the current directory.

6. **The download starts automatically.** Once complete, the video will be saved in the specified folder.

## Example Usage

```
===== Video Downloader =====
Enter the video or playlist URL: https://www.youtube.com/watch?v=xyz123

Choose Video Quality:
1. 1080p (High Quality)
2. 720p (Medium Quality)
3. 480p (Low Quality)
4. Best Available
5. Audio Only (MP3)
Select quality option (1-5): 2

Choose Format:
1. MP4
2. WebM
3. MKV
Select format (1-3): 1

Enter download directory (press Enter for current directory): /Users/username/Videos

Starting download...
Download complete!
```

## Notes
- If you choose `Audio Only (MP3)`, format selection is skipped.
- Playlists will be saved in a folder named after the playlist.
- Ensure you have a stable internet connection for better performance.

## Troubleshooting
- If the script doesn't run, ensure `yt-dlp` is installed correctly.
- If download fails, try updating `yt-dlp`:
  ```sh
  pip install --upgrade yt-dlp
  ```
- If you get a permission error, try running the script with administrator privileges.

## License
This script is free to use and modify. Happy downloading! 🚀

