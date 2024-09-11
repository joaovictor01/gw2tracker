import ctypes
import sys
from src.gui import App
from src.gui import start_new_session

try:
    import BUILD_CONSTANTS

    excluded_vars = [
        "__builtins__",
        "__cached__",
        "__doc__",
        "__loader__",
        "__package__",
        "__spec__",
    ]

    for var in dir(BUILD_CONSTANTS):
        if var in excluded_vars:
            continue
        attr = BUILD_CONSTANTS.__getattribute__(var)
except Exception:
    pass


def run():
    """This method runs the application."""
    app = App("GW2 Session Tracker", (400, 120))
    start_new_session()
    app.mainloop()


if __name__ == "__main__":
    run()
