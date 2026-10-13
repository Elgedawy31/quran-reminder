"""Restrained Islamic ornament and native buttons with a directional hover fill."""
import math
import time
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

def rounded_rectangle(context, width, height, radius=12):
    context.new_sub_path()
    context.arc(width - radius, radius, radius, -math.pi / 2, 0)
    context.arc(width - radius, height - radius, radius, 0, math.pi / 2)
    context.arc(radius, height - radius, radius, math.pi / 2, math.pi)
    context.arc(radius, radius, radius, math.pi, 3 * math.pi / 2)
    context.close_path()

def star(context, x, y, radius):
    for index in range(16):
        angle = -math.pi / 2 + index * math.pi / 8
        distance = radius if index % 2 == 0 else radius * 0.52
        point = x + math.cos(angle) * distance, y + math.sin(angle) * distance
        context.move_to(*point) if index == 0 else context.line_to(*point)
    context.close_path()

class IslamicDivider(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_size_request(-1, 28)
        self.connect("draw", self.paint)

    def paint(self, widget, context):
        x, y = self.get_allocated_width() / 2, self.get_allocated_height() / 2
        context.set_source_rgba(0.059, 0.431, 0.337, 0.45)
        context.set_line_width(1)
        star(context, x, y, 8)
        context.stroke()
        for direction in (-1, 1):
            context.move_to(x + direction * 19, y)
            context.line_to(x + direction * 54, y)
        context.stroke()
        return False

class HoverFill:
    def initialize_hover(self):
        self.hover_progress = 0.0
        self.hover_timer = None
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("enter-notify-event", self.on_pointer_enter)
        self.connect("leave-notify-event", self.on_pointer_leave)
        self.connect("destroy", self.cancel_hover)

    def on_pointer_enter(self, *_):
        if self.get_sensitive():
            window = self.get_event_window()
            if window:
                window.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "pointer"))
            self.set_hover(True)
        return False

    def on_pointer_leave(self, *_):
        window = self.get_event_window()
        if window:
            window.set_cursor(None)
        self.set_hover(False)
        return False

    def cancel_hover(self, *_):
        if self.hover_timer:
            GLib.source_remove(self.hover_timer)
            self.hover_timer = None

    def set_hover(self, hovered):
        self.cancel_hover()
        start = time.monotonic()
        initial = self.hover_progress
        target = 1.0 if hovered and self.get_sensitive() else 0.0
        settings = Gtk.Settings.get_default()
        if not settings.get_property("gtk-enable-animations"):
            self.hover_progress = target
            self.queue_draw()
            return
        def tick():
            progress = min(1.0, (time.monotonic() - start) / 0.22)
            eased = 1 - (1 - progress) ** 3
            self.hover_progress = initial + (target - initial) * eased
            self.queue_draw()
            if progress == 1:
                self.hover_timer = None
                return False
            return True
        self.hover_timer = GLib.timeout_add(16, tick)

    def paint_fill(self, context):
        if not self.get_sensitive() or not self.hover_progress:
            return
        width, height = self.get_allocated_width(), self.get_allocated_height()
        context.save()
        rounded_rectangle(context, width, height, radius=16)
        context.clip()
        # The fill enters from the right, matching the reading direction.
        context.rectangle(width * (1 - self.hover_progress), 0, width * self.hover_progress, height)
        context.set_source_rgb(0.039, 0.310, 0.243)
        context.fill()
        context.restore()
        self.propagate_draw(self.get_child(), context)

class FillButton(Gtk.Button, HoverFill):
    def __init__(self, label):
        super().__init__(label=label)
        self.initialize_hover()

    def do_draw(self, context):
        Gtk.Button.do_draw(self, context)
        self.paint_fill(context)
        return False

class IconButton(FillButton):
    ICONS = {
        "read": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
        "hide": '<path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.2A11 11 0 0 1 12 5c6 0 10 7 10 7a17 17 0 0 1-3.2 3.9M6.5 6.5A20 20 0 0 0 2 12s4 7 10 7a10 10 0 0 0 5.5-1.5"/>',
    }

    def __init__(self, icon, description):
        super().__init__(label="")
        self.remove(self.get_child())
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff2d8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{self.ICONS[icon]}</svg>'
        loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
        loader.write(svg.encode())
        loader.close()
        self.add(Gtk.Image.new_from_pixbuf(loader.get_pixbuf()))
        self.set_tooltip_text(description)
        self.get_accessible().set_name(description)
        self.get_style_context().add_class("icon-action")
