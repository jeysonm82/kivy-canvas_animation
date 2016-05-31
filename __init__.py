# -*- coding: utf-8 -*-
from kivy.app import App
from kivy.lang import Builder
from kivy import properties as props
from kivy.event import EventDispatcher
from kivy.graphics import Rectangle, Color, Fbo, ClearColor, ClearBuffers, Scale, Translate, Rotate, PushMatrix, PopMatrix
from kivy.animation import Animation


class PresetAnimation(object):
    name = None

    def __init__(self, **kwargs):
        self.root_widget = App.get_running_app().root
        self.kwargs = kwargs

    def initialize(self, widget):
        raise NotImplementedError


class FadeInPreset(PresetAnimation):
    name = 'fade_in'

    def initialize(self, canvas_widget):
        canvas_widget.opacity = 0
        return {'opacity': 1}


class StretchPreset(PresetAnimation):
    name = 'stretch'

    def initialize(self, canvas_widget):
        widget = canvas_widget.widget
        s = self.kwargs['s'] if 's' in self.kwargs else 1.5
        canvas_widget.width = widget.width * s
        canvas_widget.height = widget.height * s
        canvas_widget.x = widget.x - 0.5 * (canvas_widget.width - widget.width)
        canvas_widget.y = widget.y - 0.5 * \
            (canvas_widget.height - widget.height)
        return {'width': widget.width, 'height': widget.height, 'y': widget.y, 'x': widget.x}


class RotatePreset(PresetAnimation):
    name = 'rotate'

    def initialize(self, canvas_widget):
        widget = canvas_widget.widget
        angle_start = self.kwargs[
            'angle_start'] if 'angle_start' in self.kwargs else 0
        angle_end = self.kwargs[
            'angle_end'] if 'angle_end' in self.kwargs else 360
        def_orig = widget.x + widget.width / 2, widget.y + widget.height / 2
        origin = self.kwargs['origin'] if 'origin' in self.kwargs else def_orig
        canvas_widget.angle = angle_start
        canvas_widget.rot_origin = origin

        return {'angle': angle_end}


class SlidePreset(PresetAnimation):
    name = 'slide'

    def initialize(self, canvas_widget):
        opts = {}
        widget = canvas_widget.widget
        sf = self.kwargs[
            'slide_from'] if 'slide_from' in self.kwargs else 'left'
        if sf == 'left':
            canvas_widget.x = -widget.width
            opts['x'] = widget.x
        elif sf == 'right':
            canvas_widget.x = self.root_widget.width
            opts['x'] = widget.x
        elif sf == 'top':
            canvas_widget.y = self.root_widget.height
            opts['y'] = widget.y
        elif sf == 'bottom':
            canvas_widget.y = - widget.height
            opts['y'] = widget.y
        return opts


class CanvasAnimation(Animation):
    _preset = None
    _presets = {c.name: c for c in (
        FadeInPreset, SlidePreset, StretchPreset, RotatePreset)}
    _finalize = False

    def __init__(self, **kw):
        preset = kw['preset'] if 'preset' in kw else None
        pkw = kw['preset_kwargs'] if 'preset_kwargs' in kw else {}
        if preset:
            kw.pop('preset')
            self._preset = self._presets[preset](**pkw)
        if len(pkw):
            kw.pop('preset_kwargs')

        super(CanvasAnimation, self).__init__(**kw)

    def start(self, widget):
        canvas_widget = CanvasWidget(widget=widget)
        opts = None
        if self._preset is not None:
            opts = self._preset.initialize(canvas_widget)

        if opts is not None:
            self._animated_properties = opts

        self._finalize = False
        super(CanvasAnimation, self).start(canvas_widget)
        self._finalize = True

    def stop(self, widget):
        if hasattr(widget, 'widget'):
            if self._finalize:
                widget.finalize()
            super(CanvasAnimation, self).stop(widget.widget)
        else:
            super(CanvasAnimation, self).stop(widget)


