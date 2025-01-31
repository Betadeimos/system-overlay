# resize works, bars move, colors are fixed, font doesnt resize with window

import tkinter as tk
from tkinter import ttk
import psutil
import pynvml

class SystemOverlay:
    def __init__(self, root):
        self.root = root
        self.root.geometry("200x190")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.8)  # Set overall window transparency
        
        # Configure colors without alpha (we'll use window-level transparency instead)
        self.colors = {
            'background': '#000000',  # Black
            'cpu': '#1a9850',        # Green
            'ram': '#91cf60',        # Olive green
            'gpu': '#d9ef8b',        # Gold
            'gpu_temp': '#91cf60',   # Olive green
            'vram': '#d73027'        # Burgundy
        }
        
        # Create main frame
        self.frame = tk.Frame(
            self.root,
            bg=self.colors['background']
        )
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas for metrics
        self.canvas = tk.Canvas(
            self.frame,
            bg=self.colors['background'],
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Initialize GPU monitoring
        try:
            pynvml.nvmlInit()
            self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.gpu_available = True
        except:
            self.gpu_available = False
        
        # Setup resize handles
        self.setup_resize_handles()
        
        # Setup drag functionality
        self.canvas.bind('<Button-1>', self.start_drag)
        self.canvas.bind('<B1-Motion>', self.do_drag)
        self.canvas.bind('<Button-3>', self.show_context_menu)
        
        # Start updates
        self.update_system_info()

    def setup_resize_handles(self):
        handle_size = 8
        
        # Bottom-right handle
        self.handle_br = tk.Frame(self.root, width=handle_size, height=handle_size, 
                                bg=self.colors['background'], cursor='bottom_right_corner')
        self.handle_br.place(relx=1.0, rely=1.0, anchor='se')
        self.handle_br.bind('<Button-1>', self.start_resize)
        self.handle_br.bind('<B1-Motion>', self.do_resize)

        # Bottom-left handle
        self.handle_bl = tk.Frame(self.root, width=handle_size, height=handle_size,
                                bg=self.colors['background'], cursor='bottom_left_corner')
        self.handle_bl.place(relx=0.0, rely=1.0, anchor='sw')
        self.handle_bl.bind('<Button-1>', self.start_resize)
        self.handle_bl.bind('<B1-Motion>', self.do_resize)

        # Top-right handle
        self.handle_tr = tk.Frame(self.root, width=handle_size, height=handle_size,
                                bg=self.colors['background'], cursor='top_right_corner')
        self.handle_tr.place(relx=1.0, rely=0.0, anchor='ne')
        self.handle_tr.bind('<Button-1>', self.start_resize)
        self.handle_tr.bind('<B1-Motion>', self.do_resize)

        # Top-left handle
        self.handle_tl = tk.Frame(self.root, width=handle_size, height=handle_size,
                                bg=self.colors['background'], cursor='top_left_corner')
        self.handle_tl.place(relx=0.0, rely=0.0, anchor='nw')
        self.handle_tl.bind('<Button-1>', self.start_resize)
        self.handle_tl.bind('<B1-Motion>', self.do_resize)

    def create_metric_bar(self, y_pos, width_percent, color, text):
        # Bar height and padding
        height = 30
        padding = 5
        
        # Create background bar
        bar_width = (width_percent / 100.0) * (self.root.winfo_width() - 20)
        self.canvas.create_rectangle(
            10, y_pos,
            10 + bar_width, y_pos + height,
            fill=color,
            outline=""  # Remove border for clean look
        )
        
        # Create text
        self.canvas.create_text(
            15, y_pos + height/2,
            text=text,
            fill='white',
            anchor='w',
            font=('Arial', 12, 'bold')
        )

    def update_system_info(self):
        # Clear canvas
        self.canvas.delete("all")
        
        # Update metrics
        y_position = 10
        spacing = 35
        
        # CPU
        cpu_percent = psutil.cpu_percent()
        self.create_metric_bar(y_position, cpu_percent, self.colors['cpu'],
                             f"CPU: {cpu_percent}%")
        
        # RAM
        y_position += spacing
        ram = psutil.virtual_memory()
        self.create_metric_bar(y_position, ram.percent, self.colors['ram'],
                             f"RAM: {ram.percent}%")
        
        # GPU
        if self.gpu_available:
            try:
                # GPU Usage
                y_position += spacing
                utilization = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
                self.create_metric_bar(y_position, utilization.gpu, self.colors['gpu'],
                                     f"GPU: {utilization.gpu}%")
                
                # GPU Temperature
                y_position += spacing
                temp = pynvml.nvmlDeviceGetTemperature(self.gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
                self.create_metric_bar(y_position, temp, self.colors['gpu_temp'],
                                     f"GPU Temp: {temp}°C")
                
                # VRAM
                y_position += spacing
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
                used_mem = mem_info.used / 1024**3
                total_mem = mem_info.total / 1024**3
                vram_percent = (used_mem / total_mem) * 100
                self.create_metric_bar(y_position, vram_percent, self.colors['vram'],
                                     f"VRAM: {used_mem:.1f}/{total_mem:.1f} GB")
            except:
                pass
        
        self.root.after(1000, self.update_system_info)

    def start_drag(self, event):
        self._drag_data = {'x': event.x, 'y': event.y}

    def do_drag(self, event):
        dx = event.x - self._drag_data['x']
        dy = event.y - self._drag_data['y']
        self.root.geometry(f"+{self.root.winfo_x() + dx}+{self.root.winfo_y() + dy}")

    def start_resize(self, event):
        self._resize_data = {
            'x': event.x_root,
            'y': event.y_root,
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height()
        }

    def do_resize(self, event):
        dx = event.x_root - self._resize_data['x']
        dy = event.y_root - self._resize_data['y']
        
        if event.widget == self.handle_br:
            new_width = max(200, self._resize_data['width'] + dx)
            new_height = max(150, self._resize_data['height'] + dy)
            self.root.geometry(f"{new_width}x{new_height}")
        elif event.widget == self.handle_bl:
            new_width = max(200, self._resize_data['width'] - dx)
            new_height = max(150, self._resize_data['height'] + dy)
            new_x = self.root.winfo_x() + dx
            self.root.geometry(f"{new_width}x{new_height}+{new_x}+{self.root.winfo_y()}")
        elif event.widget == self.handle_tr:
            new_width = max(200, self._resize_data['width'] + dx)
            new_height = max(150, self._resize_data['height'] - dy)
            new_y = self.root.winfo_y() + dy
            self.root.geometry(f"{new_width}x{new_height}+{self.root.winfo_x()}+{new_y}")
        elif event.widget == self.handle_tl:
            new_width = max(200, self._resize_data['width'] - dx)
            new_height = max(150, self._resize_data['height'] - dy)
            new_x = self.root.winfo_x() + dx
            new_y = self.root.winfo_y() + dy
            self.root.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")

    def show_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Exit", command=self.root.destroy)
        menu.post(event.x_root, event.y_root)

if __name__ == '__main__':
    root = tk.Tk()
    app = SystemOverlay(root)
    root.mainloop()