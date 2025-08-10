import uuid
from enum import Enum
import json
import os

class DownloadStatus(Enum):
    QUEUED = "در صف"
    DOWNLOADING = "در حال دانلود"
    PAUSED = "متوقف شده"
    COMPLETED = "کامل شده"
    FAILED = "ناموفق"
    CANCELED = "لغو شده"

class DownloadPriority(Enum):
    LOW = "پایین"
    NORMAL = "معمولی"
    HIGH = "بالا"

class DownloadItem:
    def __init__(self, url, output_path, quality="best", priority=DownloadPriority.NORMAL, custom_headers=None, bandwidth_limit=0, retries=3):
        self.id = str(uuid.uuid4())
        self.url = url
        self.output_path = output_path
        self.quality = quality
        self.priority = priority
        self.custom_headers = custom_headers if custom_headers else {}
        self.bandwidth_limit = bandwidth_limit  # in KB/s, 0 for unlimited
        self.retries = retries

        self.status = DownloadStatus.QUEUED
        self.progress = 0
        self.speed = ""
        self.eta = ""
        self.error_message = ""
        self.retry_count = 0

    def to_dict(self):
        """Serializes the object to a dictionary for saving."""
        return {
            "id": self.id,
            "url": self.url,
            "output_path": self.output_path,
            "quality": self.quality,
            "priority": self.priority.name,
            "custom_headers": self.custom_headers,
            "bandwidth_limit": self.bandwidth_limit,
            "retries": self.retries,
            "status": self.status.name,
            "progress": self.progress,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates an object from a dictionary."""
        item = cls(
            url=data['url'],
            output_path=data['output_path'],
            quality=data.get('quality', 'best'),
            priority=DownloadPriority[data.get('priority', 'NORMAL')],
            custom_headers=data.get('custom_headers', {}),
            bandwidth_limit=data.get('bandwidth_limit', 0),
            retries=data.get('retries', 3)
        )
        item.id = data.get('id', str(uuid.uuid4()))
        item.status = DownloadStatus[data.get('status', 'QUEUED')]
        item.progress = data.get('progress', 0)
        # Non-persistent fields are reset
        item.speed = ""
        item.eta = ""
        item.error_message = ""
        item.retry_count = 0
        return item

class DownloadQueue:
    def __init__(self):
        self.items = []

    def add_item(self, item: DownloadItem):
        self.items.append(item)

    def remove_item(self, item_id):
        self.items = [item for item in self.items if item.id != item_id]

    def get_item(self, item_id):
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_next_item(self):
        """Gets the next queued item with the highest priority."""
        queued_items = [item for item in self.items if item.status == DownloadStatus.QUEUED]
        if not queued_items:
            return None

        # Sort by priority (HIGH > NORMAL > LOW)
        # Enum members are ordered by definition, but we'll sort explicitly for clarity
        priority_order = {DownloadPriority.HIGH: 0, DownloadPriority.NORMAL: 1, DownloadPriority.LOW: 2}
        queued_items.sort(key=lambda x: priority_order[x.priority])

        return queued_items[0]

    def save_to_file(self, filepath):
        """Saves the current queue to a JSON file."""
        try:
            data_to_save = [item.to_dict() for item in self.items]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving queue: {e}")

    def load_from_file(self, filepath):
        """Loads the queue from a JSON file."""
        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.items = [DownloadItem.from_dict(item_data) for item_data in data]
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"Error loading queue file: {e}")
            # Potentially handle corrupt file by backing it up and starting fresh
            self.items = []
