import json
import os

class SettingsManager:
    def __init__(self, settings_file):
        self.filepath = settings_file
        self.defaults = {
            "max_retries": 3,
            "enable_auto_retry": True,
            "post_download_action": "None", # "None", "Shutdown", "Sleep"
            "enable_notifications": True,
            "max_concurrent_downloads": 1,
            "bandwidth_limit_kb": 0 # 0 for unlimited
        }
        self.settings = self.defaults.copy()
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    loaded_settings = json.load(f)
                    # Make sure all keys are present
                    for key, value in self.defaults.items():
                        if key not in loaded_settings:
                            loaded_settings[key] = value
                    self.settings = loaded_settings
            except (json.JSONDecodeError, TypeError):
                print("Could not read settings file, using defaults.")
                self.settings = self.defaults.copy()
        else:
            print("No settings file found, using defaults.")
            self.save() # Create the file with defaults if it doesn't exist

    def save(self):
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key):
        return self.settings.get(key, self.defaults.get(key))

    def set(self, key, value):
        self.settings[key] = value
