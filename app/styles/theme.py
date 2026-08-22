DARK_THEME = """
QMainWindow {
    background-color: #111318;
}

QWidget {
    background-color: #111318;
    color: #E8EAF0;
    font-family: "Segoe UI";
}

QFrame {
    background-color: #181B22;
    border: 1px solid #252A33;
    border-radius: 14px;
}

QPushButton {
    background-color: #4F7CFF;
    color: white;
    border: none;
    border-radius: 9px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #638CFF;
}

QPushButton:pressed {
    background-color: #3D68E6;
}

QLabel {
    background: transparent;
}
"""


LIGHT_THEME = """
QMainWindow {
    background-color: #F7F8FA;
}

QWidget {
    background-color: #F7F8FA;
    color: #171A21;
    font-family: "Segoe UI";
}

QFrame {
    background-color: #FFFFFF;
    border: 1px solid #E2E5EA;
    border-radius: 14px;
}

QPushButton {
    background-color: #4F7CFF;
    color: white;
    border: none;
    border-radius: 9px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #638CFF;
}

QPushButton:pressed {
    background-color: #3D68E6;
}

QLabel {
    background: transparent;
}
"""


def get_theme(dark_mode: bool = True) -> str:
    """Return the selected WorkPulse application theme."""
    return DARK_THEME if dark_mode else LIGHT_THEME
