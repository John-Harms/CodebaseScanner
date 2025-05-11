# ui_widgets.py

import tkinter as tk

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.id_after = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<ButtonPress>", self.on_leave) # Hide on click

    def on_enter(self, event=None):
        self.schedule_tooltip()

    def on_leave(self, event=None):
        self.cancel_scheduled_tooltip()
        self.hide_tooltip()

    def schedule_tooltip(self):
        self.cancel_scheduled_tooltip()
        self.id_after = self.widget.after(700, self.show_tooltip) # Delay before showing

    def cancel_scheduled_tooltip(self):
        if self.id_after:
            self.widget.after_cancel(self.id_after)
            self.id_after = None

    def show_tooltip(self):
        if self.tooltip_window or not self.text: return

        x_root = self.widget.winfo_rootx() + 20
        y_root = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True) # No window decorations
        self.tooltip_window.wm_geometry(f"+{int(x_root)}+{int(y_root)}")

        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         wraplength=350, # Wrap text if too long
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=2, ipady=2)

        # Adjust position if tooltip goes off-screen
        self.tooltip_window.update_idletasks() # Ensure dimensions are calculated
        tip_width = self.tooltip_window.winfo_width()
        tip_height = self.tooltip_window.winfo_height()
        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()

        if x_root + tip_width > screen_width:
            x_root = screen_width - tip_width - 5 # Move left
        if x_root < 0: x_root = 5 # Ensure not off-screen left

        if y_root + tip_height > screen_height:
            y_root = self.widget.winfo_rooty() - tip_height - 5 # Move above widget
        if y_root < 0: y_root = 5 # Ensure not off-screen top

        self.tooltip_window.wm_geometry(f"+{int(x_root)}+{int(y_root)}")

    def hide_tooltip(self):
        tw = self.tooltip_window
        self.tooltip_window = None
        if tw:
            try:
                tw.destroy()
            except tk.TclError: # Can happen if root window is destroyed
                pass