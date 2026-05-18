# System Overlay

A lightweight, real-time system resource monitor overlay built with Python and Tkinter. It provides a customizable, semi-transparent window that displays CPU, RAM, and GPU metrics (including temperature and VRAM usage) directly on your desktop.

## Project Overview

- **Main Application:** `system_overlay.py` (Python 3.x)
- **GUI Framework:** Tkinter with custom styling using `PIL` (Pillow).
- **Metric Collection:** `psutil` (CPU/RAM) and `pynvml` (NVIDIA GPU).
- **Configuration:** `config.json` stores user preferences for colors, window dimensions, and opacity.
- **UI Prototyping:** The `V0/` directory contains a React-based web prototype (Next.js/Tailwind CSS) of the monitor interface.

## Features

- **Real-time Monitoring:** Smoothly animated progress bars for CPU, RAM, and GPU.
- **Customizable UI:** Adjustable transparency, colors, and font sizes via a right-click settings menu.
- **Interactive Window:** Drag-to-move and a custom resize handle.
- **Always on Top:** The overlay stays above other windows for constant visibility.
- **GPU Support:** Integrated NVIDIA GPU monitoring (requires `nvidia-ml-py`).

## Getting Started

### Prerequisites

- Python 3.x
- Virtual environment (recommended, `.venv` already present in project)

### Installation

1.  **Activate Virtual Environment:**
    ```powershell
    .\.venv\Scripts\Activate.ps1
    ```
2.  **Install Dependencies:**
    ```bash
    pip install psutil nvidia-ml-py pillow
    ```

### Running the Application

Execute the main script:
```bash
python system_overlay.py
```

## Development Conventions

- **Modular Architecture:** Although currently in a single file, the logic is organized into classes:
  - `OverlayUI`: Handles canvas drawing and progress bar rendering.
  - `SettingsMenu`: Manages the configuration UI.
  - `EventHandler`: Manages window dragging and resizing.
  - `SystemOverlay`: Orchestrates data collection and UI updates.
- **Logging:** Errors and warnings are logged to `system_overlay.log`.
- **Configuration Management:** Uses `config.json` for persistence; uses `DEFAULT_CONFIG` in code as a fallback.
- **Surgical UI Updates:** The application uses `root.after()` for high-performance periodic updates rather than blocking loops.

## Project Structure

- `system_overlay.py`: The entry point and core logic.
- `config.json`: Persistent user settings.
- `Icon/`: Contains application icons and PSD source files.
- `V0/`: A React/TypeScript version of the monitor UI components.
- `build/`: Contains artifacts from `PyInstaller` (if the project was packaged as an EXE).
