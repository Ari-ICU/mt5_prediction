import tkinter as tk
from ... import config

class Card(tk.Frame):
    def __init__(self, parent, pad=20, **kwargs):
        super().__init__(parent, bg=config.CARD_BG, padx=pad, pady=pad, **kwargs)

class ModernButton(tk.Label):
    def __init__(self, parent, text, command, bg, fg, width=None, font_spec=None):
        if font_spec is None:
            font_spec = (config.FONT_BOLD, 11, "bold")
            
        super().__init__(parent, text=text, bg=bg, fg=fg, 
                         font=font_spec, cursor="hand2")
        
        self.default_bg = bg
        self.hover_bg = self._adjust_brightness(bg, 1.2) if bg != config.INPUT_BG else config.HOVER_BG
        self.command = command
        
        self.configure(padx=15, pady=10)
        if width:
            self.configure(width=width)
            
        self.bind("<Enter>", lambda e: self.configure(bg=self.hover_bg))
        self.bind("<Leave>", lambda e: self.configure(bg=self.default_bg))
        self.bind("<Button-1>", lambda e: self.command() if self.command else None)
        
    def _adjust_brightness(self, hex_color, factor):
        # Very simple brightness adjustment for feedback
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        new_rgb = [min(255, int(c * factor)) for c in rgb]
        return '#{:02x}{:02x}{:02x}'.format(*new_rgb)

class ActionButton(ModernButton):
    def __init__(self, parent, text, command, bg):
        super().__init__(parent, text=text, command=command, bg=bg, 
                         fg=config.TEXT_ON_ACCENT, font_spec=(config.FONT_BOLD, 16, "bold"))
        self.configure(pady=15)
