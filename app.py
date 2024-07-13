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
import ctypes
import sys
import subprocess
import exif
import win32com.shell.shell as shell
import win32com.shell.shellcon as shellcon
import webbrowser

class ImageCaptionApp:
    def __init__(self, root):
        self.settings_file = "app_settings.enc"
        self.encryption_key = self.get_or_create_key()
        self.console_queue = queue.Queue()
        self.selected_model = tk.StringVar()
        self.retry_count = tk.IntVar(value=1)
        self.delay_seconds = tk.DoubleVar(value=1.0)
        self.num_hashtags = tk.IntVar(value=10)
        self.caption_query = tk.StringVar(value="Write a long accurate caption describing the image strictly in English and use explicit words only if accurate.Focus on the most prominent objects, actions, and scenes.If famous people are identified in the image, always include their names.")
        self.tags_query = tk.StringVar(value="Generate exactly {num_hashtags} strictly English keywords describing people, objects, clothes, actions, or scenes in the image using underscore between multi word hashtags and first and last names and use explicit words only if accurate, give them in a line not a list , no numbers, no remarks by you like ,here is the hashtags, or anything like that.")
        self.api_keys = []
        self.current_api_key_index = 0 if self.api_keys else None
        self.response_timeout = tk.IntVar(value=30)  
        self.caption_var = tk.BooleanVar(value=True)
        self.tags_var = tk.BooleanVar(value=True)
        self.save_txt_var = tk.BooleanVar(value=False)
        self.additional_caption = ""
        self.additional_tags = ""
        self.load_settings()
        self.root = root
        self.root.title("Tagline")
        self.root.iconbitmap('app.ico')
        self.stop_processing = False
        self.processed_images = set()

        self.api_key = tk.StringVar()

        self.current_api_key_index = 0 if self.api_keys else None
        
        self.model_options = ["gemini-pro-vision", "gemini-1.5-flash", "gemini-1.5-pro"]  
        
        self.create_widgets()
        self.image_queue = queue.Queue()
        self.active_threads = 0
        self.max_threads = 1  
        self.thread_semaphore = threading.Semaphore(self.max_threads)
        self.image_status = {}  
        self.safety_settings = [
            {
                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
            }
        ]
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    def setup_support_button(self):
        support_button = ttk.Button(self.root, text="Support Me",
                                    command=lambda: webbrowser.open("https://buymeacoffee.com/milky99"))
        support_button.pack(side=tk.BOTTOM, anchor=tk.SE, padx=10, pady=10)
        self.create_tooltip(support_button, "Support the developer")

    def create_tooltip(self, widget, text):
        def enter(event):
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1)
            label.pack()
            widget.tooltip = tooltip

        def leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)    
    def get_or_create_key(self):
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
        settings = {
            "safety_settings": [
                {
                    "category": setting["category"].name,
                    "threshold": setting["threshold"].name
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
            "additional_tags": self.additional_tags
        }
        
        encrypted_data = Fernet(self.encryption_key).encrypt(json.dumps(settings).encode())
        with open(self.settings_file, "wb") as f:
            f.write(encrypted_data)
        self.print("Settings saved successfully")

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "rb") as f:
                encrypted_data = f.read()
            
            try:
                decrypted_data = Fernet(self.encryption_key).decrypt(encrypted_data)
                settings = json.loads(decrypted_data.decode())
                
                
                self.safety_settings = []
                for item in settings.get("safety_settings", []):
                    try:
                        category = HarmCategory[item["category"]]
                        threshold = HarmBlockThreshold[item["threshold"]]
                        self.safety_settings.append({
                            "category": category,
                            "threshold": threshold
                        })
                    except KeyError:
                        self.print(f"Warning: Invalid safety setting found: {item}. Skipping.")
                
               
                if not self.safety_settings:
                    self.set_default_safety_settings()
                
                timeout = max(30.0, float(settings.get("response_timeout", 30.0)))
                self.response_timeout.set(max(30, min(300, int(settings.get("response_timeout", 30)))))
                self.selected_model.set(settings.get("selected_model", "gemini-pro-vision"))
                self.retry_count.set(settings.get("retry_count", 1))
                self.delay_seconds.set(settings.get("delay_seconds", 1.0))
                self.api_keys = settings.get("api_keys", [])
                self.num_hashtags.set(settings.get("num_hashtags", 10))
                self.caption_query.set(settings.get("caption_query", "Write a long accurate caption describing the image strictly in English and use explicit words only if accurate.Focus on the most prominent objects, actions, and scenes.If famous people are identified in the image, always include their names."))
                self.tags_query.set(settings.get("tags_query", f"Generate exactly {{num_hashtags}} strictly English keywords describing people, objects, clothes, actions, or scenes in the image using underscore between multi word hashtags and first and last names and use explicit words only if accurate, give them in a line not a list , no numbers, no remarks by you like ,here is the hashtags, or anything like that."))
                
               
                self.caption_var.set(settings.get("caption_enabled", True))
                self.tags_var.set(settings.get("tags_enabled", True))
                self.save_txt_var.set(settings.get("save_txt", False))
                self.additional_caption = settings.get("additional_caption", "")
                self.additional_tags = settings.get("additional_tags", "")
                
                self.print("Settings loaded successfully")
            except Exception as e:
                self.print(f"Error loading settings: {e}")
                self.set_default_settings()
        else:
            self.set_default_settings()

    def set_default_safety_settings(self):
        self.safety_settings = [
            {
                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": HarmBlockThreshold.BLOCK_NONE
            },
        ]
    
    async def wait_for_response(self, future, timeout):
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            return None
    
    def set_default_settings(self):
        self.set_default_safety_settings()
        self.selected_model.set("gemini-pro-vision")
        self.retry_count.set(1)
        self.delay_seconds.set(1.0)
        self.api_keys = []
        self.num_hashtags.set(10)
        self.caption_query.set("Write a long accurate caption describing the image strictly in English and use explicit words only if accurate.Focus on the most prominent objects, actions, and scenes.If famous people are identified in the image, always include their names.")
        self.tags_query.set(f"Generate exactly {{num_hashtags}} strictly English keywords describing people, objects, clothes, actions, or scenes in the image using underscore between multi word hashtags and first and last names and use explicit words only if accurate, give them in a line not a list , no numbers, no remarks by you like ,here is the hashtags, or anything like that.")
        self.save_settings()
        self.print("Default settings applied")
            
            
    def on_closing(self):
        self.save_settings()
        self.root.destroy()
    
    def load_selected_model(self):
        try:
            with open("selected_model.txt", "r") as f:
                saved_model = f.read().strip()
                if saved_model in self.model_options:
                    self.selected_model.set(saved_model)
                else:
                    self.selected_model.set("gemini-pro-vision")
        except FileNotFoundError:
            self.selected_model.set("gemini-pro-vision")

    def save_selected_model(self, *args):
        self.save_settings()
            
    
    
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
            self.safety_labels[category] = {}
            for j, (threshold_name, threshold) in enumerate(thresholds):
                rb = tk.Radiobutton(frame, text=threshold_name, variable=var, value=threshold.name, 
                                    command=lambda c=category, t=threshold: self.update_safety_setting(c, t))
                rb.grid(row=i, column=j+1, padx=2, pady=2, sticky="w")

        
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

       
        for t, label in self.safety_labels[category].items():
            if t == threshold:
                label.config(bg="light blue")
            else:
                label.config(bg="SystemButtonFace")
        
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
        model_dropdown = tk.OptionMenu(top_frame, self.selected_model, *self.model_options, command=self.on_model_change)
        model_dropdown.grid(row=0, column=5, padx=5, pady=5)

        tk.Button(top_frame, text="Extra Settings", command=self.create_settings_menu).grid(row=1, column=5, padx=5, pady=5)

        tk.Button(top_frame, text="Upload Images", command=self.upload_images).grid(row=2, column=0, padx=5, pady=5)
        tk.Button(top_frame, text="Add Photos", command=self.add_photos).grid(row=2, column=1, padx=5, pady=5)
        tk.Button(top_frame, text="Stop", command=self.stop_processing_images).grid(row=2, column=2, padx=5, pady=5)
        tk.Label(top_frame, text="Number of Tags:").grid(row=2, column=3, padx=5, pady=5)
        tk.Entry(top_frame, textvariable=self.num_hashtags).grid(row=2, column=4, padx=5, pady=5)
        
        clear_button = tk.Button(top_frame, text="Clear Tagged Images", command=self.clear_tagged_images)
        clear_button.grid(row=2, column=5, padx=5, pady=5)

        middle_frame = tk.Frame(main_frame)
        middle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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

        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.console_text = tk.Text(bottom_frame, height=10)
        self.console_text.pack(fill=tk.BOTH, expand=True)

        self.console_queue = queue.Queue()
        self.root.after(100, self.update_console)

        self.bind_mousewheel(self.queue_canvas)
        self.bind_mousewheel(self.console_text)

        self.setup_support_button()

        self.selected_model.trace("w", self.save_selected_model)
        
        

        
    def on_model_change(self, *args):
        self.save_settings()
    
    def add_api_key(self):
        new_key = self.api_key.get().strip()
        if new_key and new_key not in self.api_keys:
            self.api_keys.append(new_key)
            if self.current_api_key_index is None:
                self.current_api_key_index = 0
            else:
                self.current_api_key_index = len(self.api_keys) - 1
            self.save_settings()  
            messagebox.showinfo("Info", "API Key added successfully and set as current")
        self.api_key.set("")

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
                self.api_keys.pop(selected[0])
                self.save_settings()
                listbox.delete(selected)

        def set_current_key():
            selected = listbox.curselection()
            if selected:
                self.current_api_key_index = selected[0]
                current_key = self.api_keys[self.current_api_key_index]
                messagebox.showinfo("Info", f"Current API key set to: {current_key}")
                self.api_key.set(current_key)  
                manage_window.destroy()  
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
        
        try:
            self.print("Configuring API with current key")
            current_key = self.api_keys[self.current_api_key_index]
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(self.selected_model.get())
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
            self.image_queue.put((file, model, scrollable_frame, canvas_width, None, None, None, None))
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
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(self.selected_model.get())
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
            self.image_queue.put((file, model, scrollable_frame, canvas_width, None, None, None, None))
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
            self.image_queue.get()
            self.image_queue.task_done()
        self.clear_queue_display()

    async def process_image(self, file, model, scrollable_frame, canvas_width, retry_count=None, existing_frame=None, existing_caption_label=None, existing_tags_label=None):
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

                retry_button = tk.Button(retry_frame, text="Retry", command=lambda: self.retry_image_processing(file, model, img_label, caption_label, tags_label, retry_count_entry))
                retry_button.pack(side="left")

                copy_button = tk.Button(text_frame, text="Copy", command=lambda: self.copy_to_clipboard(caption_label, tags_label))
                copy_button.pack(anchor="w", pady=5)

            self.root.update()

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
                genai.configure(api_key=current_key)
                self.print(f"Switched to API key index: {self.current_api_key_index}")
                return genai.GenerativeModel(self.selected_model.get())
            except Exception as e:
                self.print(f"Error with API key at index {self.current_api_key_index}: {str(e)}")
            
            if self.current_api_key_index == initial_index:
                break
        
        self.print("All APIs are exhausted.")
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
        
        for attempt in range(retry_count):
            try:
                self.print(f"Generating caption and tags (Attempt {attempt + 1}/{retry_count})")
                self.print(f"Using model: {self.selected_model.get()}")
                
                formatted_caption = ""
                formatted_tags = ""

                if self.caption_var.get():
                    caption_response = await asyncio.to_thread(model.generate_content, [self.caption_query.get(), img], safety_settings=self.safety_settings)
                    formatted_caption = caption_response.text
                    formatted_caption += " " + self.additional_caption

                if self.tags_var.get():
                    num_hashtags = self.num_hashtags.get()
                    tags_query = self.tags_query.get().replace("{num_hashtags}", str(num_hashtags))
                    tags_response = await asyncio.to_thread(model.generate_content, [tags_query, img], safety_settings=self.safety_settings)
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
                return  

            except Exception as e:
                self.print(f"Attempt {attempt + 1} failed: {str(e)[:100]}...")
                if "429" in str(e) or "Resource has been exhausted" in str(e):
                    self.print("Switching API key due to rate limit")
                    model = self.switch_api_key()
                    if model is None:
                        self.print("All APIs are exhausted. Stopping processing.")
                        break
                
                if attempt == retry_count - 1:
                    self.print(f"Failed to process image {file} after {retry_count} attempts")
                    def update_error_labels():
                        if caption_label and caption_label.winfo_exists():
                            caption_label.config(text=f"Caption: Failed to generate after {retry_count} attempts")
                        if tags_label and tags_label.winfo_exists():
                            tags_label.config(text=f"Tags: Failed to generate after {retry_count} attempts")
                    self.root.after(0, update_error_labels)
                    self.image_status[file] = 0  
                    self.root.after(100, lambda: self.update_highlight(file, image_frame))
                    return

            await asyncio.sleep(self.delay_seconds.get())
                
    async def process_image_queue(self):
        while not self.stop_processing:
            if self.paused:
                await asyncio.sleep(1)
                continue
            try:
                if not self.image_queue.empty():
                    file, model, scrollable_frame, canvas_width, retry_count, existing_frame, existing_caption_label, existing_tags_label = self.image_queue.get(block=False)
                    self.thread_semaphore.acquire()
                    try:
                        await self.process_image(file, model, scrollable_frame, canvas_width, retry_count=retry_count, existing_frame=existing_frame, existing_caption_label=existing_caption_label, existing_tags_label=existing_tags_label)
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
    
    def retry_image_processing(self, file, model, img_label, caption_label, tags_label, retry_count_entry):
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
            self.image_queue.put((file, model, scrollable_frame, canvas_width, retry_count, image_info_frame, caption_label, tags_label))
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
            widget.yview_scroll(int(-1*(event.delta/120)), "units")
        
        widget.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(e):
            widget.unbind_all("<MouseWheel>")
        
        widget.bind("<Leave>", _unbind_mousewheel)
        widget.bind("<Enter>", lambda e: widget.bind_all("<MouseWheel>", _on_mousewheel))
            
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

                user_comment = b"UNICODE\0" + tags_bytes
                exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment
                
                try:
                    exif_bytes = piexif.dump(exif_dict)
                    img.save(file, "jpeg", exif=exif_bytes)
                except ValueError as e:
                    self.print(f"Error dumping EXIF data: {e}")
                    img.save(file, "jpeg")

                subprocess.run(["exiv2", "-M", f"set Iptc.Application2.Caption '{caption}'", file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                subprocess.run(["exiv2", "-M", f"add Iptc.Application2.Keywords '{tags}'", file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

            elif img.format in ["PNG", "WEBP"]:
                metadata = PngImagePlugin.PngInfo()
                metadata.add_text("Description", caption)
                metadata.add_text("Keywords", tags if isinstance(tags, str) else tags.decode('utf-8', errors='replace'))
                img.save(file, img.format.lower(), pnginfo=metadata)
            else:
                self.print(f"Unsupported image format for embedding metadata: {file}")
                messagebox.showerror("Error", f"Unsupported image format for embedding metadata: {file}")

            img.close()
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
