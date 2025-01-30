# dynmic resized works but settings are broken

import tkinter as tk
from tkinter import ttk, colorchooser
import psutil
from datetime import datetime
import pynvml

# Configuration Settings
DEFAULT_CONFIG = {
    'base_font_size': 18,
    'text_color': 'white',
    'background_color': 'black',
    'window_width': 250,
    'window_height': 160,
    'update_interval': 1000,
    'show_cpu': True,
    'show_memory': True,
    'show_gpu': True,
    'show_timestamp': False,
    'background_opacity': 0.9,
    'line_spacing': 1,
    'margin': 1
}

class SettingsWindow:
    def __init__(self, parent, config, apply_callback):
        self.window = tk.Toplevel(parent)
        self.window.title("Settings")
        # Add your settings UI elements here
        ttk.Button(self.window, text="Apply", command=apply_callback).pack()

class SystemOverlay:
    def __init__(self, root):
        self._config = DEFAULT_CONFIG.copy()
        self.root = root
        self.root.geometry(f"{self._config['window_width']}x{self._config['window_height']}")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', self._config['background_opacity'])
        
        # Create a canvas for the background
        self.canvas = tk.Canvas(
            self.root,
            bg=self._config['background_color'],
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Label for system info
        self.label = tk.Label(
            self.canvas,
            text="",
            font=("Arial", self._config['base_font_size']),
            fg=self._config['text_color'],
            bg=self._config['background_color'],
            justify=tk.LEFT,
            padx=self._config['margin'],
            pady=self._config['margin']
        )
        self.label.pack(expand=True, fill=tk.BOTH)

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
        
        handle_color = self._config['background_color']
        
        # Bottom-right handle
        self.handle_br = tk.Frame(self.root, width=handle_size, height=handle_size, bg=handle_color, cursor='bottom_right_corner')
        self.handle_br.place(relx=1.0, rely=1.0, anchor='se')
        self.handle_br.bind('<Button-1>', self.start_resize_br)
        self.handle_br.bind('<B1-Motion>', self.do_resize_br)

        # Bottom-left handle
        self.handle_bl = tk.Frame(self.root, width=handle_size, height=handle_size, bg=handle_color, cursor='bottom_left_corner')
        self.handle_bl.place(relx=0.0, rely=1.0, anchor='sw')
        self.handle_bl.bind('<Button-1>', self.start_resize_bl)
        self.handle_bl.bind('<B1-Motion>', self.do_resize_bl)

        # Top-right handle
        self.handle_tr = tk.Frame(self.root, width=handle_size, height=handle_size, bg=handle_color, cursor='top_right_corner')
        self.handle_tr.place(relx=1.0, rely=0.0, anchor='ne')
        self.handle_tr.bind('<Button-1>', self.start_resize_tr)
        self.handle_tr.bind('<B1-Motion>', self.do_resize_tr)

        # Top-left handle
        self.handle_tl = tk.Frame(self.root, width=handle_size, height=handle_size, bg=handle_color, cursor='top_left_corner')
        self.handle_tl.place(relx=0.0, rely=0.0, anchor='nw')
        self.handle_tl.bind('<Button-1>', self.start_resize_tl)
        self.handle_tl.bind('<B1-Motion>', self.do_resize_tl)

    def calculate_font_size(self):
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        base_size = self._config['base_font_size']
        
        # Calculate font size based on window area
        area = width * height
        scale_factor = (area / (250 * 160)) ** 0.5  # Square root scaling
        return int(base_size * scale_factor)

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
            return "GPU: N/A"
        try:
            utilization = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
            gpu_usage = utilization.gpu
            temp = pynvml.nvmlDeviceGetTemperature(self.gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            used_mem = mem_info.used / 1024**3
            total_mem = mem_info.total / 1024**3
            return f"GPU Usage: {gpu_usage}%\nGPU Temp: {temp}°C\nVRAM: {used_mem:.1f}/{total_mem:.1f} GB"
        except:
            return "GPU: Error"

    def update_system_info(self):
        info = []
        if self._config['show_cpu']:
            info.append(f"CPU Usage: {psutil.cpu_percent()}%")
        if self._config['show_memory']:
            memory = psutil.virtual_memory()
            info.append(f"RAM Usage: {memory.percent}%")
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
        self.canvas.config(bg=self._config['background_color'])
        self.root.attributes('-alpha', self._config['background_opacity'])
        self.label.config(fg=self._config['text_color'])
        self.update_font_size()
        self.update_system_info()

    def change_mode(self):
        print("Mode menu clicked")

    def start_resize_br(self, event):
        self._resize_data = {
            'x': event.x_root,
            'y': event.y_root,
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'aspect_ratio': self.root.winfo_width() / self.root.winfo_height()
        }

    def do_resize_br(self, event):
        dx = event.x_root - self._resize_data['x']
        dy = event.y_root - self._resize_data['y']
        
        # Calculate new dimensions maintaining aspect ratio
        new_width = self._resize_data['width'] + dx
        new_height = int(new_width / self._resize_data['aspect_ratio'])
        
        self.root.geometry(f"{new_width}x{new_height}")
        self.update_font_size()

    def start_resize_bl(self, event):
        self._resize_data = {
            'x': event.x_root,
            'y': event.y_root,
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'x_pos': self.root.winfo_x(),
            'aspect_ratio': self.root.winfo_width() / self.root.winfo_height()
        }

    def do_resize_bl(self, event):
        dx = event.x_root - self._resize_data['x']
        dy = event.y_root - self._resize_data['y']
        
        # Calculate new dimensions maintaining aspect ratio
        new_width = self._resize_data['width'] - dx
        new_height = int(new_width / self._resize_data['aspect_ratio'])
        x_pos = self._resize_data['x_pos'] + dx
        
        self.root.geometry(f"{new_width}x{new_height}+{x_pos}+{self.root.winfo_y()}")
        self.update_font_size()

    def start_resize_tr(self, event):
        self._resize_data = {
            'x': event.x_root,
            'y': event.y_root,
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'y_pos': self.root.winfo_y(),
            'aspect_ratio': self.root.winfo_width() / self.root.winfo_height()
        }

    def do_resize_tr(self, event):
        dx = event.x_root - self._resize_data['x']
        dy = event.y_root - self._resize_data['y']
        
        # Calculate new dimensions maintaining aspect ratio
        new_width = self._resize_data['width'] + dx
        new_height = int(new_width / self._resize_data['aspect_ratio'])
        y_pos = self._resize_data['y_pos'] + (self._resize_data['height'] - new_height)
        
        self.root.geometry(f"{new_width}x{new_height}+{self.root.winfo_x()}+{y_pos}")
        self.update_font_size()

    def start_resize_tl(self, event):
        self._resize_data = {
            'x': event.x_root,
            'y': event.y_root,
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'x_pos': self.root.winfo_x(),
            'y_pos': self.root.winfo_y(),
            'aspect_ratio': self.root.winfo_width() / self.root.winfo_height()
        }

    def do_resize_tl(self, event):
        dx = event.x_root - self._resize_data['x']
        dy = event.y_root - self._resize_data['y']
        
        # Calculate new dimensions maintaining aspect ratio
        new_width = self._resize_data['width'] - dx
        new_height = int(new_width / self._resize_data['aspect_ratio'])
        x_pos = self._resize_data['x_pos'] + dx
        y_pos = self._resize_data['y_pos'] + (self._resize_data['height'] - new_height)
        
        self.root.geometry(f"{new_width}x{new_height}+{x_pos}+{y_pos}")
        self.update_font_size()

if __name__ == '__main__':
    root = tk.Tk()
    app = SystemOverlay(root)
    root.mainloop()