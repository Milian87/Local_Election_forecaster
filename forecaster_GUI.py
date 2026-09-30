# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the GUI definitions for the election forecaster application.

import code
import sys
from pathlib import Path
import pandas as pd
from PySide6 import QtCore, QtGui
import PySide6.QtWidgets as QtWidgets
from forecaster_Controllers import DashboardController
from Data import SampleData
from widgets import (
    ButtonWidget,
    active_blue_button_style,
    blue_button_style,
    red_button_style,
)
from widgets import TransparentTableWidget
import forecaster_MapOrchestrator as map_orchestrator
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib.pyplot as plt

# ==========================================
# GLOBAL UI THEME CONFIGURATION
# ==========================================
# Change this single variable to update quadrant backgrounds across all screens
#Q UADRANT_BG_COLOR = "rgba(240, 242, 240, 210)"  # Faint frosted grey
QUADRANT_BG_COLOR = "rgba(0, 100, 59, 175)"   # Or Frosted Forest Green
# QUADRANT_BG_COLOR = "rgba(255, 255, 255, 220)" # Or Frosted White

GLOBAL_CONTAINER_STYLE = f"""
    QFrame {{
        background-color: {QUADRANT_BG_COLOR};
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 100);
    }}
"""

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, screens, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Election Forecaster")
        self.setMinimumSize(800, 600)

        self.screens = {
            name: screen
            for name, screen in screens.items()
        }

        central_widget = QtWidgets.QWidget()
        central_widget.setObjectName("central-widget")
        self.setCentralWidget(central_widget)
        background_path = Path(__file__).parent / "logo" / "D1 ABSTRACT BACKGROUND_ABSTRACT BACKGROUND-01.png"
        background_url = str(background_path).replace("\\", "/")
        central_widget.setStyleSheet(
            f"#central-widget {{ border-image: url('{background_url}') 0 0 0 0 stretch stretch; }}"
        )

        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.control_panel = self.create_navigation_panel()
        main_layout.addWidget(self.control_panel)

        content_area = QtWidgets.QFrame()
        content_layout = QtWidgets.QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(content_area, 1)
        content_layout.addLayout(self.create_header())

        self.stacked_widget = QtWidgets.QStackedWidget()
        content_layout.addWidget(self.stacked_widget, 1)
        for screen in self.screens.values():
            self.stacked_widget.addWidget(screen)

        if "Dashboard" in self.screens:
            self.change_screen("Dashboard")
        elif self.screens:
            self.change_screen(next(iter(self.screens)))

    def create_navigation_panel(self):
        panel = QtWidgets.QWidget()
        panel.setFixedWidth(135)
        layout = QtWidgets.QVBoxLayout(panel)
        # 50% transparent green: alpha 128 out of 255
        panel.setStyleSheet("background-color: rgba(40, 170, 30, 128);")
        self.buttons = {}

        logo_path = Path(__file__).parent / "logo" / "WNGP_Stacked_Dark.png"
        logo = QtWidgets.QLabel()
        logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = QtGui.QPixmap(str(logo_path))
        if logo_pixmap.isNull():
            logo_pixmap = QtGui.QPixmap(str(Path(__file__).parent / "logo" / "app logo.ico"))
        if not logo_pixmap.isNull():
            logo.setPixmap(logo_pixmap.scaled(90, 90, QtCore.Qt.AspectRatioMode.KeepAspectRatio))
        layout.addWidget(logo)

        for name in self.screens:
            button = ButtonWidget(
                layout,
                name,
                lambda checked=False, screen_name=name: self.change_screen(screen_name),
                button_style=blue_button_style,
            )
            self.buttons[name] = button

        self.model_selector = QtWidgets.QComboBox()
        self.model_selector.addItem("Delta Model", "Delta Model")
        self.model_selector.addItem("Softmax Model", "Softmax Model")
        self.model_selector.addItem("Hybrid Model", "Hybrid Model")
        self.model_selector.setToolTip("Choose the forecast model")
        layout.addWidget(self.model_selector)

        self.date_selector = QtWidgets.QComboBox()
        for label, date_value in (
            ("2019 election", "2019-05-02"),
            ("2021 election", "2021-05-06"),
            ("2022 election", "2022-05-05"),
            ("2023 election", "2023-05-04"),
            ("2024 election", "2024-05-02"),
            ("2025 election", "2025-05-01"),
            ("16 April 2026", "2026-04-16"),
            ("23 April 2026", "2026-04-23"),
            ("30 April 2026", "2026-04-30"),
            ("7 May 2026", "2026-05-07"),
            ("8 May 2026", "2026-05-08"),
            ("15 May 2026", "2026-05-15"),
            ("22 May 2026", "2026-05-22"),
            ("29 May 2026", "2026-05-29"),
            ("5 June 2026", "2026-06-05"),
            ("12 June 2026", "2026-06-12"),
            ("19 June 2026", "2026-06-19"),
            ("26 June 2026", "2026-06-26"),
            ("3 July 2026", "2026-07-03"),
            ("10 July 2026", "2026-07-10"),
            ("17 July 2026", "2026-07-17"),
            ("24 July 2026", "2026-07-24"),
            ("31 July 2026", "2026-07-31"),
            ("Tomorrow", "2026-09-21"),
        ):
            self.date_selector.addItem(label, date_value)
        self.date_selector.setCurrentIndex(self.date_selector.count() - 1)
        self.date_selector.setToolTip("Choose the election date to forecast or backtest")
        layout.addWidget(self.date_selector)

        self.reforecast_button = QtWidgets.QPushButton("Reforecast")
        self.reforecast_button.setToolTip("Run the selected forecast model")
        self.reforecast_button.setStyleSheet(blue_button_style)
        layout.addWidget(self.reforecast_button)

        # add a sliders and a value label for each of the 6 main parties to set current or hypothetical polls
