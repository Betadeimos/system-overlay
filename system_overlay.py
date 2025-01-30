# taken away font size and still buggy but getting there

import tkinter as tk
from tkinter import ttk, colorchooser
import psutil
from datetime import datetime
import pynvml

# Configuration Settings
DEFAULT_CONFIG = {
    'text_color': 'white',
    'background_color': 'black',
    'window_width': 600,
    'window_height': 400,
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
        self.window.geometry("350x300")
        self.window.transient(parent)

        # Text Color
        ttk.Label(self.window, text="Text Color:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.text_color_var = tk.StringVar(value=self.config['text_color'])
        ttk.Button(self.window, text="Choose", command=self.choose_text_color).grid(row=0, column=1, padx=10, pady=5)

        # Background Color
        ttk.Label(self.window, text="Background Color:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.background_color_var = tk.StringVar(value=self.config['background_color'])
        ttk.Button(self.window, text="Choose", command=self.choose_background_color).grid(row=1, column=1, padx=10, pady=5)

        # Background Opacity
        ttk.Label(self.window, text="Background Opacity:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.background_opacity_var = tk.DoubleVar(value=self.config['background_opacity'])
        ttk.Scale(self.window, from_=0.0, to=1.0, variable=self.background_opacity_var, orient="horizontal").grid(row=2, column=1, padx=10, pady=5)

        # Line Spacing
        ttk.Label(self.window, text="Line Spacing:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.line_spacing_var = tk.DoubleVar(value=self.config['line_spacing'])
        ttk.Scale(self.window, from_=0.5, to=2.0, variable=self.line_spacing_var, orient="horizontal").grid(row=3, column=1, padx=10, pady=5)

        # Apply Button
        ttk.Button(self.window, text="Apply", command=self.apply_settings).grid(row=4, column=0, columnspan=2, pady=10)

    def choose_text_color(self):
        color = colorchooser.askcolor(title="Choose Text Color")[1]
        if color:
            self.text_color_var.set(color)

    def choose_background_color(self):
        color = colorchooser.askcolor(title="Choose Background Color")[1]
        if color:
            self.background_color_var.set(color)

    def apply_settings(self):
        self.config['text_color'] = self.text_color_var.get()
        self.config['background_color'] = self.background_color_var.get()
        self.config['background_opacity'] = self.background_opacity_var.get()
        self.config['line_spacing'] = self.line_spacing_var.get()
        self.apply_callback()
        self.window.destroy()

class SystemOverlay:
    def __init__(self, root):
        self._config = DEFAULT_CONFIG.copy()
        self.root = root
        self.root.geometry(f"{self._config['window_width']}x{self._config['window_height']}")
        self.root.attributes('-topmost', True)
        self.root.configure(bg=self._config['background_color'])
        self.root.overrideredirect(True)
        self.root.attributes('-alpha', self._config['background_opacity'])
        
        # Enable resizing with proper handling
        self.root.resizable(True, True)
        
        # Create a canvas for dynamic text sizing
        self.canvas = tk.Canvas(
            self.root,
            bg=self._config['background_color'],
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Initialize GPU monitoring
        self.gpu_available = False
        self.setup_gpu()

        # Dragging functionality
        self._drag_data = {"x": 0, "y": 0}
        self.root.bind('<Button-1>', self.start_drag)
        self.root.bind('<B1-Motion>', self.do_drag)
        self.root.bind('<Button-3>', self.show_context_menu)

        # Resize handling
        self.resize_timeout = None
        self.root.bind('<Configure>', self.on_resize)

        # Start the update loop
        self.update_system_info()

    def setup_gpu(self):
        try:
            pynvml.nvmlInit()
            self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.gpu_available = True
        except Exception as e:
            print(f"GPU monitoring not available: {e}")
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
        except Exception as e:
            print(f"Error getting GPU info: {e}")
            return "GPU: Error"

    def calculate_font_size(self, text_lines, width, height):
        # Create a temporary label to measure text dimensions
        temp_label = tk.Label(self.root)
        
        # Calculate maximum possible font size based on window dimensions
        max_font = min(height, width)
        min_font = 8
        optimal_font = min_font
        
        # Test different font sizes
        for font_size in range(min_font, max_font + 1):
            total_height = 0
            max_line_width = 0
            
            # Calculate total height and maximum line width
            for line in text_lines:
                temp_label.config(font=("Arial", font_size), text=line)
                text_width = temp_label.winfo_reqwidth()
                text_height = temp_label.winfo_reqheight()
                total_height += text_height * self._config['line_spacing']
                max_line_width = max(max_line_width, text_width)
                
                # If we exceed dimensions, return previous size
                if total_height > height or max_line_width > width:
                    temp_label.destroy()
                    return max(min_font, font_size - 1)
            
        temp_label.destroy()
        return min(max_font, optimal_font)

    def draw_text(self, text_lines):
        self.canvas.delete("all")
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # Calculate optimal font size
        font_size = self.calculate_font_size(text_lines, width, height)
        
        # Calculate total text height
        total_text_height = len(text_lines) * font_size * self._config['line_spacing']
        
        # Calculate starting y position
        y = (height - total_text_height) / 2
        
        # Draw each line of text
        for line in text_lines:
            temp_label = tk.Label(self.root, text=line, font=("Arial", font_size))
            text_width = temp_label.winfo_reqwidth()
            temp_label.destroy()
            
            x = (width - text_width) / 2
            self.canvas.create_text(
                x, y,
                text=line,
                font=("Arial", font_size),
                fill=self._config['text_color'],
                anchor="nw"
            )
            y += font_size * self._config['line_spacing']

    def update_system_info(self):
        try:
            info = []
            if self._config['show_cpu']:
                info.append(f"CPU Usage: {psutil.cpu_percent()}%")
            if self._config['show_memory']:
                memory = psutil.virtual_memory()
                info.append(f"Memory Usage: {memory.percent}%")
            if self._config['show_gpu'] and self.gpu_available:
                info.append(self.get_gpu_info())
            if self._config['show_timestamp']:
                info.append(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

            # Split multi-line entries
            text_lines = []
            for entry in info:
                text_lines.extend(entry.split('\n'))
            
            self.draw_text(text_lines)
        except Exception as e:
            print(f"Error updating system info: {e}")
        finally:
            self.root.after(self._config['update_interval'], self.update_system_info)

    def on_resize(self, event):
        # Debounce resize events
        if self.resize_timeout:
            self.root.after_cancel(self.resize_timeout)
        self.resize_timeout = self.root.after(100, self.handle_resize)

    def handle_resize(self):
        self.resize_timeout = None
        self.update_system_info()

    def start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def do_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_data["x"])
        y = self.root.winfo_y() + (event.y - self._drag_data["y"])
        self.root.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Settings", command=self.show_settings)
        menu.add_command(label="Close", command=self.root.destroy)
        menu.post(event.x_root, event.y_root)

    def show_settings(self):
        SettingsWindow(self.root, self._config, self.apply_settings)

    def apply_settings(self):
        self.root.configure(bg=self._config['background_color'])
        self.root.attributes('-alpha', self._config['background_opacity'])
        self.canvas.config(bg=self._config['background_color'])
        self.update_system_info()

if __name__ == '__main__':
    root = tk.Tk()
    app = SystemOverlay(root)
    root.mainloop()