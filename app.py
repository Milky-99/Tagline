import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, BOTTOM, SE
from PIL import Image, ImageTk, PngImagePlugin, WebPImagePlugin
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from tkinter import ttk
import os
import piexif
import piexif.helper
import traceback
import subprocess
import threading
import queue
import asyncio
import time
from cryptography.fernet import Fernet
import json
import sys
import subprocess
import exif
import win32com.shell.shell as shell
import win32com.shell.shellcon as shellcon
import webbrowser
import requests  # NEW: Added for checking API key validity


class ImageCaptionApp:
    def __init__(self, root):
        self.settings_file = "app_settings.enc"
        self.encryption_key = self.get_or_create_key()
        self.selected_model = tk.StringVar()
        self.retry_count = tk.IntVar(value=1)
        self.delay_seconds = tk.DoubleVar(value=1.0)
        self.num_hashtags = tk.IntVar(value=10)
        self.caption_query = tk.StringVar(
            value="Write a long accurate caption describing the image strictly in English and use explicit words only if accurate.Focus on the most prominent objects, actions, and scenes.If famous people are identified in the image, always include their names."
        )
        self.tags_query = tk.StringVar(
            value="Generate exactly {num_hashtags} strictly English keywords describing people, objects, clothes, actions, or scenes in the image using underscore between multi word hashtags and first and last names and use explicit words only if accurate, give them in a line not a list , no numbers, no remarks by you like ,here is the hashtags, or anything like that."
        )
        self.response_timeout = tk.IntVar(
            value=30
        )  # Timeout for API calls, good practice
        self.caption_var = tk.BooleanVar(value=True)
        self.tags_var = tk.BooleanVar(value=True)
        self.save_txt_var = tk.BooleanVar(value=False)
        self.api_key = tk.StringVar()  # For the input field
        self.model_options = []  # Initialize as empty
        self.additional_caption = ""
        self.additional_tags = ""
        self.console_queue = queue.Queue()
        self.api_keys = []  # List to store multiple API keys
        self.current_api_key_index = (
            0 if self.api_keys else None
        )  # Index of the currently used API key  INITIALIZE BEFORE LOAD SETTINGS
        self.processed_images = set()
        self.image_queue = queue.Queue()
        self.image_status = {}  # Track image processing status (0=failed, 1=success, -1=pending)
        self.safety_settings = []
        self.paused = False

        self.root = root
        self.root.title("Tagline")
        self.root.iconbitmap("app.ico")  # Assuming you have an icon file
        self.stop_processing = False  # Flag to stop processing
        self.log_to_file_var = tk.BooleanVar(
            value=False
        )  # NEW: Option to enable/disable logging to file
        self.log_file_path = "app_log.txt"  # NEW: Log file path
        self.log_file = None  # File handle, initialized later

        self.load_settings()  # Load settings *before* configuring the API

        # Configure API *after* loading settings (which might include API keys)
        # AND after initializing current_api_key_index
        if self.api_keys:
            if self.current_api_key_index is not None:  # Check index validity
                try:
                    genai.configure(api_key=self.api_keys[self.current_api_key_index])
                    self.print("Initial API key configuration successful.")
                except Exception as e:
                    self.print(f"Initial API key configuration failed: {e}")
            else:
                self.print("No valid API key index found after loading settings.")
        else: #handle no API keys
            self.print("No API keys loaded.")

        # Fetch available models *after* potentially configuring the API key
        self.model_options = self.fetch_available_models()
        if not self.model_options:
            self.model_options = [
                "gemini-1.5-pro-002"
            ]  # Use a default if no models are found.
            self.print("Using default model: gemini-1.5-pro-002")
        self.selected_model.set(
            self.model_options[0] if self.model_options else "gemini-1.5-pro-002"
        )

        self.create_widgets()
        self.active_threads = 0
        self.max_threads = (
            1  # NEW: Limit the number of concurrent processing threads
        )
        self.thread_semaphore = threading.Semaphore(
            self.max_threads
        )  # Control concurrent access

        self.root.protocol(
            "WM_DELETE_WINDOW", self.on_closing
        )  # Handle window close event

    def toggle_logging(self):
        """Enables or disables logging to file."""
        if self.log_to_file_var.get():
            self.open_log_file()
        else:
            self.close_log_file()
        self.save_settings()  # Save the logging preference

    def open_log_file(self):
        """Opens the log file for appending."""
        try:
            self.log_file = open(
                self.log_file_path, "a", encoding="utf-8"
            )  # Append mode
            self.print("Logging to file enabled.")  # Log this event
        except Exception as e:
            self.print(f"Error opening log file: {e}")
            #  Don't reset self.log_to_file_var here; user explicitly enabled it.

    def close_log_file(self):
        """Closes the log file if it's open."""
        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.print("Logging to file disabled.")  # Log this event

    def fetch_available_models(self):
        """Fetches the list of available models from the API."""
        try:
            if not self.api_keys:
                self.print("No API keys configured. Cannot fetch models.")
                return []

            # Use the currently selected API key
            if self.current_api_key_index is not None:
                try:
                    # Configure the API key
                    genai.configure(api_key=self.api_keys[self.current_api_key_index])
                except Exception as e:
                    self.print(f"API Key configuration failed: {e}")
                    return []
            else:
                self.print("Current API key index is None. Cannot fetch models.")
                return []

            available_models = []
            # Use genai.list_models()
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    available_models.append(m.name)
            return available_models

        except Exception as e:
            self.print(f"Error fetching models: {e}")
            return []
            
            
            
            
            
            
            
            
            
            
            
            
            
    def get_model_info(self, model_name):
        """Retrieves information about a specific model."""
        try:
            model = genai.GenerativeModel(model_name=model_name)

            info_str = f"{model.display_name}\n"  # display_name *does* exist
            info_str += f"{model.name}\n"
            if hasattr(model, 'version'):
                info_str += f"Version: {model.version}\n"


            if hasattr(model, 'description'):
                info_str += f"Description: {model.description}\n"

            # Input/Output Token Limits
            if hasattr(model, 'input_token_limit'):
                info_str += f"Input Token Limit: {model.input_token_limit}\n"
            if hasattr(model, 'output_token_limit'):
                info_str += f"Output Token Limit: {model.output_token_limit}\n"


            # Best for (this section requires more manual mapping as there's no direct attribute)
            if hasattr(model, 'supported_generation_methods'):

                best_for = []
                if "generateContent" in model.supported_generation_methods:
                    best_for.append("Multimodal understanding")
                if "generateContentStream" in model.supported_generation_methods:
                    best_for.append("Streaming responses")  # Example
                if any("tuneModel" in method for method in model.supported_generation_methods):  # Example condition
                   best_for.append("Fine-tuning") #example fine tuning

                info_str += "Best for:\n" + "\n".join(best_for) + "\n"


            # Use case (also requires mapping, similar to "Best for")
            if hasattr(model, 'supported_generation_methods'):
                use_cases = []

                if "generateContent" in model.supported_generation_methods:
                   use_cases.append("Process 10,000 lines of code") #example use case
                   use_cases.append("Call tools natively, like Search") #example use case
                if "generateContent" in model.supported_generation_methods and "embedContent" in model.supported_generation_methods:  # Example for a combo capability
                    use_cases.append("Create embeddings and generate content")

                info_str += "Use case:\n" + "\n".join(use_cases) + "\n"



            # Pricing -  There is no direct 'pricing' attribute, needs more research if available.
            # We'll add a placeholder for now, and you can investigate further.
            info_str += "Pricing: (Information not directly available via API - check documentation)\n"

            # Supported Generation Methods (good to list explicitly)
            if hasattr(model, 'supported_generation_methods'):
                info_str += "Supported Generation Methods: " + ", ".join(model.supported_generation_methods) + "\n"
            
            #Knowledge and Rate (still keeping default but can be removed or updated)
            info_str += f"Knowledge cutoff\nAug 2024\n"
            info_str += "Rate limits\n10 RPM\n"


            return info_str

        except Exception as e:
            self.print(f"Error getting model info for {model_name}: {e}")
            return f"Error: Could not retrieve information for {model_name}."

    def setup_support_button(self):
        """Adds a 'Support Me' button linking to Buy Me a Coffee."""
        support_button = ttk.Button(
            self.root,
            text="Support Me",
            command=lambda: webbrowser.open("https://buymeacoffee.com/milky99"),
        )
        support_button.pack(side=tk.BOTTOM, anchor=tk.SE, padx=10, pady=10)
        self.create_tooltip(support_button, "Support the developer")

    def create_tooltip(self, widget, text):
        """Creates a simple tooltip for a widget."""

        def enter(event):
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(
                tooltip,
                text=text,
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
            )
            label.pack()
            widget.tooltip = tooltip

        def leave(event):
            if hasattr(widget, "tooltip"):
                widget.tooltip.destroy()

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def get_or_create_key(self):
        """Retrieves or generates an encryption key for settings."""
        key_file = "encryption_key.key"
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            return key

    def save_settings(self):
        """Saves the application settings to an encrypted file."""
        settings = {
            "safety_settings": [
                {
                    "category": setting["category"].name,
                    "threshold": setting["threshold"].name,
                }
                for setting in self.safety_settings
            ],
            "selected_model": self.selected_model.get(),
            "retry_count": self.retry_count.get(),
            "delay_seconds": self.delay_seconds.get(),
            "api_keys": self.api_keys,
            "num_hashtags": self.num_hashtags.get(),
            "caption_query": self.caption_query.get(),
            "tags_query": self.tags_query.get(),
            "response_timeout": self.response_timeout.get(),
            "caption_enabled": self.caption_var.get(),
            "tags_enabled": self.tags_var.get(),
            "save_txt": self.save_txt_var.get(),
            "additional_caption": self.additional_caption,
            "log_to_file": self.log_to_file_var.get(),  # Save log setting
            "additional_tags": self.additional_tags,
        }

        encrypted_data = Fernet(self.encryption_key).encrypt(
            json.dumps(settings).encode()
        )
        with open(self.settings_file, "wb") as f:
            f.write(encrypted_data)
        self.print("Settings saved successfully")

    def load_settings(self):
        """Loads the application settings from an encrypted file."""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "rb") as f:
                encrypted_data = f.read()

            try:
                decrypted_data = Fernet(self.encryption_key).decrypt(encrypted_data)
                settings = json.loads(decrypted_data.decode())

                # Load safety settings, handling potential errors
                self.safety_settings = []
                for item in settings.get("safety_settings", []):
                    try:
                        category = HarmCategory[item["category"]]
                        threshold = HarmBlockThreshold[item["threshold"]]
                        self.safety_settings.append(
                            {"category": category, "threshold": threshold}
                        )
                    except KeyError:
                        self.print(
                            f"Warning: Invalid safety setting found: {item}. Skipping."
                        )

                # If no valid safety settings were loaded, use defaults:
                if not self.safety_settings:
                    self.set_default_safety_settings()

                # Load other settings, using get() with defaults for safety:
                self.response_timeout.set(
                    max(
                        30,
                        min(
                            300,
                            int(
                                settings.get(
                                    "response_timeout", self.response_timeout.get()
                                )
                            ),
                        ),
                    )
                )
                self.selected_model.set(
                    settings.get("selected_model", self.selected_model.get())
                )
                self.retry_count.set(
                    settings.get("retry_count", self.retry_count.get())
                )
                self.delay_seconds.set(
                    settings.get("delay_seconds", self.delay_seconds.get())
                )
                self.api_keys = settings.get("api_keys", [])
                self.num_hashtags.set(
                    settings.get("num_hashtags", self.num_hashtags.get())
                )
                self.caption_query.set(
                    settings.get("caption_query", self.caption_query.get())
                )
                self.tags_query.set(
                    settings.get("tags_query", self.tags_query.get())
                )
                self.log_to_file_var.set(
                    settings.get("log_to_file", False)
                )  # Load log setting

                self.caption_var.set(
                    settings.get("caption_enabled", self.caption_var.get())
                )
                self.tags_var.set(settings.get("tags_enabled", self.tags_var.get()))
                self.save_txt_var.set(settings.get("save_txt", self.save_txt_var.get()))
                self.additional_caption = settings.get(
                    "additional_caption", self.additional_caption
                )
                self.additional_tags = settings.get(
                    "additional_tags", self.additional_tags
                )

            except Exception as e:
                self.print(f"Error loading settings: {e}")
                self.set_default_settings()  # Apply defaults if loading fails
        else:
            self.set_default_settings()  # Apply defaults if no settings file

    def set_default_safety_settings(self):
        """Sets default safety settings."""
        self.safety_settings = [
            {
                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": HarmBlockThreshold.BLOCK_NONE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": HarmBlockThreshold.BLOCK_NONE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": HarmBlockThreshold.BLOCK_NONE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": HarmBlockThreshold.BLOCK_NONE,
            },
        ]

    def set_default_settings(self):
        """Applies default settings."""
        self.set_default_safety_settings()
        if self.model_options:
            self.selected_model.set(self.model_options[0])
        else:
            self.selected_model.set(
                "gemini-1.5-pro-002"
            )  # Use the default if model list is empty
        self.retry_count.set(1)
        self.delay_seconds.set(1.0)
        self.api_keys = []
        self.num_hashtags.set(10)
        self.caption_query.set(
            "Write a long accurate caption describing the image strictly in English and use explicit words only if accurate. Focus on the most prominent objects, actions, and scenes. If famous people are identified in the image, always include their names."
        )
        self.tags_query.set(
            "Generate exactly {num_hashtags} strictly English keywords describing people, objects, clothes, actions, or scenes in the image using underscore between multi word hashtags and first and last names and use explicit words only if accurate, give them in a line not a list , no numbers, no remarks by you like ,here is the hashtags, or anything like that."
        )
        self.response_timeout.set(30)  # Set default timeout
        self.log_to_file_var.set(False)  # Default: no logging
        self.save_settings()  # Save the defaults
        self.print("Default settings applied")

    def on_closing(self):
        """Handles the application closing event."""
        self.save_settings()
        self.close_log_file()  # Close log file on exit
        self.root.destroy()

    def create_context_menu(self, event, file_path):
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Open", command=lambda: self.open_file(file_path))
        context_menu.add_command(label="Open Containing Folder", command=lambda: self.open_containing_folder(file_path))
        context_menu.post(event.x_root, event.y_root)

    def delete_from_canvas(self, file_path):
        self.print(f"Attempting to delete {file_path} from canvas")
        for widget in self.image_frame.winfo_children():
            if isinstance(widget, tk.Canvas):
                scrollable_frame = widget.winfo_children()[0]
                for child_frame in scrollable_frame.winfo_children():
                    if isinstance(child_frame, tk.Frame):
                        for subwidget in child_frame.winfo_children():
                            if isinstance(subwidget, tk.Label) and hasattr(subwidget, 'image_path') and subwidget.image_path == file_path:
                                child_frame.destroy()
                                self.processed_images.discard(file_path)
                                self.image_status.pop(file_path, None)
                                self.print(f"Successfully deleted {file_path} from canvas")
                                return
        self.print(f"Could not find {file_path} in canvas")

    def open_file(self, file_path):
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":
            subprocess.call(["open", file_path])
        else:
            subprocess.call(["xdg-open", file_path])

    def open_containing_folder(self, file_path):
        if sys.platform == "win32":
            subprocess.run(["explorer", "/select,", os.path.normpath(file_path)])
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", file_path])
        else:
            subprocess.run(["xdg-open", os.path.dirname(file_path)])
    
    def show_properties(self, file_path):
        if sys.platform == "win32":
            try:
                shell.ShellExecuteEx(lpVerb="properties", lpFile=file_path, lpParameters="", nShow=1)
            except Exception as e:
                self.print(f"Error showing properties: {e}")
                self.show_properties_dialog(file_path, self.get_file_properties(file_path))
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e", f'tell application "Finder" to open information window of (POSIX file "{file_path}")'])
        else:
            properties = self.get_file_properties(file_path)
            self.show_properties_dialog(file_path, properties)
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
    def is_duplicate(self, file_path):
        if file_path in self.processed_images:
            return True
        for _, _, _, path in self.image_queue.queue:
            if path == file_path:
                return True
        return False

    def get_file_properties(self, file_path):
        properties = {}
        properties["File Name"] = os.path.basename(file_path)
        properties["File Size"] = f"{os.path.getsize(file_path) / 1024:.2f} KB"
        properties["Last Modified"] = time.ctime(os.path.getmtime(file_path))

        return properties

    def show_properties_dialog(self, file_path, properties):
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Properties: {os.path.basename(file_path)}")
        for key, value in properties.items():
            tk.Label(dialog, text=f"{key}:").grid(sticky="w", padx=5, pady=2)
            tk.Label(dialog, text=value).grid(column=1, sticky="w", padx=5, pady=2)
        tk.Button(dialog, text="Close", command=dialog.destroy).grid(columnspan=2, pady=10)



    def show_hover_info(self, event, img_label, file_path):
        title, tags = self.get_image_metadata(file_path)
        hover_window = tk.Toplevel(self.root)
        hover_window.overrideredirect(True)
        hover_window.attributes("-topmost", True)
        hover_window.attributes("-alpha", 0.9)

        info_label = tk.Label(hover_window, text=f"Title: {title}\nTags: {tags}",
                              bg="yellow", justify="left", padx=5, pady=5)
        info_label.pack()

        def update_position(e):
            hover_window.geometry(f"+{e.x_root+10}+{e.y_root+10}")

        def on_leave(e):
            hover_window.destroy()

        img_label.bind("<Motion>", update_position)
        img_label.bind("<Leave>", on_leave)
        hover_window.bind("<Leave>", on_leave)

        update_position(event)

    def get_image_metadata(self, file_path):
        title = "N/A"
        tags = "N/A"

        try:
            with Image.open(file_path) as img:
                if file_path.lower().endswith(('.jpg', '.jpeg')):
                    exif_data = img._getexif()
                    if exif_data:
                        if 270 in exif_data:
                            title = exif_data[270]
                        if 37510 in exif_data:
                            tags = exif_data[37510]
                            if isinstance(tags, bytes):
                                tags = tags.decode('utf-8', errors='ignore').replace("UNICODE\x00", "")
                elif file_path.lower().endswith(('.png', '.webp')):
                    if 'Description' in img.info:
                        title = img.info['Description']
                    if 'Keywords' in img.info:
                        tags = img.info['Keywords']
        except Exception as e:
            self.print(f"Error reading metadata: {e}")

        return str(title), str(tags)

    def create_settings_menu(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Extra Settings")
        settings_window.geometry("800x800")
        settings_window.grab_set()

        categories = [
            ("Harassment", HarmCategory.HARM_CATEGORY_HARASSMENT),
            ("Hate Speech", HarmCategory.HARM_CATEGORY_HATE_SPEECH),
            ("Sexually Explicit", HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT),
            ("Dangerous Content", HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT),
        ]

        thresholds = [
            ("Block none", HarmBlockThreshold.BLOCK_NONE),
            ("Block few", HarmBlockThreshold.BLOCK_ONLY_HIGH),
            ("Block some", HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
            ("Block most", HarmBlockThreshold.BLOCK_LOW_AND_ABOVE),
        ]

        self.safety_vars = {}
        self.safety_labels = {}

        frame = tk.Frame(settings_window)
        frame.pack(fill="both", expand=True)

        for i, (category_name, category) in enumerate(categories):
            tk.Label(frame, text=category_name, font=("Arial", 10, "bold")).grid(row=i, column=0, padx=5, pady=2, sticky="w")
            var = tk.StringVar(value=next(setting['threshold'].name for setting in self.safety_settings if setting['category'] == category))
            self.safety_vars[category] = var
            self.safety_labels[category] = {}  # Initialize the dictionary
            for j, (threshold_name, threshold) in enumerate(thresholds):
                rb = tk.Radiobutton(frame, text=threshold_name, variable=var, value=threshold.name,
                                    command=lambda c=category, t=threshold: self.update_safety_setting(c, t))
                rb.grid(row=i, column=j+1, padx=2, pady=2, sticky="w")
                self.safety_labels[category][threshold] = rb  # Store the radio button


        self.caption_var = tk.BooleanVar(value=True)
        self.tags_var = tk.BooleanVar(value=True)

        tk.Label(frame, text="Query Options:", font=("Arial", 10, "bold")).grid(row=len(categories), column=0, padx=5, pady=5, sticky="w")
        tk.Checkbutton(frame, text="Generate Captions", variable=self.caption_var, command=self.update_query_options).grid(row=len(categories), column=1, padx=5, pady=5, sticky="w")
        tk.Checkbutton(frame, text="Generate Tags", variable=self.tags_var, command=self.update_query_options).grid(row=len(categories), column=2, padx=5, pady=5, sticky="w")

        self.save_txt_var = tk.BooleanVar(value=self.save_txt_var.get())
        tk.Checkbutton(frame, text="Save as TXT", variable=self.save_txt_var).grid(row=len(categories)+1, column=0, padx=5, pady=5, sticky="w")


        tk.Label(frame, text="Additional Caption Text:", font=("Arial", 10, "bold")).grid(row=len(categories)+2, column=0, padx=5, pady=5, sticky="w")
        self.additional_caption_text = tk.Text(frame, height=3, width=50)
        self.additional_caption_text.grid(row=len(categories)+3, column=0, columnspan=4, padx=5, pady=5, sticky="w")
        self.additional_caption_text.insert(tk.END, self.additional_caption)

        tk.Label(frame, text="Additional Tags Text:", font=("Arial", 10, "bold")).grid(row=len(categories)+4, column=0, padx=5, pady=5, sticky="w")
        self.additional_tags_text = tk.Text(frame, height=3, width=50)
        self.additional_tags_text.grid(row=len(categories)+5, column=0, columnspan=4, padx=5, pady=5, sticky="w")
        self.additional_tags_text.insert(tk.END, self.additional_tags)

        
        log_checkbox = tk.Checkbutton(frame, text="Log to File", variable=self.log_to_file_var,
                                command=self.toggle_logging)
        log_checkbox.grid(row=len(categories) + 1, column=1, padx=5, pady=5, sticky="w")
        
        tk.Label(frame, text="Caption Query:", font=("Arial", 10, "bold")).grid(row=len(categories)+6, column=0, padx=5, pady=5, sticky="w")
        caption_frame = tk.Frame(frame)
        caption_frame.grid(row=len(categories)+7, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")
        caption_text = tk.Text(caption_frame, height=5, wrap=tk.WORD)
        caption_text.pack(side="left", fill="both", expand=True)
        caption_scrollbar = tk.Scrollbar(caption_frame, command=caption_text.yview)
        caption_scrollbar.pack(side="right", fill="y")
        caption_text.config(yscrollcommand=caption_scrollbar.set)
        caption_text.insert(tk.END, self.caption_query.get())
        tk.Button(frame, text="Default Caption", command=lambda: self.set_default_caption(caption_text)).grid(row=len(categories)+7, column=4, padx=5, pady=5)

        tk.Label(frame, text="Tags Query:", font=("Arial", 10, "bold")).grid(row=len(categories)+8, column=0, padx=5, pady=5, sticky="w")
        tags_frame = tk.Frame(frame)
        tags_frame.grid(row=len(categories)+9, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")
        tags_text = tk.Text(tags_frame, height=5, wrap=tk.WORD)
        tags_text.pack(side="left", fill="both", expand=True)
        tags_scrollbar = tk.Scrollbar(tags_frame, command=tags_text.yview)
        tags_scrollbar.pack(side="right", fill="y")
        tags_text.config(yscrollcommand=tags_scrollbar.set)
        tags_text.insert(tk.END, self.tags_query.get())
        tk.Button(frame, text="Default Tags", command=lambda: self.set_default_tags(tags_text)).grid(row=len(categories)+9, column=4, padx=5, pady=5)

        timeout_frame = tk.Frame(frame)
        timeout_frame.grid(row=len(categories)+10, column=0, columnspan=4, padx=5, pady=5, sticky="w")
        tk.Label(timeout_frame, text="Response Timeout:").pack(side="left")
        timeout_slider = tk.Scale(timeout_frame, from_=30, to=300, orient="horizontal", length=200,
                                  variable=self.response_timeout, resolution=1, label="seconds")
        timeout_slider.pack(side="left", padx=5)

        tk.Button(frame, text="Close", command=lambda: self.close_settings(settings_window, caption_text, tags_text)).grid(row=len(categories)+11, column=0, columnspan=5, pady=10)

        frame.grid_rowconfigure(len(categories)+7, weight=1)
        frame.grid_rowconfigure(len(categories)+9, weight=1)
        frame.grid_columnconfigure(0, weight=1)

    def update_query_options(self):
        if not self.caption_var.get() and not self.tags_var.get():
            self.caption_var.set(True)



    def save_txt_file(self, file_path, caption, tags):
        if self.save_txt_var.get():
            txt_path = os.path.splitext(file_path)[0] + ".txt"
            with open(txt_path, "w", encoding="utf-8") as txt_file:
                txt_file.write(f"Caption: {caption}\n\nTags: {tags}")

    def set_default_caption(self, caption_text):
        default_caption = "Write a long accurate caption describing the image strictly in English and use explicit words only if accurate.Focus on the most prominent objects, actions, and scenes.If famous people are identified in the image, always include their names."
        caption_text.delete("1.0", tk.END)
        caption_text.insert(tk.END, default_caption)

    def set_default_tags(self, tags_text):
        default_tags = "Generate exactly {num_hashtags} strictly English keywords describing people, objects, clothes, actions, or scenes in the image using underscore between multi word hashtags and first and last names and use explicit words only if accurate, give them in a line not a list , no numbers, no remarks by you like ,here is the hashtags, or anything like that."
        tags_text.delete("1.0", tk.END)
        tags_text.insert(tk.END, default_tags)

    def close_settings(self, settings_window, caption_text, tags_text):
        self.caption_query.set(caption_text.get("1.0", tk.END).strip())
        self.tags_query.set(tags_text.get("1.0", tk.END).strip())
        self.additional_caption = self.additional_caption_text.get("1.0", tk.END).strip()
        self.additional_tags = self.additional_tags_text.get("1.0", tk.END).strip()
        self.save_settings()
        settings_window.destroy()

    def update_safety_setting(self, category, threshold):
        for setting in self.safety_settings:
            if setting['category'] == category:
                setting['threshold'] = threshold
                break

        category_name = category.name.replace("HARM_CATEGORY_", "").replace("_", " ").title()
        threshold_name = threshold.name.replace("BLOCK_", "").replace("_AND_ABOVE", "").replace("_", " ").title()
        self.print(f"{category_name} changed to {threshold_name}")

        self.save_settings()

        # This part is now correct, using the stored radio buttons
        for t, label in self.safety_labels[category].items():
            if t == threshold:
                label.config(bg="light blue")
            else:
                label.config(bg="SystemButtonFace")  # Use SystemButtonFace for consistency

    def print_safety_settings(self):
        self.print("Current Safety Settings:")
        for setting in self.safety_settings:
            self.print(f"{setting['category']}: {setting['threshold']}")
            
            
            
            
            
            
            
            
            
            
            
            
            
            









    def create_widgets(self):
        self.api_key = tk.StringVar()

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)



        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(top_frame, text="Enter your API Key:").grid(row=0, column=0, padx=5, pady=5)
        tk.Entry(top_frame, textvariable=self.api_key).grid(row=0, column=1, padx=5, pady=5)


        tk.Button(top_frame, text="Save API Key", command=self.add_api_key).grid(row=0, column=2, padx=5, pady=5)
        tk.Button(top_frame, text="Manage API Keys", command=self.manage_api_keys).grid(row=0, column=3, padx=5, pady=5)

        tk.Label(top_frame, text="Delay (seconds):").grid(row=1, column=0, padx=5, pady=5)
        tk.Entry(top_frame, textvariable=self.delay_seconds).grid(row=1, column=1, padx=5, pady=5)
        tk.Label(top_frame, text="Retry Count:").grid(row=1, column=2, padx=5, pady=5)
        tk.Entry(top_frame, textvariable=self.retry_count).grid(row=1, column=3, padx=5, pady=5)

        tk.Label(top_frame, text="Select Model:").grid(row=0, column=4, padx=5, pady=5)

        self.model_options = self.fetch_available_models()  # Fetch models
        if not self.model_options:
            self.model_options = ["gemini-1.5-pro-002"]  # Default if fetching fails

        self.selected_model.set(self.model_options[0] if self.model_options else "gemini-1.5-pro-002") #set the default model
        self.model_dropdown = tk.OptionMenu(top_frame, self.selected_model, *self.model_options, command=self.on_model_change)
        self.model_dropdown.grid(row=0, column=5, padx=5, pady=5)

        # Add a refresh button (optional, but recommended)
        refresh_button = tk.Button(top_frame, text="Refresh Models", command=self.refresh_models)
        refresh_button.grid(row=0, column=6, padx=5, pady=5) #adjust column if needed

        # Add Model Info Display
        tk.Label(top_frame, text="Model Information:").grid(row=1, column=4, padx=5, pady=5)
        self.model_info_text = tk.Text(top_frame, height=10, width=40, wrap=tk.WORD)  # Adjust size as needed
        self.model_info_text.grid(row=1, column=5, columnspan=2, padx=5, pady=5)  # Span across columns
        self.model_info_text.config(state=tk.DISABLED)  # Make it read-only

        tk.Button(top_frame, text="Extra Settings", command=self.create_settings_menu).grid(row=2, column=4, padx=5, pady=5)

        tk.Button(top_frame, text="Upload Images", command=self.upload_images).grid(row=3, column=0, padx=5, pady=5)
        tk.Button(top_frame, text="Add Photos", command=self.add_photos).grid(row=3, column=1, padx=5, pady=5)
        tk.Button(top_frame, text="Stop", command=self.stop_processing_images).grid(row=3, column=2, padx=5, pady=5)
        tk.Label(top_frame, text="Number of Tags:").grid(row=3, column=3, padx=5, pady=5)
        tk.Entry(top_frame, textvariable=self.num_hashtags).grid(row=3, column=4, padx=5, pady=5)

        clear_button = tk.Button(top_frame, text="Clear Tagged Images", command=self.clear_tagged_images)
        clear_button.grid(row=3, column=5, padx=5, pady=5)

        middle_frame = tk.Frame(main_frame)
        middle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Console Frame (Pack BEFORE image frame) ---
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)  # Use expand=True
        bottom_frame.pack_propagate(False)  # Prevent resizing based on content
        bottom_frame.config(height=200)  # Set a fixed height (adjust as needed)

        self.console_text = tk.Text(bottom_frame, height=10)
        self.console_text.pack(fill=tk.BOTH, expand=True)



        self.image_frame = tk.Frame(middle_frame)
        self.image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        queue_frame = tk.Frame(middle_frame, width=200)
        queue_frame.pack(side=tk.RIGHT, fill=tk.Y)
        queue_frame.pack_propagate(False)

        tk.Label(queue_frame, text="Image Queue", font=("Arial", 12, "bold")).pack(pady=5)

        self.queue_canvas = tk.Canvas(queue_frame)
        queue_scrollbar = tk.Scrollbar(queue_frame, orient="vertical", command=self.queue_canvas.yview)
        self.scrollable_queue_frame = tk.Frame(self.queue_canvas)

        self.scrollable_queue_frame.bind(
            "<Configure>",
            lambda e: self.queue_canvas.configure(
                scrollregion=self.queue_canvas.bbox("all")
            )
        )

        self.queue_canvas.create_window((0, 0), window=self.scrollable_queue_frame, anchor="nw")
        self.queue_canvas.configure(yscrollcommand=queue_scrollbar.set)

        self.queue_canvas.pack(side="left", fill="both", expand=True)
        queue_scrollbar.pack(side="right", fill="y")

        # --- Remove bottom_frame (no longer needed) ---


        self.console_queue = queue.Queue()
        self.root.after(100, self.update_console)

        self.bind_mousewheel(self.queue_canvas)
        self.bind_mousewheel(self.console_text)
        self.bind_mousewheel(self.model_info_text)

        self.setup_support_button()

        self.selected_model.trace("w", lambda *args: self.save_settings())


        # --- Limit Window Size ---
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.minsize(800, 600)  # Set a reasonable minimum size
        self.root.maxsize(screen_width, screen_height)  # Limit to screen size


    def refresh_models(self):
        if not self.api_keys:
            self.print("No API keys configured. Cannot refresh models.")
            return

        if self.current_api_key_index is not None:
            try:
                # Use genai.configure
                genai.configure(api_key=self.api_keys[self.current_api_key_index])
                self.print("API key configured for refresh.")
            except Exception as e:
                self.print(f"API Key configuration failed during refresh: {e}")
                return

        new_models = self.fetch_available_models()
        if new_models:
            self.model_options = new_models
            self.selected_model.set(self.model_options[0])

            self.model_dropdown['menu'].delete(0, 'end')
            for model in self.model_options:
                self.model_dropdown['menu'].add_command(label=model, command=tk._setit(self.selected_model, model, self.on_model_change))

            self.print("Model list refreshed.")
        else:
            self.print("Failed to refresh model list.")

    def on_model_change(self, *args):
        self.save_settings()
        selected_model_name = self.selected_model.get()
        model_info = self.get_model_info(selected_model_name) #get model info in string format

        # Clear existing text and insert the new info
        self.model_info_text.config(state=tk.NORMAL)  # Temporarily enable editing
        self.model_info_text.delete("1.0", tk.END)
        self.model_info_text.insert(tk.END, model_info)  # Insert the string
        self.model_info_text.config(state=tk.DISABLED)  # Disable editing again

    def add_api_key(self):
        new_key = self.api_key.get().strip()
        if new_key:  # Only proceed if the key isn't empty
            if new_key not in self.api_keys:
                self.api_keys.append(new_key)
                self.current_api_key_index = len(self.api_keys) - 1  # Set to the newly added key
                self.save_settings()
                messagebox.showinfo("Info", "API Key added successfully and set as current")
                # Configure the API immediately after adding
                try:
                    genai.configure(api_key=self.api_keys[self.current_api_key_index])
                    self.print("API key configured after adding.")
                    self.refresh_models() #refresh the models after adding
                except Exception as e:
                    self.print(f"API Key configuration failed after adding: {e}")

            else:
                messagebox.showinfo("Info", "API Key already exists.")
            self.api_key.set("")  # Clear the input field
        else:
            messagebox.showwarning("Warning", "Please enter an API key.")

    def manage_api_keys(self):
        manage_window = tk.Toplevel(self.root)
        manage_window.title("Manage API Keys")
        manage_window.grab_set()

        listbox = tk.Listbox(manage_window)
        listbox.pack(fill=tk.BOTH, expand=True)
        for key in self.api_keys:
            listbox.insert(tk.END, key)

        def delete_key():
            selected = listbox.curselection()
            if selected:
                index_to_delete = selected[0]
                self.api_keys.pop(index_to_delete)
                listbox.delete(selected)
                # Adjust current_api_key_index if necessary
                if self.current_api_key_index >= index_to_delete:
                    self.current_api_key_index = max(0, self.current_api_key_index -1)
                if not self.api_keys:
                    self.current_api_key_index = None

                self.save_settings()


        def set_current_key():
            selected = listbox.curselection()
            if selected:
                self.current_api_key_index = selected[0]
                current_key = self.api_keys[self.current_api_key_index]
                messagebox.showinfo("Info", f"Current API key set to: {current_key}")
                # Configure genai with the new current key
                try:
                    genai.configure(api_key=current_key)
                    self.print("API key configured after setting as current.")
                except Exception as e:
                    self.print(f"Failed to configure API key: {e}")
                # self.api_key.set("") #dont set the entry to the key
                manage_window.destroy()
                self.refresh_models()

        manage_window.geometry("800x400")
        tk.Button(manage_window, text="Delete Selected", command=delete_key).pack(pady=5)
        tk.Button(manage_window, text="Set as Current", command=set_current_key).pack(pady=5)

    def clear_tagged_images(self):
        self.print("Starting to clear tagged images...")
        widgets_to_remove = []

        for canvas_widget in self.image_frame.winfo_children():
            if isinstance(canvas_widget, tk.Canvas):
                scrollable_frame = canvas_widget.winfo_children()[0]

                for child_frame in scrollable_frame.winfo_children():
                    if isinstance(child_frame, tk.Frame):
                        image_frame = None
                        for widget in child_frame.winfo_children():
                            if isinstance(widget, tk.Frame):
                                image_frame = widget
                                break

                        if image_frame and image_frame.cget('bg') == 'green':
                            widgets_to_remove.append(child_frame)
                            for widget in child_frame.winfo_children():
                                if isinstance(widget, tk.Label) and hasattr(widget, 'image_path'):
                                    self.processed_images.discard(widget.image_path)
                                    break

        self.print(f"Number of widgets marked for removal: {len(widgets_to_remove)}")

        for widget in widgets_to_remove:
            widget.destroy()

        self.print("Finished clearing tagged images")
        self.image_frame.update()



    def update_console(self):
        try:
            while True:
                line = self.console_queue.get_nowait()
                self.console_text.insert(tk.END, line + '\n')
                self.console_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.update_console)

    def print(self, *args, **kwargs):
        message = " ".join(map(str, args))
        self.console_queue.put(message)
        if self.log_to_file_var.get() and self.log_file:
            try:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                self.log_file.write(f"[{timestamp}] {message}\n")
                self.log_file.flush()  # Ensure it's written immediately
            except Exception as e:
               self.console_queue.put(f"Error writing to log file: {e}")

    def configure_canvas(self):
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        canvas_width = int(window_width * 0.9)
        canvas_height = int(window_height * 0.8)

        return canvas_width, canvas_height
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
    def upload_images(self):
        self.resume_processing()
        files = filedialog.askopenfilenames(filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp")])
        if not files:
            self.print("No files selected")
            return

        if not self.api_keys:
            self.print("Error: No API keys available. Please add an API key.")
            return

        self.stop_processing = True

        for widget in self.image_frame.winfo_children():
            widget.destroy()

        while not self.image_queue.empty():
            self.image_queue.get()
        self.processed_images.clear()

        self.stop_processing = False

        if self.current_api_key_index is None:
            self.print("Error: No current API key selected. Please add or select an API key.")
            return
        #use genai.configure
        try:
            self.print("Configuring API with current key")
            current_key = self.api_keys[self.current_api_key_index]
            genai.configure(api_key=current_key)  # configure the api
        except Exception as e:
            self.print(f"Failed to configure API: {e}")
            traceback.print_exc()
            return


        canvas_width, canvas_height = self.configure_canvas()
        canvas = tk.Canvas(self.image_frame, width=canvas_width, height=canvas_height)
        scrollbar = tk.Scrollbar(self.image_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.bind_mousewheel(canvas)

        self.image_status.clear()
        for file in files:
            # Pass model name, not the client object
            self.image_queue.put((file, self.selected_model.get(), scrollable_frame, canvas_width, None, None, None, None))
            self.image_status[file] = -1
            self.processed_images.add(file)


        if not any(t.name == "ImageProcessingThread" for t in threading.enumerate()):
            threading.Thread(target=lambda: asyncio.run(self.process_image_queue()), daemon=True, name="ImageProcessingThread").start()
        self.bind_mousewheel(canvas)
        self.update_queue_display()

    def add_photos(self):
        self.resume_processing()
        files = filedialog.askopenfilenames(filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp")])
        if not files:
            self.print("No files selected")
            return

        if not self.api_keys:
            self.print("Error: No API keys available. Please add an API key.")
            return

        if self.current_api_key_index is None:
            self.print("Error: No current API key selected. Please add or select an API key.")
            return

        try:
            self.print("Configuring API with current key")
            current_key = self.api_keys[self.current_api_key_index]
            genai.configure(api_key=current_key)  # Configure API
        except Exception as e:
            self.print(f"Failed to configure API: {e}")
            traceback.print_exc()
            return

        canvas = None
        scrollable_frame = None
        canvas_width = 0

        for widget in self.image_frame.winfo_children():
            if isinstance(widget, tk.Canvas):
                canvas = widget
                scrollable_frame = canvas.winfo_children()[0]
                canvas_width = canvas.winfo_width()
                break

        if not canvas or not scrollable_frame:
            canvas_width, canvas_height = self.configure_canvas()
            canvas = tk.Canvas(self.image_frame, width=canvas_width, height=canvas_height)
            scrollbar = tk.Scrollbar(self.image_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox("all")
                )
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            self.bind_mousewheel(canvas)

        new_files = [file for file in files if file not in self.processed_images and not self.is_in_queue(file)]
        self.print(f"Adding {len(new_files)} new images to the queue")

        for file in new_files:
            # Pass model name, not a client object.
            self.image_queue.put((file, self.selected_model.get(), scrollable_frame, canvas_width, None, None, None, None))
            self.image_status[file] = -1
            self.processed_images.add(file)

        active_threads = sum(1 for t in threading.enumerate() if t.name == "ImageProcessingThread")
        new_threads = min(self.max_threads - active_threads, len(new_files))
        self.print(f"Starting {new_threads} new processing threads")
        for _ in range(new_threads):
            threading.Thread(target=lambda: asyncio.run(self.process_image_queue()), daemon=True, name="ImageProcessingThread").start()

        self.root.after(0, self.update_queue_display)

    def is_in_queue(self, file):
        return any(item[0] == file for item in self.image_queue.queue)

    def stop_processing_images(self):
        self.paused = True
        while not self.image_queue.empty():
            try:
                self.image_queue.get_nowait()  # Use get_nowait to avoid blocking
                self.image_queue.task_done()
            except queue.Empty:
                pass  # Queue is already empty
        self.clear_queue_display()


    async def process_image(self, file, model_name, scrollable_frame, canvas_width, retry_count=None, existing_frame=None, existing_caption_label=None, existing_tags_label=None):
        if retry_count is None:
            retry_count = self.retry_count.get()

        try:
            self.print(f"Processing file: {file}")

            if not scrollable_frame or not scrollable_frame.winfo_exists():
                self.print(f"Scrollable frame no longer exists. Skipping {file}")
                return

            img = Image.open(file)
            img.thumbnail((200, 200))
            img_tk = ImageTk.PhotoImage(img)

            if existing_frame and existing_frame.winfo_exists():
                image_info_frame = existing_frame
                image_frame = image_info_frame.winfo_children()[0] if image_info_frame.winfo_children() else None
                img_label = image_frame.winfo_children()[0] if image_frame and image_frame.winfo_children() else None
                text_frame = image_info_frame.winfo_children()[1] if len(image_info_frame.winfo_children()) > 1 else None
                caption_label = existing_caption_label if existing_caption_label else (text_frame.winfo_children()[0] if text_frame and text_frame.winfo_children() else None)
                tags_label = existing_tags_label if existing_tags_label else (text_frame.winfo_children()[1] if text_frame and len(text_frame.winfo_children()) > 1 else None)
            else:
                image_info_frame = tk.Frame(scrollable_frame)
                image_info_frame.pack(pady=10, padx=10, fill="x", expand=True)
                image_info_frame.image_id = file
                image_frame = tk.Frame(image_info_frame)
                image_frame.pack(side="left", padx=10)

                img_label = tk.Label(image_frame, image=img_tk)
                img_label.image = img_tk
                img_label.image_path = file
                img_label.pack()

                img_label.bind("<Button-3>", lambda event, path=file: self.create_context_menu(event, path))
                img_label.bind("<Enter>", lambda event, label=img_label, path=file: self.show_hover_info(event, label, path))

                image_name_label = tk.Label(image_info_frame, text=os.path.basename(file))
                image_name_label.pack(side="bottom", pady=5, padx=10)

                text_frame = tk.Frame(image_info_frame)
                text_frame.pack(side="left", fill="x", expand=True)

                caption_label = tk.Label(text_frame, text="Loading caption...", wraplength=canvas_width-250, justify="left")
                caption_label.pack(anchor="w")

                tags_label = tk.Label(text_frame, text="Loading tags...", wraplength=canvas_width-250, justify="left")
                tags_label.pack(anchor="w")

                retry_frame = tk.Frame(text_frame)
                retry_frame.pack(anchor="w", pady=5)

                retry_count_label = tk.Label(retry_frame, text="Retry count:")
                retry_count_label.pack(side="left")

                retry_count_entry = tk.Entry(retry_frame, width=5)
                retry_count_entry.insert(tk.END, str(self.retry_count.get()))
                retry_count_entry.pack(side="left", padx=5)

                retry_button = tk.Button(retry_frame, text="Retry", command=lambda: self.retry_image_processing(file, model_name, img_label, caption_label, tags_label, retry_count_entry))
                retry_button.pack(side="left")

                copy_button = tk.Button(text_frame, text="Copy", command=lambda: self.copy_to_clipboard(caption_label, tags_label))
                copy_button.pack(anchor="w", pady=5)

            self.root.update()
            # Pass model name.  Create the model object here.
            model = genai.GenerativeModel(model_name=model_name)
            await self.process_and_embed_metadata(file, img, model, caption_label, tags_label, image_frame, retry_count=retry_count, image_info_frame=image_info_frame)

        except Exception as e:
            self.print(f"Failed to process image {file} due to {e}")
            traceback.print_exc()
            self.image_status[file] = 0
            self.root.after(0, lambda: self.update_highlight(file, image_frame, image_info_frame=image_info_frame))
        finally:
            self.thread_semaphore.release()
            await asyncio.sleep(self.delay_seconds.get())

    def switch_api_key(self):
        if not self.api_keys:
            self.print("No API keys available.")
            return None

        initial_index = self.current_api_key_index
        for _ in range(len(self.api_keys)):
            self.current_api_key_index = (self.current_api_key_index + 1) % len(self.api_keys)
            try:
                current_key = self.api_keys[self.current_api_key_index]
                # Use genai.configure
                genai.configure(api_key=current_key)
                self.print(f"Switched to API key index: {self.current_api_key_index}")
                return "switched" #we dont need to return model
            except Exception as e:
                self.print(f"Error with API key at index {self.current_api_key_index}: {str(e)}")

            if self.current_api_key_index == initial_index:
                break

        self.print("All APIs are exhausted.")
        self.stop_processing_images()
        messagebox.showerror("Error", "All API keys are exhausted.  Processing stopped.")
        return None

    def update_highlight(self, file, image_frame, image_info_frame=None):
        if not image_frame.winfo_exists():
            self.print(f"Image frame for {file} no longer exists. Skipping highlight update.")
            return

        status = self.image_status.get(file, -1)
        self.print(f"Updating highlight for {file}, status: {status}")

        color = "SystemButtonFace"

        if status == 1:
            color = "green"
        elif status == 0:
            color = "red"

        try:
            image_frame.config(bg=color)

            for child in image_frame.winfo_children():
                if child.winfo_exists():
                    child.config(bg=color)
        except tk.TclError as e:
            self.print(f"Error updating highlight for {file}: {e}")



    async def process_and_embed_metadata(self, file, img, model, caption_label, tags_label, image_frame, retry_count=None, image_info_frame=None):
        if retry_count is None:
            retry_count = self.retry_count.get()

        attempt = 0  # Initialize attempt counter
        while attempt < retry_count:
            try:
                self.print(f"Generating caption and tags (Attempt {attempt + 1}/{retry_count})")
                self.print(f"Using model: {self.selected_model.get()} and API key index {self.current_api_key_index}")

                formatted_caption = ""
                formatted_tags = ""

                if self.caption_var.get():
                    # Use model.generate_content
                    caption_response = await asyncio.to_thread(model.generate_content, contents=[self.caption_query.get(), img], safety_settings=self.safety_settings)
                    formatted_caption = caption_response.text
                    formatted_caption += " " + self.additional_caption

                if self.tags_var.get():
                    num_hashtags = self.num_hashtags.get()
                    tags_query = self.tags_query.get().replace("{num_hashtags}", str(num_hashtags))
                    # Use model.generate_content
                    tags_response =  await asyncio.to_thread(model.generate_content, contents=[tags_query, img], safety_settings=self.safety_settings)
                    tag_list = [tag.strip() for tag in tags_response.text.split() if tag.strip()]
                    tag_list = [tag[1:] if tag.startswith('#') else tag for tag in tag_list][:num_hashtags]
                    formatted_tags = " ".join(tag_list)
                    formatted_tags += " " + self.additional_tags

                def update_labels():
                    if caption_label and caption_label.winfo_exists():
                        caption_label.config(text=f"Caption: {formatted_caption}")
                    if tags_label and tags_label.winfo_exists():
                        tags_label.config(text=f"Tags: {formatted_tags}")
                self.root.after(0, update_labels)

                if self.save_txt_var.get():
                    self.save_txt_file(file, formatted_caption, formatted_tags)

                self.embed_metadata(file, formatted_caption, formatted_tags)
                self.image_status[file] = 1
                self.root.after(0, lambda: self.update_highlight(file, image_frame))
                return  # Success! Exit the function

            except Exception as e:
                self.print(f"Attempt {attempt + 1} failed: {str(e)[:100]}...")
                # Check for rate limit errors (429 or specific message)
                if "429" in str(e) or "Resource has been exhausted" in str(e) or "quota" in str(e).lower():
                    self.print("Rate limit error detected. Switching API key...")
                    if self.switch_api_key() is None:
                        #update labels with error
                        def update_error_labels():
                            if caption_label and caption_label.winfo_exists():
                                caption_label.config(text=f"Caption: Failed to generate. All API Keys Exhausted")
                            if tags_label and tags_label.winfo_exists():
                                tags_label.config(text=f"Tags: Failed to generate. All API Keys Exhausted")
                        self.root.after(0, update_error_labels)
                        self.image_status[file] = 0
                        self.root.after(0, lambda: self.update_highlight(file, image_frame, image_info_frame=image_info_frame))

                        return

                else: #it is an exception not related to rate limit
                    attempt += 1 #increment attempts only for non-rate-limit errors
                    if attempt >= retry_count:
                        self.print(f"Failed to process image {file} after {retry_count} attempts")
                        # Update labels with the error
                        def update_error_labels():
                            if caption_label and caption_label.winfo_exists():
                                caption_label.config(text=f"Caption: Failed to generate after {retry_count} attempts")
                            if tags_label and tags_label.winfo_exists():
                                tags_label.config(text=f"Tags: Failed to generate after {retry_count} attempts")
                        self.root.after(0, update_error_labels)
                        self.image_status[file] = 0
                        self.root.after(0, lambda: self.update_highlight(file, image_frame, image_info_frame=image_info_frame))
                        return  # Stop retrying this image

            await asyncio.sleep(self.delay_seconds.get())

    async def process_image_queue(self):
        while not self.stop_processing:
            if self.paused:
                await asyncio.sleep(1)
                continue
            try:
                if not self.image_queue.empty():
                    # Get model name instead of client
                    file, model_name, scrollable_frame, canvas_width, retry_count, existing_frame, existing_caption_label, existing_tags_label = self.image_queue.get(block=False)
                    self.thread_semaphore.acquire()
                    try:
                        # Pass model_name
                        await self.process_image(file, model_name, scrollable_frame, canvas_width, retry_count=retry_count, existing_frame=existing_frame, existing_caption_label=existing_caption_label, existing_tags_label=existing_tags_label)
                    finally:
                        self.thread_semaphore.release()
                        self.image_queue.task_done()
                        self.root.after(0, self.update_queue_display)
                else:
                    await asyncio.sleep(0.1)
            except queue.Empty:
                pass
            except Exception as e:
                self.print(f"Error in process_image_queue: {str(e)}")
                await asyncio.sleep(1)

    def resume_processing(self):
        self.paused = False
        self.stop_processing = False
        if not any(t.name == "ImageProcessingThread" for t in threading.enumerate()):
            threading.Thread(target=lambda: asyncio.run(self.process_image_queue()), daemon=True, name="ImageProcessingThread").start()
            self.print("Started new processing thread")
        else:
            self.print("Processing thread already running")

    def find_scrollable_frame(self):
        for widget in self.image_frame.winfo_children():
            if isinstance(widget, tk.Canvas):
                return widget.winfo_children()[0]
        return None

    def is_in_queue(self, file):
        return any(item[0] == file for item in self.image_queue.queue)

    def retry_image_processing(self, file, model_name, img_label, caption_label, tags_label, retry_count_entry):
        self.resume_processing()
        try:
            if not all(widget.winfo_exists() for widget in [img_label, caption_label, tags_label, retry_count_entry]):
                raise ValueError("Some widgets no longer exist")

            retry_count = int(retry_count_entry.get())
            image_frame = img_label.master
            image_info_frame = image_frame.master

            self.image_status[file] = -1

            if caption_label.winfo_exists():
                caption_label.config(text="Loading caption...")
            if tags_label.winfo_exists():
                tags_label.config(text="Loading tags...")

            self.update_highlight(file, image_frame)

            new_queue = queue.Queue()
            while not self.image_queue.empty():
                item = self.image_queue.get()
                if item[0] != file:
                    new_queue.put(item)
            self.image_queue = new_queue

            scrollable_frame = self.find_scrollable_frame()
            canvas_width = self.image_frame.winfo_width()
            # Pass model name
            self.image_queue.put((file, model_name, scrollable_frame, canvas_width, retry_count, image_info_frame, caption_label, tags_label))
            self.update_queue_display()

            self.print(f"Image {file} added back to the queue for retry")
        except Exception as e:
            self.print(f"Error in retry_image_processing: {str(e)}")
            messagebox.showerror("Error", f"Failed to retry image processing: {str(e)}")

    def clear_queue_display(self):
        for widget in self.scrollable_queue_frame.winfo_children():
            widget.destroy()
        self.root.update_idletasks()

    def update_queue_display(self):
        for widget in self.scrollable_queue_frame.winfo_children():
            widget.destroy()

        queue_items = list(self.image_queue.queue)
        for i, item in enumerate(queue_items):
            file = item[0]
            frame = tk.Frame(self.scrollable_queue_frame)
            frame.pack(pady=5, padx=5, fill="x")

            img = Image.open(file)
            img.thumbnail((50, 50))
            img_tk = ImageTk.PhotoImage(img)

            label = tk.Label(frame, image=img_tk)
            label.image = img_tk
            label.pack(side="left")

            remove_btn = tk.Button(frame, text="X", command=lambda f=file: self.remove_from_queue(f))
            remove_btn.pack(side="right")

        self.root.update_idletasks()

    def remove_from_queue(self, file):
        new_queue = queue.Queue()
        while not self.image_queue.empty():
            item = self.image_queue.get()
            if item[0] != file:
                new_queue.put(item)
        self.image_queue = new_queue
        self.processed_images.discard(file)
        self.update_queue_display()

    def bind_mousewheel(self, widget):
        def _on_mousewheel(event):
            if sys.platform == "darwin":  # macOS scroll direction is inverted
                widget.yview_scroll(int(-1 * event.delta), "units")
            else:
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")

        widget.bind_all("<MouseWheel>", _on_mousewheel)

        # The following is not necessary and can cause unexpected behavior.  Removing.
        # def _unbind_mousewheel(e):
        #     widget.unbind_all("<MouseWheel>")
        # widget.bind("<Leave>", _unbind_mousewheel)
        # widget.bind("<Enter>", lambda e: widget.bind_all("<MouseWheel>", _on_mousewheel))
        # It's better to let the binding stay active all the time.

    def embed_metadata(self, file, caption, tags):
        try:
            self.print(f"Embedding metadata for file: {file}")
            self.print(f"Type of tags: {type(tags)}")
            self.print(f"Value of tags: {tags[:100] if isinstance(tags, (str, bytes)) else str(tags)[:100]}...")  # Print first 100 characters

            img = Image.open(file)

            if img.format == "JPEG":
                try:
                    exif_data = img.info.get("exif", None)
                    if exif_data:
                        exif_dict = piexif.load(exif_data)
                    else:
                        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
                except Exception as e:
                    self.print(f"Error loading EXIF data: {e}")
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

                exif_dict["0th"][piexif.ImageIFD.ImageDescription] = caption.encode('utf-8')

                if isinstance(tags, str):
                    tags_bytes = tags.encode('utf-8')
                elif isinstance(tags, bytes):
                    tags_bytes = tags
                else:
                    tags_bytes = str(tags).encode('utf-8')

                user_comment = b"UNICODE\x00" + tags_bytes  # Correct way to add UserComment
                exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment

                try:
                    exif_bytes = piexif.dump(exif_dict)
                    img.save(file, "jpeg", exif=exif_bytes)
                except ValueError as e:
                    self.print(f"Error dumping EXIF data: {e}")
                    # If piexif fails, still try to save (some EXIF data might be ok)
                    img.save(file, "jpeg")

                # Use exiv2 as a fallback (and for IPTC data, which piexif doesn't handle)
                try:
                    subprocess.run(["exiv2", "-M", f"set Iptc.Application2.Caption '{caption}'", file], check=True, capture_output=True, text=True, shell=True)
                    subprocess.run(["exiv2", "-M", f"add Iptc.Application2.Keywords '{tags}'", file], check=True, capture_output=True, text=True, shell=True)
                except subprocess.CalledProcessError as e:
                    self.print(f"Error with exiv2: {e.stderr}") # Print exiv2 errors


            elif img.format in ["PNG", "WEBP"]:
                metadata = PngImagePlugin.PngInfo()
                metadata.add_text("Description", caption)
                # Ensure tags are a string for PNG/WEBP
                metadata.add_text("Keywords", tags if isinstance(tags, str) else tags.decode('utf-8', errors='replace'))
                img.save(file, img.format.lower(), pnginfo=metadata)
            else:
                self.print(f"Unsupported image format for embedding metadata: {file}")
                messagebox.showerror("Error", f"Unsupported image format for embedding metadata: {file}")

            img.close()  # Close the image after processing
        except Exception as e:
            self.print(f"Failed to embed metadata in image {file} due to {e}")
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to embed metadata in image {file} due to {e}")

    def copy_to_clipboard(self, caption_label, tags_label):
        caption = caption_label.cget("text").replace("Caption: ", "")
        tags = tags_label.cget("text").replace("Tags: ", "")
        clipboard_content = f"{caption}\n{tags}"
        self.root.clipboard_clear()
        self.root.clipboard_append(clipboard_content)
        self.print("Copied to clipboard!")


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageCaptionApp(root)
    root.mainloop()