class CanvasWidget(EventDispatcher):
    x = props.NumericProperty(0)
    y = props.NumericProperty(0)
    pos = props.ReferenceListProperty(x, y)
    width = props.NumericProperty(0)
    height = props.NumericProperty(0)
    size = props.ReferenceListProperty(width, height)
    angle = props.NumericProperty(0)

    rot_origx = props.NumericProperty(0)
    rot_origy = props.NumericProperty(0)
    rot_origin = props.ReferenceListProperty(rot_origx, rot_origy)

    opacity = props.NumericProperty(1)
    widget = props.ObjectProperty(None)
    uid = props.NumericProperty(0)

    _reg = {}
    _debug = False

    def __init__(self, *args, **kwargs):
        super(CanvasWidget, self).__init__(*args, **kwargs)
        self.widget = kwargs["widget"]
        self.uid = self.widget.uid
        self.initialize()

    def _get_canvas_instructions(self):
        """ Returns canvas instructions used to manipulate the visual appearance
        of the widget. Canvas instructions from here are singleton, that way
        to parallel animation can operate on the same set of instructions"""

        if self.uid in CanvasWidget._reg:
            CanvasWidget._reg[self.uid][-1] += 1
        else:
            widget = self.widget
            # Grab widget.canvas texture. (From Widget.export_to_png)
            if widget.parent is not None:
                canvas_parent_index = widget.parent.canvas.indexof(
                    widget.canvas)
                if canvas_parent_index > -1:
                    widget.parent.canvas.remove(widget.canvas)

            fbo = Fbo(size=widget.size, with_stencilbuffer=True)
            with fbo:
                Translate(-widget.x, -widget.y, 0)
            fbo.add(widget.canvas)
            fbo.draw()
            fbo.remove(widget.canvas)

            if widget.parent is not None and canvas_parent_index > -1:
                widget.parent.canvas.insert(canvas_parent_index, widget.canvas)
            # End grab
            c = (1, 1, 1, 1) if not self._debug else (1, 0, 1, 0.5)
            with self.root_widget.canvas:
                PushMatrix()
                scale = Scale(1, 1, 1)
                rotate = Rotate(angle=0, axis=(0, 0, 1))
                color = Color(*c)
                rect = Rectangle(
                    size=widget.size, pos=widget.pos, texture=fbo.texture)
                PopMatrix()
            CanvasWidget._reg[self.uid] = [scale, rotate, color, rect, 1]
        return CanvasWidget._reg[self.uid][:-1]

    def initialize(self):
        widget = self.widget
        self.root_widget = App.get_running_app().root
        self._scale, self._rotate, self._color, self._rect = self._get_canvas_instructions()

        self.y = widget.y
        self.x = widget.x
        self.opacity = 1
        widget.opacity = 0

    def on_opacity(self, *args):
        self._color.a = self.opacity

    def on_pos(self, *args):
        self._rect.pos = self.x, self.y

    def on_size(self, *args):
        self._rect.size = self.width, self.height

    def on_angle(self, *args):
        self._rotate.angle = self.angle

    def on_rot_origin(self, *args):
        self._rotate.origin = self.rot_origin

    def finalize(self):
        root_widget = App.get_running_app().root
        CanvasWidget._reg[self.uid][-1] -= 1
        if not CanvasWidget._reg[self.uid][-1]:
            self.widget.opacity = 1
            if self._debug:
                return
            root_widget.canvas.remove(self._rect)
            root_widget.canvas.remove(self._color)
            root_widget.canvas.remove(self._rotate)
            root_widget.canvas.remove(self._scale)
            CanvasWidget._reg.pop(self.uid)

if __name__ in ('__main__', '__android__'):
    from kivy.config import Config
    from kivy.core.window import Window

    class MainApp(App):

        def animate(self, btn):
            fa = CanvasAnimation(
                preset='stretch', duration=.8, t='out_sine', preset_kwargs={'s': 0.8})
            fa_final = fa
            fa_final.start(btn)

    Window.size = (1200, 800)
    app = MainApp()
    app.run()
