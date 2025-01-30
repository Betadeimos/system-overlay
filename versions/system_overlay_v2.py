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

        # Resize handles
        self.resize_handles = []
        self.create_resize_handles()

    def create_resize_handles(self):
        handle_size = 10
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

    def start_resize_br(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_width = self.root.winfo_width()
        self._resize_start_height = self.root.winfo_height()

    def do_resize_br(self, event):
        new_width = self._resize_start_width + (event.x_root - self._resize_start_x)
        new_height = self._resize_start_height + (event.y_root - self._resize_start_y)
        self.root.geometry(f"{new_width}x{new_height}")

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