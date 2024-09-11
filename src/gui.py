import os
import json
import sys
import threading
import time
import tkinter as tk
from tkinter import CENTER, TOP, StringVar, ttk, W, E, BOTTOM, X, messagebox
from typing import Optional, Tuple
from session_tracker import SessionTracker
from loguru import logger
from helpers import get_current_file_path, create_session_file

BUTTONS_FRAME = None
MAIN_FRAME = None
CONFIG = {}
SESSION_TRACKER = None
STOP_SESSION = False
CURRENT_SESSION_THREAD = None

API_KEY = ""


def set_api_key(key: str):
    global API_KEY
    print(f"Key: {key}")
    API_KEY = key


def load_config():
    global CONFIG
    logger.info("Loading config")
    config_file_name = (
        "config_dev.json" if os.environ.get("MODE") == "dev" else "config.json"
    )
    with open(os.path.join(get_current_file_path(), config_file_name), "r") as f:
        CONFIG = json.load(f)


class App(tk.Tk):
    def __init__(self, title: str, size: Tuple[int, int]):
        global MAIN_FRAME, SESSION_TRACKER
        super().__init__()
        self.title(title)
        self.style = ttk.Style(self)
        self.set_transparency(0.5)
        self.geometry(f"{size[0]}x{size[1]}")
        self.minsize(size[0], size[1])
        self.configure_style()
        load_config()
        if CONFIG.get("api_key"):
            SESSION_TRACKER = SessionTracker(CONFIG.get("api_key"))
            self._frame = None
            MAIN_FRAME = MainFrame(self)
            self.main_frame = MAIN_FRAME
            self.buttons_frame = ButtonsFrame(self)
            MAIN_FRAME.pack(side=TOP, fill=X)
            BUTTONS_FRAME = ButtonsFrame(self)
            BUTTONS_FRAME.pack(side=BOTTOM, fill=X)
        else:
            self._frame = Config(self)

    def load_main_frame(self):
        self.main_frame = MAIN_FRAME
        # self.switch_frame(SessionProfitTracker)
        self.buttons_frame = ButtonsFrame(self)
        MAIN_FRAME.pack(side=TOP, fill=X)
        BUTTONS_FRAME = ButtonsFrame(app)
        BUTTONS_FRAME.pack(side=BOTTOM, fill=X)

    def configure_style(self):
        self.configure(background="black")
        self.style.configure("TFrame", background="black")
        self.style.configure(
            "TLabel",
            background="black",
            foreground="white",
            font=("Helvetica", 12, "bold"),
        )
        self.style.configure(
            "TButton",
            background="black",
            foreground="white",
            font=("Helvetica", 12, "bold"),
        )

    def switch_frame(self, frame_class, extra=None):
        """Allow lazy switch between :class:`tkinter.Frame` objects.

        :param frame_class: a :class:`tkinter.Frame` object
        :type frame_class: :class:`tkinter.Frame`
        :param extra: a dictionary with extra arguments
        :type extra: dict, optional
        """
        new_frame = frame_class(self)
        if self._frame is not None:
            self._frame.destroy()
        self._frame = new_frame
        self._frame.pack()

    def set_transparency(self, transparency):
        self.wait_visibility()
        self.wm_attributes("-alpha", transparency)


class ButtonsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        # self.pack(side=BOTTOM, fill=X)


class MainFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.session_profit_tracker = SessionProfitTracker(self)
        self.session_profit_tracker.grid()


