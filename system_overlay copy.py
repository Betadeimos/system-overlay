# System Overlay with proper sizing and spacing
import tkinter as tk
import psutil
import pynvml
from collections import deque

# Configuration Settings
DEFAULT_CONFIG = {
    'base_font_size': 18,
    'text_color': 'white',
    'background_color': 'black',
    'window_width': 210,
    'window_height': 175,
    'update_interval': 500,
    'show_cpu': True,
    'show_memory': True,
    'show_gpu': True,
    'background_opacity': 0.9,
    'bar_height': 30,
    'bar_padding': 5,
    'colors': {
        'cpu': '#505050',
        'ram': '#505050',
        'gpu': '#505050',
        'gpu_temp': '#505050',
        'vram': '#505050'
    },
    'smoothing_samples': 5,
    'vertical_spacing': 43,
    'top_margin': 5,       # Reduced margin
    'bottom_margin': 5     # Reduced margin
}

class SystemOverlay:
    def __init__(self, root):
        self._config = DEFAULT_CONFIG.copy()
        self.root = root
        self.root.geometry(f"{self._config['window_width']}x{self._config['window_height']}")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', self._config['background_opacity'])
        
        # Create main canvas
        self.canvas = tk.Canvas(
            self.root,
            bg=self._config['background_color'],
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Initialize GPU monitoring
        self.setup_gpu()
        
        # Setup resize handles
        self.setup_resize_handles()
        
        # Setup drag functionality
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.canvas.bind('<Button-1>', self.start_drag)
        self.canvas.bind('<B1-Motion>', self.do_drag)
        self.canvas.bind('<Button-3>', self.show_context_menu)
        
        # Initialize smoothing buffers
        self.cpu_buffer = deque(maxlen=self._config['smoothing_samples'])
        self.ram_buffer = deque(maxlen=self._config['smoothing_samples'])
        self.gpu_buffer = deque(maxlen=self._config['smoothing_samples'])
        self.temp_buffer = deque(maxlen=self._config['smoothing_samples'])
        self.vram_buffer = deque(maxlen=self._config['smoothing_samples'])
        
        # Store canvas items for efficient updates
        self.metric_items = {
            'cpu': {'bar': None, 'text': None},
            'ram': {'bar': None, 'text': None},
            'gpu': {'bar': None, 'text': None},
            'gpu_temp': {'bar': None, 'text': None},
            'vram': {'bar': None, 'text': None}
        }
        
        # Start system info updates
        self.update_system_info()

    def setup_gpu(self):
        self.gpu_available = False
        try:
            pynvml.nvmlInit()
            self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.gpu_available = True
        except:
            self.gpu_available = False

    def get_gpu_info(self):
        if self.gpu_available:
            try:
                utilization = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
                memory = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
                temp = pynvml.nvmlDeviceGetTemperature(self.gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
                return {
                    'usage': utilization.gpu,
                    'used_mem': memory.used / (1024 ** 3),
                    'total_mem': memory.total / (1024 ** 3),
                    'temp': temp
                }
            except:
                return None
        return None

    def calculate_vertical_spacing(self):
        base_height = 220
        return int(self._config['vertical_spacing'] * (self.root.winfo_height() / base_height) ** 1.05)

    def get_smoothed_value(self, buffer, new_value):
        buffer.append(new_value)
        return sum(buffer) / len(buffer)

    def update_system_info(self):
        self.canvas.delete("temp_text")
        
        padding = 10  # Consistent padding for all sides
        y_position = padding  # Start from top padding
        spacing = self.calculate_vertical_spacing()
        
        # CPU
        if self._config['show_cpu']:
            cpu_percent = self.get_smoothed_value(self.cpu_buffer, psutil.cpu_percent())
            self.create_metric_bar(y_position, cpu_percent,
                                 self._config['colors']['cpu'],
                                 f"CPU: {cpu_percent:.1f}%", 'cpu')
            y_position += spacing
        
        # RAM
        if self._config['show_memory']:
            ram = psutil.virtual_memory()
            ram_percent = self.get_smoothed_value(self.ram_buffer, ram.percent)
            self.create_metric_bar(y_position, ram_percent,
                                 self._config['colors']['ram'],
                                 f"RAM: {ram_percent:.1f}%", 'ram')
            y_position += spacing
        
        # GPU
        if self._config['show_gpu'] and self.gpu_available:
            try:
                gpu_info = self.get_gpu_info()
                if gpu_info:
                    # GPU Usage
                    gpu_usage = self.get_smoothed_value(self.gpu_buffer, gpu_info['usage'])
                    self.create_metric_bar(y_position, gpu_usage,
                                         self._config['colors']['gpu'],
                                         f"GPU: {gpu_usage:.1f}%", 'gpu')
                    y_position += spacing
                    
                    # GPU Temperature
                    gpu_temp = self.get_smoothed_value(self.temp_buffer, gpu_info['temp'])
                    self.create_metric_bar(y_position, gpu_temp,
                                         self._config['colors']['gpu_temp'],
                                         f"GPU Temp: {gpu_temp:.1f}°C", 'gpu_temp')
                    y_position += spacing
                    
                    # VRAM
                    vram_percent = (gpu_info['used_mem'] / gpu_info['total_mem']) * 100
                    vram_percent = self.get_smoothed_value(self.vram_buffer, vram_percent)
                    self.create_metric_bar(y_position, vram_percent,
                                         self._config['colors']['vram'],
                                         f"VRAM: {gpu_info['used_mem']:.1f}/{gpu_info['total_mem']:.1f} GB", 'vram')
                    y_position += spacing
            except:
                pass
        
        self.root.after(self._config['update_interval'], self.update_system_info)

    def create_metric_bar(self, y_pos, width_percent, color, text, metric_name):
        # Calculate dimensions
        padding = 10  # Keep consistent initial padding
        height = int(self._config['bar_height'] * (self.root.winfo_height() / 220) ** 1.05)
        available_width = self.root.winfo_width() - (padding * 2)
        bar_width = (width_percent / 100.0) * available_width
        font_size = self.calculate_font_size()
        
        # Update or create bar
        if self.metric_items[metric_name]['bar']:
            self.canvas.coords(self.metric_items[metric_name]['bar'],
                             padding, y_pos, padding + bar_width, y_pos + height)
        else:
            self.metric_items[metric_name]['bar'] = self.canvas.create_rectangle(
                padding, y_pos, padding + bar_width, y_pos + height,
                fill=color, outline='', tags='bar'
            )
        
        # Update or create text
        text_padding = padding + 5  # Slight additional padding for text from the left edge
        if self.metric_items[metric_name]['text']:
            self.canvas.coords(self.metric_items[metric_name]['text'],
                             text_padding, y_pos + (height / 2))
            self.canvas.itemconfig(self.metric_items[metric_name]['text'],
                                 text=text, font=('Arial', font_size))
        else:
            self.metric_items[metric_name]['text'] = self.canvas.create_text(
                text_padding, y_pos + (height / 2),
                text=text, anchor='w', fill=self._config['text_color'],
                font=('Arial', font_size), tags='text'
            )

    def calculate_font_size(self):
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        base_size = self._config['base_font_size']
        area = width * height
        scale_factor = (area / (250 * 220)) ** 0.55
        return int(base_size * scale_factor)

    def start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def do_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_start_x
        y = self.root.winfo_y() + event.y - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Close", command=self.root.destroy)
        menu.post(event.x_root, event.y_root)

    def setup_resize_handles(self):
        handle_size = 8
        
        # Bottom-right handle
        self.handle_br = tk.Frame(self.root, width=handle_size, height=handle_size, 
                                bg=self._config['background_color'], cursor='bottom_right_corner')
        self.handle_br.place(relx=1.0, rely=1.0, anchor='se')
        self.handle_br.bind('<Button-1>', self.start_resize)
        self.handle_br.bind('<B1-Motion>', self.do_resize)

        # Bottom-left handle
        self.handle_bl = tk.Frame(self.root, width=handle_size, height=handle_size,
                                bg=self._config['background_color'], cursor='bottom_left_corner')
        self.handle_bl.place(relx=0.0, rely=1.0, anchor='sw')
        self.handle_bl.bind('<Button-1>', self.start_resize)
        self.handle_bl.bind('<B1-Motion>', self.do_resize)

        # Top-right handle
        self.handle_tr = tk.Frame(self.root, width=handle_size, height=handle_size,
                                bg=self._config['background_color'], cursor='top_right_corner')
        self.handle_tr.place(relx=1.0, rely=0.0, anchor='ne')
        self.handle_tr.bind('<Button-1>', self.start_resize)
        self.handle_tr.bind('<B1-Motion>', self.do_resize)

        # Top-left handle
        self.handle_tl = tk.Frame(self.root, width=handle_size, height=handle_size,
                                bg=self._config['background_color'], cursor='top_left_corner')
        self.handle_tl.place(relx=0.0, rely=0.0, anchor='nw')
        self.handle_tl.bind('<Button-1>', self.start_resize)
        self.handle_tl.bind('<B1-Motion>', self.do_resize)

    def start_resize(self, event):
        self._resize_data = {
            'x': event.x_root,
            'y': event.y_root,
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'x_pos': self.root.winfo_x(),
            'y_pos': self.root.winfo_y(),
            'aspect_ratio': self.root.winfo_width() / self.root.winfo_height()
        }

    def do_resize(self, event):
        dx = event.x_root - self._resize_data['x']
        dy = event.y_root - self._resize_data['y']
        
        # Calculate new dimensions maintaining aspect ratio
        if abs(dx) > abs(dy):
            # Width-based resize
            new_width = max(200, self._resize_data['width'] + dx)
            new_height = int(new_width / self._resize_data['aspect_ratio'])
        else:
            # Height-based resize
            new_height = max(150, self._resize_data['height'] + dy)
            new_width = int(new_height * self._resize_data['aspect_ratio'])
        
        # Adjust position if resizing from left or top
        if event.widget == self.handle_bl or event.widget == self.handle_tl:
            new_x = self._resize_data['x_pos'] + (self._resize_data['width'] - new_width)
            self.root.geometry(f"{new_width}x{new_height}+{new_x}+{self.root.winfo_y()}")
        elif event.widget == self.handle_tr:
            new_y = self._resize_data['y_pos'] + (self._resize_data['height'] - new_height)
            self.root.geometry(f"{new_width}x{new_height}+{self.root.winfo_x()}+{new_y}")
        elif event.widget == self.handle_tl:
            new_x = self._resize_data['x_pos'] + (self._resize_data['width'] - new_width)
            new_y = self._resize_data['y_pos'] + (self._resize_data['height'] - new_height)
            self.root.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")
        else:
            self.root.geometry(f"{new_width}x{new_height}")

if __name__ == '__main__':
    root = tk.Tk()
    app = SystemOverlay(root)
    root.mainloop()