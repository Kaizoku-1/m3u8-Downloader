import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import shutil
import re
import threading
import queue
from urllib.parse import urlparse

class M3U8DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("M3U8 Downloader")
        self.root.geometry("600x400")

        self.progress_queue = queue.Queue()

        # --- Main Frame ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.create_widgets(main_frame)

    def create_widgets(self, parent):
        # URL Entry
        url_label = ttk.Label(parent, text="M3U8 URL:")
        url_label.pack(fill=tk.X, padx=5, pady=2)
        self.url_entry = ttk.Entry(parent, width=80)
        self.url_entry.pack(fill=tk.X, padx=5, pady=2)

        # Save Path Frame
        path_frame = ttk.Frame(parent)
        path_frame.pack(fill=tk.X, padx=5, pady=5)

        save_label = ttk.Label(path_frame, text="Save to:")
        save_label.pack(side=tk.LEFT, anchor="w")
        self.save_path_var = tk.StringVar()
        self.save_path_entry = ttk.Entry(path_frame, textvariable=self.save_path_var, state="readonly")
        self.save_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        browse_button = ttk.Button(path_frame, text="Browse...", command=self.browse_directory)
        browse_button.pack(side=tk.LEFT)

        # Download Button
        self.download_button = ttk.Button(parent, text="Download", command=self.start_download_thread)
        self.download_button.pack(fill=tk.X, padx=5, pady=10)

        # Progress Bar
        self.progress_bar = ttk.Progressbar(parent, orient="horizontal", length=100, mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)

        # Status Box
        self.status_box = tk.Text(parent, height=10, state="disabled")
        self.status_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Set default save directory
        default_path = os.path.join(os.path.expanduser("~"), "m3u8_downloads")
        if not os.path.exists(default_path):
            os.makedirs(default_path)
        self.save_path_var.set(default_path)

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.save_path_var.set(directory)

    def log_message(self, message):
        self.status_box.config(state="normal")
        self.status_box.insert(tk.END, message + "\n")
        self.status_box.config(state="disabled")
        self.status_box.see(tk.END)

    def get_filename_from_url(self, url):
        """Parses a URL to generate a sanitized .mp4 filename."""
        try:
            path = urlparse(url).path
            name = os.path.basename(path)
            # Sanitize filename
            name = re.sub(r'[\\/*?:"<>|]',"", name)
            if name.endswith(".m3u8"):
                return name.replace(".m3u8", ".mp4")
            return name + ".mp4" if name else "output.mp4"
        except Exception:
            return "output.mp4"

    def start_download_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a URL.")
            return

        output_dir = self.save_path_var.get()
        if not output_dir:
            messagebox.showwarning("Warning", "Please select a save directory.")
            return

        filename = self.get_filename_from_url(url)

        output_path = filedialog.asksaveasfilename(
            initialdir=output_dir,
            initialfile=filename,
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )

        if not output_path:
            self.log_message("Download cancelled by user.")
            return

        self.download_button.config(state="disabled")
        self.progress_bar["value"] = 0
        self.progress_bar["mode"] = "determinate"

        thread = threading.Thread(
            target=self._download_stream_worker,
            args=(url, output_path)
        )
        thread.daemon = True
        thread.start()
        self.process_queue()

    def process_queue(self):
        try:
            while not self.progress_queue.empty():
                message = self.progress_queue.get_nowait()
                if isinstance(message, tuple):
                    msg_type = message[0]
                    if msg_type == "progress":
                        self.progress_bar["value"] = message[1]
                    elif msg_type == "log":
                        self.log_message(message[1])
                    elif msg_type == "mode":
                        self.progress_bar["mode"] = message[1]
                    elif msg_type == "complete":
                        self.on_download_complete(message[1], message[2])
        finally:
            # Check again after 100ms
            self.root.after(100, self.process_queue)

    def get_video_duration(self, url):
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", url
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            self.progress_queue.put(("log", f"Warning: Could not get duration. Progress bar will be indeterminate."))
            self.progress_queue.put(("log", f"[dim]{e}[/dim]"))
            return None

    def _download_stream_worker(self, url, output_path):
        self.progress_queue.put(("log", f"Starting download for: {url}"))
        self.progress_queue.put(("log", f"Saving to: {output_path}"))

        total_duration = self.get_video_duration(url)
        if not total_duration:
            self.progress_queue.put(("mode", "indeterminate"))

        cmd = [
            "ffmpeg", "-i", url, "-c", "copy", "-bsf:a", "aac_adtstoasc",
            output_path, "-y", "-progress", "pipe:1", "-nostats"
        ]

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8')

            time_pattern = re.compile(r"out_time_ms=(\d+)")

            # Use stderr for ffmpeg's own logs if stdout is the pipe
            for line in iter(process.stdout.readline, ""):
                match = time_pattern.search(line)
                if match and total_duration:
                    elapsed_us = int(match.group(1))
                    progress = (elapsed_us / (total_duration * 1_000_000)) * 100
                    self.progress_queue.put(("progress", progress))
                # Log other ffmpeg output
                if "frame=" not in line and "size=" not in line and "time=" not in line:
                     self.progress_queue.put(("log", line.strip()))

            process.wait()
            self.progress_queue.put(("complete", process.returncode, output_path))

        except FileNotFoundError:
            self.progress_queue.put(("complete", -1, "ffmpeg not found."))
        except Exception as e:
            self.progress_queue.put(("complete", -1, str(e)))

    def on_download_complete(self, returncode, output_path):
        """Callback to run in the main thread after download finishes."""
        self.download_button.config(state="normal")
        if returncode == 0:
            self.log_message(f"✔ Download completed successfully: {output_path}")
            messagebox.showinfo("Success", "Download completed successfully!")
        else:
            self.log_message(f"✘ Download failed. ffmpeg exited with code {returncode}.")
            messagebox.showerror("Error", f"Download failed. See logs for details.")

    def check_for_ffmpeg(self):
        self.log_message("Checking for ffmpeg...")
        if not shutil.which("ffmpeg"):
            messagebox.showerror("Error", "ffmpeg is not installed or not in your PATH.\nPlease install it from https://ffmpeg.org/download.html")
            self.log_message("Error: ffmpeg not found.")
            return False
        self.log_message("ffmpeg found!")
        return True

def main():
    root = tk.Tk()
    # Apply a theme
    style = ttk.Style(root)
    try:
        # 'clam' is a good cross-platform theme
        style.theme_use('clam')
    except tk.TclError:
        # Fallback if theme is not available
        pass

    app = M3U8DownloaderApp(root)
    if not app.check_for_ffmpeg():
        root.destroy()
        return
    root.mainloop()

if __name__ == "__main__":
    main()
