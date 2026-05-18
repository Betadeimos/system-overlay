import tkinter as tk
from tkinter import ttk, colorchooser
from PIL import ImageTk, Image, ImageDraw
import json
import os
import logging
import psutil
import pynvml
from collections import deque

# --- Setup Logging ---
logging.basicConfig(filename='system_overlay.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

class GPUManager:
    """Manages NVML initialization and data retrieval to avoid redundant overhead."""
    _initialized = False
    _gpu_available = False

    @classmethod
    def initialize(cls):
        if not cls._initialized:
            try:
                pynvml.nvmlInit()
                cls._gpu_available = True
            except Exception as e:
                logging.error(f"Failed to initialize NVML: {e}")
            cls._initialized = True
        return cls._gpu_available

    @classmethod
    def get_info(cls):
        if not cls.initialize():
            return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            return {
                'usage': utilization.gpu,
                'used_mem': memory.used / (1024 ** 3),
                'total_mem': memory.total / (1024 ** 3),
                'temp': temp
            }
        except Exception as e:
            logging.error(f"Error getting GPU info: {e}")
            return None

class MetricCollector:
    """Handles smoothed metric collection."""
    def __init__(self, samples=5):
        self.samples = samples
        self.buffers = {
            'cpu': deque(maxlen=samples),
            'ram': deque(maxlen=samples),
            'gpu': deque(maxlen=samples),
            'temp': deque(maxlen=samples),
            'vram': deque(maxlen=samples)
        }

    def _smooth(self, key, value):
        self.buffers[key].append(value)
        return sum(self.buffers[key]) / len(self.buffers[key])

    def collect(self, show_gpu=True):
        metrics = {
            'cpu': self._smooth('cpu', psutil.cpu_percent()),
            'ram': self._smooth('ram', psutil.virtual_memory().percent)
        }
        
        if show_gpu:
            gpu_info = GPUManager.get_info()
            if gpu_info:
                metrics['gpu'] = self._smooth('gpu', gpu_info['usage'])
                metrics['gpu_temp'] = self._smooth('temp', gpu_info['temp'])
                vram_p = (gpu_info['used_mem'] / gpu_info['total_mem']) * 100
                metrics['vram'] = self._smooth('vram', vram_p)
            else:
                metrics.update({'gpu': None, 'gpu_temp': None, 'vram': None})
        return metrics

class OverlayUI:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.canvas = tk.Canvas(self.root, bg='#000001', highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.bg_image_id = None
        self.bg_photo = None
        self.metric_items = {} # Stores canvas IDs: {name: {'bar': id, 'text': id}}
        self._last_size = (0, 0)
        
    def update_background(self):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if (w, h) == self._last_size or w < 2 or h < 2: return
        self._last_size = (w, h)
        
        rgb = hex_to_rgb(self.config['background_color'])
        alpha = int(255 * self.config['background_opacity'])
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([(0, 0), (w-1, h-1)], radius=self.config['window_corner_radius'], fill=(*rgb, alpha))
        
        self.bg_photo = ImageTk.PhotoImage(img)
        if self.bg_image_id:
            self.canvas.itemconfig(self.bg_image_id, image=self.bg_photo)
        else:
            self.bg_image_id = self.canvas.create_image(0, 0, image=self.bg_photo, anchor='nw', tags='bg')
        self.canvas.tag_lower('bg')

    def render_metrics(self, metrics):
        padding = 10
        y = padding
        w = self.root.winfo_width()
        spacing = int(self.config['vertical_spacing'] * (self.root.winfo_height() / 220) ** 1.06)
        bar_h = max(1, int(self.config['bar_height'] * (self.root.winfo_height() / 220) ** 1.06))
        font_size = max(8, int(self.config['base_font_size'] * ((w * self.root.winfo_height()) / 55000) ** 0.55))

        for name, val in metrics.items():
            if val is None: continue
            
            label = f"{name.upper().replace('_', ' ')}: {val:.1f}%"
            if name == 'gpu_temp': label = f"GPU TEMP: {val:.1f}°C"
            
            self._draw_metric(name, y, val, bar_h, w - 2*padding, label, font_size)
            y += spacing

    def _draw_metric(self, name, y, percent, h, max_w, label, font_size):
        bar_w = max(1, int((percent / 100) * max_w))
        color = self.config['colors'].get(name, self.config['colors']['cpu'])
        
        if name not in self.metric_items:
            self.metric_items[name] = {
                'bar': self.canvas.create_rectangle(10, y, 10 + bar_w, y + h, fill=color, outline=""),
                'text': self.canvas.create_text(15, y + h/2, text=label, anchor='w', fill='#eeeeee', font=('Arial', font_size))
            }
        else:
            self.canvas.coords(self.metric_items[name]['bar'], 10, y, 10 + bar_w, y + h)
            self.canvas.itemconfig(self.metric_items[name]['bar'], fill=color)
            self.canvas.itemconfig(self.metric_items[name]['text'], text=label, font=('Arial', font_size))
            self.canvas.coords(self.metric_items[name]['text'], 15, y + h/2)

class EventHandler:
    def __init__(self, root, ui, config, save_callback):
        self.root = root
        self.ui = ui
        self.config = config
        self.save_callback = save_callback
        self._drag_data = {'x': 0, 'y': 0}
        self._resize_data = {}
        
        self.ui.canvas.bind('<Button-1>', self.start_drag)
        self.ui.canvas.bind('<B1-Motion>', self.do_drag)
        self.ui.canvas.bind('<Button-3>', self.show_menu)
        
        self.resize_handle = tk.Canvas(root, width=15, height=15, bg='#000001', highlightthickness=0)
        self.resize_handle.place(relx=1, rely=1, anchor='se', x=-5, y=-5)
        self.resize_handle.bind('<Button-1>', self.start_resize)
        self.resize_handle.bind('<B1-Motion>', self.do_resize)

    def start_drag(self, e): self._drag_data = {'x': e.x, 'y': e.y}
    def do_drag(self, e):
        self.root.geometry(f"+{self.root.winfo_x() + e.x - self._drag_data['x']}+{self.root.winfo_y() + e.y - self._drag_data['y']}")

    def show_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Settings", command=self.open_settings)
        m.add_command(label="Close", command=self.root.destroy)
        m.post(e.x_root, e.y_root)

    def start_resize(self, e):
        self._resize_data = {'x': e.x_root, 'y': e.y_root, 'w': self.root.winfo_width(), 'h': self.root.winfo_height()}
    
    def do_resize(self, e):
        nw = max(130, self._resize_data['w'] + (e.x_root - self._resize_data['x']))
        nh = max(130, self._resize_data['h'] + (e.y_root - self._resize_data['y']))
        self.root.geometry(f"{nw}x{nh}")
        self.ui.update_background()

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.attributes('-topmost', True)
        
        def pick_color(key):
            c = colorchooser.askcolor(color=self.config['colors'].get(key, self.config['text_color']))[1]
            if c:
                if key == 'bg': self.config['background_color'] = c
                else: 
                    for k in self.config['colors']: self.config['colors'][k] = c
                self.ui.update_background()
                self.save_callback()

        ttk.Button(win, text="Text/Bar Color", command=lambda: pick_color('cpu')).pack(pady=5)
        ttk.Button(win, text="Background Color", command=lambda: pick_color('bg')).pack(pady=5)
        
        s = ttk.Scale(win, from_=0.1, to=1.0, value=self.config['background_opacity'], 
                      command=lambda v: [self.config.__setitem__('background_opacity', float(v)), 
                                         self.root.attributes('-alpha', float(v)),
                                         self.ui.update_background(), self.save_callback()])
        s.pack(pady=5, padx=10, fill='x')

class SystemOverlay:
    def __init__(self, root):
        self.root = root
        self.config = self.load_config()
        
        root.overrideredirect(True)
        root.attributes('-topmost', True, '-alpha', self.config['background_opacity'], '-transparentcolor', '#000001')
        root.geometry(f"{self.config['window_width']}x{self.config['window_height']}")
        
        self.collector = MetricCollector(self.config['smoothing_samples'])
        self.ui = OverlayUI(root, self.config)
        self.handler = EventHandler(root, self.ui, self.config, self.save_config)
        
        GPUManager.initialize()
        self.update()

    def load_config(self):
        default = {
            'base_font_size': 18, 'text_color': '#eeeeee', 'background_color': '#0e1113',
            'window_width': 180, 'window_height': 175, 'update_interval': 500,
            'show_cpu': True, 'show_memory': True, 'show_gpu': True, 'background_opacity': 0.9,
            'bar_height': 30, 'vertical_spacing': 43, 'window_corner_radius': 14,
            'colors': {k: '#34434f' for k in ['cpu', 'ram', 'gpu', 'gpu_temp', 'vram']},
            'smoothing_samples': 5
        }
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                try: default.update(json.load(f))
                except: pass
        return default

    def save_config(self):
        self.config['window_width'] = self.root.winfo_width()
        self.config['window_height'] = self.root.winfo_height()
        with open("config.json", "w") as f: json.dump(self.config, f, indent=4)

    def update(self):
        metrics = self.collector.collect(self.config['show_gpu'])
        self.ui.render_metrics(metrics)
        self.root.after(self.config['update_interval'], self.update)

if __name__ == '__main__':
    root = tk.Tk()
    app = SystemOverlay(root)
    root.mainloop()
