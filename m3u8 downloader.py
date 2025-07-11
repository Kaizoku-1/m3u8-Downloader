import os
import sys
import subprocess
from urllib.parse import urlparse

def get_filename_from_url(url):
    path = urlparse(url).path
    name = os.path.basename(path)
    if name.endswith(".m3u8"):
        return name.replace(".m3u8", ".mp4")
    return name + ".mp4"

def create_directory_if_not_exists(path):
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            print(f"Directory created: {path}")
        except Exception as e:
            print(f"Failed to create directory: {e}")
            sys.exit(1)

def main():
    target_dir = input("Enter target directory: ").strip()
    create_directory_if_not_exists(target_dir)

    while True:
        url = input("\nEnter m3u8 URL: ").strip()
        if not url:
            print("Invalid URL. Try again.")
            continue

        filename = get_filename_from_url(url)
        output_path = os.path.join(target_dir, filename)

        print(f"\nPlanned output file: {output_path}")
        user_choice = input("Type 'y' to start, 'n' to exit, or enter a new filename (without extension): ").strip()

        if user_choice.lower() == 'n':
            print("Exiting.")
            sys.exit(0)
        elif user_choice.lower() == 'y':
            pass  # keep original filename
        else:
            safe_name = user_choice + ".mp4"
            output_path = os.path.join(target_dir, safe_name)
            print(f"Using custom filename: {output_path}")

        print("Starting download with ffmpeg...\n")

        cmd = [
            "ffmpeg",
            "-i", url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            output_path
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            for line in process.stdout:
                print(line, end='')

            process.wait()
            if process.returncode == 0:
                print(f"\n\u2713 Download completed successfully: {output_path}")
            else:
                print(f"\n\u2717 ffmpeg exited with code {process.returncode}")
        except Exception as e:
            print(f"\n\u2717 Error running ffmpeg: {e}")

if __name__ == "__main__":
    main()
