# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run the overlay
python system_overlay.py
```

Dependencies (if reinstalling): `pip install psutil nvidia-ml-py pillow`

There is no test suite or linter configured.

## Architecture

Everything lives in `system_overlay.py`. Three classes plus a startup block:

- **`GPUManager`** — singleton that lazily initialises `pynvml` and exposes `get_info()`. Returns `None` if unavailable.
- **`MetricCollector`** — collects CPU/RAM via `psutil` and GPU via `GPUManager`. Applies a rolling-average smoother (configurable `smoothing_samples`).
- **`OverlayApp`** — owns two Tkinter windows and drives the render loop via `root.after()`.

### Two-window architecture

Transparency is split across two layered windows that always share the same geometry:

- **`bg_win`** (`tk.Toplevel`) — renders the background panel and bar tracks as a PIL RGB image. Its `-alpha` attribute is the opacity slider value, so the entire panel fades smoothly from 0 → 1. Uses `TRANSPARENT = '#000001'` as the colour key for the rounded-rectangle corner cutout.
- **`root`** (`tk.Tk`) — renders text labels, values, bar fills, and the resize grip. Always at full opacity so content never fades with the panel. Also uses `TRANSPARENT = '#000001'` as its colour key.

Both canvases bind the same click/drag/menu handlers so interaction works whether the user clicks on opaque content or on a gap that falls through to `bg_win`.

### Rendering pipeline

Each frame `_loop()` calls:
1. `_draw_bg(visible, w, h)` — composites the rounded rectangle + bar tracks into a `PIL.Image.RGB`, converts to `ImageTk.PhotoImage`, and updates a single canvas image item (never recreated).
2. `_draw_content(visible, w, h)` — renders text and bar fills into a `PIL.Image.RGBA`, composites it against `TRANSPARENT_RGB = (0, 0, 1)` to produce an RGB image where transparent areas are exactly `#000001`, and updates a single canvas image item.

## Configuration

`config.json` is read at startup and written on every settings change. `load_config()` merges the file over hardcoded defaults, so any key can be omitted. The file is committed to the repo.

## Key Constraints

- **Colour key `#000001`**: both canvases use this as background and both windows set `-transparentcolor` to it. Never use this colour for visible content — it will disappear.
- **No per-frame item recreation**: `_draw_bg` and `_draw_content` create their canvas image items on the first call and use `itemconfig` to swap the `PhotoImage` reference on subsequent frames.
- **GPU is always optional**: all GPU paths guard on `show_gpu` config key and `None` returns from `GPUManager.get_info()`.
- **`bg_win` must stay behind `root`**: `_sync_bg()` calls `root.lift()` after every geometry change.
- Errors are logged to `system_overlay.log` (not raised), so the overlay stays alive if NVML fails.
