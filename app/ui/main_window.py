from datetime import datetime, timedelta, date
import time
import ctypes

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStyle,
    QSystemTrayIcon,
    QMenu,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.data.storage import (
    add_break_record,
    add_water_record,
    add_work_session,
    load_history,
    save_settings,
    get_settings,
    save_history,
)


class WorkPulseWindow(QMainWindow):
    """
    WorkPulse
    ----------
    Desktop work-health companion.

    Improvements:
    - Cleaner dashboard
    - Correct 2L hydration target
    - Hydration progress capped at 100%
    - Today's data separated from historical totals
    - Better activity display
    - Functional Settings page
    - Better break handling
    - Eye-care countdown
    - Safer reset behaviour
    - Cleaner navigation
    - No Unicode-dependent navigation icons
    """

    WATER_GOAL_ML = 2000
    EYE_BREAK_INTERVAL = 20 * 60

    def __init__(self):
        super().__init__()

        self.setWindowTitle("WorkPulse")
        self.resize(1400, 850)
        self.setMinimumSize(1050, 700)

        self.session_seconds = 0.0
        self.session_running = True
        self.on_break = False

        self.idle_timeout = 60  # seconds
        self.user_idle = False

        self.session_started_at = datetime.now()
        self.last_runtime = time.monotonic()
        self.save_active_session()


        self.water_goal_ml = self.WATER_GOAL_ML
        self.eye_break_interval = self.EYE_BREAK_INTERVAL
        self.eye_break_remaining = self.eye_break_interval

        self.current_page = "Overview"

        saved = load_history().get("active_session")
        if saved:
            self.session_seconds = float(
                saved.get("session_seconds", 0)
            )
            try:
                self.session_started_at = datetime.fromisoformat(
                    saved.get("started_at")
                )
            except Exception:
                pass

        self.build_ui()
        self.apply_styles()

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.show()

        self.runtime_timer = QTimer(self)
        self.runtime_timer.timeout.connect(self.update_runtime)
        self.runtime_timer.start(1000)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.save_active_session)
        self.autosave_timer.start(10000)

        self.update_overview_values()

    # =========================================================
    # UI
    # =========================================================

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -----------------------------------------------------
        # SIDEBAR
        # -----------------------------------------------------

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(270)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(22, 28, 22, 22)
        sidebar_layout.setSpacing(8)

        brand = QLabel("WorkPulse")
        brand.setObjectName("brand")

        tagline = QLabel("Work health companion")
        tagline.setObjectName("tagline")

        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(tagline)
        sidebar_layout.addSpacing(28)

        self.overview_button = self.create_nav_button(
            "Overview",
            True,
        )

        self.history_button = self.create_nav_button(
            "History",
        )

        self.insights_button = self.create_nav_button(
            "Insights",
        )

        sidebar_layout.addWidget(self.overview_button)
        sidebar_layout.addWidget(self.history_button)
        sidebar_layout.addWidget(self.insights_button)

        sidebar_layout.addSpacing(22)

        preferences = QLabel("PREFERENCES")
        preferences.setObjectName("navSection")

        sidebar_layout.addWidget(preferences)

        self.settings_button = self.create_nav_button(
            "Settings",
        )

        self.privacy_button = self.create_nav_button(
            "Privacy",
        )

        sidebar_layout.addWidget(self.settings_button)
        sidebar_layout.addWidget(self.privacy_button)

        sidebar_layout.addStretch()

        self.monitor_dot = QLabel("â—  Monitoring active")
        self.monitor_dot.setObjectName("monitorStatus")

        sidebar_layout.addWidget(self.monitor_dot)

        root_layout.addWidget(sidebar)

        # -----------------------------------------------------
        # PAGE STACK
        # -----------------------------------------------------

        self.page_stack = QStackedWidget()

        self.overview_page = QWidget()
        self.history_page = QWidget()
        self.insights_page = QWidget()
        self.settings_page = QWidget()
        self.privacy_page = QWidget()

        self.overview_layout = self.create_page_layout(
            self.overview_page
        )

        self.history_layout = self.create_page_layout(
            self.history_page
        )

        self.insights_layout = self.create_page_layout(
            self.insights_page
        )

        self.settings_layout = self.create_page_layout(
            self.settings_page
        )

        self.privacy_layout = self.create_page_layout(
            self.privacy_page
        )

        self.page_stack.addWidget(self.overview_page)
        self.page_stack.addWidget(self.history_page)
        self.page_stack.addWidget(self.insights_page)
        self.page_stack.addWidget(self.settings_page)
        self.page_stack.addWidget(self.privacy_page)

        root_layout.addWidget(self.page_stack)

        self.build_overview_page()
        self.build_settings_page()
        self.build_privacy_page()

        self.overview_button.clicked.connect(
            self.show_overview
        )

        self.history_button.clicked.connect(
            self.show_history
        )

        self.insights_button.clicked.connect(
            self.show_insights
        )

        self.settings_button.clicked.connect(
            self.show_settings
        )

        self.privacy_button.clicked.connect(
            self.show_privacy
        )

    def create_page_layout(self, page):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)

        layout.setContentsMargins(
            44,
            38,
            44,
            38,
        )

        layout.setSpacing(18)

        scroll.setWidget(content)

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        return layout

    def create_nav_button(
        self,
        text,
        active=False,
    ):
        button = QPushButton(text)
        button.setObjectName(
            "navActive" if active else "navButton"
        )

        button.setMinimumHeight(48)
        button.setCursor(Qt.PointingHandCursor)

        return button

    # =========================================================
    # OVERVIEW
    # =========================================================

    def build_overview_page(self):
        layout = self.overview_layout

        header = QHBoxLayout()

        header_left = QVBoxLayout()
        header_left.setSpacing(4)

        title = QLabel(
            self.get_greeting()
        )
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Stay productive without ignoring your health."
        )
        subtitle.setObjectName("pageSubtitle")

        header_left.addWidget(title)
        header_left.addWidget(subtitle)

        header.addLayout(header_left)
        header.addStretch()

        self.status_label = QLabel("WORKING")
        self.status_label.setObjectName("statusBadge")
        self.status_label.setAlignment(Qt.AlignCenter)

        header.addWidget(self.status_label)

        layout.addLayout(header)

        # -----------------------------------------------------
        # TIMER CARD
        # -----------------------------------------------------

        timer_card = QFrame()
        timer_card.setObjectName("timerCard")

        timer_layout = QVBoxLayout(timer_card)

        timer_layout.setContentsMargins(
            28,
            25,
            28,
            25,
        )

        timer_layout.setSpacing(10)

        timer_top = QHBoxLayout()

        timer_title = QLabel(
            "CURRENT WORK SESSION"
        )
        timer_title.setObjectName("eyebrow")

        timer_top.addWidget(timer_title)
        timer_top.addStretch()

        self.timer_indicator = QLabel("ACTIVE")
        self.timer_indicator.setObjectName(
            "timerIndicator"
        )

        timer_top.addWidget(
            self.timer_indicator
        )

        timer_layout.addLayout(timer_top)

        self.session_value = QLabel(
            "00:00:00"
        )
        self.session_value.setObjectName(
            "bigTimer"
        )

        self.session_value.setAlignment(
            Qt.AlignCenter
        )

        timer_layout.addWidget(
            self.session_value
        )

        self.session_status = QLabel(
            "Work timer is running"
        )
        self.session_status.setObjectName(
            "timerStatus"
        )

        self.session_status.setAlignment(
            Qt.AlignCenter
        )

        timer_layout.addWidget(
            self.session_status
        )

        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.break_button = QPushButton(
            "Take a Break"
        )
        self.break_button.setObjectName(
            "primary"
        )
        self.break_button.setMinimumHeight(50)
        self.break_button.setCursor(
            Qt.PointingHandCursor
        )

        self.break_button.clicked.connect(
            self.toggle_break
        )

        self.reset_button = QPushButton(
            "Stop & Save"
        )
        self.reset_button.setObjectName(
            "secondary"
        )
        self.reset_button.setMinimumHeight(50)
        self.reset_button.setCursor(
            Qt.PointingHandCursor
        )

        self.reset_button.clicked.connect(
            self.stop_work
        )

        actions.addWidget(
            self.break_button,
            2,
        )

        actions.addWidget(
            self.reset_button,
            1,
        )

        timer_layout.addLayout(actions)

        layout.addWidget(timer_card)

        # -----------------------------------------------------
        # METRICS
        # -----------------------------------------------------

        metrics = QHBoxLayout()
        metrics.setSpacing(12)

        work_card, self.work_value = (
            self.create_metric_card(
                "WORK TIME",
                "00:00:00",
                "Current session",
            )
        )

        water_card, self.water_value = (
            self.create_metric_card(
                "HYDRATION",
                "0 ml",
                "Today's intake",
            )
        )

        break_card, self.break_value = (
            self.create_metric_card(
                "BREAKS",
                "0",
                "Breaks today",
            )
        )

        metrics.addWidget(work_card)
        metrics.addWidget(water_card)
        metrics.addWidget(break_card)

        layout.addLayout(metrics)

        # -----------------------------------------------------
        # HEALTH
        # -----------------------------------------------------

        health_header = QHBoxLayout()

        health_title = QLabel(
            "Health check"
        )
        health_title.setObjectName(
            "sectionTitle"
        )

        health_subtitle = QLabel(
            "Small habits during work make a difference."
        )
        health_subtitle.setObjectName(
            "mutedText"
        )

        health_header.addWidget(
            health_title
        )

        health_header.addStretch()

        health_header.addWidget(
            health_subtitle
        )

        layout.addLayout(health_header)

        health_row = QHBoxLayout()
        health_row.setSpacing(12)

        # Hydration

        hydration_card = QFrame()
        hydration_card.setObjectName(
            "healthCard"
        )

        hydration_layout = QVBoxLayout(
            hydration_card
        )

        hydration_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        hydration_layout.setSpacing(10)

        hydration_top = QHBoxLayout()

        hydration_title = QLabel(
            "Hydration"
        )
        hydration_title.setObjectName(
            "cardTitle"
        )

        self.hydration_percentage = QLabel(
            "0%"
        )
        self.hydration_percentage.setObjectName(
            "percentageLabel"
        )

        hydration_top.addWidget(
            hydration_title
        )

        hydration_top.addStretch()

        hydration_top.addWidget(
            self.hydration_percentage
        )

        hydration_layout.addLayout(
            hydration_top
        )

        self.water_progress = QProgressBar()

        self.water_progress.setRange(
            0,
            100,
        )

        self.water_progress.setValue(0)

        self.water_progress.setTextVisible(
            False
        )

        self.water_progress.setFixedHeight(
            9
        )

        hydration_layout.addWidget(
            self.water_progress
        )

        self.water_info = QLabel(
            "0 / 2,000 ml"
        )

        self.water_info.setObjectName(
            "mutedText"
        )

        hydration_layout.addWidget(
            self.water_info
        )

        water_buttons = QHBoxLayout()
        water_buttons.setSpacing(8)

        add_250 = QPushButton(
            "+ 250 ml"
        )
        add_250.setObjectName(
            "smallButton"
        )
        add_250.setCursor(
            Qt.PointingHandCursor
        )

        add_250.clicked.connect(
            lambda: self.add_water(250)
        )

        add_500 = QPushButton(
            "+ 500 ml"
        )
        add_500.setObjectName(
            "smallButton"
        )
        add_500.setCursor(
            Qt.PointingHandCursor
        )

        add_500.clicked.connect(
            lambda: self.add_water(500)
        )

        water_buttons.addWidget(
            add_250
        )

        water_buttons.addWidget(
            add_500
        )

        hydration_layout.addLayout(
            water_buttons
        )

        health_row.addWidget(
            hydration_card,
            2,
        )

        # Eye care

        eye_card = QFrame()
        eye_card.setObjectName(
            "healthCard"
        )

        eye_layout = QVBoxLayout(
            eye_card
        )

        eye_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        eye_layout.setSpacing(6)

        eye_title = QLabel(
            "Eye care"
        )
        eye_title.setObjectName(
            "cardTitle"
        )

        self.eye_value = QLabel(
            "20:00"
        )
        self.eye_value.setObjectName(
            "healthValue"
        )

        eye_description = QLabel(
            "Next eye break reminder"
        )
        eye_description.setObjectName(
            "mutedText"
        )

        eye_layout.addWidget(
            eye_title
        )

        eye_layout.addWidget(
            self.eye_value
        )

        eye_layout.addWidget(
            eye_description
        )

        health_row.addWidget(
            eye_card,
            1,
        )

        layout.addLayout(
            health_row
        )

        # -----------------------------------------------------
        # ACTIVITY
        # -----------------------------------------------------

        activity_title = QLabel(
            "Today's activity"
        )
        activity_title.setObjectName(
            "sectionTitle"
        )

        layout.addWidget(
            activity_title
        )

        self.activity_container = QFrame()
        self.activity_container.setObjectName(
            "activityContainer"
        )

        self.activity_layout = QVBoxLayout(
            self.activity_container
        )

        self.activity_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        self.activity_layout.setSpacing(8)

        layout.addWidget(
            self.activity_container
        )

        layout.addStretch()

    # =========================================================
    # SETTINGS
    # =========================================================

    def build_settings_page(self):
        layout = self.settings_layout

        title = QLabel("Settings")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Configure how WorkPulse behaves."
        )
        subtitle.setObjectName("pageSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Health settings

        card = QFrame()
        card.setObjectName("contentCard")

        card_layout = QVBoxLayout(card)

        card_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        card_layout.setSpacing(14)

        heading = QLabel(
            "Health preferences"
        )
        heading.setObjectName(
            "cardTitle"
        )

        card_layout.addWidget(
            heading
        )

        water_label = QLabel(
            "Daily hydration target"
        )
        water_label.setObjectName(
            "bodyText"
        )

        self.water_target_label = QLabel(
            "2,000 ml"
        )
        self.water_target_label.setObjectName(
            "settingValue"
        )

        water_buttons = QHBoxLayout()

        for amount in (
            1500,
            2000,
            2500,
            3000,
        ):
            button = QPushButton(
                f"{amount // 1000:g} L"
            )

            button.setObjectName(
                "smallButton"
            )

            button.setCursor(
                Qt.PointingHandCursor
            )

            button.clicked.connect(
                lambda checked=False,
                value=amount:
                self.set_water_goal(value)
            )

            water_buttons.addWidget(
                button
            )

        card_layout.addWidget(
            water_label
        )

        card_layout.addWidget(
            self.water_target_label
        )

        card_layout.addLayout(
            water_buttons
        )

        eye_label = QLabel(
            "Eye-care reminder"
        )
        eye_label.setObjectName(
            "bodyText"
        )

        self.eye_target_label = QLabel(
            "Every 20 minutes"
        )
        self.eye_target_label.setObjectName(
            "settingValue"
        )

        eye_buttons = QHBoxLayout()

        for minutes in (
            10,
            20,
            30,
        ):
            button = QPushButton(
                f"{minutes} min"
            )

            button.setObjectName(
                "smallButton"
            )

            button.setCursor(
                Qt.PointingHandCursor
            )

            button.clicked.connect(
                lambda checked=False,
                value=minutes:
                self.set_eye_interval(value)
            )

            eye_buttons.addWidget(
                button
            )

        card_layout.addWidget(
            eye_label
        )

        card_layout.addWidget(
            self.eye_target_label
        )

        card_layout.addLayout(
            eye_buttons
        )

        layout.addWidget(card)

        # Current configuration

        info_card = QFrame()
        info_card.setObjectName(
            "contentCard"
        )

        info_layout = QVBoxLayout(
            info_card
        )

        info_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        info_layout.setSpacing(8)

        info_heading = QLabel(
            "Current configuration"
        )
        info_heading.setObjectName(
            "cardTitle"
        )

        self.configuration_label = QLabel()
        self.configuration_label.setObjectName(
            "bodyText"
        )

        self.configuration_label.setWordWrap(
            True
        )

        info_layout.addWidget(
            info_heading
        )

        info_layout.addWidget(
            self.configuration_label
        )

        layout.addWidget(
            info_card
        )

        self.update_settings_display()

        layout.addStretch()

    # =========================================================
    # PRIVACY
    # =========================================================

    def build_privacy_page(self):
        layout = self.privacy_layout

        title = QLabel("Privacy")
        title.setObjectName(
            "pageTitle"
        )

        subtitle = QLabel(
            "Understand what WorkPulse records."
        )
        subtitle.setObjectName(
            "pageSubtitle"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName(
            "contentCard"
        )

        card_layout = QVBoxLayout(card)

        card_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        card_layout.setSpacing(12)

        heading = QLabel(
            "Local activity data"
        )
        heading.setObjectName(
            "cardTitle"
        )

        body = QLabel(
            "WorkPulse records work sessions, breaks "
            "and hydration activity so the dashboard "
            "can show your work-health patterns."
        )

        body.setObjectName(
            "bodyText"
        )

        body.setWordWrap(True)

        card_layout.addWidget(
            heading
        )

        card_layout.addWidget(
            body
        )

        layout.addWidget(
            card
        )

        layout.addStretch()

    # =========================================================
    # NAVIGATION
    # =========================================================

    def set_active_nav(
        self,
        active_button,
    ):
        buttons = (
            self.overview_button,
            self.history_button,
            self.insights_button,
            self.settings_button,
            self.privacy_button,
        )

        for button in buttons:
            button.setObjectName(
                "navActive"
                if button is active_button
                else "navButton"
            )

            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def show_overview(self):
        self.current_page = "Overview"

        self.page_stack.setCurrentWidget(
            self.overview_page
        )

        self.set_active_nav(
            self.overview_button
        )

        self.update_overview_values()

    def show_history(self):
        self.current_page = "History"

        self.refresh_history_page()

        self.page_stack.setCurrentWidget(
            self.history_page
        )

        self.set_active_nav(
            self.history_button
        )

    def show_insights(self):
        self.current_page = "Insights"

        self.refresh_insights()

        self.page_stack.setCurrentWidget(
            self.insights_page
        )

        self.set_active_nav(
            self.insights_button
        )

    def show_settings(self):
        self.current_page = "Settings"

        self.page_stack.setCurrentWidget(
            self.settings_page
        )

        self.set_active_nav(
            self.settings_button
        )

    def show_privacy(self):
        self.current_page = "Privacy"

        self.page_stack.setCurrentWidget(
            self.privacy_page
        )

        self.set_active_nav(
            self.privacy_button
        )

    # =========================================================
    # TIMER
    # =========================================================

    def save_active_session(self):
        if not self.session_running:
            return

        try:
            data = load_history()
            data["active_session"] = {
                "started_at": self.session_started_at.isoformat(),
                "session_seconds": int(self.session_seconds),
            }
            save_history(data)
        except Exception:
            pass

    def get_idle_seconds(self):
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("dwTime", ctypes.c_uint),
            ]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)

        if ctypes.windll.user32.GetLastInputInfo(
            ctypes.byref(info)
        ):
            tick = ctypes.windll.kernel32.GetTickCount()
            return max(
                0,
                (tick - info.dwTime) / 1000,
            )

        return 0
    def update_runtime(self):
        now = time.monotonic()

        elapsed = now - self.last_runtime

        self.last_runtime = now

        if elapsed < 0:
            elapsed = 0

        if elapsed > 2:
            elapsed = 1

        idle_seconds = self.get_idle_seconds()

        if idle_seconds >= self.idle_timeout:
            if not self.user_idle:
                self.user_idle = True
                self.status_label.setText("IDLE")
                self.timer_indicator.setText("PAUSED")
                self.monitor_dot.setText("Inactive - timer paused")
        else:
            if self.user_idle:
                self.user_idle = False
                self.status_label.setText("WORKING")
                self.timer_indicator.setText("ACTIVE")
                self.monitor_dot.setText("Monitoring active")

        if (
            self.session_running
            and not self.on_break
            and not self.user_idle
        ):
            self.session_seconds += elapsed
            self.eye_break_remaining -= elapsed

            if self.eye_break_remaining <= 0:
                self.eye_break_remaining = (
                    self.eye_break_interval
                )

                self.show_eye_reminder()

        self.update_overview_values()

    def toggle_break(self):
        if self.on_break:
            self.resume_work()
        else:
            self.start_break()

    def start_break(self):
        if self.on_break:
            return

        self.on_break = True

        self.session_status.setText(
            "Break in progress"
        )

        self.status_label.setText(
            "ON BREAK"
        )

        self.timer_indicator.setText(
            "BREAK"
        )

        self.break_button.setText(
            "Resume Work"
        )

        self.monitor_dot.setText("Break in progress")

        try:
            add_break_record(
                datetime.now().strftime(
                    "%H:%M:%S"
                )
            )
        except Exception:
            pass

        self.update_overview_values()

        if self.current_page == "History":
            self.refresh_history_page()

        if self.current_page == "Insights":
            self.refresh_insights()

    def resume_work(self):
        if not self.on_break:
            return

        self.on_break = False

        self.eye_break_remaining = (
            self.eye_break_interval
        )

        self.session_status.setText(
            "Work timer is running"
        )

        self.status_label.setText(
            "WORKING"
        )

        self.timer_indicator.setText(
            "ACTIVE"
        )

        self.break_button.setText(
            "Take a Break"
        )

        self.monitor_dot.setText("Monitoring active")

        self.update_overview_values()

    def stop_work(self):
        if not self.session_running:
            return

        if self.session_seconds <= 0:
            return

        try:
            add_work_session(
                self.session_started_at.strftime("%H:%M:%S"),
                datetime.now().strftime("%H:%M:%S"),
                int(self.session_seconds),
            )
            data = load_history()
            data["active_session"] = None
            save_history(data)
        except Exception as e:
            print("HISTORY SAVE ERROR:", e)

        self.session_running = False
        self.on_break = False

        try:
            data = load_history()
            data["active_session"] = None
            save_history(data)
        except Exception:
            pass


        self.session_status.setText(
            "Work session stopped and saved"
        )

        self.status_label.setText(
            "STOPPED"
        )

        self.timer_indicator.setText(
            "STOPPED"
        )

        self.break_button.setText(
            "Take a Break"
        )

        self.monitor_dot.setText(
            "Monitoring stopped"
        )

        if (
            hasattr(self, "tray_icon")
            and QSystemTrayIcon.isSystemTrayAvailable()
            and QSystemTrayIcon.supportsMessages()
        ):
            self.tray_icon.showMessage(
                "WorkPulse",
                "Work session saved successfully.",
                QSystemTrayIcon.Information,
                5000,
            )

        self.update_overview_values()

        if self.current_page == "History":
            self.refresh_history_page()

        if self.current_page == "Insights":
            self.refresh_insights()
    # =========================================================
    # WATER
    # =========================================================

    def add_water(self, amount):
        try:
            record = add_water_record(
                int(amount)
            )

            recorded_amount = int(
                record.get(
                    "amount_ml",
                    amount,
                )
            )

            if recorded_amount <= 0:
                return

        except Exception:
            return

        self.update_overview_values()

        if self.current_page == "History":
            self.refresh_history_page()

        if self.current_page == "Insights":
            self.refresh_insights()

    def set_water_goal(self, amount):
        self.water_goal_ml = int(amount)

        self.update_settings_display()
        self.update_overview_values()

    def set_eye_interval(self, minutes):
        self.eye_break_interval = (
            int(minutes) * 60
        )

        self.eye_break_remaining = (
            self.eye_break_interval
        )

        self.update_settings_display()
        self.update_overview_values()

    # =========================================================
    # DATA
    # =========================================================

    def get_history(self):
        try:
            data = load_history()

            if isinstance(data, dict):
                return data

        except Exception:
            pass

        return {
            "work_sessions": [],
            "break_records": [],
            "water_records": [],
        }

    def get_today_records(self):
        history = self.get_history()

        return (
            history.get(
                "work_sessions",
                [],
            ),
            history.get(
                "break_records",
                [],
            ),
            history.get(
                "water_records",
                [],
            ),
        )

    def get_water_total(self):
        _, _, records = (
            self.get_today_records()
        )

        total = 0

        for record in records:
            try:
                total += max(
                    0,
                    int(
                        record.get(
                            "amount_ml",
                            0,
                        )
                    ),
                )
            except Exception:
                continue

        return total

    def get_break_count(self):
        _, records, _ = (
            self.get_today_records()
        )

        return len(records)

    # =========================================================
    # OVERVIEW UPDATE
    # =========================================================

    def update_overview_values(self):
        if not hasattr(
            self,
            "session_value",
        ):
            return

        water_total = self.get_water_total()
        break_count = self.get_break_count()

        session_time = self.format_time(
            self.session_seconds
        )

        self.session_value.setText(
            session_time
        )

        self.work_value.setText(
            session_time
        )

        self.water_value.setText(
            f"{water_total:,} ml"
        )

        self.break_value.setText(
            str(break_count)
        )

        percentage = int(
            (
                water_total
                / max(
                    1,
                    self.water_goal_ml,
                )
            )
            * 100
        )

        percentage = min(
            100,
            percentage,
        )

        self.hydration_percentage.setText(
            f"{percentage}%"
        )

        self.water_progress.setValue(
            percentage
        )

        self.water_info.setText(
            f"{water_total:,} / "
            f"{self.water_goal_ml:,} ml"
        )

        remaining = max(
            0,
            int(
                self.eye_break_remaining
            ),
        )

        self.eye_value.setText(
            self.format_short_time(
                remaining
            )
        )

        self.refresh_activity()

    def refresh_activity(self):
        if not hasattr(
            self,
            "activity_layout",
        ):
            return

        self.clear_layout(
            self.activity_layout
        )

        history = self.get_history()

        events = []

        for record in history.get(
            "water_records",
            [],
        ):
            events.append(
                (
                    record.get(
                        "time",
                        record.get(
                            "timestamp",
                            "--:--:--",
                        ),
                    ),
                    "Water",
                    f"+ {int(record.get('amount_ml', 0)):,} ml",
                )
            )

        for record in history.get(
            "break_records",
            [],
        ):
            events.append(
                (
                    record.get(
                        "time",
                        record.get(
                            "timestamp",
                            "--:--:--",
                        ),
                    ),
                    "Break",
                    "Break taken",
                    record.get("date", ""),
                )
            )

        seen_work = set()

        for record in history.get(
            "work_sessions",
            [],
        ):
            key = (
                record.get("start_time"),
                record.get("date"),
            )

            if key in seen_work:
                continue

            seen_work.add(key)
            duration = int(
                record.get(
                    "duration_seconds",
                    0,
                )
            )

            events.append(
                (
                    record.get(
                        "end_time",
                        record.get(
                            "time",
                            record.get(
                                "timestamp",
                                "--:--:--",
                            ),
                        ),
                    ),
                    "Work",
                    f"Session completed · {self.format_time(duration)}",
                )
            )

        events.sort(
            key=lambda item: str(
                item[0]
            ),
            reverse=True,
        )

        events = events[:8]

        if not events:
            empty = QLabel(
                "No activity recorded yet."
            )

            empty.setObjectName(
                "mutedText"
            )

            self.activity_layout.addWidget(
                empty
            )

            return

        for event_time, event_type, text in events:
            row = QFrame()
            row.setObjectName(
                "activityRow"
            )

            row_layout = QHBoxLayout(row)

            row_layout.setContentsMargins(
                10,
                8,
                10,
                8,
            )

            time_label = QLabel(
                str(event_time)
            )

            time_label.setObjectName(
                "activityTime"
            )

            type_label = QLabel(
                event_type
            )

            type_label.setObjectName(
                "activityType"
            )

            text_label = QLabel(
                text
            )

            text_label.setObjectName(
                "activityText"
            )

            row_layout.addWidget(
                time_label
            )

            row_layout.addWidget(
                type_label
            )

            row_layout.addWidget(
                text_label
            )

            row_layout.addStretch()

            self.activity_layout.addWidget(
                row
            )

    # =========================================================
    # HISTORY
    # =========================================================

    def refresh_history_page(self):
        self.clear_layout(
            self.history_layout
        )

        layout = self.history_layout

        title = QLabel("History")
        title.setObjectName(
            "pageTitle"
        )

        subtitle = QLabel(
            "Review your recorded work, breaks and hydration."
        )
        subtitle.setObjectName(
            "pageSubtitle"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)

        history = self.get_history()

        sessions = history.get(
            "work_sessions",
            [],
        )

        breaks = history.get(
            "break_records",
            [],
        )

        water = history.get(
            "water_records",
            [],
        )

        summary = QHBoxLayout()
        summary.setSpacing(12)

        today = datetime.now().strftime("%Y-%m-%d")

        today_sessions = [
            r for r in sessions
            if r.get("date") == today
        ]

        card, _ = self.create_metric_card(
            "WORK SESSIONS",
            str(len(today_sessions)),
            "Today's sessions",
        )

        summary.addWidget(card)

        total_work = sum(
            int(r.get("duration_seconds", 0))
            for r in sessions
            if r.get("date") == today
        )

        card, _ = self.create_metric_card(
            "WORK TIME",
            self.format_time(total_work),
            "Recorded work time",
        )
        summary.addWidget(card)

        today_breaks = [
            r for r in breaks
            if r.get("date") == today
        ]

        card, _ = self.create_metric_card(
            "BREAKS",
            str(len(today_breaks)),
            "Today's breaks",
        )

        summary.addWidget(card)

        total_water = 0

        for record in water:
            try:
                total_water += int(
                    record.get(
                        "amount_ml",
                        0,
                    )
                )
            except Exception:
                pass

        card, _ = self.create_metric_card(
            "WATER",
            f"{total_water:,} ml",
            "Recorded hydration",
        )

        summary.addWidget(card)

        card, _ = self.create_metric_card(
            "TODAY",
            self.format_time(total_work),
            "Today's work time",
        )

        summary.addWidget(card)

        layout.addLayout(summary)

        section = QLabel(
            "Recent activity"
        )

        section.setObjectName(
            "sectionTitle"
        )

        layout.addWidget(
            section
        )

        container = QFrame()
        container.setObjectName(
            "contentCard"
        )

        container_layout = QVBoxLayout(
            container
        )

        container_layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )

        events = []

        for record in water:
            events.append(
                (
                    str(
                        record.get(
                            "time",
                            "--:--:--",
                        )
                    ),
                    "Water",
                    f"{record.get('amount_ml', 0)} ml",
                    record.get("date", ""),
                )
            )

        for record in breaks:
            events.append(
                (
                    str(
                        record.get(
                            "time",
                            record.get(
                                "end_time",
                                "--:--:--",
                            ),
                        )
                    ),
                    "Break",
                    "Break taken",
                )
            )

        for record in sessions:
            duration = int(
                record.get(
                    "duration_seconds",
                    0,
                )
            )

            events.append(
                (
                    str(
                        record.get(
                            "end_time",
                            record.get(
                                "time",
                                "--:--:--",
                            ),
                        )
                    ),
                    "Work",
                    f"Session completed - {self.format_time(duration)}",
                    record.get("date", ""),
                )
            )

        events.sort(
            key=lambda item: (
                str(item[3]),
                str(item[0]),
            ),
            reverse=True,
        )

        events = events[:15]

        if not events:
            empty = QLabel(
                "No records yet."
            )

            empty.setObjectName(
                "mutedText"
            )

            container_layout.addWidget(
                empty
            )

        else:
            for event_time, event_type, value, event_date in events:
                label_date = event_date

                if event_date == datetime.now().strftime("%Y-%m-%d"):
                    label_date = "Today"
                elif event_date == (
                    datetime.now() - timedelta(days=1)
                ).strftime("%Y-%m-%d"):
                    label_date = "Yesterday"

                row = QLabel(
                    f"{label_date}  {event_time}    "
                    f"{event_type}    "
                    f"{value}"
                )

                row.setObjectName(
                    "bodyText"
                )

                container_layout.addWidget(
                    row
                )

        layout.addWidget(
            container
        )

        layout.addStretch()

    # =========================================================
    # INSIGHTS
    # =========================================================

    def refresh_insights(self):
        self.clear_layout(
            self.insights_layout
        )

        layout = self.insights_layout

        title = QLabel("Insights")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Today's work-health summary and progress."
        )
        subtitle.setObjectName("pageSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        history = self.get_history()

        sessions = history.get(
            "work_sessions",
            [],
        )

        breaks = history.get(
            "break_records",
            [],
        )

        water = history.get(
            "water_records",
            [],
        )

        total_work = 0

        for record in sessions:
            try:
                total_work += int(
                    record.get(
                        "duration_seconds",
                        0,
                    )
                )
            except Exception:
                pass

        total_water = 0

        for record in water:
            try:
                total_water += int(
                    record.get(
                        "amount_ml",
                        0,
                    )
                )
            except Exception:
                pass

        water_percentage = int(
            (
                total_water
                / max(
                    1,
                    self.water_goal_ml,
                )
            )
            * 100
        )

        water_percentage = min(
            100,
            max(
                0,
                water_percentage,
            )
        )

        metrics = QHBoxLayout()
        metrics.setSpacing(12)

        card, _ = self.create_metric_card(
            "TOTAL WORK",
            self.format_time(total_work),
            "Recorded work time",
        )
        metrics.addWidget(card)

        card, _ = self.create_metric_card(
            "SESSIONS",
            str(len(sessions)),
            "Completed sessions",
        )
        metrics.addWidget(card)

        card, _ = self.create_metric_card(
            "BREAKS",
            str(len(breaks)),
            "Recorded breaks",
        )
        metrics.addWidget(card)

        card, _ = self.create_metric_card(
            "HYDRATION",
            f"{water_percentage}%",
            f"{total_water:,} / "
            f"{self.water_goal_ml:,} ml",
        )
        metrics.addWidget(card)

        layout.addLayout(metrics)

        progress_card = QFrame()
        progress_card.setObjectName(
            "contentCard"
        )

        progress_layout = QVBoxLayout(
            progress_card
        )

        progress_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        progress_layout.setSpacing(10)

        progress_title = QLabel(
            "Hydration progress"
        )
        progress_title.setObjectName(
            "cardTitle"
        )

        progress_layout.addWidget(
            progress_title
        )

        hydration_bar = QProgressBar()

        hydration_bar.setRange(
            0,
            100,
        )

        hydration_bar.setValue(
            water_percentage
        )

        hydration_bar.setTextVisible(
            False
        )

        hydration_bar.setFixedHeight(
            10
        )

        progress_layout.addWidget(
            hydration_bar
        )

        remaining = max(
            0,
            self.water_goal_ml - total_water,
        )

        hydration_text = QLabel(
            f"{total_water:,} ml consumed  |  "
            f"{remaining:,} ml remaining"
        )

        hydration_text.setObjectName(
            "mutedText"
        )

        progress_layout.addWidget(
            hydration_text
        )

        layout.addWidget(
            progress_card
        )

        recommendation = QFrame()
        recommendation.setObjectName(
            "insightCard"
        )

        recommendation_layout = QVBoxLayout(
            recommendation
        )

        recommendation_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        recommendation_layout.setSpacing(10)

        heading = QLabel(
            "Work health summary"
        )

        heading.setObjectName(
            "cardTitle"
        )

        recommendation_layout.addWidget(
            heading
        )

        if total_water >= self.water_goal_ml:
            message = (
                "Hydration target reached. "
                "Keep your water intake consistent."
            )

        elif len(breaks) == 0 and total_work >= 3600:
            message = (
                "You have recorded a long work period "
                "without a break. Take a short break."
            )

        elif total_work >= 4 * 3600:
            message = (
                "You have recorded more than four hours "
                "of work. Keep your breaks regular."
            )

        elif total_water < self.water_goal_ml * 0.5:
            message = (
                "Hydration is below halfway to the target. "
                "Keep drinking water regularly."
            )

        elif len(sessions) == 0:
            message = (
                "No completed work sessions have been "
                "recorded yet."
            )

        else:
            message = (
                "Your activity is progressing normally. "
                f"{remaining:,} ml remains to reach "
                "your hydration target."
            )

        message_label = QLabel(
            message
        )

        message_label.setObjectName(
            "bodyText"
        )

        message_label.setWordWrap(
            True
        )

        recommendation_layout.addWidget(
            message_label
        )

        layout.addWidget(
            recommendation
        )

        layout.addStretch()

    # =========================================================
    # SETTINGS HELPERS
    # =========================================================

    def update_settings_display(self):
        if hasattr(
            self,
            "water_target_label",
        ):
            self.water_target_label.setText(
                f"{self.water_goal_ml:,} ml"
            )

        if hasattr(
            self,
            "eye_target_label",
        ):
            minutes = (
                self.eye_break_interval
                // 60
            )

            self.eye_target_label.setText(
                f"Every {minutes} minutes"
            )

        if hasattr(
            self,
            "configuration_label",
        ):
            minutes = (
                self.eye_break_interval
                // 60
            )

            self.configuration_label.setText(
                f"Hydration target: "
                f"{self.water_goal_ml:,} ml\n"
                f"Eye-care reminder: every "
                f"{minutes} minutes\n"
                f"Current session: "
                f"{self.format_time(self.session_seconds)}"
            )

    # =========================================================
    # REMINDER
    # =========================================================

    def show_eye_reminder(self):
        # Windows notification
        if (
            hasattr(self, "tray_icon")
            and QSystemTrayIcon.isSystemTrayAvailable()
            and QSystemTrayIcon.supportsMessages()
        ):
            self.tray_icon.showMessage(
                "WorkPulse",
                "20 minutes completed. Take a short eye break.",
                QSystemTrayIcon.Information,
                7000,
            )

        # Non-blocking reminder popup
        reminder = QMessageBox(self)
        reminder.setWindowTitle("Eye-care reminder")
        reminder.setText("Time for an eye break.")
        reminder.setInformativeText(
            "Look away from the screen and rest your eyes "
            "for a few minutes."
        )
        reminder.setIcon(QMessageBox.Information)
        reminder.setStandardButtons(QMessageBox.Ok)
        reminder.setModal(False)
        reminder.setAttribute(Qt.WA_DeleteOnClose)

        reminder.show()
    # =========================================================
    # UTILITIES
    # =========================================================

    def create_metric_card(
        self,
        title,
        value,
        subtitle,
    ):
        card = QFrame()
        card.setObjectName(
            "metricCard"
        )

        layout = QVBoxLayout(card)

        layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        layout.setSpacing(5)

        top = QLabel(title)
        top.setObjectName(
            "metricTitle"
        )

        value_label = QLabel(value)
        value_label.setObjectName(
            "metricValue"
        )

        bottom = QLabel(subtitle)
        bottom.setObjectName(
            "metricSubtitle"
        )

        layout.addWidget(top)
        layout.addWidget(value_label)
        layout.addWidget(bottom)

        return card, value_label

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
                continue

            child_layout = item.layout()

            if child_layout is not None:
                WorkPulseWindow.clear_layout(
                    child_layout
                )

    @staticmethod
    def format_time(total_seconds):
        total_seconds = max(
            0,
            int(total_seconds),
        )

        hours = total_seconds // 3600

        minutes = (
            total_seconds % 3600
        ) // 60

        seconds = total_seconds % 60

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    @staticmethod
    def format_short_time(total_seconds):
        total_seconds = max(
            0,
            int(total_seconds),
        )

        minutes = total_seconds // 60
        seconds = total_seconds % 60

        return (
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    @staticmethod
    def get_greeting():
        hour = datetime.now().hour

        if hour < 12:
            return "Good morning"

        if hour < 17:
            return "Good afternoon"

        return "Good evening"

    # =========================================================
    # STYLES
    # =========================================================

    def apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: #0b0f16;
            }

            QWidget {
                font-family: "Segoe UI";
                color: #e8edf5;
            }

            QScrollArea {
                background: #0b0f16;
                border: none;
            }

            QScrollBar:vertical {
                background: #0b0f16;
                width: 10px;
                margin: 4px;
            }

            QScrollBar::handle:vertical {
                background: #27344a;
                border-radius: 5px;
                min-height: 40px;
            }

            QScrollBar::handle:vertical:hover {
                background: #34445e;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QFrame#sidebar {
                background: #0b1420;
                border-right: 1px solid #1c2738;
            }

            QLabel#brand {
                color: #f4f7fb;
                font-size: 24px;
                font-weight: 800;
            }

            QLabel#tagline {
                color: #667892;
                font-size: 12px;
            }

            QLabel#navSection {
                color: #71809a;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 1px;
                padding-left: 4px;
                padding-bottom: 4px;
            }

            QPushButton#navButton,
            QPushButton#navActive {
                text-align: left;
                padding: 0 18px;
                border-radius: 10px;
                border: none;
                font-size: 13px;
                font-weight: 700;
            }

            QPushButton#navButton {
                background: transparent;
                color: #8492a8;
            }

            QPushButton#navButton:hover {
                background: #121d2c;
                color: #dbe5f3;
            }

            QPushButton#navActive {
                background: #182943;
                color: #6ea0ff;
            }

            QLabel#monitorStatus {
                background: #101b29;
                border: 1px solid #20314a;
                border-radius: 10px;
                padding: 11px 12px;
                color: #5ed99a;
                font-size: 11px;
            }

            QLabel#pageTitle {
                color: #f4f7fb;
                font-size: 30px;
                font-weight: 800;
            }

            QLabel#pageSubtitle {
                color: #73839c;
                font-size: 12px;
            }

            QLabel#statusBadge {
                background: #103322;
                color: #4fe095;
                border: 1px solid #1d5b3b;
                border-radius: 20px;
                padding: 9px 16px;
                font-size: 10px;
                font-weight: 800;
                min-width: 70px;
            }

            QLabel#eyebrow {
                color: #71809a;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 1px;
            }

            QLabel#timerIndicator {
                background: #101d38;
                color: #6e9bff;
                border: 1px solid #1d3767;
                border-radius: 12px;
                padding: 6px 11px;
                font-size: 9px;
                font-weight: 800;
            }

            QFrame#timerCard {
                background: #101722;
                border: 1px solid #223149;
                border-radius: 16px;
            }

            QLabel#bigTimer {
                color: #f6f8fc;
                font-size: 48px;
                font-weight: 800;
                padding: 10px;
            }

            QLabel#timerStatus {
                color: #718099;
                font-size: 12px;
                font-weight: 600;
            }

            QPushButton#primary {
                background: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 0 22px;
                font-size: 13px;
                font-weight: 700;
            }

            QPushButton#primary:hover {
                background: #3475f3;
            }

            QPushButton#primary:pressed {
                background: #1d4ed8;
            }

            QPushButton#secondary {
                background: #151f2e;
                color: #d2dbea;
                border: 1px solid #2a3a52;
                border-radius: 10px;
                padding: 0 22px;
                font-size: 13px;
                font-weight: 700;
            }

            QPushButton#secondary:hover {
                background: #1b2738;
                border-color: #3a4a63;
            }

            QPushButton#smallButton {
                background: #151f2e;
                color: #d6dfec;
                border: 1px solid #293a52;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 700;
            }

            QPushButton#smallButton:hover {
                background: #1c2a3d;
                border-color: #3f6aa8;
            }

            QFrame#metricCard,
            QFrame#healthCard,
            QFrame#contentCard,
            QFrame#insightCard {
                background: #101722;
                border: 1px solid #223149;
                border-radius: 13px;
            }

            QLabel#metricTitle {
                color: #64738a;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 1px;
            }

            QLabel#metricValue {
                color: #f1f5fb;
                font-size: 24px;
                font-weight: 800;
                padding-top: 2px;
            }

            QLabel#metricSubtitle,
            QLabel#mutedText {
                color: #6f8099;
                font-size: 10px;
            }

            QLabel#sectionTitle {
                color: #e8edf5;
                font-size: 17px;
                font-weight: 800;
            }

            QLabel#cardTitle {
                color: #e7ecf5;
                font-size: 14px;
                font-weight: 800;
            }

            QLabel#healthValue {
                color: #f1f5fb;
                font-size: 29px;
                font-weight: 800;
                padding-top: 5px;
            }

            QLabel#percentageLabel {
                color: #70a1ff;
                font-size: 12px;
                font-weight: 800;
            }

            QLabel#settingValue {
                color: #f1f5fb;
                font-size: 19px;
                font-weight: 800;
            }

            QLabel#bodyText {
                color: #9aa8bb;
                font-size: 12px;
                line-height: 1.4;
            }

            QProgressBar {
                background: #172233;
                border: none;
                border-radius: 4px;
            }

            QProgressBar::chunk {
                background: #3982f6;
                border-radius: 4px;
            }

            QFrame#activityContainer {
                background: #101722;
                border: 1px solid #223149;
                border-radius: 13px;
            }

            QFrame#activityRow {
                background: #131d2b;
                border: 1px solid #1e2c40;
                border-radius: 8px;
            }

            QLabel#activityTime {
                color: #63758e;
                font-size: 10px;
                min-width: 70px;
            }

            QLabel#activityType {
                color: #6fa0ff;
                font-size: 11px;
                font-weight: 800;
                min-width: 60px;
            }

            QLabel#activityText {
                color: #cbd5e3;
                font-size: 11px;
            }
            """
        )


def run():
    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    window = WorkPulseWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(
        run()
    )






































