"""Keep a USB console close from changing the ESP's reset control lines."""
import sys
import serial


class ConsoleSerial(serial.Serial):
    """Avoid two separate modem-control writes just to observe a USB console.

    Explicit DTR/RTS operations still work for a caller performing a flash reset.
    """
    def open(self):
        self._console_opening = sys.platform == "darwin"
        try:
            super().open()
            preserve_lines(self)
        finally:
            self._console_opening = False

    def _update_dtr_state(self):
        if not getattr(self, "_console_opening", False):
            super()._update_dtr_state()

    def _update_rts_state(self):
        if not getattr(self, "_console_opening", False):
            super()._update_rts_state()


def preserve_lines(port):
    if sys.platform == "darwin":
        import termios
        settings = termios.tcgetattr(port.fileno())
        settings[2] &= ~termios.HUPCL
        termios.tcsetattr(port.fileno(), termios.TCSANOW, settings)