# Define party colors matching your orchestrator schema
        party_colors = {
            'Labour': '#d50000',
            'Conservative': '#0087dc',
            'Liberal Democrats': '#FDBB30',
            'Green Party': '#00a85a',
            'Reform UK': '#00c3d9',
            'Restore Britain\n(Great Yarmouth First)': '#000080',
        }

        self.party_sliders = {}
        self.party_slider_values = {}

        for party, color in party_colors.items():
            # Party name label (centered)
            party_label = QtWidgets.QLabel(party)
            party_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            party_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")
            
            # Value display label (centered)
            value_label = QtWidgets.QLabel("50")
            value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("color: #ffffff; font-size: 11px;")
            
            # Slider setup with dynamic party-specific color injection
            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(66)
            slider.setValue(50)
            
            slider_stylesheet = f"""
                QSlider::groove:horizontal {{
                    border: 1px solid #999999;
                    height: 6px;
                    background: #ffffff;
                    border-radius: 3px;
                }}
                QSlider::sub-page:horizontal {{
                    background: {color};
                    border: 1px solid {color};
                    height: 6px;
                    border-radius: 3px;
                }}
                QSlider::add-page:horizontal {{
                    background: #dddddd;
                    border: 1px solid #cccccc;
                    height: 6px;
                    border-radius: 3px;
                }}
                QSlider::handle:horizontal {{
                    background: {color};
                    border: 1px solid #1a2b3c;
                    width: 14px;
                    margin: -4px 0;
                    border-radius: 7px;
                }}
                QSlider::handle:horizontal:hover {{
                    background: #ffffff;
                }}
            """
            slider.setStyleSheet(slider_stylesheet)
            slider.setToolTip(f"Set the current or hypothetical poll for {party}")
            
            # Connect value change to update the text label
            slider.valueChanged.connect(lambda value, lbl=value_label: lbl.setText(str(value)))

            # Add widgets to the navigation layout in order
            layout.addWidget(party_label)
            layout.addWidget(slider)
            layout.addWidget(value_label)

            self.party_sliders[party] = slider
            self.party_slider_values[party] = value_label

        self.reset_polls_button = QtWidgets.QPushButton("Reset Polls")
        self.reset_polls_button.setToolTip("Reset all party poll sliders to their default value")
        self.reset_polls_button.setStyleSheet(blue_button_style)
        self.reset_polls_button.clicked.connect(self._reset_party_polls)
        layout.addWidget(self.reset_polls_button)

        self.ignore_user_polls_checkbox = QtWidgets.QCheckBox("Ignore user polls")
        self.ignore_user_polls_checkbox.setToolTip("Forecast using database polling data instead of the sliders above")
        self.ignore_user_polls_checkbox.setChecked(True)
        layout.addWidget(self.ignore_user_polls_checkbox)

        layout.addStretch()
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        ButtonWidget(layout, "Exit", app.quit, button_style=red_button_style)
        return panel

    def set_reforecast_callback(self, callback):
        self.reforecast_button.clicked.connect(
            lambda: callback(
                self.model_selector.currentData(),
                self.date_selector.currentData(),
                self.date_selector.currentText(),
                self.get_party_polls(),
                self.get_ignore_user_polls(),
            )
        )

    def set_reforecast_enabled(self, enabled: bool):
        self.reforecast_button.setEnabled(enabled)
        self.model_selector.setEnabled(enabled)
        self.date_selector.setEnabled(enabled)

    def set_forecaster_label(self, model_name: str):
        self.forecaster_label.setText(f"Results: {model_name}")

    def create_header(self):
        layout = QtWidgets.QHBoxLayout()

        title_layout = QtWidgets.QVBoxLayout()
        main_title_font = QtGui.QFont("Bebas Neue", 24, QtGui.QFont.Weight.Bold)
        ui_title_font = QtGui.QFont("Bebas Neue", 20, QtGui.QFont.Weight.Bold)

        self.main_title = QtWidgets.QLabel("Local Election Forecaster")
        self.main_title.setFont(main_title_font)
        self.main_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.main_title.setStyleSheet("color: #ffffff; font-weight: bold;")

        self.ui_title = QtWidgets.QLabel()
        self.ui_title.setFont(ui_title_font)
        self.ui_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        
        self.ui_title.setStyleSheet("color: #ffffff; font-weight: bold;")

        self.datetime_label = QtWidgets.QLabel()
        self.datetime_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.datetime_label.setFont(QtGui.QFont("Manrope", 14))
        self.datetime_label.setStyleSheet("font-size: 14px; color: #ffffff;")

        title_layout.addWidget(self.main_title)
        title_layout.addWidget(self.ui_title)
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.addWidget(self.datetime_label)
        self.forecaster_label = QtWidgets.QLabel("Results: Delta Model")
        self.forecaster_label.setFont(QtGui.QFont("Manrope", 14))
        self.forecaster_label.setStyleSheet("font-size: 14px; color: #ffffff;")
        status_layout.addWidget(self.forecaster_label)
        status_layout.addStretch()
        title_layout.addLayout(status_layout)
        layout.addLayout(title_layout)
        layout.addStretch()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
        return layout

    def update_time(self):
        self.datetime_label.setText(
            QtCore.QDateTime.currentDateTime().toString("dddd, MMMM d, yyyy - hh:mm:ss AP")
        )

    def change_screen(self, screen_name):
        screen = self.screens.get(screen_name)
        if screen is None:
            return
        self.stacked_widget.setCurrentWidget(screen)
        self.ui_title.setText(screen_name)
        for name, button in self.buttons.items():
            button.set_style(active_blue_button_style if name == screen_name else blue_button_style)

    def get_party_polls(self) -> dict[str, float]:
        """Extract user-defined poll share slider values."""
        polls = {}
        for party, slider in self.party_sliders.items():
            polls[party] = float(slider.value())
        return polls

    def get_ignore_user_polls(self) -> bool:
        """Whether the forecast should ignore the user-defined poll sliders."""
        return self.ignore_user_polls_checkbox.isChecked()

    def _reset_party_polls(self) -> None:
        """Reset every party poll slider back to its default value."""
        for slider in self.party_sliders.values():
            slider.setValue(50)

