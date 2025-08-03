"""
PixelSynth – Draw Music, Hear Colors
One-file, offline, zero-API, fun synth.
Author: You (15-year-old prodigy!)
Run:   python pixelsynth.py
Keys:  SPACE = play / pause
       S     = save .wav + .png
       M     = mutate canvas
       R     = clear canvas
       T     = test audio
       ESC   = quit

🔴 Kick: Deep analog-style with soft punch (55Hz fundamental)
🔵 Snare: Crispy trap snare with noise + tone blend
🟢 Hi-Hat: Gentle noise with fast decay
🟡 Bass: Smooth pluck with gentle envelope
🟣 Lead: Dreamy 3-oscillator synth with slow decay

Change entire code if you want just make sure our project is point to point
"""
import pygame
import numpy as np
import wave
import struct
import datetime
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import os
import random
import time

# =============== CONSTANTS ===============
GRID_SIZE = 64
PIXEL_ZOOM = 8
BPM = 120
SAMPLE_RATE = 44100
UI_HEIGHT = 110
LOOP_LEN_SEC = 4
INSTRUMENTS = [
    ((255, 80, 80),  "Kick",   "1", "🔴"),
    ((80, 160, 255), "Snare",  "2", "🔵"),
    ((100, 220, 100),"Hi-Hat", "3", "🟢"),
    ((255, 230, 100),"Bass",   "4", "🟡"),
    ((200, 120, 255),"Lead",   "5", "🟣")
]
COLOR_TO_IDX = {tuple(c): i for i, (c, *_ ) in enumerate(INSTRUMENTS)}

# ============ INITIALIZATION ============
pygame.init()
window_size = (GRID_SIZE * PIXEL_ZOOM, GRID_SIZE * PIXEL_ZOOM + UI_HEIGHT)
screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
pygame.display.set_caption("PixelSynth – Draw Music, Hear Colors")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 16, bold=True)
fullscreen = False
playhead_start_time = None

# ============ GRID ============
grid = np.zeros((GRID_SIZE, GRID_SIZE, 3), dtype=np.uint8)
current_color_idx = 0
playing = False
mouse_down = False
mouse_button = 1

# ============ AUDIO ENGINE ============
def synth_note(inst_idx, t):
    # t: time array (float, seconds)
    if inst_idx == 0:  # Kick
        env = np.exp(-t*8)
        return 0.8 * env * np.sin(2*np.pi*55*(1-0.5*t)*t)
    elif inst_idx == 1:  # Snare
        env = np.exp(-t*12)
        noise = np.random.uniform(-1,1,len(t))
        tone = np.sin(2*np.pi*220*t) * 0.3
        return env * (0.7*noise + 0.3*tone)
    elif inst_idx == 2:  # Hi-Hat
        env = np.exp(-t*30)
        noise = np.random.uniform(-1,1,len(t))
        return 0.5 * env * noise
    elif inst_idx == 3:  # Bass
        env = np.exp(-t*4)
        return 0.7 * env * np.sin(2*np.pi*110*t)
    elif inst_idx == 4:  # Lead
        env = np.exp(-t*2)
        osc = (np.sin(2*np.pi*440*t) + np.sin(2*np.pi*660*t)*0.5 + np.sin(2*np.pi*880*t)*0.3)
        return 0.5 * env * osc
    return np.zeros_like(t)

def grid_to_audio(grid):
    # Each column = 1 step, each row = instrument
    steps = GRID_SIZE
    step_samples = SAMPLE_RATE * LOOP_LEN_SEC // steps
    audio = np.zeros(LOOP_LEN_SEC * SAMPLE_RATE)
    for x in range(steps):
        for y in range(GRID_SIZE):
            color = tuple(grid[y, x])
            if color in COLOR_TO_IDX:
                inst_idx = COLOR_TO_IDX[color]
                t = np.linspace(0, step_samples/SAMPLE_RATE, step_samples, endpoint=False)
                note = synth_note(inst_idx, t)
                start = x * step_samples
                end = start + step_samples
                audio[start:end] += note[:min(len(note), end-start)]
    # Normalize
    audio = audio / (np.max(np.abs(audio)) + 1e-6)
    return audio

