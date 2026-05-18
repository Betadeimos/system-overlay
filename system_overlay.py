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
        if not cls.initialize(): return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            return {'usage': util.gpu, 'used_mem': mem.used / (1024**3), 'total_mem': mem.total / (1024**3), 'temp': temp}
        except Exception: return None

class MetricCollector:
    def __init__(self, samples=5):
        self.buffers = {k: deque(maxlen=samples) for k in ['cpu', 'ram', 'gpu', 'temp', 'vram']}
    def _smooth(self, key, val):
        self.buffers[key].append(val)
        return sum(self.buffers[key]) / len(self.buffers[key])
    def collect(self, show_gpu=True):
        metrics = {'cpu': self._smooth('cpu', psutil.cpu_percent()), 'ram': self._smooth('ram', psutil.virtual_memory().percent)}
        if show_gpu:
            info = GPUManager.get_info()
            if info:
                metrics['gpu'] = self._smooth('gpu', info['usage'])
                metrics['gpu_temp'] = self._smooth('temp', info['temp'])
                metrics['vram'] = self._smooth('vram', (info['used_mem'] / info['total_mem']) * 100)
        return metrics

class OverlayApp:
    def __init__(self, root):
        self.root = root
        self.config = self.load_config()
        self.collector = MetricCollector(self.config['smoothing_samples'])
        
        # Window Setup
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', '#000001') # This color will be invisible
        self.root.geometry(f"{self.config['window_width']}x{self.config['window_height']}")
        
        # Main Canvas
        self.canvas = tk.Canvas(root, bg='#000001', highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # State
        self.bg_photo = None
        self.bg_id = None
        self.metric_ui = {}
        self.drag_start = (0, 0)
        
        # UI Elements
        self.setup_bindings()
        self.draw_ui()
        self.update_loop()

    def load_config(self):
        default = {
            'window_width': 180, 'window_height': 175, 'update_interval': 500,
            'background_color': '#0e1113', 'background_opacity': 0.8,
            'bar_color': '#34434f', 'text_color': '#eeeeee',
            'corner_radius': 14, 'smoothing_samples': 5, 'show_gpu': True
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

    def setup_bindings(self):
        self.canvas.bind('<Button-1>', lambda e: setattr(self, 'drag_start', (e.x, e.y)))
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<Button-3>', self.show_menu)
        self.root.bind('<Configure>', lambda e: self.draw_background())

    def on_drag(self, e):
        x = self.root.winfo_x() + (e.x - self.drag_start[0])
        y = self.root.winfo_y() + (e.y - self.drag_start[1])
        self.root.geometry(f"+{x}+{y}")

    def draw_background(self):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if w < 10 or h < 10: return
        
        # Create image with transparency
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        rgb = hex_to_rgb(self.config['background_color'])
        alpha = int(255 * self.config['background_opacity'])
        
        draw.rounded_rectangle([0, 0, w, h], radius=self.config['corner_radius'], fill=(*rgb, alpha))
        
        self.bg_photo = ImageTk.PhotoImage(img)
        if self.bg_id: self.canvas.delete(self.bg_id)
        self.bg_id = self.canvas.create_image(0, 0, image=self.bg_photo, anchor='nw')
        self.canvas.tag_lower(self.bg_id)

    def draw_ui(self):
        # Initial background draw
        self.root.update_idletasks()
        self.draw_background()
        
        # Resize Handle (Visual Only, Logic in separate binding for stability)
        self.resize_marker = self.canvas.create_oval(0, 0, 0, 0, fill="#333333", outline="", tags="resize")
        self.canvas.tag_bind("resize", "<Button-1>", self.start_resize)
        self.canvas.tag_bind("resize", "<B1-Motion>", self.do_resize)
        self.update_resize_handle_pos()

    def update_resize_handle_pos(self):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        self.canvas.coords(self.resize_marker, w-15, h-15, w-5, h-5)

    def start_resize(self, e):
        self.resizing = True
        self.resize_base = (e.x_root, e.y_root, self.root.winfo_width(), self.root.winfo_height())
    
    def do_resize(self, e):
        dx, dy = e.x_root - self.resize_base[0], e.y_root - self.resize_base[1]
        nw, nh = max(130, self.resize_base[2] + dx), max(130, self.resize_base[3] + dy)
        self.root.geometry(f"{nw}x{nh}")
        self.update_resize_handle_pos()

    def update_loop(self):
        metrics = self.collector.collect(self.config['show_gpu'])
        self.render_metrics(metrics)
        self.root.after(self.config['update_interval'], self.update_loop)

    def render_metrics(self, metrics):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        padding = 15
        y = 15
        spacing = (h - 2*padding) / len([m for m in metrics.values() if m is not None])
        bar_h = max(4, int(spacing * 0.4))
        font_sz = max(8, int(h / 20))
        
        for name, val in metrics.items():
            if val is None: continue
            
            label = f"{name.upper()}: {val:.1f}%"
            if name == 'gpu_temp': label = f"TEMP: {val:.1f}°C"
            
            self._update_metric_item(name, y, val, bar_h, w - 2*padding, label, font_sz)
            y += spacing

    def _update_metric_item(self, name, y, pct, h, max_w, txt, font_sz):
        bar_w = max(2, int((pct/100) * max_w))
        
        if name not in self.metric_ui:
            # Note: We use the canvas bg color #000001 for "invisible" areas, 
            # but Tkinter doesn't support per-item alpha. 
            # To keep text/bars opaque while BG is transparent, we draw them normally.
            self.metric_ui[name] = {
                'bar_bg': self.canvas.create_rectangle(15, y+font_sz+5, 15+max_w, y+font_sz+5+h, fill="#222222", outline=""),
                'bar': self.canvas.create_rectangle(15, y+font_sz+5, 15+bar_w, y+font_sz+5+h, fill=self.config['bar_color'], outline=""),
                'text': self.canvas.create_text(15, y, text=txt, anchor='nw', fill=self.config['text_color'], font=('Arial', font_sz, 'bold'))
            }
        else:
            item = self.metric_ui[name]
            self.canvas.coords(item['bar_bg'], 15, y+font_sz+5, 15+max_w, y+font_sz+5+h)
            self.canvas.coords(item['bar'], 15, y+font_sz+5, 15+bar_w, y+font_sz+5+h)
            self.canvas.coords(item['text'], 15, y)
            self.canvas.itemconfig(item['text'], text=txt, font=('Arial', font_sz, 'bold'), fill=self.config['text_color'])
            self.canvas.itemconfig(item['bar'], fill=self.config['bar_color'])

    def show_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Settings", command=self.open_settings)
        m.add_separator()
        m.add_command(label="Exit", command=self.root.destroy)
        m.post(e.x_root, e.y_root)

    def open_settings(self):
        swin = tk.Toplevel(self.root)
        swin.title("Settings")
        swin.attributes('-topmost', True)
        
        def set_color(target):
            c = colorchooser.askcolor()[1]
            if c:
                if target == 'bg': self.config['background_color'] = c
                elif target == 'bar': self.config['bar_color'] = c
                elif target == 'text': self.config['text_color'] = c
                self.draw_background()
                self.save_config()

        ttk.Button(swin, text="Background Color", command=lambda: set_color('bg')).pack(pady=5, padx=10)
        ttk.Button(swin, text="Bar Color", command=lambda: set_color('bar')).pack(pady=5, padx=10)
        ttk.Button(swin, text="Text Color", command=lambda: set_color('text')).pack(pady=5, padx=10)
        
        tk.Label(swin, text="Background Opacity").pack()
        op_scale = ttk.Scale(swin, from_=0.0, to=1.0, value=self.config['background_opacity'],
                            command=lambda v: self.update_opacity(v))
        op_scale.pack(fill='x', padx=10)

    def update_opacity(self, val):
        self.config['background_opacity'] = float(val)
        self.draw_background()
        self.save_config()

if __name__ == '__main__':
    root = tk.Tk()
    app = OverlayApp(root)
    root.mainloop()