class BaseScreen(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("base-screen")
        self.setStyleSheet("#base-screen { background: transparent; }")

class DashboardScreen(BaseScreen):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller or DashboardController(SampleData())
        # Initialize map_view attribute to prevent AttributeError
        self.map_view = None
        
        # 1. Main layout as a 2x2 Grid Layout for the dashboard quadrants
        main_layout = QtWidgets.QGridLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Configure row and column stretch for proportional scaling
        main_layout.setRowStretch(0, 1)  # Top row (Summary Table & Map)
        main_layout.setRowStretch(1, 1)  # Bottom row (Vote Share Table & Secondary View)
        main_layout.setColumnStretch(0, 1)  # Left column (Tables)
        main_layout.setColumnStretch(1, 1)  # Right column (Map & Analytics)

        # ==========================================
        # QUADRANT 1: TOP-LEFT (Council Summaries Table)
        # ==========================================
        top_left_container = QtWidgets.QFrame()
        top_left_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        top_left_layout = QtWidgets.QVBoxLayout(top_left_container)

        # Level selector combo box
        self.level_combo_box = QtWidgets.QComboBox()
        self.level_combo_box.addItems(["District / Unitary", "County 2026", "County 2025"])
        self.level_combo_box.setCurrentText("County 2026")
        self.level_combo_box.currentIndexChanged.connect(lambda: self.refresh_map())
        top_left_layout.addWidget(self.level_combo_box)

        # Summary Table
        self.summary_table = QtWidgets.QTableWidget()
        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels(["Council", "Current Largest Party", "Forecasted Winner", "Expected Seat Gains"])
        self.summary_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.summary_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.summary_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        top_left_layout.addWidget(self.summary_table, 1)

        main_layout.addWidget(top_left_container, 0, 0)  # Row 0, Col 0

        # ==========================================
        # QUADRANT 2: TOP-RIGHT (Interactive Map)
        # ==========================================
        top_right_container = QtWidgets.QFrame()
        top_right_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        self.right_layout = QtWidgets.QStackedLayout(top_right_container)
        self.right_layout.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackAll)

        self.forecast_loading_label = QtWidgets.QLabel(
            "Please wait while we conduct the forecast"
        )
        self.forecast_loading_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.forecast_loading_label.setWordWrap(True)
        self.forecast_loading_label.setMaximumSize(340, 110)
        self.forecast_loading_label.setMargin(12)
        self.forecast_loading_label.setStyleSheet(
            "background-color: rgba(255, 255, 255, 220); "
            "border: 1px solid rgba(20, 70, 90, 150); "
            "border-radius: 8px; color: #123; font-size: 16px; "
            "font-weight: bold; padding: 12px;"
        )
        self.right_layout.addWidget(self.forecast_loading_label)
        self.right_layout.setAlignment(
            self.forecast_loading_label,
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter,
        )

        main_layout.addWidget(top_right_container, 0, 1, 2, 1)  # Row 0, Col 1

        # ==========================================
        # QUADRANT 3: BOTTOM-LEFT (Vote Share Table)
        # ==========================================
        bottom_left_container = QtWidgets.QFrame()
        bottom_left_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        bottom_left_layout = QtWidgets.QVBoxLayout(bottom_left_container)

        self.vote_share_table = QtWidgets.QTableWidget()
        self.vote_share_table.setColumnCount(3)
        self.vote_share_table.setHorizontalHeaderLabels(["Party", "National Vote Share", "Seats"])
        self.vote_share_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.vote_share_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.vote_share_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        bottom_left_layout.addWidget(self.vote_share_table, 1)

        main_layout.addWidget(bottom_left_container, 1, 0)  # Row 1, Col 0


    def populate_tables(self):
        summary = self.controller.get_summary()
        council_summaries = self.controller.get_council_summaries()
        self.summary_table.setRowCount(len(council_summaries))
        for row_index, (_, row) in enumerate(council_summaries.iterrows()):
            values = [
                str(row["council"]),
                str(row["current_party"]),
                str(row["forecasted_winner"]),
                f"{int(row['seats_gained']):+d}",
            ]
            for column_index, value in enumerate(values):
                self.summary_table.setItem(row_index, column_index, QtWidgets.QTableWidgetItem(value))

        total_seats = summary["seats_forecast"].sum()
        self.vote_share_table.setRowCount(len(summary))
        for row_index, (_, row) in enumerate(summary.iterrows()):
            seat_share = 0 if total_seats == 0 else row["seats_forecast"] / total_seats * 100
            values = [
                row["party"],
                f"{seat_share:.1f}%",
                str(int(row["seats_forecast"])),
            ]
            for column_index, value in enumerate(values):
                self.vote_share_table.setItem(
                    row_index,
                    column_index,
                    QtWidgets.QTableWidgetItem(value),
                )

    def set_controller(self, controller) -> None:
        self.controller = controller
        self.populate_tables()
        self.refresh_map()

    def set_forecast_loading(self, loading: bool) -> None:
        self.forecast_loading_label.setVisible(loading)
        if loading:
            self.forecast_loading_label.raise_()

    @QtCore.Slot(object)
    def set_forecaster(self, forecaster) -> None:
        self.set_controller(DashboardController(forecaster))
        self.set_forecast_loading(False)

    def refresh_map(self) -> None:
        if self.map_view is not None:
            self.right_layout.removeWidget(self.map_view)
            self.map_view.deleteLater()

        if self.level_combo_box.currentText() == "District / Unitary":
            boundary_path = (
                Path(__file__).parent
                / "data"
                / "Borough and District Boundaries 2025"
                / "WD_MAY_2026_UK_BFC.shp"
            )
            forecast_data = self.controller.get_forecast_data()
        elif self.level_combo_box.currentText() == "County 2025":
            boundary_path = (
                Path(__file__).parent
                / "data" / "County Electoral Division (May 2025) Boundaries EN BFE"
                / "CED_MAY_2025_EN_BFC.shp"
            )
            forecast_data = self.controller.get_county_and_unitary_forecast()
        else:
            boundary_path = Path(__file__).parent / "data" / "boundaries_2026" / "CED_MAY_2026_EN_BFC.shp"
            forecast_data = self.controller.get_county_and_unitary_forecast()
        try:
            self.map_orchestrator = map_orchestrator.CouncilMapOrchestrator(str(boundary_path))
            self.map_view = self.map_orchestrator.generate(forecast_data)
        except (OSError, ValueError, ImportError) as error:
            self.map_view = QtWidgets.QLabel(f"Map unavailable: {error}")
            self.map_view.setWordWrap(True)
        self.right_layout.addWidget(self.map_view)
        self.forecast_loading_label.raise_()