def play_audio(audio):
    # Convert to 16-bit and play with pygame
    arr = (audio * 32767).astype(np.int16)
    sound = pygame.sndarray.make_sound(arr.reshape(-1,1).repeat(2,axis=1))
    sound.play(loops=-1)  # Loop forever until stopped
    return sound

# ============ UI ============
def draw_ui():
    panel = pygame.Surface((GRID_SIZE * PIXEL_ZOOM, UI_HEIGHT))
    panel.fill((22, 24, 32))
    # Title (centered)
    title = font.render("PixelSynth – Draw Music, Hear Colors", True, (255,255,255))
    panel.blit(title, ((panel.get_width() - title.get_width()) // 2, 10))

    # Horizontal line under title
    pygame.draw.line(panel, (40, 60, 100), (20, 38), (panel.get_width()-20, 38), 2)

    # Instrument palette (centered horizontally)
    palette_w = len(INSTRUMENTS) * 110
    palette_x = (panel.get_width() - palette_w) // 2
    for i, (color, name, key, emoji) in enumerate(INSTRUMENTS):
        x = palette_x + i*110
        y = 50
        # Highlight box for selected
        if i == current_color_idx:
            pygame.draw.rect(panel, (100,200,255), (x-6, y-6, 92, 38), border_radius=8)
        # Color swatch
        pygame.draw.rect(panel, color, (x, y, 30, 30), border_radius=6)
        # Emoji and name
        label = font.render(f"{emoji} {name}", True, (255,255,255) if i==current_color_idx else (180,180,180))
        panel.blit(label, (x+38, y+4))
        # Key shortcut
        keytxt = font.render(f"[{key}]", True, (120,180,255) if i==current_color_idx else (100,100,120))
        panel.blit(keytxt, (x+38, y+18))

    # Controls bar (bottom, minimal)
    controls = [
        ("SPACE", "Play/Pause"),
        ("S", "Save"),
        ("M", "Mutate"),
        ("R", "Reset"),
        ("T", "Test"),
        ("F", "Fullscreen"),
        ("G", "GIF"),
        ("ESC", "Quit")
    ]
    cx = 30
    cy = UI_HEIGHT - 18  # Move closer to the bottom
    for key, label in controls:
        ktxt = font.render(key, True, (120,200,255))
        ltxt = font.render(label, True, (180,180,180))
        panel.blit(ktxt, (cx, cy))
        panel.blit(ltxt, (cx+ktxt.get_width()+8, cy))
        cx += ktxt.get_width() + ltxt.get_width() + 32

    # Subtle line above controls
    pygame.draw.line(panel, (40, 60, 100), (20, UI_HEIGHT-28), (panel.get_width()-20, UI_HEIGHT-28), 1)

    screen.blit(panel, (0,0))

def draw_grid(playhead_col=None):
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            rect = pygame.Rect(x*PIXEL_ZOOM, y*PIXEL_ZOOM+UI_HEIGHT, PIXEL_ZOOM, PIXEL_ZOOM)
            pygame.draw.rect(screen, grid[y,x], rect)
            # Step highlight: outline cells in playhead column
            if playhead_col is not None and x == playhead_col:
                pygame.draw.rect(screen, (255,255,180), rect, 2)
            else:
                pygame.draw.rect(screen, (50,50,50), rect, 1)
    # Draw playhead if provided
    if playhead_col is not None:
        s = pygame.Surface((PIXEL_ZOOM, GRID_SIZE*PIXEL_ZOOM), pygame.SRCALPHA)
        s.fill((120,220,255, 70))
        screen.blit(s, (playhead_col*PIXEL_ZOOM, UI_HEIGHT))

def scanline_shader():
    arr = pygame.surfarray.pixels3d(screen)
    arr[:,UI_HEIGHT::2,:] = (arr[:,UI_HEIGHT::2,:]//2)

# ============ MUTATE ============
def mutate_grid():
    for _ in range(GRID_SIZE*GRID_SIZE//10):
        x = random.randint(0, GRID_SIZE-1)
        y = random.randint(0, GRID_SIZE-1)
        if random.random() < 0.5:
            # Flip color
            grid[y,x] = INSTRUMENTS[random.randint(0,4)][0]
        else:
            # Mirror or rotate
            grid[y,x] = grid[x%GRID_SIZE, y%GRID_SIZE]

# ============ SNAPSHOT ============
def save_snapshot():
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    img = Image.fromarray(grid, 'RGB').resize((GRID_SIZE*PIXEL_ZOOM, GRID_SIZE*PIXEL_ZOOM), Image.NEAREST)
    img.save(f"pixelsynth_{now}.png")
    audio = grid_to_audio(grid)
    with wave.open(f"pixelsynth_{now}.wav", 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        arr = (audio * 32767).astype(np.int16)
        wf.writeframes(arr.tobytes())
    # Spectrogram
    plt.figure(figsize=(8,4))
    plt.specgram(audio, Fs=SAMPLE_RATE, cmap='nipy_spectral')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(f"pixelsynth_{now}_spec.png", bbox_inches='tight', pad_inches=0)
    plt.close()

# ============ ANIMATED GIF ============
def save_gif():
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    frames = []
    g = grid.copy()
    for _ in range(8):
        img = Image.fromarray(g, 'RGB').resize((GRID_SIZE*PIXEL_ZOOM, GRID_SIZE*PIXEL_ZOOM), Image.NEAREST)
        frames.append(img)
        mutate_grid()
    frames[0].save(f"pixelsynth_{now}.gif", save_all=True, append_images=frames[1:], duration=300, loop=0)

# ============ MAIN LOOP ============
sound = None
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit(); exit()
            elif event.key == pygame.K_SPACE:
                playing = not playing
                if playing:
                    playhead_start_time = time.time()
                    audio = grid_to_audio(grid)
                    if sound: sound.stop()
                    sound = play_audio(audio)
                else:
                    if sound: sound.stop()
            elif event.key == pygame.K_s:
                save_snapshot()
            elif event.key == pygame.K_m:
                mutate_grid()
            elif event.key == pygame.K_r:
                grid[:,:] = 0
            elif event.key == pygame.K_t:
                audio = grid_to_audio(grid)
                if sound: sound.stop()
                sound = play_audio(audio)
            elif event.key == pygame.K_f:
                fullscreen = not fullscreen
                if fullscreen:
                    screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
                else:
                    screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
            elif event.key == pygame.K_g:
                save_gif()
            elif event.unicode in "12345":
                current_color_idx = int(event.unicode)-1
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_down = True
            mouse_button = event.button
            mx, my = event.pos
            gx = mx // PIXEL_ZOOM
            gy = (my - UI_HEIGHT) // PIXEL_ZOOM
            if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
                if mouse_button == 1:
                    grid[gy, gx] = INSTRUMENTS[current_color_idx][0]
                elif mouse_button == 3:
                    grid[gy, gx] = (0,0,0)
            if event.button == 4:  # wheel up
                current_color_idx = (current_color_idx - 1) % len(INSTRUMENTS)
            elif event.button == 5:  # wheel down
                current_color_idx = (current_color_idx + 1) % len(INSTRUMENTS)
        elif event.type == pygame.MOUSEBUTTONUP:
            mouse_down = False
        elif event.type == pygame.MOUSEMOTION and mouse_down:
            mx, my = event.pos
            gx = mx // PIXEL_ZOOM
            gy = (my - UI_HEIGHT) // PIXEL_ZOOM
            if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
                if mouse_button == 1:
                    grid[gy, gx] = INSTRUMENTS[current_color_idx][0]
                elif mouse_button == 3:
                    grid[gy, gx] = (0,0,0)

    # Playhead logic
    playhead_col = None
    if playing:
        if playhead_start_time is None:
            playhead_start_time = time.time()
        elapsed = (time.time() - playhead_start_time) % LOOP_LEN_SEC
        playhead_col = int((elapsed / LOOP_LEN_SEC) * GRID_SIZE)
    else:
        playhead_start_time = None
        playhead_col = None

    screen.fill((15,15,20))
    draw_ui()
    draw_grid(playhead_col)
    scanline_shader()
    pygame.display.flip()
    clock.tick(60)
       # lo_2
