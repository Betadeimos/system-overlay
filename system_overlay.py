# system_overlay.py
import tkinter as tk
from tkinter import colorchooser
import psutil
import pynvml
from collections import deque
from PIL import ImageTk, Image, ImageDraw

# Configuration Settings
DEFAULT_CONFIG = {
    'base_font_size': 18,
    'text_color': '#eeeeee',
    'background_color': '#0e1113',
    'window_width': 180,
    'window_height': 175,
    'update_interval': 500,  # in ms
    'show_cpu': True,
    'show_memory': True,
    'show_gpu': True,
    'background_opacity': 0.9,
    'bar_height': 30,
    'bar_padding': 5,
    # Default bars colors for each metric (will be overwritten by a single “bars color” setting)
    'colors': {
        'cpu': '#34434f',
        'ram': '#34434f',
        'gpu': '#34434f',
        'gpu_temp': '#34434f',
        'vram': '#34434f'
    },
    'smoothing_samples': 5,
    'vertical_spacing': 43,
    'top_margin': 5,
    'bottom_margin': 5,
    'bar_corner_radius': 4,
    'window_corner_radius': 14
}


def hex_to_rgb(hex_color):
    """Convert a hex color string (e.g. '#FF00AA') to an (R, G, B) tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        raise ValueError("Invalid hex color format")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


class SystemOverlay:
    def __init__(self, root):
        self._config = DEFAULT_CONFIG.copy()
        self.root = root

        # Calculate center position for initial placement
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - self._config['window_width']) // 2
        y = (screen_height - self._config['window_height']) // 2

        # Set window geometry and attributes
        self.root.geometry(f"{self._config['window_width']}x{self._config['window_height']}+{x}+{y}")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', self._config['background_opacity'])
        # We use a magic transparent color (which should not be used elsewhere)
        self.root.attributes('-transparentcolor', '#000001')
        self.root.configure(bg='#000001')

        # Create main canvas
        self.canvas = tk.Canvas(
            self.root,
            bg='#000001',
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Variables to store the background image and its canvas ID
        self.bg_image = None
        self.bg_image_id = None
        self._last_bg_size = (0, 0)

        # Force an initial idle update so that geometry is available, then update background.
        self.root.update_idletasks()
        self.update_background()

        # Bind the <Configure> event to update the background when the window size changes.
        self.root.bind("<Configure>", self.on_configure)

        # Initialize GPU monitoring
        self.setup_gpu()

        # Setup resize handle and drag functionality
        self.setup_resize_handles()
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
            'cpu': {'bar': None, 'bar_image': None, 'text': None},
            'ram': {'bar': None, 'bar_image': None, 'text': None},
            'gpu': {'bar': None, 'bar_image': None, 'text': None},
            'gpu_temp': {'bar': None, 'bar_image': None, 'text': None},
            'vram': {'bar': None, 'bar_image': None, 'text': None}
        }

        # Start system info updates every update_interval ms.
        self.update_system_info()

    def on_configure(self, event):
        """Called when the window is resized or moved."""
        new_size = (self.root.winfo_width(), self.root.winfo_height())
        if new_size != self._last_bg_size:
            self.update_background()
            self._last_bg_size = new_size

    def update_background(self):
        """Create or update the rounded background using the current background color and opacity."""
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        if width < 2 or height < 2:
            return  # Skip if the size is too small

        # Convert the background hex color to RGB.
        rgb = hex_to_rgb(self._config['background_color'])
        alpha = int(255 * self._config['background_opacity'])

        # Create a new image with transparency (the transparent color is #000001)
        image = Image.new('RGBA', (width, height), (0, 0, 1, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            [(0, 0), (width - 1, height - 1)],
            radius=self._config['window_corner_radius'],
            fill=(rgb[0], rgb[1], rgb[2], alpha)
        )

        # Convert to a PhotoImage for Tkinter and keep a reference.
        self.bg_image = ImageTk.PhotoImage(image)

        # Update or create the canvas image item for the background.
        if self.bg_image_id is not None:
            self.canvas.itemconfig(self.bg_image_id, image=self.bg_image)
        else:
            self.bg_image_id = self.canvas.create_image(
                0, 0,
                image=self.bg_image,
                anchor='nw',
                tags='background'
            )
        self.canvas.tag_lower('background')

    def setup_gpu(self):
        self.gpu_available = False
        try:
            pynvml.nvmlInit()
            self.gpu_available = True
        except Exception:
            pass

    def get_gpu_info(self):
        if self.gpu_available:
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
            except Exception:
                return None
        return None

    def calculate_vertical_spacing(self):
        base_height = 220
        return int(self._config['vertical_spacing'] * (self.root.winfo_height() / base_height) ** 1.06)

    def get_smoothed_value(self, buffer, new_value):
        buffer.append(new_value)
        return sum(buffer) / len(buffer)

    def update_system_info(self):
        padding = 10
        y_position = padding
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

        # GPU (if available)
        if self._config['show_gpu'] and self.gpu_available:
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

        # Schedule the next update
        self.root.after(self._config['update_interval'], self.update_system_info)

    def create_metric_bar(self, y_pos, value_percent, color, text, metric_name):
        padding = 10
        height = max(1, int(self._config['bar_height'] * (self.root.winfo_height() / 220) ** 1.06))
        available_width = max(1, self.root.winfo_width() - (padding * 2))
        bar_width = max(1, int((value_percent / 100.0) * available_width))
        font_size = self.calculate_font_size()

        # Remove any previous bar image if it exists.
        if self.metric_items[metric_name]['bar']:
            self.canvas.delete(self.metric_items[metric_name]['bar'])

        # Create a new bar image with rounded corners.
        bar_image = Image.new('RGBA', (bar_width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(bar_image)
        draw.rounded_rectangle(
            [(0, 0), (bar_width - 1, height - 1)],
            radius=min(self._config['bar_corner_radius'], height // 2, bar_width // 2),
            fill=color
        )

        self.metric_items[metric_name]['bar_image'] = ImageTk.PhotoImage(bar_image)
        self.metric_items[metric_name]['bar'] = self.canvas.create_image(
            padding, y_pos,
            image=self.metric_items[metric_name]['bar_image'],
            anchor='nw',
            tags='bar'
        )

        # Remove the previous text if it exists.
        if self.metric_items[metric_name]['text']:
            self.canvas.delete(self.metric_items[metric_name]['text'])

        # Draw the text on top of the bar.
        self.metric_items[metric_name]['text'] = self.canvas.create_text(
            padding + 5, y_pos + (height / 2),
            text=text, anchor='w', fill=self._config['text_color'],
            font=('Arial', font_size),
            tags='text'
        )
        self.canvas.tag_raise('text')

    def calculate_font_size(self):
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        base_size = self._config['base_font_size']
        area = width * height
        scale_factor = (area / (250 * 220)) ** 0.55
        return max(8, int(base_size * scale_factor))

    def start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def do_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_start_x
        y = self.root.winfo_y() + event.y - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Settings", command=self.open_settings)
        menu.add_command(label="Close", command=self.root.destroy)
        menu.post(event.x_root, event.y_root)

    def open_settings(self):
        """Open a settings window with options to change text color, bars color, background color, and transparency."""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.geometry("350x250")
        settings_win.attributes('-topmost', True)

        # Text Color Setting
        text_frame = tk.Frame(settings_win)
        text_frame.pack(pady=5, fill=tk.X, padx=10)
        tk.Label(text_frame, text="Text Color:").pack(side=tk.LEFT)
        text_color_btn = tk.Button(text_frame, text="Select", command=lambda: self.select_color('text'))
        text_color_btn.pack(side=tk.RIGHT)

        # Bars Color Setting
        bars_frame = tk.Frame(settings_win)
        bars_frame.pack(pady=5, fill=tk.X, padx=10)
        tk.Label(bars_frame, text="Bars Color:").pack(side=tk.LEFT)
        bars_color_btn = tk.Button(bars_frame, text="Select", command=lambda: self.select_color('bars'))
        bars_color_btn.pack(side=tk.RIGHT)

        # Background Color Setting
        bg_frame = tk.Frame(settings_win)
        bg_frame.pack(pady=5, fill=tk.X, padx=10)
        tk.Label(bg_frame, text="Background Color:").pack(side=tk.LEFT)
        bg_color_btn = tk.Button(bg_frame, text="Select", command=lambda: self.select_color('background'))
        bg_color_btn.pack(side=tk.RIGHT)

        # Background Transparency Setting
        trans_frame = tk.Frame(settings_win)
        trans_frame.pack(pady=5, fill=tk.X, padx=10)
        tk.Label(trans_frame, text="Background Transparency:").pack(side=tk.LEFT)
        transparency_scale = tk.Scale(trans_frame, from_=0, to=1, resolution=0.05, orient=tk.HORIZONTAL,
                                      command=self.update_transparency)
        transparency_scale.set(self._config['background_opacity'])
        transparency_scale.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def select_color(self, target):
        """Opens a color chooser and updates the target setting."""
        if target == 'text':
            init_color = self._config['text_color']
        elif target == 'bars':
            # Use the current CPU bar color as representative.
            init_color = self._config['colors']['cpu']
        elif target == 'background':
            init_color = self._config['background_color']
        else:
            return

        color = colorchooser.askcolor(color=init_color, title=f"Select {target.capitalize()} Color")
        if color[1] is not None:
            if target == 'text':
                self._config['text_color'] = color[1]
            elif target == 'bars':
                # Update all bars colors with the chosen color.
                for key in self._config['colors']:
                    self._config['colors'][key] = color[1]
            elif target == 'background':
                self._config['background_color'] = color[1]
                self.update_background()

    def update_transparency(self, value):
        """Update the background transparency and the window alpha."""
        try:
            val = float(value)
        except ValueError:
            return
        self._config['background_opacity'] = val
        self.root.attributes('-alpha', self._config['background_opacity'])
        self.update_background()

    def setup_resize_handles(self):
        # Create a small resize handle at the bottom-right corner.
        self.handle_br = tk.Frame(
            self.root,
            bg='#505050',
            cursor='sizing'
        )
        self.handle_br.configure(width=6, height=6)
        self.handle_br.place(relx=1, rely=1, anchor='se')
        self.handle_br.pack_propagate(False)
        self.handle_br.bind('<Button-1>', self.start_resize)
        self.handle_br.bind('<B1-Motion>', self.do_resize)

    def start_resize(self, event):
        self._resize_data = {
            'x': event.x_root,
            'y': event.y_root,
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'aspect_ratio': self.root.winfo_width() / self.root.winfo_height()
        }

    def do_resize(self, event):
        dx = event.x_root - self._resize_data['x']
        dy = event.y_root - self._resize_data['y']

        if abs(dx) > abs(dy):
            new_width = max(200, self._resize_data['width'] + dx)
            new_height = int(new_width / self._resize_data['aspect_ratio'])
        else:
            new_height = max(150, self._resize_data['height'] + dy)
            new_width = int(new_height * self._resize_data['aspect_ratio'])

        # Update window geometry and canvas size.
        self.root.geometry(f"{new_width}x{new_height}")
        self.canvas.config(width=new_width, height=new_height)
        self.update_background()


if __name__ == '__main__':
    root = tk.Tk()
    app = SystemOverlay(root)
    root.mainloop()
