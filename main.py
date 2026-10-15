# -*- coding: utf-8 -*-
"""
Cooler Control - Arduino HC-05 Controller
Modern UI without emoji
"""

import threading
import time
from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock
from kivy.utils import platform
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.properties import ListProperty, ColorProperty


# ============================================================
# Bluetooth Manager
# ============================================================
class BluetoothManager:
    SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

    def __init__(self):
        self.socket = None
        self.input_stream = None
        self.output_stream = None
        self.connected = False
        self.read_thread = None
        self.stop_flag = False
        self.on_line_received = None
        self.on_connection_change = None

    def is_android(self):
        return platform == 'android'

    def get_paired_devices(self):
        if not self.is_android():
            return [
                {"name": "HC-05 (Demo)", "address": "00:11:22:33:44:55"},
                {"name": "Cooler-BT", "address": "AA:BB:CC:DD:EE:FF"},
            ]
        try:
            from jnius import autoclass
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None:
                return []
            bonded = adapter.getBondedDevices()
            devices = []
            it = bonded.iterator()
            while it.hasNext():
                d = it.next()
                devices.append({
                    "name": d.getName(),
                    "address": d.getAddress(),
                    "device": d,
                })
            return devices
        except Exception as e:
            print("BT scan error:", e)
            return []

    def connect(self, device_info):
        if not self.is_android():
            self.connected = True
            if self.on_connection_change:
                self.on_connection_change(True)
            return True
        try:
            from jnius import autoclass
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            UUID = autoclass('java.util.UUID')
            adapter = BluetoothAdapter.getDefaultAdapter()
            device = device_info.get("device")
            if device is None:
                device = adapter.getRemoteDevice(device_info["address"])
            uuid = UUID.fromString(self.SPP_UUID)
            self.socket = device.createRfcommSocketToServiceRecord(uuid)
            adapter.cancelDiscovery()
            self.socket.connect()
            self.input_stream = self.socket.getInputStream()
            self.output_stream = self.socket.getOutputStream()
            self.connected = True
            self.stop_flag = False
            self.read_thread = threading.Thread(target=self.read_loop)
            self.read_thread.daemon = True
            self.read_thread.start()
            if self.on_connection_change:
                self.on_connection_change(True)
            return True
        except Exception as e:
            print("Connect error:", e)
            self.connected = False
            if self.on_connection_change:
                self.on_connection_change(False)
            return False

    def disconnect(self):
        self.stop_flag = True
        self.connected = False
        try:
            if self.input_stream: self.input_stream.close()
            if self.output_stream: self.output_stream.close()
            if self.socket: self.socket.close()
        except Exception:
            pass
        self.socket = None
        self.input_stream = None
        self.output_stream = None
        if self.on_connection_change:
            self.on_connection_change(False)

    def send(self, command):
        if not self.connected:
            return False
        if not command.endswith("\n"):
            command += "\n"
        if not self.is_android():
            print("SIM:", repr(command))
            if self.on_line_received:
                Clock.schedule_once(
                    lambda dt: self.on_line_received("Echo: " + command.strip()),
                    0.1
                )
            return True
        try:
            self.output_stream.write(command.encode('utf-8'))
            self.output_stream.flush()
            return True
        except Exception as e:
            print("Send error:", e)
            return False

    def read_loop(self):
        buf = ""
        while not self.stop_flag and self.connected:
            try:
                if self.input_stream.available() > 0:
                    data = self.input_stream.read()
                    ch = chr(data)
                    if ch == '\n':
                        line = buf.strip()
                        buf = ""
                        if line and self.on_line_received:
                            Clock.schedule_once(
                                lambda dt, l=line: self.on_line_received(l), 0
                            )
                    else:
                        buf += ch
                else:
                    time.sleep(0.05)
            except Exception as e:
                print("Read error:", e)
                self.connected = False
                if self.on_connection_change:
                    Clock.schedule_once(
                        lambda dt: self.on_connection_change(False), 0
                    )
                break


