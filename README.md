# M3U8 Downloader Pro

This is an advanced download manager for downloading m3u8 video streams, built with Python and Tkinter.

## Features

- **Modern & Professional UI**: A clean and user-friendly interface built with `ttkbootstrap`.
- **Download Queue**: Add multiple downloads to a queue and manage them.
- **Priority Management**: Set high, normal, or low priority for downloads.
- **Video Quality Selection**: Automatically fetches available video qualities from a master m3u8 URL and lets you choose.
- **Advanced Download Options**:
    - **Bandwidth Limiting**: Limit the download speed to save bandwidth.
    - **Custom Headers**: Add custom HTTP headers for streams that require them.
    - **Automatic Retries**: Automatically retries failed downloads.
    - **System Proxy**: Uses the system's configured proxy on Windows.
- **Settings Panel**: A dedicated window to configure:
    - Number of retries (and enable/disable the feature).
    - Post-download actions (Shutdown or Sleep).
    - System notifications.
- **Persistent Queue & Settings**: Your download list and settings are saved and loaded automatically.
- **System Notifications**: Get a native notification when a download is complete or fails.

## Requirements

- **Python 3**: Make sure Python 3 is installed and added to your system's PATH.
- **ffmpeg**: This application requires `ffmpeg` to be installed and accessible in your system's PATH. You can download it from [ffmpeg.org](https://ffmpeg.org/download.html).

---

## How to Run

There are two ways to run the application:

### 1. From Source Code (Recommended for developers)

This method is great if you want to see the code or modify it.

**Step 1: Install Dependencies**

Open a command prompt or terminal and run the following command to install the necessary Python libraries:
```bash
pip install -r src/requirements.txt
```

**Step 2: Run the Application**

Once the dependencies are installed, run the main GUI script:
```bash
python src/main_gui.py
```

### 2. Build the `.exe` Executable

This method will package the entire application into a single `.exe` file that you can run on any Windows machine (that has ffmpeg installed).

**Step 1: Run the Build Script**

Simply double-click the `build.bat` file.

This script will automatically:
1. Check if you have Python installed.
2. Install all the required dependencies.
3. Run `PyInstaller` to build the executable.

**Step 2: Find the Executable**

After the script finishes, you will find the final application in the `dist` folder: `dist/M3U8_Downloader_Pro.exe`. You can copy this file anywhere and run it.
