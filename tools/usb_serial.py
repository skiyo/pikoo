"""Keep a USB console close from changing the ESP's reset control lines."""
import sys


def preserve_lines(port):
    if sys.platform == "darwin":
        import termios
        settings = termios.tcgetattr(port.fileno())
        settings[2] &= ~termios.HUPCL
        termios.tcsetattr(port.fileno(), termios.TCSANOW, settings)
