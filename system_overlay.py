# works fine but simple

import tkinter as tk
import psutil
from datetime import datetime
import pynvml

# Configuration Settings
DEFAULT_CONFIG = {
    'font_size': 12,
    'text_color': 'white',
    'background_color': 'black',
    'window_width': 300,
    'window_height': 200,
    'update_interval': 1000,  # in milliseconds
    'show_cpu': True,
    'show_memory': True,
    'show_gpu': True,
    'show_timestamp': True
}

class SystemOverlay:
    def __init__(self, root):
        self._config = DEFAULT_CONFIG.copy()
        self.root = root
        self.root.geometry(f"{self._config['window_width']}x{self._config['window_height']}")
        self.root.attributes('-topmost', True)
        self.root.configure(bg=self._config['background_color'])
        self.root.overrideredirect(True)  # Borderless window

        self.label = tk.Label(
            self.root,
            font=("Arial", self._config['font_size']),
            fg=self._config['text_color'],
            bg=self._config['background_color'],
            justify="left",
            anchor="nw"
        )
        self.label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.setup_gpu()
        self.update_system_info()

        # Dragging functionality
        self.root.bind('<Button-1>', self.start_drag)
        self.root.bind('<B1-Motion>', self.do_drag)
        self.root.bind('<Button-3>', self.show_context_menu)

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
        # Placeholder for settings functionality
        print("Settings menu clicked")

    def change_mode(self):
        # Placeholder for mode-changing functionality
        print("Mode menu clicked")

if __name__ == '__main__':
    root = tk.Tk()
    app = SystemOverlay(root)
    root.mainloop()
