import os
import sys
import subprocess
import shutil
import re
from urllib.parse import urlparse
from rich.console import Console
from rich.panel import Panel
from tqdm import tqdm

# --- Globals ---
console = Console()

# --- Functions ---

def check_for_ffmpeg():
    """Checks if ffmpeg is installed and available in the system's PATH."""
    console.print("Checking for [bold magenta]ffmpeg[/bold magenta]...")
    if not shutil.which("ffmpeg"):
        console.print("[bold red]Error: ffmpeg is not installed or not in your PATH.[/bold red]")
        console.print("This script requires ffmpeg to download and process videos.")
        console.print("Please install it and make sure it's accessible from your terminal.")
        console.print("Download from: [link=https://ffmpeg.org/download.html]https://ffmpeg.org/download.html[/link]")
        sys.exit(1)
    console.print("[bold green]ffmpeg found![/bold green]\n")


def get_filename_from_url(url):
    """Parses a URL to generate a sanitized .mp4 filename."""
    try:
        path = urlparse(url).path
        name = os.path.basename(path)
        if name.endswith(".m3u8"):
            return name.replace(".m3u8", ".mp4")
        return name + ".mp4" if name else "output.mp4"
    except Exception:
        return "output.mp4"


def create_directory_if_not_exists(path):
    """Creates a directory if it doesn't already exist."""
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            console.print(f"Directory created: [cyan]{path}[/cyan]")
        except Exception as e:
            console.print(f"[bold red]Failed to create directory: {e}[/bold red]")
            sys.exit(1)


def get_video_duration(url):
    """Gets the total duration of the video using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        duration = float(result.stdout.strip())
        return duration
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        console.print(f"[yellow]Warning: Could not determine video duration. Progress bar may not show percentage.[/yellow]\n[dim]{e}[/dim]")
        return None

def download_stream(url, output_path):
    """Handles the ffmpeg download process with a progress bar."""
    console.print("\nDetermining video duration...")
    total_duration = get_video_duration(url)

    cmd = [
        "ffmpeg",
        "-i", url,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        output_path,
        "-y" # Overwrite output file if it exists
    ]

    console.print("Starting download with [bold magenta]ffmpeg[/bold magenta]...")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )

        time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

        with tqdm(total=int(total_duration) if total_duration else None,
                  unit='s',
                  dynamic_ncols=True,
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]") as progress_bar:

            last_seconds = 0
            for line in iter(process.stdout.readline, ""):
                match = time_pattern.search(line)
                if match:
                    hours, minutes, seconds, _ = map(int, match.groups())
                    current_seconds = hours * 3600 + minutes * 60 + seconds
                    update_amount = current_seconds - last_seconds
                    if update_amount > 0:
                        progress_bar.update(update_amount)
                        last_seconds = current_seconds

        process.wait()
        if process.returncode == 0:
            console.print(f"\n[bold green]✔ Download completed successfully: {output_path}[/bold green]")
        else:
            console.print(f"\n[bold red]✘ ffmpeg exited with code {process.returncode}[/bold red]")
            console.print(f"[red]There might have been an issue with the stream or the file.[/red]")

    except FileNotFoundError:
        console.print("[bold red]Error: ffmpeg command not found.[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]✘ An error occurred: {e}[/bold red]")


def main():
    """Main function to run the downloader."""
    console.print(Panel.fit("[bold cyan]M3U8 Downloader[/bold cyan]\nby @bespider", title="Welcome"))
    check_for_ffmpeg()

    try:
        target_dir = console.input("[bold yellow]Enter target directory for downloads: [/bold yellow]").strip()
        if not target_dir:
            target_dir = os.path.join(os.path.expanduser("~"), "m3u8_downloads")
            console.print(f"No directory provided. Using default: [cyan]{target_dir}[/cyan]")

        create_directory_if_not_exists(target_dir)

        while True:
            url = console.input("\n[bold yellow]Enter m3u8 URL (or press Enter to exit): [/bold yellow]").strip()
            if not url:
                break

            filename = get_filename_from_url(url)
            output_path = os.path.join(target_dir, filename)

            console.print(f"\nPlanned output file: [cyan]{output_path}[/cyan]")
            user_choice = console.input(
                "Type [bold green]'y'[/bold green] to start, "
                "[bold red]'n'[/bold red] to cancel, "
                "or enter a new filename (without extension): "
            ).strip()

            if user_choice.lower() == 'n':
                console.print("Download cancelled.")
                continue
            elif user_choice.lower() != 'y' and user_choice:
                safe_name = user_choice + ".mp4"
                output_path = os.path.join(target_dir, safe_name)
                console.print(f"Using custom filename: [cyan]{output_path}[/cyan]")

            download_stream(url, output_path)

    except KeyboardInterrupt:
        console.print("\n[bold blue]Script interrupted by user. Exiting.[/bold blue]")

    console.print("\n[bold blue]Exiting program.[/bold blue]")


if __name__ == "__main__":
    main()
