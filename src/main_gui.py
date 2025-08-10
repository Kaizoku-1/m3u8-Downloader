import tkinter as tk
from tkinter import ttk, W, BOTH, YES, LEFT, RIGHT, X, Y, VERTICAL, NO, CENTER, END, Toplevel, filedialog, messagebox
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import os
import threading
import queue
import requests
import m3u8

from models import DownloadQueue, DownloadItem, DownloadStatus, DownloadPriority
from downloader import DownloadWorker
from settings import SettingsManager

class AddUrlDialog(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Add New Download")
        self.geometry("600x350")
        self.transient(parent)
        self.grab_set()

        self.qualities = []
        self.result_queue = queue.Queue()

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=BOTH, expand=YES)

        # URL
        url_frame = ttk.Frame(frame)
        url_frame.pack(fill=X, pady=(0, 5))
        url_label = ttk.Label(url_frame, text="M3U8 URL:")
        url_label.pack(fill=X)
        self.url_entry = ttk.Entry(url_frame)
        self.url_entry.pack(side=LEFT, fill=X, expand=YES)
        self.fetch_btn = ttkb.Button(url_frame, text="Fetch Qualities", command=self.start_fetch_qualities, bootstyle="info-outline")
        self.fetch_btn.pack(side=LEFT, padx=(5, 0))
        self.url_entry.focus_set()

        # Quality Selection
        quality_label = ttk.Label(frame, text="Quality:")
        quality_label.pack(fill=X, pady=(10, 0))
        self.quality_combo = ttk.Combobox(frame, state="readonly")
        self.quality_combo.pack(fill=X, pady=(0, 10))

        # Output Path
        path_label = ttk.Label(frame, text="Save To:")
        path_label.pack(fill=X)
        path_frame = ttk.Frame(frame)
        path_frame.pack(fill=X, pady=(0, 10))
        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, state="readonly")
        path_entry.pack(side=LEFT, fill=X, expand=YES)
        browse_btn = ttk.Button(path_frame, text="Browse...", command=self.browse_path)
        browse_btn.pack(side=LEFT, padx=(5, 0))

        default_path = os.path.join(os.path.expanduser("~"), "m3u8_downloads_pro")
        if not os.path.exists(default_path):
            os.makedirs(default_path)
        self.path_var.set(default_path)

        # Status label for fetching
        self.fetch_status_label = ttk.Label(frame, text="")
        self.fetch_status_label.pack(fill=X, pady=(5,0))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=X, side=BOTTOM, pady=(10, 0))

        self.add_btn = ttkb.Button(btn_frame, text="Add Download", bootstyle="success", command=self.on_add, state="disabled")
        self.add_btn.pack(side=RIGHT)
        cancel_btn = ttkb.Button(btn_frame, text="Cancel", bootstyle="secondary", command=self.destroy)
        cancel_btn.pack(side=RIGHT, padx=(0, 5))

        self.after(100, self.process_queue)

    def start_fetch_qualities(self):
        url = self.url_entry.get().strip()
        if not url:
            return

        self.fetch_btn.config(state="disabled")
        self.fetch_status_label.config(text="Fetching qualities...")

        thread = threading.Thread(target=self.fetch_qualities_worker, args=(url,))
        thread.daemon = True
        thread.start()

    def fetch_qualities_worker(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            m3u8_obj = m3u8.loads(response.text, uri=url)

            if m3u8_obj.is_variant:
                qualities = []
                for playlist in m3u8_obj.playlists:
                    resolution = "Unknown"
                    if playlist.stream_info.resolution:
                        resolution = f"{playlist.stream_info.resolution[1]}p"

                    bandwidth = "Unknown"
                    if playlist.stream_info.bandwidth:
                        bandwidth = f"{playlist.stream_info.bandwidth / 1000:.0f} kbps"

                    display_name = f"{resolution} ({bandwidth})"
                    qualities.append({"display": display_name, "url": playlist.absolute_uri})
                self.result_queue.put(("success", qualities))
            else:
                # Not a master playlist, just a single stream
                qualities = [{"display": "Default", "url": url}]
                self.result_queue.put(("success", qualities))
        except Exception as e:
            self.result_queue.put(("error", str(e)))

    def process_queue(self):
        try:
            msg = self.result_queue.get_nowait()
            msg_type, data = msg

            if msg_type == "success":
                self.qualities = data
                self.quality_combo['values'] = [q['display'] for q in self.qualities]
                if self.qualities:
                    self.quality_combo.current(0)
                self.fetch_status_label.config(text=f"Found {len(self.qualities)} quality option(s).")
                self.add_btn.config(state="normal")
            elif msg_type == "error":
                 self.fetch_status_label.config(text=f"Error: {data}")
                 messagebox.showerror("Fetch Error", f"Could not fetch qualities:\n{data}", parent=self)

            self.fetch_btn.config(state="normal")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    def browse_path(self):
        directory = filedialog.askdirectory(initialdir=self.path_var.get())
        if directory:
            self.path_var.set(directory)

    def on_add(self):
        selected_index = self.quality_combo.current()
        if selected_index < 0:
            messagebox.showwarning("Input Error", "Please select a quality.", parent=self)
            return

        selected_quality = self.qualities[selected_index]
        url = selected_quality['url']
        quality_display = selected_quality['display']
        path = self.path_var.get()

        try:
            filename = os.path.basename(self.url_entry.get().strip()).split('?')[0].replace(".m3u8", ".mp4")
            if not filename: filename = "video.mp4"
        except:
            filename = "video.mp4"

        output_path = os.path.join(path, filename)

        retries = self.parent.settings_manager.get("max_retries") if self.parent.settings_manager.get("enable_auto_retry") else 0
        item = DownloadItem(url=url, output_path=output_path, quality=quality_display, retries=retries)
        self.parent.add_download_item(item)
        self.destroy()

class SettingsDialog(Toplevel):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.parent = parent
        self.settings_manager = settings_manager
        self.title("Settings")
        self.geometry("450x350")
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=BOTH, expand=YES)

        # Max Retries
        retry_frame = ttk.Frame(frame)
        retry_frame.pack(fill=X, pady=5)
        retry_label = ttk.Label(retry_frame, text="Max Retries:")
        retry_label.pack(side=LEFT, padx=(0,10))
        self.max_retries_var = tk.IntVar(value=self.settings_manager.get("max_retries"))
        retry_spinbox = ttk.Spinbox(retry_frame, from_=0, to=10, textvariable=self.max_retries_var)
        retry_spinbox.pack(side=LEFT)

        # Enable Auto Retry
        self.enable_retry_var = tk.BooleanVar(value=self.settings_manager.get("enable_auto_retry"))
        retry_check = ttk.Checkbutton(frame, text="Enable Automatic Retries", variable=self.enable_retry_var, bootstyle="round-toggle")
        retry_check.pack(fill=X, pady=5)

        # Post Download Action
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=X, pady=10)
        action_label = ttk.Label(action_frame, text="After Queue Finishes:")
        action_label.pack(side=LEFT, padx=(0,10))
        self.post_action_var = tk.StringVar(value=self.settings_manager.get("post_download_action"))
        action_combo = ttk.Combobox(action_frame, textvariable=self.post_action_var, state="readonly", values=["None", "Shutdown", "Sleep"])
        action_combo.pack(side=LEFT, fill=X, expand=YES)

        # Notifications
        self.enable_notifications_var = tk.BooleanVar(value=self.settings_manager.get("enable_notifications"))
        notifications_check = ttk.Checkbutton(frame, text="Enable System Notifications", variable=self.enable_notifications_var, bootstyle="round-toggle")
        notifications_check.pack(fill=X, pady=5)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=X, side=BOTTOM, pady=(20, 0))

        save_btn = ttkb.Button(btn_frame, text="Save", bootstyle="success", command=self.on_save)
        save_btn.pack(side=RIGHT)
        cancel_btn = ttkb.Button(btn_frame, text="Cancel", bootstyle="secondary", command=self.destroy)
        cancel_btn.pack(side=RIGHT, padx=(0, 5))

    def on_save(self):
        self.settings_manager.set("max_retries", self.max_retries_var.get())
        self.settings_manager.set("enable_auto_retry", self.enable_retry_var.get())
        self.settings_manager.set("post_download_action", self.post_action_var.get())
        self.settings_manager.set("enable_notifications", self.enable_notifications_var.get())
        self.settings_manager.save()
        messagebox.showinfo("Settings Saved", "Settings have been saved successfully.", parent=self)
        self.destroy()

class AdvancedDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced M3U8 Downloader")
        self.root.geometry("1100x600")

        settings_path = os.path.join(os.path.expanduser("~"), "m3u8_downloads_pro", "settings.json")
        self.settings_manager = SettingsManager(settings_path)

        self.queue_save_path = os.path.join(os.path.expanduser("~"), "m3u8_downloads_pro", "queue.json")
        self.download_queue = DownloadQueue()
        self.progress_queue = queue.Queue()
        self.is_queue_running = False
        self.stop_event = threading.Event()
        self.active_worker = None
        self.queue_processor_thread = None

        self.create_widgets()
        self.load_queue()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.after(100, self.process_progress_queue)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=X, pady=5)

        self.add_btn = ttkb.Button(toolbar, text="Add URL", bootstyle="success", command=self.show_add_url_dialog)
        self.add_btn.pack(side=LEFT, padx=5)

        self.remove_btn = ttkb.Button(toolbar, text="Remove", bootstyle="danger", command=self.remove_selected_items)
        self.remove_btn.pack(side=LEFT, padx=5)

        self.start_btn = ttkb.Button(toolbar, text="Start Queue", bootstyle="info", command=self.start_queue)
        self.start_btn.pack(side=LEFT, padx=5)

        self.stop_btn = ttkb.Button(toolbar, text="Stop Queue", bootstyle="warning", command=self.stop_queue, state="disabled")
        self.stop_btn.pack(side=LEFT, padx=5)

        self.settings_btn = ttkb.Button(toolbar, text="Settings", bootstyle="secondary", command=self.show_settings_dialog)
        self.settings_btn.pack(side=RIGHT, padx=5)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=BOTH, expand=YES, pady=5)

        columns = ("filename", "size", "progress", "speed", "eta", "status", "priority")
        self.tree = ttkb.Treeview(master=tree_frame, columns=columns, bootstyle="primary")
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)

        scrollbar = ttkb.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview, bootstyle="round")
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.tree.heading("#0", text="ID", anchor=W)
        self.tree.heading("filename", text="Filename", anchor=W)
        self.tree.heading("size", text="Size", anchor=W)
        self.tree.heading("progress", text="Progress", anchor=W)
        self.tree.heading("speed", text="Speed", anchor=W)
        self.tree.heading("eta", text="ETA", anchor=W)
        self.tree.heading("status", text="Status", anchor=W)
        self.tree.heading("priority", text="Priority", anchor=W)

        self.tree.column("#0", width=0, stretch=NO)
        self.tree.column("filename", width=300)
        self.tree.column("size", width=80, anchor=CENTER)
        self.tree.column("progress", width=200, anchor=CENTER)
        self.tree.column("speed", width=100, anchor=CENTER)
        self.tree.column("eta", width=100, anchor=CENTER)
        self.tree.column("status", width=120, anchor=CENTER)
        self.tree.column("priority", width=80, anchor=CENTER)

        # Configure tags for status colors
        self.tree.tag_configure(DownloadStatus.COMPLETED.name, background=ttkb.Style().colors.success)
        self.tree.tag_configure(DownloadStatus.DOWNLOADING.name, background=ttkb.Style().colors.info)
        self.tree.tag_configure(DownloadStatus.FAILED.name, background=ttkb.Style().colors.danger)
        self.tree.tag_configure(DownloadStatus.CANCELED.name, background=ttkb.Style().colors.secondary)
        self.tree.tag_configure(DownloadStatus.PAUSED.name, background=ttkb.Style().colors.warning)

        status_bar_frame = ttk.Frame(main_frame)
        status_bar_frame.pack(fill=X, side=tk.BOTTOM, pady=(5, 0))
        self.status_label = ttk.Label(status_bar_frame, text="Ready", anchor=W)
        self.status_label.pack(side=LEFT, padx=5)

    def show_add_url_dialog(self):
        dialog = AddUrlDialog(self.root)
        self.root.wait_window(dialog)

    def add_download_item(self, item):
        self.download_queue.add_item(item)
        self.refresh_treeview()

    def remove_selected_items(self):
        selected_ids = self.tree.selection()
        if not selected_ids:
            messagebox.showinfo("Information", "No items selected to remove.", parent=self.root)
            return

        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to remove {len(selected_ids)} item(s)?", parent=self.root):
            for item_id in selected_ids:
                self.download_queue.remove_item(item_id)
            self.refresh_treeview()

    def refresh_treeview(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        for item in self.download_queue.items:
            progress_val = item.progress
            values = (
                os.path.basename(item.output_path),
                item.size,
                f"{progress_val}%",
                item.speed,
                item.eta,
                item.status.value,
                item.priority.value
            )
            self.tree.insert("", END, iid=item.id, values=values, tags=(item.status.name,))

    def load_queue(self):
        self.download_queue.load_from_file(self.queue_save_path)
        self.refresh_treeview()

    def on_closing(self):
        """Called when the main window is closed."""
        if self.is_queue_running:
            self.stop_queue()
        self.download_queue.save_to_file(self.queue_save_path)
        self.root.destroy()

    def start_queue(self):
        if self.is_queue_running:
            return
        self.is_queue_running = True
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Queue started...")

        self.queue_processor_thread = threading.Thread(target=self.queue_processor_worker)
        self.queue_processor_thread.daemon = True
        self.queue_processor_thread.start()

    def stop_queue(self):
        if not self.is_queue_running:
            return
        self.is_queue_running = False
        self.stop_event.set()
        if self.active_worker:
            self.active_worker.stop()
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Stopping queue...")

    def queue_processor_worker(self):
        while self.is_queue_running:
            item = self.download_queue.get_next_item()
            if item:
                self.active_worker = DownloadWorker(item, self.progress_queue, self.stop_event)
                self.active_worker.start()
                self.active_worker.join() # Wait for the current download to finish
                self.active_worker = None
            else:
                # Queue is empty, stop processing
                self.is_queue_running = False

        # Finished processing
        self.root.after(0, self.on_queue_finished)

    def on_queue_finished(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Queue finished.")
        self.execute_post_action()

    def process_progress_queue(self):
        try:
            while not self.progress_queue.empty():
                msg = self.progress_queue.get_nowait()
                msg_type = msg[0]
                item_id = msg[1]

                if msg_type == "update_item":
                    data = msg[2]
                    self.update_item_in_treeview(item_id, data)
                elif msg_type == "log":
                    # For now, just print logs. Could be added to a details pane later.
                    print(f"LOG [{item_id}]: {msg[2]}")
                elif msg_type == "download_finished":
                    # This signal is used by the queue processor, no GUI action needed here
                    pass
        finally:
            self.root.after(100, self.process_progress_queue)

    def update_item_in_treeview(self, item_id, data):
        """Updates a specific item's data in the treeview."""
        if not self.tree.exists(item_id):
            return

        item = self.download_queue.get_item(item_id)
        if not item:
            return

        # Update the item object with new data
        final_status = False
        if "status" in data:
            new_status = data["status"]
            if new_status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELED]:
                final_status = True
            item.status = new_status

        for key, value in data.items():
            if key != "status" and hasattr(item, key):
                setattr(item, key, value)

        # Update the treeview values
        values = (
            os.path.basename(item.output_path),
            item.size,
            f"{item.progress}%",
            item.speed,
            item.eta,
            item.status.value,
            item.priority.value
        )
        self.tree.item(item_id, values=values, tags=(item.status.name,))

        if final_status:
            title = f"Download {item.status.name.capitalize()}"
            message = f"{os.path.basename(item.output_path)} has finished."
            if item.status == DownloadStatus.FAILED:
                message = f"{os.path.basename(item.output_path)} has failed."
            self.show_notification(title, message)

    def show_settings_dialog(self):
        dialog = SettingsDialog(self.root, self.settings_manager)
        self.root.wait_window(dialog)

    def show_notification(self, title, message):
        if self.settings_manager.get("enable_notifications"):
            try:
                from plyer import notification
                # Run in a separate thread to not block the GUI
                threading.Thread(
                    target=notification.notify,
                    kwargs={
                        "title": title,
                        "message": message,
                        "app_name": "M3U8 Downloader Pro",
                        "timeout": 10
                    },
                    daemon=True
                ).start()
            except (ImportError, NotImplementedError):
                print("Plyer not installed or notifications not supported on this system.")
            except Exception as e:
                print(f"Failed to show notification: {e}")

    def execute_post_action(self):
        action = self.settings_manager.get("post_download_action")
        if action == "Shutdown":
            self.status_label.config(text="Queue finished. Shutting down in 60 seconds...")
            os.system("shutdown /s /t 60")
        elif action == "Sleep":
            self.status_label.config(text="Queue finished. Sleeping computer...")
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")


if __name__ == "__main__":
    root = ttkb.Window(themename="superhero")
    app = AdvancedDownloaderApp(root)
    root.mainloop()