class SessionProfitTracker(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.start_value = 0
        self.current_value = 0
        self.profit = 0
        self.style = ttk.Style(self)
        self.create_session_tracker_widgets(parent)

    def set_start_value(self, value: int):
        self.start_value = str(value)

    def set_current_value(self, value: int):
        self.current_value = str(value)

    def set_profit(self, value: int):
        self.profit = str(value)

    def set_values(self, start: int = 0, current: int = 0, profit: int = 0):
        self.set_start_value(start)
        self.set_current_value(current)
        self.set_profit(profit)

    def format_value(self, value) -> str:
        value = int(value)
        gold = int(value / (100 * 100))
        silver = int(int(str(value / (100 * 100)).split(".")[1]) / 100)
        copper = int(str(value / 100).split(".")[1])
        formatted_value = f"{gold} gold, {silver} silver, {copper} copper"
        return formatted_value

    def update_values(self):
        self.start_value_label["text"] = self.format_value(self.start_value)
        self.start_value_label.configure(text=self.format_value(self.start_value))
        self.current_value_label["text"] = self.format_value(self.current_value)
        self.current_value_label.configure(text=self.format_value(self.current_value))
        self.profit_label["text"] = self.format_value(self.profit)
        self.profit_label.configure(text=self.format_value(self.profit))
        self.current_value_label.grid()

    def create_session_tracker_widgets(self, parent):
        # self.configure_style()
        self.style = "SessionFrame"
        parent.columnconfigure(0, weight=2)
        parent.columnconfigure(1, weight=3)
        parent.rowconfigure((0, 1, 2), weight=1)

        start_value_text_label = ttk.Label(parent, text="Start value")
        start_value_text_label.grid(row=0, column=0, sticky=W, padx=2, pady=2)
        self.start_value_label = ttk.Label(
            parent, text=self.start_value, justify="center"
        )
        self.start_value_label.grid(row=0, column=1, sticky=W, padx=2, pady=2)

        current_value_text_label = ttk.Label(parent, text="Current value")
        current_value_text_label.grid(row=1, column=0, sticky=W, padx=2, pady=2)
        self.current_value_label = ttk.Label(parent, text=self.current_value)
        self.current_value_label.grid(row=1, column=1, sticky=W, padx=2, pady=2)

        profit_text_label = ttk.Label(parent, text="Profit")
        profit_text_label.grid(row=2, column=0, sticky=W + E, padx=2, pady=2)
        self.profit_label = ttk.Label(parent, text=self.profit)
        self.profit_label.grid(row=2, column=1, sticky=W, padx=2, pady=2)

        self.start_new_session_btn = ttk.Button(
            BUTTONS_FRAME, text="New session", command=lambda: start_new_session()
        )
        self.start_new_session_btn.pack(side=BOTTOM, fill=X)
        self.export_session_btn = ttk.Button(
            BUTTONS_FRAME,
            text="Export and save session details",
            command=lambda: save_session(),
        )
        self.export_session_btn.pack(side=BOTTOM, fill=X)


class Config(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        ttk.Label(self, background="green").pack(expand=True, fill="both")
        self.pack(expand=True, fill="both")
        self.create_widgets(parent)

    def save_api_key_btn_pressed(self, parent):
        global MAIN_FRAME
        parent.api_key = self.api_key_input.get()
        MAIN_FRAME = MainFrame
        parent.switch_frame(MAIN_FRAME)
        parent.load_main_frame()

    def create_widgets(self, parent):
        input_text = StringVar()
        self.api_key_input = ttk.Entry(self, textvariable=input_text, justify=CENTER)
        self.api_key_input.focus_force()
        self.api_key_input.pack(side=TOP, ipadx=30, ipady=6)
        save_btn = ttk.Button(
            self,
            text="Save",
            command=lambda: self.save_api_key_btn_pressed(parent),
        )
        save_btn.pack(side=TOP, pady=10)


def test_watch_for_changes():
    global MAIN_FRAME
    current_value = 0
    while True:
        time.sleep(3)
        current_value += 10
        MAIN_FRAME.session_profit_tracker.set_current_value(current_value)
        MAIN_FRAME.session_profit_tracker.update_values()
        MAIN_FRAME.pack()


def watch_for_changes():
    global MAIN_FRAME
    while True:
        values = SESSION_TRACKER.update_session()
        MAIN_FRAME.session_profit_tracker.set_current_value(values.get("current_value"))
        MAIN_FRAME.session_profit_tracker.set_profit(values.get("profit_value"))
        MAIN_FRAME.session_profit_tracker.update_values()
        MAIN_FRAME.pack()
        time.sleep(CONFIG.get("update_every_minutes") * 60)


def save_session(session_data: Optional[dict] = None):
    global SESSION_TRACKER
    session_data = session_data if session_data else SESSION_TRACKER.get_session_data()
    session_file = create_session_file("gw2tracker")
    logger.info(f"Saving session to {session_file}")
    session_data_json = json.dumps(session_data, indent=2)
    with open(session_file, "w") as f:
        f.write(session_data_json)
    logger.info("Session saved")
    messagebox.showinfo("Session saved", f"Session saved to {session_file}")


def start_session_tracker():
    global SESSION_TRACKER, STOP_SESSION
    SESSION_TRACKER = SessionTracker()
    start_session_values = SESSION_TRACKER.start_session()
    start_value = start_session_values.get("start_value")
    MAIN_FRAME.session_profit_tracker.set_start_value(start_value)
    MAIN_FRAME.session_profit_tracker.update_values()
    MAIN_FRAME.pack()
    while not STOP_SESSION:
        time.sleep(CONFIG.get("update_every_minutes") * 60)
        values = SESSION_TRACKER.update_session()
        MAIN_FRAME.session_profit_tracker.set_start_value(start_value)
        MAIN_FRAME.session_profit_tracker.set_current_value(values.get("current_value"))
        MAIN_FRAME.session_profit_tracker.set_profit(values.get("profit_value"))
        MAIN_FRAME.session_profit_tracker.update_values()
        MAIN_FRAME.pack()
    sys.exit()
    return


def start_new_session():
    global SESSION_TRACKER, STOP_SESSION, CURRENT_SESSION_THREAD
    STOP_SESSION = True
    session_data = SESSION_TRACKER.get_session_data()
    SESSION_TRACKER.reset_session()
    MAIN_FRAME.session_profit_tracker.set_values(0, 0, 0)
    MAIN_FRAME.session_profit_tracker.update_values()
    MAIN_FRAME.pack()
    STOP_SESSION = False
    if CURRENT_SESSION_THREAD:
        save_session(session_data)
        # CURRENT_SESSION_THREAD.exit()
        CURRENT_SESSION_THREAD.join()
        CURRENT_SESSION_THREAD = None
    CURRENT_SESSION_THREAD = threading.Thread(target=start_session_tracker)
    CURRENT_SESSION_THREAD.start()


if __name__ == "__main__":
    app = App("GW2 Session Tracker", (400, 120))
    start_new_session()
    app.mainloop()
