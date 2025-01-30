# dynmic resized kind of works

import tkinter as tk
from tkinter import ttk, colorchooser
import psutil
from datetime import datetime
import pynvml

# Configuration Settings
DEFAULT_CONFIG = {
    'base_font_size': 12,
    'text_color': 'white',
    'background_color': 'black',
    'window_width': 300,
    'window_height': 200,
    'update_interval': 1000,  # in milliseconds
    'show_cpu': True,
    'show_memory': True,
    'show_gpu': True,
    'show_timestamp': True,
    'background_opacity': 0.8,  # 0.0 (fully transparent) to 1.0 (fully opaque)
    'line_spacing': 1.2  # Multiplier for line spacing
}

class SettingsWindow:
    def __init__(self, parent, config, apply_callback):
        self.parent = parent
        self.config = config
        self.apply_callback = apply_callback

        self.window = tk.Toplevel(parent)
        self.window.title("Settings")
        self.window.geometry("300x300")
        self.window.transient(parent)

        # Base Font Size
        ttk.Label(self.window, text="Base Font Size:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.font_size_var = tk.IntVar(value=self.config['base_font_size'])
        ttk.Spinbox(self.window, from_=8, to=24, textvariable=self.font_size_var).grid(row=0, column=1, padx=10, pady=5)

        # Text Color
        ttk.Label(self.window, text="Text Color:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.text_color_var = tk.StringVar(value=self.config['text_color'])
        ttk.Button(self.window, text="Choose", command=self.choose_text_color).grid(row=1, column=1, padx=10, pady=5)

        # Background Color
        ttk.Label(self.window, text="Background Color:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.background_color_var = tk.StringVar(value=self.config['background_color'])
        ttk.Button(self.window, text="Choose", command=self.choose_background_color).grid(row=2, column=1, padx=10, pady=5)

        # Metrics to Display
        ttk.Label(self.window, text="Display Metrics:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.show_cpu_var = tk.BooleanVar(value=self.config['show_cpu'])
        ttk.Checkbutton(self.window, text="CPU", variable=self.show_cpu_var).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.show_memory_var = tk.BooleanVar(value=self.config['show_memory'])
        ttk.Checkbutton(self.window, text="Memory", variable=self.show_memory_var).grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.show_gpu_var = tk.BooleanVar(value=self.config['show_gpu'])
        ttk.Checkbutton(self.window, text="GPU", variable=self.show_gpu_var).grid(row=6, column=0, padx=10, pady=5, sticky="w")
        self.show_timestamp_var = tk.BooleanVar(value=self.config['show_timestamp'])
        ttk.Checkbutton(self.window, text="Timestamp", variable=self.show_timestamp_var).grid(row=7, column=0, padx=10, pady=5, sticky="w")

        # Apply Button
        ttk.Button(self.window, text="Apply", command=self.apply_settings).grid(row=8, column=0, columnspan=2, pady=10)

    def choose_text_color(self):
        color = colorchooser.askcolor(title="Choose Text Color")[1]
        if color:
            self.text_color_var.set(color)

    def choose_background_color(self):
        color = colorchooser.askcolor(title="Choose Background Color")[1]
        if color:
            self.background_color_var.set(color)

    def apply_settings(self):
        self.config['base_font_size'] = self.font_size_var.get()
        self.config['text_color'] = self.text_color_var.get()
        self.config['background_color'] = self.background_color_var.get()
        self.config['show_cpu'] = self.show_cpu_var.get()
        self.config['show_memory'] = self.show_memory_var.get()
        self.config['show_gpu'] = self.show_gpu_var.get()
        self.config['show_timestamp'] = self.show_timestamp_var.get()
        self.apply_callback()
        self.window.destroy()

class SystemOverlay:
    def __init__(self, root):
        self._config = DEFAULT_CONFIG.copy()
        self.root = root
        self.root.geometry(f"{self._config['window_width']}x{self._config['window_height']}")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', self._config['background_opacity'])
        self.root.configure(bg=self._config['background_color'])

        # Label for system info
        self.label = tk.Label(
            self.root,
            text="",
            font=("Arial", self._config['base_font_size']),
            fg=self._config['text_color'],
            bg=self._config['background_color'],
            justify=tk.LEFT
        )
        self.label.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Setup resize handles
        self.setup_resize_handles()

        # Setup GPU monitoring
        self.setup_gpu()

        # Setup drag functionality
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.label.bind('<Button-1>', self.start_drag)
        self.label.bind('<B1-Motion>', self.do_drag)

        # Right-click context menu
        self.label.bind('<Button-3>', self.show_context_menu)

        # Start system info updates
        self.update_system_info()

    def setup_resize_handles(self):
        handle_size = 8
        # Bottom-right handle
        self.handle_br = tk.Frame(self.root, width=handle_size, height=handle_size, bg='gray')
        self.handle_br.place(relx=1.0, rely=1.0, anchor='se')
        self.handle_br.bind('<Button-1>', self.start_resize_br)
        self.handle_br.bind('<B1-Motion>', self.do_resize_br)

        # Bottom-left handle
        self.handle_bl = tk.Frame(self.root, width=handle_size, height=handle_size, bg='gray')
        self.handle_bl.place(relx=0.0, rely=1.0, anchor='sw')
        self.handle_bl.bind('<Button-1>', self.start_resize_bl)
        self.handle_bl.bind('<B1-Motion>', self.do_resize_bl)

        # Top-right handle
        self.handle_tr = tk.Frame(self.root, width=handle_size, height=handle_size, bg='gray')
        self.handle_tr.place(relx=1.0, rely=0.0, anchor='ne')
        self.handle_tr.bind('<Button-1>', self.start_resize_tr)
        self.handle_tr.bind('<B1-Motion>', self.do_resize_tr)

        # Top-left handle
        self.handle_tl = tk.Frame(self.root, width=handle_size, height=handle_size, bg='gray')
        self.handle_tl.place(relx=0.0, rely=0.0, anchor='nw')
        self.handle_tl.bind('<Button-1>', self.start_resize_tl)
        self.handle_tl.bind('<B1-Motion>', self.do_resize_tl)

    def calculate_font_size(self):
        # Calculate font size based on window dimensions
        base_size = self._config['base_font_size']
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # Use the smaller dimension to determine font size
        min_dimension = min(width, height)
        scale_factor = min_dimension / 300  # 300 is the default window size
        return max(8, min(24, int(base_size * scale_factor)))

    def start_resize_br(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_width = self.root.winfo_width()
        self._resize_start_height = self.root.winfo_height()

    def do_resize_br(self, event):
        new_width = self._resize_start_width + (event.x_root - self._resize_start_x)
        new_height = self._resize_start_height + (event.y_root - self._resize_start_y)
        self.root.geometry(f"{new_width}x{new_height}")
        self.update_font_size()

    def start_resize_bl(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_width = self.root.winfo_width()
        self._resize_start_height = self.root.winfo_height()

    def do_resize_bl(self, event):
        new_width = self._resize_start_width - (event.x_root - self._resize_start_x)
        new_height = self._resize_start_height + (event.y_root - self._resize_start_y)
        x = self.root.winfo_x() + (event.x_root - self._resize_start_x)
        self.root.geometry(f"{new_width}x{new_height}+{x}+{self.root.winfo_y()}")
        self.update_font_size()

    def start_resize_tr(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_width = self.root.winfo_width()
        self._resize_start_height = self.root.winfo_height()

    def do_resize_tr(self, event):
        new_width = self._resize_start_width + (event.x_root - self._resize_start_x)
        new_height = self._resize_start_height - (event.y_root - self._resize_start_y)
        y = self.root.winfo_y() + (event.y_root - self._resize_start_y)
        self.root.geometry(f"{new_width}x{new_height}+{self.root.winfo_x()}+{y}")
        self.update_font_size()

    def start_resize_tl(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_width = self.root.winfo_width()
        self._resize_start_height = self.root.winfo_height()

    def do_resize_tl(self, event):
        new_width = self._resize_start_width - (event.x_root - self._resize_start_x)
        new_height = self._resize_start_height - (event.y_root - self._resize_start_y)
        x = self.root.winfo_x() + (event.x_root - self._resize_start_x)
        y = self.root.winfo_y() + (event.y_root - self._resize_start_y)
        self.root.geometry(f"{new_width}x{new_height}+{x}+{y}")
        self.update_font_size()

    def update_font_size(self):
        font_size = self.calculate_font_size()
        self.label.config(font=("Arial", font_size))

    def setup_gpu(self):
        try:
            pynvml.nvmlInit()
            self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.gpu_available = True
        except:
            self.gpu_available = False

    def get_gpu_info(self):
        if not self.gpu_available:
            return "GPU: Not Available"

        try:
            utilization = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
            gpu_usage = utilization.gpu
            temp = pynvml.nvmlDeviceGetTemperature(self.gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            used_mem = mem_info.used / 1024**2
            total_mem = mem_info.total / 1024**2
            return f"GPU Usage: {gpu_usage}%\nGPU Temp: {temp}°C\nVRAM: {used_mem:.1f}/{total_mem:.1f} MB"
        except:
            return "GPU: Error"

    def update_system_info(self):
        info = []
        if self._config['show_cpu']:
            info.append(f"CPU Usage: {psutil.cpu_percent()}%")
        if self._config['show_memory']:
            memory = psutil.virtual_memory()
            info.append(f"Memory Usage: {memory.percent}%")
        if self._config['show_gpu']:
            info.append(self.get_gpu_info())
        if self._config['show_timestamp']:
            info.append(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

        self.label.config(text="\n".join(info))
        self.root.after(self._config['update_interval'], self.update_system_info)

    def start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def do_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_start_x
        y = self.root.winfo_y() + event.y - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Settings", command=self.show_settings)
        menu.add_command(label="Mode", command=self.change_mode)
        menu.add_separator()
        menu.add_command(label="Close", command=self.root.destroy)
        menu.post(event.x_root, event.y_root)

    def show_settings(self):
        SettingsWindow(self.root, self._config, self.apply_settings)

    def apply_settings(self):
        self.label.config(fg=self._config['text_color'], bg=self._config['background_color'])
        self.root.configure(bg=self._config['background_color'])
        self.update_font_size()
        self.update_system_info()

    def change_mode(self):
        print("Mode menu clicked")

if __name__ == '__main__':
    root = tk.Tk()
    app = SystemOverlay(root)
    root.mainloop()