# ============================================================
# Custom Widgets
# ============================================================
class GlassCard(BoxLayout):
    bg_color = ColorProperty([1, 1, 1, 1])
    border_color = ColorProperty([0.85, 0.88, 0.95, 1])
    corner_radius = ListProperty([20, 20, 20, 20])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint = (None, None)
        self.pos_hint = {"center_x": 0.5}
        self.padding = dp(15)
        self.spacing = dp(8)
        self.bind(pos=self._update_canvas, size=self._update_canvas)
        Clock.schedule_once(lambda dt: self._update_canvas(), 0.05)

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        if self.width < 10 or self.height < 10:
            return
        with self.canvas.before:
            # سایه
            Color(0.7, 0.75, 0.85, 0.4)
            RoundedRectangle(
                pos=(self.x + dp(1), self.y - dp(3)),
                size=self.size,
                radius=[dp(r) for r in self.corner_radius],
            )
            # پس‌زمینه
            Color(*self.bg_color)
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(r) for r in self.corner_radius],
            )
            # حاشیه نازک
            Color(*self.border_color)
            from kivy.graphics import Line
            Line(
                rounded_rectangle=(
                    self.x, self.y, self.width, self.height, dp(20)
                ),
                width=1.1,
            )


class RoundIcon(ButtonBehavior, Label):
    bg_color = ColorProperty([0.2, 0.5, 0.85, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(70), dp(70))
        self.color = (1, 1, 1, 1)
        self.font_size = dp(22)
        self.bold = True
        self.bind(pos=self._update_canvas, size=self._update_canvas)
        Clock.schedule_once(lambda dt: self._update_canvas(), 0.05)

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        if self.width < 10 or self.height < 10:
            return
        with self.canvas.before:
            # سایه دایره
            Color(0, 0, 0, 0.1)
            Ellipse(
                pos=(self.x + dp(1), self.y - dp(2)),
                size=self.size,
            )
            # دایره اصلی
            Color(*self.bg_color)
            Ellipse(pos=self.pos, size=self.size)


# ============================================================
# Screens
# ============================================================
class HomeScreen(Screen):
    pass

class TimerScreen(Screen):
    pass

class StatusScreen(Screen):
    pass

class SettingsScreen(Screen):
    pass


# ============================================================
# KV UI - بدون ایموجی، با رنگ‌های زنده
# ============================================================
KV = """
#:import dp kivy.metrics.dp

<HomeScreen>:
    name: "home"
    BoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: 0.93, 0.95, 0.98, 1
            Rectangle:
                pos: self.pos
                size: self.size

        # === HEADER ===
        BoxLayout:
            size_hint_y: None
            height: dp(85)
            padding: dp(20), dp(15), dp(20), dp(10)
            canvas.before:
                Color:
                    rgba: 0.13, 0.29, 0.65, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            BoxLayout:
                orientation: "vertical"
                Label:
                    text: "Cooler Control"
                    color: 1, 1, 1, 1
                    font_size: dp(22)
                    bold: True
                    halign: "left"
                    valign: "middle"
                    text_size: self.size

                Label:
                    id: bt_status
                    text: "Disconnected"
                    color: 1, 0.6, 0.6, 1
                    font_size: dp(13)
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                    size_hint_y: None
                    height: dp(22)

            Label:
                text: "❄"
                color: 1, 1, 1, 0.9
                font_size: dp(38)
                size_hint_x: None
                width: dp(50)

        # === SCROLL ===
        ScrollView:
            BoxLayout:
                orientation: "vertical"
                padding: dp(20)
                spacing: dp(18)
                size_hint_y: None
                height: self.minimum_height

                # === TEMP CARD ===
                GlassCard:
                    size: dp(340), dp(190)

                    Label:
                        text: "TEMPERATURE"
                        font_size: dp(12)
                        color: 0.55, 0.58, 0.65, 1
                        bold: True
                        size_hint_y: None
                        height: dp(20)

                    BoxLayout:
                        orientation: "horizontal"

                        Label:
                            id: temp_label
                            text: "--.-"
                            font_size: dp(64)
                            bold: True
                            color: 0.85, 0.2, 0.2, 1
                            halign: "right"
                            valign: "middle"

                        BoxLayout:
                            orientation: "vertical"
                            size_hint_x: None
                            width: dp(70)
                            padding: dp(5), dp(10)

                            Label:
                                text: "C"
                                font_size: dp(26)
                                color: 0.85, 0.2, 0.2, 1
                                bold: True
                                size_hint_y: None
                                height: dp(40)

                            Label:
                                text: "Celsius"
                                font_size: dp(11)
                                color: 0.6, 0.6, 0.6, 1
                                size_hint_y: None
                                height: dp(20)

                    BoxLayout:
                        orientation: "horizontal"
                        size_hint_y: None
                        height: dp(40)
                        spacing: dp(10)
                        padding: dp(5), 0

                        Label:
                            id: hum_label
                            text: "Humidity  --.- %"
                            font_size: dp(14)
                            color: 0.2, 0.5, 0.85, 1
                            bold: True

                        Label:
                            id: rtc_label
                            text: "Time  --:--"
                            font_size: dp(14)
                            color: 0.4, 0.4, 0.45, 1
                            bold: True

                # === CONTROL BUTTONS ===
                Label:
                    text: "QUICK CONTROLS"
                    font_size: dp(12)
                    color: 0.4, 0.42, 0.5, 1
                    bold: True
                    size_hint_y: None
                    height: dp(25)
                    halign: "left"
                    padding_x: dp(5)

                BoxLayout:
                    orientation: "horizontal"
                    spacing: dp(10)
                    size_hint: None, None
                    size: dp(340), dp(110)
                    pos_hint: {"center_x": 0.5}

                    BoxLayout:
                        orientation: "vertical"
                        spacing: dp(5)
                        RoundIcon:
                            text: "P"
                            bg_color: 0.2, 0.6, 0.95, 1
                            font_size: dp(24)
                            pos_hint: {"center_x": 0.5}
                            on_release: app.send_command("1")
                        Label:
                            text: "Pump"
                            font_size: dp(12)
                            color: 0.25, 0.25, 0.3, 1
                            size_hint_y: None
                            height: dp(20)
                            bold: True

                    BoxLayout:
                        orientation: "vertical"
                        spacing: dp(5)
                        RoundIcon:
                            text: "S"
                            bg_color: 0.95, 0.7, 0.15, 1
                            font_size: dp(24)
                            pos_hint: {"center_x": 0.5}
                            on_release: app.send_command("2")
                        Label:
                            text: "Slow"
                            font_size: dp(12)
                            color: 0.25, 0.25, 0.3, 1
                            size_hint_y: None
                            height: dp(20)
                            bold: True

                    BoxLayout:
                        orientation: "vertical"
                        spacing: dp(5)
                        RoundIcon:
                            text: "F"
                            bg_color: 0.95, 0.4, 0.15, 1
                            font_size: dp(24)
                            pos_hint: {"center_x": 0.5}
                            on_release: app.send_command("3")
                        Label:
                            text: "Fast"
                            font_size: dp(12)
                            color: 0.25, 0.25, 0.3, 1
                            size_hint_y: None
                            height: dp(20)
                            bold: True

                    BoxLayout:
                        orientation: "vertical"
                        spacing: dp(5)
                        RoundIcon:
                            text: "M"
                            bg_color: 0.6, 0.35, 0.85, 1
                            font_size: dp(24)
                            pos_hint: {"center_x": 0.5}
                            on_release: app.send_command("4")
                        Label:
                            text: "Mode"
                            font_size: dp(12)
                            color: 0.25, 0.25, 0.3, 1
                            size_hint_y: None
                            height: dp(20)
                            bold: True

                # === QUICK NAV ===
                BoxLayout:
                    orientation: "horizontal"
                    spacing: dp(10)
                    size_hint: None, None
                    size: dp(340), dp(60)
                    pos_hint: {"center_x": 0.5}

                    Button:
                        text: "Timer"
                        font_size: dp(14)
                        bold: True
                        background_normal: ""
                        background_color: 1, 1, 1, 1
                        color: 0.15, 0.3, 0.7, 1
                        on_release: app.go("timer")

                    Button:
                        text: "Status"
                        font_size: dp(14)
                        bold: True
                        background_normal: ""
                        background_color: 1, 1, 1, 1
                        color: 0.15, 0.3, 0.7, 1
                        on_release: app.go("status")

                    Button:
                        text: "Settings"
                        font_size: dp(14)
                        bold: True
                        background_normal: ""
                        background_color: 1, 1, 1, 1
                        color: 0.15, 0.3, 0.7, 1
                        on_release: app.go("settings")


<TimerScreen>:
    name: "timer"
    BoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: 0.93, 0.95, 0.98, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(70)
            padding: dp(10), dp(15), dp(15), dp(10)
            canvas.before:
                Color:
                    rgba: 0.13, 0.29, 0.65, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: "<"
                size_hint: None, None
                size: dp(45), dp(45)
                pos_hint: {"center_y": 0.5}
                background_normal: ""
                background_color: 0.1, 0.22, 0.5, 1
                color: 1, 1, 1, 1
                font_size: dp(20)
                bold: True
                on_release: app.go("home")

            Label:
                text: "Timer Settings"
                color: 1, 1, 1, 1
                font_size: dp(19)
                bold: True

        ScrollView:
            BoxLayout:
                orientation: "vertical"
                padding: dp(20)
                spacing: dp(20)
                size_hint_y: None
                height: self.minimum_height

                GlassCard:
                    size: dp(340), dp(170)
                    bg_color: 0.9, 0.98, 0.9, 1
                    border_color: 0.7, 0.9, 0.7, 1

                    Label:
                        text: "TURN ON AT"
                        font_size: dp(13)
                        bold: True
                        color: 0.15, 0.55, 0.2, 1
                        size_hint_y: None
                        height: dp(25)

                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(10)

                        Spinner:
                            id: on_hour
                            text: "07"
                            values: [str(i).zfill(2) for i in range(24)]
                            background_normal: ""
                            background_color: 1, 1, 1, 1
                            color: 0.1, 0.1, 0.3, 1
                            font_size: dp(28)
                            bold: True
                            on_text: app.update_preview()

                        Label:
                            text: ":"
                            font_size: dp(32)
                            bold: True
                            color: 0.15, 0.55, 0.2, 1
                            size_hint_x: None
                            width: dp(30)

                        Spinner:
                            id: on_min
                            text: "30"
                            values: [str(i).zfill(2) for i in range(60)]
                            background_normal: ""
                            background_color: 1, 1, 1, 1
                            color: 0.1, 0.1, 0.3, 1
                            font_size: dp(28)
                            bold: True
                            on_text: app.update_preview()

                GlassCard:
                    size: dp(340), dp(170)
                    bg_color: 1, 0.92, 0.92, 1
                    border_color: 0.95, 0.7, 0.7, 1

                    Label:
                        text: "TURN OFF AT"
                        font_size: dp(13)
                        bold: True
                        color: 0.7, 0.15, 0.15, 1
                        size_hint_y: None
                        height: dp(25)

                    BoxLayout:
                        orientation: "horizontal"
                        spacing: dp(10)

                        Spinner:
                            id: off_hour
                            text: "19"
                            values: [str(i).zfill(2) for i in range(24)]
                            background_normal: ""
                            background_color: 1, 1, 1, 1
                            color: 0.1, 0.1, 0.3, 1
                            font_size: dp(28)
                            bold: True
                            on_text: app.update_preview()

                        Label:
                            text: ":"
                            font_size: dp(32)
                            bold: True
                            color: 0.7, 0.15, 0.15, 1
                            size_hint_x: None
                            width: dp(30)

                        Spinner:
                            id: off_min
                            text: "30"
                            values: [str(i).zfill(2) for i in range(60)]
                            background_normal: ""
                            background_color: 1, 1, 1, 1
                            color: 0.1, 0.1, 0.3, 1
                            font_size: dp(28)
                            bold: True
                            on_text: app.update_preview()

                Label:
                    id: preview
                    text: "ON: 07:30  ->  OFF: 19:30"
                    font_size: dp(17)
                    bold: True
                    color: 0.15, 0.3, 0.7, 1
                    size_hint_y: None
                    height: dp(45)

                Button:
                    text: "SAVE & SEND"
                    size_hint: None, None
                    size: dp(300), dp(58)
                    pos_hint: {"center_x": 0.5}
                    background_normal: ""
                    background_color: 0.15, 0.7, 0.3, 1
                    color: 1, 1, 1, 1
                    font_size: dp(16)
                    bold: True
                    on_release: app.save_timer()

                Button:
                    text: "Toggle Timer"
                    size_hint: None, None
                    size: dp(300), dp(52)
                    pos_hint: {"center_x": 0.5}
                    background_normal: ""
                    background_color: 0.6, 0.35, 0.85, 1
                    color: 1, 1, 1, 1
                    font_size: dp(15)
                    bold: True
                    on_release: app.send_command("T")


<StatusScreen>:
    name: "status"
    BoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: 0.93, 0.95, 0.98, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(70)
            padding: dp(10), dp(15), dp(15), dp(10)
            canvas.before:
                Color:
                    rgba: 0.13, 0.29, 0.65, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: "<"
                size_hint: None, None
                size: dp(45), dp(45)
                pos_hint: {"center_y": 0.5}
                background_normal: ""
                background_color: 0.1, 0.22, 0.5, 1
                color: 1, 1, 1, 1
                font_size: dp(20)
                bold: True
                on_release: app.go("home")

            Label:
                text: "Status Log"
                color: 1, 1, 1, 1
                font_size: dp(19)
                bold: True

            Button:
                text: "R"
                size_hint: None, None
                size: dp(45), dp(45)
                pos_hint: {"center_y": 0.5}
                background_normal: ""
                background_color: 0.15, 0.7, 0.3, 1
                color: 1, 1, 1, 1
                font_size: dp(20)
                bold: True
                on_release: app.send_command("s")

        ScrollView:
            BoxLayout:
                id: log_box
                orientation: "vertical"
                padding: dp(15)
                spacing: dp(6)
                size_hint_y: None
                height: self.minimum_height


<SettingsScreen>:
    name: "settings"
    BoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: 0.93, 0.95, 0.98, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(70)
            padding: dp(10), dp(15), dp(15), dp(10)
            canvas.before:
                Color:
                    rgba: 0.13, 0.29, 0.65, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: "<"
                size_hint: None, None
                size: dp(45), dp(45)
                pos_hint: {"center_y": 0.5}
                background_normal: ""
                background_color: 0.1, 0.22, 0.5, 1
                color: 1, 1, 1, 1
                font_size: dp(20)
                bold: True
                on_release: app.go("home")

            Label:
                text: "Settings"
                color: 1, 1, 1, 1
                font_size: dp(19)
                bold: True

        ScrollView:
            BoxLayout:
                orientation: "vertical"
                padding: dp(20)
                spacing: dp(20)
                size_hint_y: None
                height: self.minimum_height

                GlassCard:
                    size: dp(340), dp(310)

                    Label:
                        text: "BLUETOOTH CONNECTION"
                        font_size: dp(12)
                        bold: True
                        color: 0.15, 0.3, 0.7, 1
                        size_hint_y: None
                        height: dp(25)

                    Button:
                        text: "Scan Paired Devices"
                        size_hint_y: None
                        height: dp(48)
                        background_normal: ""
                        background_color: 0.2, 0.5, 0.9, 1
                        color: 1, 1, 1, 1
                        bold: True
                        font_size: dp(14)
                        on_release: app.scan_devices()

                    ScrollView:
                        BoxLayout:
                            id: device_list
                            orientation: "vertical"
                            size_hint_y: None
                            height: self.minimum_height
                            spacing: dp(4)

                    Button:
                        id: bt_toggle_btn
                        text: "Connect"
                        size_hint_y: None
                        height: dp(48)
                        background_normal: ""
                        background_color: 0.15, 0.7, 0.3, 1
                        color: 1, 1, 1, 1
                        bold: True
                        font_size: dp(14)
                        on_release: app.toggle_bluetooth()

                GlassCard:
                    size: dp(340), dp(470)

                    Label:
                        text: "SET RTC CLOCK"
                        font_size: dp(12)
                        bold: True
                        color: 0.15, 0.3, 0.7, 1
                        size_hint_y: None
                        height: dp(25)

                    Label:
                        id: keypad_display
                        text: "00:00"
                        font_size: dp(48)
                        bold: True
                        color: 0.1, 0.15, 0.35, 1
                        size_hint_y: None
                        height: dp(80)

                    GridLayout:
                        cols: 3
                        spacing: dp(6)
                        size_hint_y: None
                        height: dp(300)

                        Button:
                            text: "1"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("1")
                        Button:
                            text: "2"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("2")
                        Button:
                            text: "3"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("3")
                        Button:
                            text: "4"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("4")
                        Button:
                            text: "5"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("5")
                        Button:
                            text: "6"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("6")
                        Button:
                            text: "7"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("7")
                        Button:
                            text: "8"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("8")
                        Button:
                            text: "9"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("9")
                        Button:
                            text: "DEL"
                            background_normal: ""
                            background_color: 0.95, 0.5, 0.15, 1
                            color: 1, 1, 1, 1
                            font_size: dp(14)
                            bold: True
                            on_release: app.keypad_back()
                        Button:
                            text: "0"
                            background_normal: ""
                            background_color: 0.94, 0.96, 1, 1
                            color: 0.1, 0.15, 0.35, 1
                            font_size: dp(24)
                            bold: True
                            on_release: app.keypad_digit("0")
                        Button:
                            text: "OK"
                            background_normal: ""
                            background_color: 0.15, 0.7, 0.3, 1
                            color: 1, 1, 1, 1
                            font_size: dp(18)
                            bold: True
                            on_release: app.send_rtc()
"""


# ============================================================
# App
# ============================================================
class CoolerApp(App):
    def build(self):
        self.title = "Cooler Control"
        Window.clearcolor = (0.93, 0.95, 0.98, 1)

        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.BLUETOOTH,
                    Permission.BLUETOOTH_ADMIN,
                    Permission.BLUETOOTH_CONNECT,
                    Permission.BLUETOOTH_SCAN,
                ])
            except Exception as e:
                print("Perm error:", e)

        self.bt = BluetoothManager()
        self.bt.on_line_received = self.on_bt_line
        self.bt.on_connection_change = self.on_bt_connection_change
        self.selected_device = None
        self.keypad_value = ""

        Builder.load_string(KV)

        self.sm = ScreenManager(transition=SlideTransition(duration=0.2))
        self.sm.add_widget(HomeScreen(name="home"))
        self.sm.add_widget(TimerScreen(name="timer"))
        self.sm.add_widget(StatusScreen(name="status"))
        self.sm.add_widget(SettingsScreen(name="settings"))
        return self.sm

    def go(self, name):
        self.sm.current = name

    def update_preview(self):
        try:
            timer = self.sm.get_screen("timer")
            oh = timer.ids.on_hour.text
            om = timer.ids.on_min.text
            fh = timer.ids.off_hour.text
            fm = timer.ids.off_min.text
            timer.ids.preview.text = "ON: %s:%s  ->  OFF: %s:%s" % (oh, om, fh, fm)
        except Exception as e:
            print("Preview error:", e)

    def save_timer(self):
        if not self.bt.connected:
            self.add_log("!! Not connected")
            return
        try:
            timer = self.sm.get_screen("timer")
            on_cmd = "ON" + timer.ids.on_hour.text + timer.ids.on_min.text
            off_cmd = "OFF" + timer.ids.off_hour.text + timer.ids.off_min.text
            self.bt.send(on_cmd)
            self.add_log(">> " + on_cmd)

            def send_off(dt):
                self.bt.send(off_cmd)
                self.add_log(">> " + off_cmd)
                self.add_log("== Timer sent ==")
            Clock.schedule_once(send_off, 0.5)
        except Exception as e:
            print("Save timer error:", e)

    def keypad_digit(self, d):
        if len(self.keypad_value) < 4:
            self.keypad_value += d
            self._update_keypad_display()

    def keypad_back(self):
        if self.keypad_value:
            self.keypad_value = self.keypad_value[:-1]
            self._update_keypad_display()

    def _update_keypad_display(self):
        try:
            settings = self.sm.get_screen("settings")
            v = self.keypad_value
            if len(v) == 0:
                settings.ids.keypad_display.text = "00:00"
            elif len(v) <= 2:
                settings.ids.keypad_display.text = v.zfill(2) + ":00"
            else:
                settings.ids.keypad_display.text = v[:2] + ":" + v[2:].ljust(2, '0')
        except Exception as e:
            print("Keypad display error:", e)

    def send_rtc(self):
        if not self.bt.connected:
            self.add_log("!! Not connected")
            return
        if len(self.keypad_value) != 4:
            self.add_log("!! Enter 4 digits")
            return
        cmd = "S" + self.keypad_value
        self.bt.send(cmd)
        self.add_log(">> " + cmd)
        self.keypad_value = ""
        self._update_keypad_display()

    def on_bt_line(self, line):
        self.add_log("<< " + line)
        self.parse_status(line)

    def on_bt_connection_change(self, connected):
        try:
            home = self.sm.get_screen("home")
            settings = self.sm.get_screen("settings")
            if connected:
                home.ids.bt_status.text = "Connected"
                home.ids.bt_status.color = (0.4, 1, 0.4, 1)
                settings.ids.bt_toggle_btn.text = "Disconnect"
                settings.ids.bt_toggle_btn.background_color = (0.85, 0.25, 0.25, 1)
                self.add_log(">> Connected")
            else:
                home.ids.bt_status.text = "Disconnected"
                home.ids.bt_status.color = (1, 0.6, 0.6, 1)
                settings.ids.bt_toggle_btn.text = "Connect"
                settings.ids.bt_toggle_btn.background_color = (0.15, 0.7, 0.3, 1)
                self.add_log(">> Disconnected")
        except Exception as e:
            print("Conn change error:", e)

    def parse_status(self, line):
        try:
            home = self.sm.get_screen("home")
            if "Temp:" in line:
                val = line.split("Temp:")[1].strip().split(" ")[0]
                home.ids.temp_label.text = val
            elif "Humidity:" in line:
                val = line.split("Humidity:")[1].strip().split(" ")[0]
                home.ids.hum_label.text = "Humidity  " + val + " %"
            elif "Time:" in line:
                val = line.split("Time:")[1].strip()
                home.ids.rtc_label.text = "Time  " + val
        except Exception as e:
            print("Parse error:", e)

    def send_command(self, cmd):
        if not self.bt.connected:
            self.add_log("!! Not connected")
            return
        self.bt.send(cmd)
        self.add_log(">> " + cmd)

    def scan_devices(self):
        try:
            settings = self.sm.get_screen("settings")
            device_list = settings.ids.device_list
            device_list.clear_widgets()
            devices = self.bt.get_paired_devices()
            if not devices:
                self.add_log("!! No paired devices")
                return
            from kivy.uix.button import Button
            for d in devices:
                btn = Button(
                    text=d["name"] + "  -  " + d["address"],
                    size_hint_y=None,
                    height=dp(50),
                    background_normal="",
                    background_color=(0.92, 0.94, 1, 1),
                    color=(0.15, 0.2, 0.5, 1),
                    font_size=dp(13),
                    bold=True,
                )
                btn.bind(on_release=lambda x, dev=d: self.select_device(dev))
                device_list.add_widget(btn)
            self.add_log(">> Found %d devices" % len(devices))
        except Exception as e:
            print("Scan error:", e)

    def select_device(self, device):
        self.selected_device = device
        self.add_log(">> Selected: " + device["name"])

    def toggle_bluetooth(self):
        if self.bt.connected:
            self.bt.disconnect()
        else:
            if self.selected_device is None:
                self.add_log("!! Select a device first")
                return
            self.bt.connect(self.selected_device)

    def add_log(self, text):
        try:
            status = self.sm.get_screen("status")
            log_box = status.ids.log_box
            from kivy.uix.label import Label
            from kivy.graphics import Color, RoundedRectangle

            if text.startswith(">>"):
                bg = (0.85, 0.9, 1, 1)
                fg = (0.15, 0.25, 0.55, 1)
            elif text.startswith("<<"):
                bg = (0.88, 1, 0.88, 1)
                fg = (0.1, 0.45, 0.1, 1)
            elif text.startswith("!!"):
                bg = (1, 0.9, 0.9, 1)
                fg = (0.7, 0.15, 0.15, 1)
            elif text.startswith("=="):
                bg = (1, 0.98, 0.85, 1)
                fg = (0.55, 0.4, 0.05, 1)
            else:
                bg = (1, 1, 1, 1)
                fg = (0.2, 0.2, 0.2, 1)

            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(38),
                padding=dp(10),
            )

            with row.canvas.before:
                Color(*bg)
                rect = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(8)])

            def update_rect(w, v):
                rect.pos = w.pos
                rect.size = w.size

            row.bind(pos=update_rect, size=update_rect)

            lbl = Label(
                text=text,
                font_size=dp(13),
                color=fg,
                halign="left",
                valign="middle",
                bold=True,
            )
            lbl.bind(size=lambda s, v: setattr(s, "text_size", v))
            row.add_widget(lbl)
            log_box.add_widget(row)
        except Exception as e:
            print("Log error:", e, text)


if __name__ == "__main__":
    CoolerApp().run()