class ForecastScreen(BaseScreen):
    incumbent_party_colors = {
        "Reform UK": "#00c3d9",
        "Liberal Democrats": "#FDBB30",
        "Green Party": "#00a85a",
        "Conservative": "#0087dc",
        "Labour": "#d50000",
        "Independent": "#F598E5",
        "Great Yarmouth First": "#000080",
        "Restore Britain": "#000080",
    }

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        
        # 1. Main layout as a 2x2 Grid Layout for the four quadrants
        main_layout = QtWidgets.QGridLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Configure row and column stretch for proportional scaling
        main_layout.setRowStretch(0, 1)  # Top row (Selectors/Tables & Map)
        main_layout.setRowStretch(1, 1)  # Bottom row (Vote Shares & Ward Results)
        main_layout.setColumnStretch(0, 1)  # Left column (Tables & Controls)
        main_layout.setColumnStretch(1, 1)  # Right column (Map & Detailed Breakdown)

        # ==========================================
        # QUADRANT 1: TOP-LEFT (Selectors & Summary Table)
        # ==========================================
        top_left_container = QtWidgets.QFrame()
        top_left_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        top_left_layout = QtWidgets.QVBoxLayout(top_left_container)

        # Selectors layout (Level, Council, Division)
        self.selector_layout = QtWidgets.QHBoxLayout()
        top_left_layout.addLayout(self.selector_layout)

        self.level_combo_box = QtWidgets.QComboBox()
        self.level_combo_box.addItems(["District / Unitary", "County 2026", "County 2025"])
        self.level_combo_box.setCurrentText("County 2026")
        self.level_combo_box.currentIndexChanged.connect(self._level_selection_changed)
        self.selector_layout.addWidget(self.level_combo_box)

        self.council_selector = QtWidgets.QComboBox()
        self.council_selector.addItem("All councils", "")
        self.council_selector.setToolTip("Filter divisions and focus the map by council")
        self.council_selector.currentIndexChanged.connect(self._council_selection_changed)
        self.selector_layout.addWidget(self.council_selector)

        self.division_selector = QtWidgets.QComboBox()
        self.division_selector.addItem("All divisions", "")
        self.division_selector.setToolTip("Filter the map by division")
        self.division_selector.currentIndexChanged.connect(self._division_selection_changed)
        self.selector_layout.addWidget(self.division_selector)

        # Summary Table
        self.ward_table = QtWidgets.QTableWidget()
        self.ward_table.setColumnCount(5)
        self.ward_table.setHorizontalHeaderLabels(["Council", "Division", "Current Councilor", "Party", "Forecast"])
        self.ward_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ward_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ward_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        top_left_layout.addWidget(self.ward_table, 1)
        self.ward_table.cellClicked.connect(self._focus_map_from_table)

        # Make the left column span both row 0 and row 1
        main_layout.addWidget(top_left_container, 0, 0, 2, 1)  # (Row 0, Col 0, span 2 rows, span 1 col)

        # ==========================================
        # QUADRANT 2: TOP-RIGHT (Interactive Map)
        # ==========================================
        top_right_container = QtWidgets.QFrame()
        top_right_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        self.map_layout = QtWidgets.QVBoxLayout(top_right_container)

        self.forecast_loading_label = QtWidgets.QLabel(
            "We are now conducting the forecast, please wait"
        )
        self.forecast_loading_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.forecast_loading_label.setWordWrap(True)
        self.forecast_loading_label.setMaximumSize(340, 110)
        self.forecast_loading_label.setMargin(12)
        self.forecast_loading_label.setStyleSheet(
            "background-color: rgba(255, 255, 255, 220); "
            "border: 1px solid rgba(20, 70, 90, 150); "
            "border-radius: 8px; color: #123; font-size: 16px; "
            "font-weight: bold; padding: 12px;"
        )
        self.map_layout.addWidget(self.forecast_loading_label)
        self.map_layout.setAlignment(
            self.forecast_loading_label,
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter,
        )

        main_layout.addWidget(top_right_container, 0, 1)  # Row 0, Col 1

        # ==========================================
        # QUADRANT 4: BOTTOM-RIGHT (Ward Results Breakdown Table)
        # ==========================================
        bottom_right_container = QtWidgets.QFrame()
        bottom_right_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        ward_forecast_layout = QtWidgets.QVBoxLayout(bottom_right_container)

        self.results_table = QtWidgets.QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Candidate", "Party", "Vote Share", "Forecasted Share"])
        self.results_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        ward_forecast_layout.addWidget(self.results_table)

        main_layout.addWidget(bottom_right_container, 1, 1)  # Row 1, Col 1

        self.map_view = None

    def populate_tables(self):
        division_forecasts = self.controller.get_division_forecasts()  # type: ignore
        selected_council = self.council_selector.currentData()
        self.council_selector.blockSignals(True)
        self.council_selector.clear()
        self.council_selector.addItem("All councils", "")
        councils = sorted(
            division_forecasts["council"].dropna().astype(str).str.strip().unique().tolist()
        )
        for council in councils:
            self.council_selector.addItem(council, council)
        selected_index = self.council_selector.findData(selected_council)
        self.council_selector.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.council_selector.blockSignals(False)

        if selected_council:
            division_forecasts = division_forecasts[
                division_forecasts["council"].astype(str).str.strip() == str(selected_council).strip()
            ].copy()
        self.ward_table.setColumnCount(5)
        self.ward_table.setHorizontalHeaderLabels(
            ["Council", "Division", "Current Councillor", "Current Party", "Forecasted Party"]
        )
        self.ward_table.setRowCount(len(division_forecasts))
        self.results_table.setRowCount(0)
        for row_index, (_, row) in enumerate(division_forecasts.iterrows()):
            values = [
                str(row["council"]),
                str(row["division"]),
                str(row["current_councillor"]),
                "",
                str(row["forecasted_party"]),
            ]
            for column_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if column_index == 3:
                    party = str(row["incumbent_party"])
                    color = QtGui.QColor(self.incumbent_party_colors.get(party, "#bdbdbd"))
                    item.setText("      ")
                    item.setBackground(QtGui.QBrush(color))
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    item.setToolTip(party)
                self.ward_table.setItem(row_index, column_index, item)

        self.ward_table.resizeColumnsToContents()
        self._division_forecasts = division_forecasts

    def _council_selection_changed(self) -> None:
        selected_council = self.council_selector.currentData()
        all_divisions = self.controller.get_division_forecasts()  # type: ignore
        if selected_council:
            filtered = all_divisions[
                all_divisions["council"].astype(str).str.strip() == str(selected_council).strip()
            ].copy()
        else:
            filtered = all_divisions

        self._division_forecasts = filtered
        self.ward_table.setRowCount(len(filtered))
        for row_index, (_, row) in enumerate(filtered.iterrows()):
            values = [
                str(row["council"]),
                str(row["division"]),
                str(row["current_councillor"]),
                "",
                str(row["forecasted_party"]),
            ]
            for column_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if column_index == 3:
                    party = str(row["incumbent_party"])
                    color = QtGui.QColor(self.incumbent_party_colors.get(party, "#bdbdbd"))
                    item.setText("      ")
                    item.setBackground(QtGui.QBrush(color))
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    item.setToolTip(party)
                self.ward_table.setItem(row_index, column_index, item)
        self.ward_table.resizeColumnsToContents()
        self.refresh_map(focus_council=selected_council or None)

    def _level_selection_changed(self) -> None:
        self.populate_tables()
        self.refresh_map()

    def _focus_map_from_table(self, row_index: int, column_index: int) -> None:
        if not hasattr(self, "_division_forecasts") or row_index >= len(self._division_forecasts):
            return
        row = self._division_forecasts.iloc[row_index]
        if column_index == 0:
            self.populate_council_results(row["council"])
            self.refresh_map(focus_council=row["council"])
        elif column_index == 1:
            self.populate_division_results(row["division_code"])
            self.refresh_map(focus_division=row["division_code"])

    def populate_council_results(self, council_name: str) -> None:
        results = self.controller.get_council_results(council_name)  # type: ignore
        self.results_table.setHorizontalHeaderLabels(
            ["Party", "Current Seats", "Forecast Seats", "Seats Gained"]
        )
        self.results_table.setColumnCount(4)
        self.results_table.setRowCount(len(results))
        for row_index, (_, row) in enumerate(results.iterrows()):
            values = [
                str(row["party"]),
                str(int(row["current_seats"])),
                str(int(row["forecast_seats"])),
                f"{int(row['seats_gained']):+d}",
            ]
            for column_index, value in enumerate(values):
                self.results_table.setItem(
                    row_index,
                    column_index,
                    QtWidgets.QTableWidgetItem(value),
                )
        self.results_table.resizeColumnsToContents()

    def populate_division_results(self, division_code: str) -> None:
        results = self.controller.get_division_results(division_code)  # type: ignore
        self.results_table.setHorizontalHeaderLabels(
            ["Candidate", "Party", "Current Share", "Forecast Share"]
        )
        self.results_table.setColumnCount(4)
        if results.empty:
            self.results_table.setRowCount(0)
            return

        results = results.sort_values("final_forecast_share", ascending=False)
        self.results_table.setRowCount(len(results))
        for row_index, (_, row) in enumerate(results.iterrows()):
            values = [
                str(row.get("candidate_name", "")),
                str(row.get("party_label", "")),
                f"{float(row.get('party_vote_share', 0.0)):.1f}%",
                f"{float(row.get('final_forecast_share', 0.0)):.1f}%",
            ]
            for column_index, value in enumerate(values):
                self.results_table.setItem(
                    row_index,
                    column_index,
                    QtWidgets.QTableWidgetItem(value),
                )
        self.results_table.resizeColumnsToContents()

    def set_controller(self, controller) -> None:
        self.controller = controller
        self.populate_tables()
        self.refresh_map()

    def set_forecast_loading(self, loading: bool) -> None:
        self.forecast_loading_label.setVisible(loading)
        if loading:
            self.forecast_loading_label.raise_()

    @QtCore.Slot(object)
    def set_forecaster(self, forecaster) -> None:
        self.set_controller(DashboardController(forecaster))
        self.set_forecast_loading(False)

    def refresh_map(self, focus_division=None, focus_council=None) -> None:
        if self.map_view is not None:
            self.map_layout.removeWidget(self.map_view)
            self.map_view.deleteLater()

        self.forecast_loading_label.setText("Loading map...")
        self.forecast_loading_label.setVisible(True)
        self.forecast_loading_label.raise_()
        QtWidgets.QApplication.processEvents()

        if self.level_combo_box.currentText() == "District / Unitary":
            boundary_path = (
                Path(__file__).parent
                / "data"
                / "Borough and District Boundaries 2025"
                / "WD_MAY_2026_UK_BFC.shp"
            )
            forecast_data = self.controller.get_forecast_data()  # type: ignore
        elif self.level_combo_box.currentText() == "County 2025":
            boundary_path = (
                Path(__file__).parent
                / "data" / "County Electoral Division (May 2025) Boundaries EN BFE"
                / "CED_MAY_2025_EN_BFC.shp"
            )
            forecast_data = self.controller.get_county_and_unitary_forecast()  # type: ignore
        else:
            boundary_path = Path(__file__).parent / "data" / "boundaries_2026" / "CED_MAY_2026_EN_BFC.shp"
            forecast_data = self.controller.get_county_and_unitary_forecast()  # type: ignore
        try:
            self.map_orchestrator = map_orchestrator.WardMapOrchestrator(str(boundary_path))
            self.map_view = self.map_orchestrator.generate(
                forecast_data,
                focus_division=focus_division,
                focus_council=focus_council,
            )
        except (OSError, ValueError, ImportError) as error:
            self.map_view = QtWidgets.QLabel(f"Map unavailable: {error}")
            self.map_view.setWordWrap(True)
        self.map_layout.addWidget(self.map_view)
        self.forecast_loading_label.setVisible(False)

    def _division_selection_changed(self) -> None:
        selected_division_code = self.division_selector.currentData()
        if not selected_division_code:
            return
        self.populate_division_results(selected_division_code)
        self.refresh_map(focus_division=selected_division_code)

