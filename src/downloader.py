import subprocess
import re
import threading

from models import DownloadStatus

class DownloadWorker(threading.Thread):
    def __init__(self, item, progress_queue, stop_event):
        super().__init__()
        self.item = item
        self.progress_queue = progress_queue
        self.stop_event = stop_event
        self.process = None
        self.daemon = True

    def run(self):
        """Executes the ffmpeg download process with retries."""
        for i in range(self.item.retries + 1):
            self.item.retry_count = i
            if self.stop_event.is_set():
                self.item.status = DownloadStatus.CANCELED
                break

            try:
                self.item.status = DownloadStatus.DOWNLOADING
                self.progress_queue.put(("update_item", self.item.id, {"status": self.item.status, "progress": 0, "retry_count": i}))

                total_duration = self.get_video_duration()

                cmd = self.build_ffmpeg_command()

                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='replace'
                )

            progress_pattern = re.compile(r"(\w+?)\s*=\s*(.*)")
            progress_data = {}

            # Read from stdout for progress
            for line in iter(self.process.stdout.readline, ""):
                if self.stop_event.is_set():
                    break

                match = progress_pattern.match(line.strip())
                if match:
                    key, value = match.groups()
                    progress_data[key] = value

                    if key == "progress" and value == "end":
                        break

                    if total_duration and 'out_time_us' in progress_data:
                        elapsed_us = int(progress_data['out_time_us'])
                        progress = min(100, (elapsed_us / (total_duration * 1_000_000)) * 100)
                        speed = progress_data.get('speed', '0x').replace('x', '')
                        eta_seconds = 0
                        if float(speed) > 0:
                            eta_seconds = (total_duration - (elapsed_us / 1_000_000)) / float(speed)

                        update = {
                            "progress": int(progress),
                            "speed": f"{float(speed):.1f}x",
                            "eta": f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s" if eta_seconds > 0 else "N/A"
                        }
                        self.progress_queue.put(("update_item", self.item.id, update))

            # Read stderr for any error messages
            stderr_output = self.process.stderr.read()
            if stderr_output:
                self.progress_queue.put(("log", self.item.id, "--- FFMPEG LOG ---"))
                self.progress_queue.put(("log", self.item.id, stderr_output.strip()))
                self.progress_queue.put(("log", self.item.id, "--------------------"))

            self.process.wait()

            if self.stop_event.is_set():
                self.item.status = DownloadStatus.CANCELED
            elif self.process.returncode == 0:
                self.item.status = DownloadStatus.COMPLETED
                self.item.progress = 100
            else:
                self.item.status = DownloadStatus.FAILED
                self.item.error_message = f"ffmpeg exited with code {self.process.returncode}"

        except Exception as e:
            if self.stop_event.is_set():
                self.item.status = DownloadStatus.CANCELED
                break # Exit retry loop if stopped

            if i < self.item.retries:
                self.progress_queue.put(("log", self.item.id, f"Download failed. Retrying ({i+1}/{self.item.retries})... Error: {e}"))
                self.stop_event.wait(5) # Wait 5 seconds before retrying
            else:
                self.item.status = DownloadStatus.FAILED
                self.item.error_message = str(e)

        finally:
            # Send final status update
            update_data = {
                "status": self.item.status,
                "progress": self.item.progress,
                "error": self.item.error_message,
                "speed": "",
                "eta": ""
            }
            self.progress_queue.put(("update_item", self.item.id, update_data))
            # Signal that this download has finished
            self.progress_queue.put(("download_finished", self.item.id))

    def get_video_duration(self):
        """Gets video duration using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", self.item.url
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
            return float(result.stdout.strip())
        except Exception as e:
            self.progress_queue.put(("log", self.item.id, f"Could not get duration: {e}"))
            return None

    def stop(self):
        """Stops the download process."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception as e:
                print(f"Error terminating process for {self.item.id}: {e}")

    def get_system_proxy(self):
        """
        Attempts to get system proxy settings on Windows.
        Returns proxy URL or None.
        """
        if threading.current_thread().name != 'MainThread':
             # This should be called from the main thread if it involves registry access
             # For now, we are assuming it's safe. A more robust solution might use a queue.
             pass
        try:
            import winreg
            proxy_key = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, proxy_key)
            proxy_enabled = winreg.QueryValueEx(key, 'ProxyEnable')[0]
            if proxy_enabled:
                proxy_server = winreg.QueryValueEx(key, 'ProxyServer')[0]
                return f"http://{proxy_server}"
        except (ImportError, FileNotFoundError, OSError):
            # Not on Windows or registry key not found
            return None
        return None

    def build_ffmpeg_command(self):
        """Builds the ffmpeg command list based on item properties."""
        cmd = ["ffmpeg"]

        # Add proxy if detected
        proxy = self.get_system_proxy()
        if proxy:
            cmd.extend(["-http_proxy", proxy])

        # Add custom headers
        if self.item.custom_headers:
            header_str = "".join([f"{key}: {value}\r\n" for key, value in self.item.custom_headers.items()])
            cmd.extend(["-headers", header_str])

        cmd.extend(["-i", self.item.url])

        # Add bandwidth limit if set
        if self.item.bandwidth_limit > 0:
            cmd.extend(["-limit_rate", f"{self.item.bandwidth_limit}K"])

        cmd.extend([
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            self.item.output_path,
            "-y",
            "-progress", "pipe:1",
            "-nostats"
        ])
        return cmd
