import tkinter as tk
from tkinter import colorchooser
from PIL import ImageTk, Image, ImageDraw, ImageFont
import json
import os
import time
import logging
import psutil
import pynvml
from collections import deque

logging.basicConfig(filename='system_overlay.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

TRANSPARENT = '#000001'
TRANSPARENT_RGB = (0, 0, 1)

DEFAULT_COLORS = {
    'cpu': '#93b8e8',
    'ram': '#c4aef0',
    'gpu': '#87c498',
    'gpu_temp': '#dfc77e',
    'vram': '#7cc4cc',
}


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
        if not cls.initialize():
            return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            return {
                'usage': util.gpu,
                'used_mem': mem.used / 1073741824,
                'total_mem': mem.total / 1073741824,
                'temp': temp,
            }
        except Exception:
            return None


class MetricCollector:
    def __init__(self, samples=5):
        self.buffers = {k: deque(maxlen=samples) for k in ['cpu', 'ram', 'gpu', 'temp', 'vram']}

    def _smooth(self, key, val):
        self.buffers[key].append(val)
        return sum(self.buffers[key]) / len(self.buffers[key])

    def collect(self, show_gpu=True):
        metrics = {
            'cpu': self._smooth('cpu', psutil.cpu_percent()),
            'ram': self._smooth('ram', psutil.virtual_memory().percent),
        }
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
        self.cfg = self.load_config()
        self.collector = MetricCollector(self.cfg['smoothing_samples'])

        self._lt = self._load_lifetime()
        self._lt_base_seconds = self._lt['total_seconds']
        self._lt_session_start = time.time()
        self._lt_tick = 0

        w, h = self.cfg['window_width'], self.cfg['window_height']
        sx = (root.winfo_screenwidth() - w) // 2
        sy = (root.winfo_screenheight() - h) // 2

        # Background window — its -alpha drives panel opacity.
        # Content that should fade with the background (the panel itself
        # and bar tracks) lives here.
        self.bg_win = tk.Toplevel(root)
        self.bg_win.overrideredirect(True)
        self.bg_win.attributes('-topmost', True)
        self.bg_win.attributes('-transparentcolor', TRANSPARENT)
        self.bg_win.attributes('-alpha', max(0.01, self.cfg['background_opacity']))
        self.bg_win.geometry(f'{w}x{h}+{sx}+{sy}')
        self.bg_canvas = tk.Canvas(self.bg_win, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.bg_canvas.pack(fill='both', expand=True)
        self._bg_photo = None
        self._bg_id = None

        # Content window — always fully opaque. Text, bar fills, and
        # the resize grip live here so they never fade.
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', TRANSPARENT)
        self.root.geometry(f'{w}x{h}+{sx}+{sy}')
        self.canvas = tk.Canvas(root, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)
        self._ct_photo = None
        self._ct_id = None

        self._drag_start = (0, 0)
        self._resize_base = None
        self._fonts = {}

        for c in (self.canvas, self.bg_canvas):
            c.bind('<Button-1>', self._on_click)
            c.bind('<B1-Motion>', self._on_motion)
            c.bind('<Button-3>', self._on_menu)

        self.root.bind('<Configure>',
                       lambda e: self._sync_bg() if e.widget is self.root else None)

        self.root.update_idletasks()
        self._sync_bg()
        self._loop()

    # ── Fonts ────────────────────────────────────────────────────────

    def _font(self, size, bold=False):
        key = (max(8, int(size)), bold)
        if key not in self._fonts:
            names = ['segoeuib', 'arialbd'] if bold else ['segoeui', 'arial']
            for name in names:
                for path in (name + '.ttf', f'C:/Windows/Fonts/{name}.ttf'):
                    try:
                        self._fonts[key] = ImageFont.truetype(path, key[0])
                        return self._fonts[key]
                    except OSError:
                        pass
            self._fonts[key] = ImageFont.load_default()
        return self._fonts[key]

    # ── Config ───────────────────────────────────────────────────────

    def load_config(self):
        defaults = {
            'window_width': 224, 'window_height': 224, 'update_interval': 500,
            'background_color': '#0e1113', 'background_opacity': 0.75,
            'text_color': '#e2e8f0', 'corner_radius': 14,
            'smoothing_samples': 5, 'show_gpu': True,
            'colors': dict(DEFAULT_COLORS),
            'min_width': 150, 'min_height': 120,
        }
        if os.path.exists('config.json'):
            with open('config.json') as f:
                try:
                    defaults.update(json.load(f))
                except Exception:
                    pass
        return defaults

    def _save(self):
        self.cfg['window_width'] = self.root.winfo_width()
        self.cfg['window_height'] = self.root.winfo_height()
        with open('config.json', 'w') as f:
            json.dump(self.cfg, f, indent=4)

    # ── Lifetime stats ───────────────────────────────────────────────

    def _load_lifetime(self):
        data = {'total_seconds': 0.0, 'sums': {}, 'counts': {}}
        if os.path.exists('lifetime_stats.json'):
            with open('lifetime_stats.json') as f:
                try:
                    data.update(json.load(f))
                except Exception:
                    pass
        return data

    def _save_lifetime(self):
        self._lt['total_seconds'] = self._lt_base_seconds + (time.time() - self._lt_session_start)
        try:
            with open('lifetime_stats.json', 'w') as f:
                json.dump(self._lt, f, indent=4)
        except Exception:
            pass

    def _accumulate_lifetime(self, metrics):
        for name, val in metrics.items():
            if val is not None:
                self._lt['sums'][name] = self._lt['sums'].get(name, 0.0) + val
                self._lt['counts'][name] = self._lt['counts'].get(name, 0) + 1
        self._lt_tick += 1
        if self._lt_tick >= 120:  # autosave every ~60 s
            self._save_lifetime()
            self._lt_tick = 0

    def _fmt_time(self, seconds):
        s = int(seconds)
        if s < 60:
            return f"{s}s"
        elif s < 3600:
            return f"{s // 60}m {s % 60}s"
        elif s < 86400:
            h, rem = divmod(s, 3600)
            return f"{h}h {rem // 60}m"
        else:
            d, rem = divmod(s, 86400)
            return f"{d}d {rem // 3600}h"

    def _quit(self):
        self._save_lifetime()
        self.root.destroy()

    # ── Window sync ──────────────────────────────────────────────────

    def _sync_bg(self):
        x, y = self.root.winfo_x(), self.root.winfo_y()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        self.bg_win.geometry(f'{w}x{h}+{x}+{y}')
        self.root.lift()

    # ── Input ────────────────────────────────────────────────────────

    def _on_click(self, e):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if e.x > w - 22 and e.y > h - 22:
            self._resize_base = (e.x_root, e.y_root, w, h)
        else:
            self._resize_base = None
            self._drag_start = (e.x, e.y)

    def _on_motion(self, e):
        if self._resize_base:
            dx = e.x_root - self._resize_base[0]
            dy = e.y_root - self._resize_base[1]
            nw = max(self.cfg['min_width'], int(self._resize_base[2] + dx))
            nh = max(self.cfg['min_height'], int(self._resize_base[3] + dy))
            self.root.geometry(f'{nw}x{nh}')
        else:
            x = self.root.winfo_x() + (e.x - self._drag_start[0])
            y = self.root.winfo_y() + (e.y - self._drag_start[1])
            self.root.geometry(f'+{x}+{y}')
        self._sync_bg()

    # ── Layout ───────────────────────────────────────────────────────

    def _layout(self, n, w, h):
        mx = max(12, int(w * 0.07))
        my = max(10, int(h * 0.06))
        cw = w - 2 * mx
        ch = h - 2 * my
        rh = ch / max(1, n)
        fsz = max(9, min(15, int(rh * 0.32)))
        bh = max(6, min(22, int(rh * 0.4)))
        br = max(3, bh // 2)
        gap = max(4, int(rh * 0.14))
        return mx, my, cw, rh, fsz, bh, br, gap

    # ── Rendering ────────────────────────────────────────────────────

    def _draw_bg(self, visible, w, h):
        bg_rgb = hex_to_rgb(self.cfg['background_color'])
        radius = self.cfg.get('corner_radius', 14)

        img = Image.new('RGB', (w, h), TRANSPARENT_RGB)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=bg_rgb)

        if visible:
            mx, my, cw, rh, fsz, bh, br, gap = self._layout(len(visible), w, h)
            track_rgb = tuple(min(255, c + 18) for c in bg_rgb)
            y = my
            for _ in visible:
                bar_y = y + fsz + gap
                draw.rounded_rectangle([mx, bar_y, mx + cw, bar_y + bh],
                                       radius=br, fill=track_rgb)
                y += rh

        self._bg_photo = ImageTk.PhotoImage(img)
        if self._bg_id:
            self.bg_canvas.itemconfig(self._bg_id, image=self._bg_photo)
        else:
            self._bg_id = self.bg_canvas.create_image(0, 0, image=self._bg_photo, anchor='nw')

    def _draw_content(self, visible, w, h):
        text_rgb = hex_to_rgb(self.cfg['text_color'])
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if visible:
            mx, my, cw, rh, fsz, bh, br, gap = self._layout(len(visible), w, h)
            font = self._font(fsz, bold=True)

            y = my
            for name, val in visible:
                pct = min(1.0, val / 100.0)
                if name == 'gpu_temp':
                    label, val_str = 'TEMP', f'{val:.0f}°C'
                else:
                    label, val_str = name.upper(), f'{val:.1f}%'

                draw.text((mx, y), label, fill=(*text_rgb, 255), font=font)
                bb = draw.textbbox((0, 0), val_str, font=font)
                draw.text((w - mx - (bb[2] - bb[0]), y), val_str,
                          fill=(*text_rgb, 255), font=font)

                bar_y = y + fsz + gap
                fill_w = max(0, int(pct * cw))
                if fill_w > 0:
                    bar_rgb = hex_to_rgb(
                        self.cfg.get('colors', {}).get(name, '#3b82f6'))
                    draw.rounded_rectangle(
                        [mx, bar_y, mx + fill_w, bar_y + bh],
                        radius=br, fill=(*bar_rgb, 255))

                y += rh

        for gx in range(3):
            for gy in range(3):
                if gx + gy >= 2:
                    cx, cy = w - 7 - gx * 5, h - 7 - gy * 5
                    draw.ellipse([cx - 1, cy - 1, cx + 1, cy + 1],
                                 fill=(*text_rgb, 100))

        final = Image.new('RGB', (w, h), TRANSPARENT_RGB)
        final.paste(img, mask=img.split()[3])
        self._ct_photo = ImageTk.PhotoImage(final)
        if self._ct_id:
            self.canvas.itemconfig(self._ct_id, image=self._ct_photo)
        else:
            self._ct_id = self.canvas.create_image(0, 0, image=self._ct_photo, anchor='nw')

    # ── Main loop ────────────────────────────────────────────────────

    def _loop(self):
        metrics = self.collector.collect(self.cfg['show_gpu'])
        visible = [(n, v) for n, v in metrics.items() if v is not None]
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if w >= 10 and h >= 10:
            self._draw_bg(visible, w, h)
            self._draw_content(visible, w, h)
        self._accumulate_lifetime(metrics)
        self.root.after(self.cfg['update_interval'], self._loop)

    # ── Menu / Settings ──────────────────────────────────────────────

    def _on_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label='Settings', command=self._open_settings)
        m.add_separator()
        m.add_command(label='Exit', command=self._quit)
        m.post(e.x_root, e.y_root)

    def _open_settings(self):
        sw = tk.Toplevel(self.root)
        sw.title('Overlay Settings')
        sw.attributes('-topmost', True)
        sw.geometry('280x620')
        sw.configure(bg='#16192e')
        sw.resizable(False, False)

        f = tk.Frame(sw, bg='#16192e', padx=16, pady=12)
        f.pack(fill='both', expand=True)

        def heading(text):
            tk.Label(f, text=text, font=('Segoe UI', 10, 'bold'),
                     fg='#94a3b8', bg='#16192e').pack(anchor='w', pady=(10, 4))

        def color_btn(text, cmd):
            tk.Button(f, text=text, font=('Segoe UI', 9), fg='#e2e8f0',
                      bg='#1e293b', activebackground='#334155',
                      activeforeground='#e2e8f0', bd=0, padx=10, pady=5,
                      cursor='hand2', command=cmd).pack(fill='x', pady=2)

        def pick(key, nested=None):
            c = colorchooser.askcolor()[1]
            if not c:
                return
            if nested:
                self.cfg.setdefault(nested, {})[key] = c
            else:
                self.cfg[key] = c
            self._save()

        heading('Opacity')
        s = tk.Scale(f, from_=0.0, to=1.0, resolution=0.01, orient='horizontal',
                     bg='#16192e', fg='#e2e8f0', troughcolor='#1e293b',
                     highlightthickness=0, bd=0, sliderrelief='flat',
                     command=self._set_opacity)
        s.set(self.cfg['background_opacity'])
        s.pack(fill='x', pady=(0, 5))

        heading('Colors')
        color_btn('Background', lambda: pick('background_color'))
        color_btn('Text', lambda: pick('text_color'))

        heading('Metric Colors')
        for mkey, label in [('cpu', 'CPU'), ('ram', 'RAM'), ('gpu', 'GPU'),
                            ('gpu_temp', 'Temperature'), ('vram', 'VRAM')]:
            color_btn(f'  {label}', lambda k=mkey: pick(k, 'colors'))

        heading('Lifetime Stats')

        total_secs = self._lt_base_seconds + (time.time() - self._lt_session_start)

        sf = tk.Frame(f, bg='#1e293b', padx=10, pady=8)
        sf.pack(fill='x', pady=(0, 4))
        sf.columnconfigure(1, weight=1)

        rows = [('Time monitored', self._fmt_time(total_secs))]
        for name, lbl in [('cpu', 'CPU'), ('ram', 'RAM'), ('gpu', 'GPU'),
                           ('gpu_temp', 'Temp'), ('vram', 'VRAM')]:
            count = self._lt['counts'].get(name, 0)
            if count:
                avg = self._lt['sums'][name] / count
                val_str = f'{avg:.0f}°C' if name == 'gpu_temp' else f'{avg:.1f}%'
                rows.append((f'{lbl} avg', val_str))

        for i, (lbl, val) in enumerate(rows):
            tk.Label(sf, text=lbl, font=('Segoe UI', 9), fg='#64748b',
                     bg='#1e293b', anchor='w').grid(row=i, column=0, sticky='w', pady=2)
            tk.Label(sf, text=val, font=('Segoe UI', 9, 'bold'), fg='#e2e8f0',
                     bg='#1e293b', anchor='e').grid(row=i, column=1, sticky='e', pady=2)

    def _set_opacity(self, val):
        v = float(val)
        self.cfg['background_opacity'] = v
        self.bg_win.attributes('-alpha', max(0.01, v))
        self._save()


if __name__ == '__main__':
    root = tk.Tk()
    app = OverlayApp(root)
    root.mainloop()