class DataScreen(BaseScreen):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = QtWidgets.QVBoxLayout(self)
        # Add more widgets and functionality for the Data screen here

class AnalysisScreen(BaseScreen):
    wardSelected = QtCore.Signal(str, str)  # Emits (wd_code, ward_name) when selected

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        
        # 1. Main layout as a 2x2 Grid Layout for the four quadrants
        main_layout = QtWidgets.QGridLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        main_layout.setRowStretch(0, 1)
        main_layout.setRowStretch(1, 1)
        main_layout.setColumnStretch(0, 1)
        main_layout.setColumnStretch(1, 1)
        
        # ==========================================
        # QUADRANT 1: TOP-LEFT (Navigation & Tables Stack)
        # ==========================================
        top_left_container = QtWidgets.QFrame()
        top_left_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        top_left_layout = QtWidgets.QVBoxLayout(top_left_container)
        
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.setSpacing(4)
        
        self.view_selector = QtWidgets.QComboBox()
        self.view_selector.addItem("County", "county")
        self.view_selector.addItem("District", "district")
        
        self.region_selector = QtWidgets.QComboBox()
        nav_layout.addWidget(self.region_selector)
        nav_layout.addWidget(self.view_selector)
        
        self.btn_select_view = QtWidgets.QPushButton("Select Ward")
        self.btn_results_view = QtWidgets.QPushButton("Ward Results")
        
        btn_style = """
            QPushButton {
                background-color: #1a4d2e;
                color: white;
                border: none;
                padding: 6px 10px;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #28aa1e;
            }
        """
        self.btn_select_view.setStyleSheet(btn_style)
        self.btn_results_view.setStyleSheet(btn_style)
        self.btn_select_view.setCheckable(True)
        self.btn_results_view.setCheckable(True)
        self.btn_select_view.setChecked(True)
        
        nav_layout.addWidget(self.btn_select_view)
        nav_layout.addWidget(self.btn_results_view)
        top_left_layout.addLayout(nav_layout)
        
        # Stacked Widget for Ward List vs Results Table
        self.stack = QtWidgets.QStackedWidget()
        
        self.ward_table = QtWidgets.QTableWidget()
        self.ward_table.setColumnCount(5)
        self.ward_table.setHorizontalHeaderLabels(["Council", "Division", "Current Councilor", "Party", "Forecast"])
        self.ward_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ward_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ward_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stack.addWidget(self.ward_table)
        
        self.results_table = QtWidgets.QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Candidate", "Party", "Current %", "Forecast %"])
        self.results_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stack.addWidget(self.results_table)
        
        top_left_layout.addWidget(self.stack)
        main_layout.addWidget(top_left_container, 0, 0)
        
        # ==========================================
        # QUADRANT 2: TOP-RIGHT (Interactive Map)
        # ==========================================
        top_right_container = QtWidgets.QFrame()
        top_right_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        self.top_right_layout = QtWidgets.QVBoxLayout(top_right_container)
        
        map_placeholder = QtWidgets.QLabel("Interactive Map View (Top-Right)")
        map_placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.top_right_layout.addWidget(map_placeholder)
        main_layout.addWidget(top_right_container, 0, 1)
        
        # ==========================================
        # QUADRANT 3: BOTTOM-LEFT (Local / National Polls Graph)
        # ==========================================
        bottom_left_container = QtWidgets.QFrame()
        bottom_left_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        self.bottom_left_layout = QtWidgets.QVBoxLayout(bottom_left_container)
        
        polls_placeholder = QtWidgets.QLabel("National & Ward Polling Trend Graph (Bottom-Left)")
        polls_placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.bottom_left_layout.addWidget(polls_placeholder)
        main_layout.addWidget(bottom_left_container, 1, 0)
        
        # ==========================================
        # QUADRANT 4: BOTTOM-RIGHT (SHAP Explainability Chart)
        # ==========================================
        bottom_right_container = QtWidgets.QFrame()
        bottom_right_container.setStyleSheet(GLOBAL_CONTAINER_STYLE)
        self.bottom_right_layout = QtWidgets.QVBoxLayout(bottom_right_container)
        
        self.shap_canvas_container = QtWidgets.QWidget()
        self.shap_layout = QtWidgets.QVBoxLayout(self.shap_canvas_container)
        self.bottom_right_layout.addWidget(self.shap_canvas_container)
        main_layout.addWidget(bottom_right_container, 1, 1)
        
        self.show_default_shap_chart()
        
        self.btn_select_view.clicked.connect(lambda: self.switch_view(0))
        self.btn_results_view.clicked.connect(lambda: self.switch_view(1))
        self.ward_table.cellClicked.connect(self.on_ward_row_clicked)

    def show_default_shap_chart(self):
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.set_facecolor("none")
        fig.patch.set_facecolor("none")
        ax.text(0.5, 0.5, "Select a ward to view spatial SHAP impact", 
                horizontalalignment='center', verticalalignment='center', 
                transform=ax.transAxes, color='white', fontweight='bold')
        ax.axis('off')
        self.set_shap_figure(fig)

    def set_shap_figure(self, fig):
        while self.shap_layout.count():
            child = self.shap_layout.takeAt(0)
            if child is not None:
                widget = child.widget()
                if widget is not None:
                    widget.deleteLater()
                
        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet("background-color: transparent;")
        self.shap_layout.addWidget(canvas)
        canvas.draw()

    def switch_view(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_select_view.setChecked(index == 0)
        self.btn_results_view.setChecked(index == 1)

    def populate_ward_list(self, wards_data):
        self.ward_table.setRowCount(len(wards_data))
        for row_idx, (council, division, councillor, party, forecast, division_code) in enumerate(wards_data):
            item_council = QtWidgets.QTableWidgetItem(str(council))
            item_division = QtWidgets.QTableWidgetItem(str(division))
            item_councillor = QtWidgets.QTableWidgetItem(str(councillor))
            item_party = QtWidgets.QTableWidgetItem(str(party))
            item_forecast = QtWidgets.QTableWidgetItem(str(forecast))
            
            # Store the division code secretly in the UserRole data of the division cell
            item_division.setData(QtCore.Qt.ItemDataRole.UserRole, str(division_code))
            
            self.ward_table.setItem(row_idx, 0, item_council)
            self.ward_table.setItem(row_idx, 1, item_division)
            self.ward_table.setItem(row_idx, 2, item_councillor)
            self.ward_table.setItem(row_idx, 3, item_party)
            self.ward_table.setItem(row_idx, 4, item_forecast)

    def populate_ward_results(self, ward_name, candidates_data):
        self.btn_results_view.setText(f"Results: {ward_name}")
        self.results_table.setRowCount(len(candidates_data))
        for row_idx, data in enumerate(candidates_data):
            party, current_share, forecast_share, incumbent = data
            self.results_table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(str(party)))
            self.results_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(f"{float(current_share):.1f}%"))
            self.results_table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(f"{float(forecast_share):.1f}%"))
            self.results_table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem("Yes" if incumbent else "No"))
        self.switch_view(1)

    def on_ward_row_clicked(self, row, column):
        division_item = self.ward_table.item(row, 1)
        if division_item:
            ward_name = division_item.text()
            division_code = division_item.data(QtCore.Qt.ItemDataRole.UserRole)
            self.wardSelected.emit(division_code, ward_name)
            
            # Pass the active forecaster instance safely
            if self.controller is not None and hasattr(self.controller, "data_source"):
                forecaster_instance = getattr(self.controller, "data_source", None)
                if forecaster_instance is not None and hasattr(forecaster_instance, "explainer"):
                    self.display_ward_shap(forecaster_instance, ward_name)

    def display_ward_shap(self, forecaster, ward_name, feature_name="top_2"):
        """Generates and displays the SHAP explanation chart for a specific ward."""
        try:
            # 1. Check if forecaster has an explainer ready
            explainer = getattr(forecaster, "explainer", None)
            if explainer is None:
                # Softmax or uninitialized models won't have TreeExplainer
                return

            # 2. Safely find whichever feature DataFrame exists on the forecaster
            df_features = None
            for attr in (
                "latest_features",
                "X",
                "training_matrix",
                "forecast_df",
                "df",
            ):
                val = getattr(forecaster, attr, None)
                if isinstance(val, pd.DataFrame) and not val.empty:
                    df_features = val
                    break

            # 3. Locate the ward row if feature dataframe exists
            top_features, top_values = None, None

            if hasattr(forecaster, "get_shap_values_for_ward"):
                top_features, top_values = forecaster.get_shap_values_for_ward(
                    ward_name
                )

            elif df_features is not None:
                # Wrap OR conditions in parentheses to avoid NoneType evaluation
                col = None
                for c in ("ward_name", "division", "CED25NM", "CED26NM", "Name"):
                    if c in df_features.columns:
                        col = c
                        break

                if col is not None:
                    ward_row = df_features[
                        df_features[col].astype(str).str.strip().str.lower()
                        == str(ward_name).strip().lower()
                    ]

                    if not ward_row.empty:
                        # Exclude non-numeric and metadata columns
                        non_feature_cols = [
                            "wd_code",
                            "ward_name",
                            "division",
                            "division_code",
                            "party_label",
                            "council",
                            "geometry",
                        ]
                        feature_row = ward_row.drop(
                            columns=[
                                c
                                for c in non_feature_cols
                                if c in ward_row.columns
                            ]
                        )
                        # Keep only numeric columns
                        feature_row = feature_row.select_dtypes(
                            include=["number"]
                        )

                        if not feature_row.empty:
                            shap_output = explainer(feature_row)
                            raw_vals = (
                                shap_output.values
                                if hasattr(shap_output, "values")
                                else shap_output
                            )
                            # Handle 2D or 3D SHAP outputs (samples, features, [classes])
                            if hasattr(raw_vals, "ndim") and raw_vals.ndim == 3:
                                vals = raw_vals[0, :, 0]
                            elif (
                                hasattr(raw_vals, "ndim")
                                and raw_vals.ndim == 2
                            ):
                                vals = raw_vals[0]
                            else:
                                vals = raw_vals

                            import numpy as np

                            cols = feature_row.columns.tolist()
                            top_k = min(8, len(cols))
                            top_idx = np.argsort(np.abs(vals))[-top_k:]

                            top_features = [cols[i] for i in top_idx]
                            top_values = [vals[i] for i in top_idx]

            # 4. Fallback rendering if values could not be computed
            if not top_features or not top_values:
                return

            # 5. Render to matplotlib canvas
            fig, ax = plt.subplots(figsize=(6, 4))
            fig.patch.set_facecolor("none")
            ax.set_facecolor("none")

            colors = ["#00c3d9" if v >= 0 else "#d50000" for v in top_values]
            ax.barh(top_features, top_values, color=colors)
            ax.set_title(
                f"SHAP Feature Impact: {ward_name}",
                color="white",
                fontsize=11,
                fontweight="bold",
            )
            ax.tick_params(colors="white", labelsize=9)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#888888")
            ax.spines["bottom"].set_color("#888888")
            plt.tight_layout()

            self.set_shap_figure(fig)

        except Exception as e:
            print(f"[SHAP UI] Could not render SHAP chart: {e}")


    def set_controller(self, controller) -> None:
        self.controller = controller
        self.populate_from_controller()

    def populate_from_controller(self):
        if self.controller is None:
            return
        try:
            division_forecasts = self.controller.get_division_forecasts()
            if division_forecasts is not None and not division_forecasts.empty:
                wards_data = []
                for _, row in division_forecasts.iterrows():
                    council = str(row.get("council", ""))
                    division = str(row.get("division", ""))
                    councillor = str(row.get("current_councillor", ""))
                    party = str(row.get("incumbent_party", ""))
                    forecast = str(row.get("forecasted_party", ""))
                    code = str(row.get("division_code", ""))
                    wards_data.append((council, division, councillor, party, forecast, code))
                
                self.populate_ward_list(wards_data)
        except Exception as e:
            print(f"[ANALYSIS SCREEN] Could not load ward list: {e}")

    @QtCore.Slot(object)
    def set_forecaster(self, forecaster) -> None:
        self.set_controller(DashboardController(forecaster))