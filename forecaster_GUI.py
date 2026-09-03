# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the GUI definitions for the election forecaster application.

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
        panel.setFixedWidth(120)
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

        layout.addStretch()
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        ButtonWidget(layout, "Exit", app.quit, button_style=red_button_style)
        return panel

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
        title_layout.addWidget(self.datetime_label)
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

        if screen_name == "Forecast":  # TEMP: run the forecaster system when the Forecast nav button is pressed
            self._run_temp_forecast_confirmation()  # TEMP: remove this call once the forecaster system is confirmed working

    def _run_temp_forecast_confirmation(self):  # TEMP: temporary end-to-end confirmation hook, safe to delete
        if getattr(self, "_temp_forecast_ran", False):  # TEMP: only run once per app session
            return
        self._temp_forecast_ran = True  # TEMP: guard flag for the one-shot run above
        from forecaster_forecast_service import Forecaster, Forecast_Repository, ForecastService  # TEMP: temporary import
        forecaster = Forecaster(use_xgboost=False)  # TEMP: fast Random Forest path for a quick confirmation run
        repository = Forecast_Repository()  # TEMP: repository owns its own DB connection
        service = ForecastService(forecaster, repository)  # TEMP: coordinator wiring repository + forecaster
        try:
            forecast_df = service.run_forecast()  # TEMP: load data -> prepare_data -> train_model -> predict
            message = (
                f"Forecast pipeline ran successfully: {len(forecast_df)} rows "
                f"across {forecast_df['wd_code'].nunique()} wards."
            )  # TEMP: confirmation message
            print(f"[TEMP FORECAST CHECK] {message}")  # TEMP: console confirmation
            QtWidgets.QMessageBox.information(self, "Forecast Check", message)  # TEMP: visible GUI confirmation
        except Exception as error:  # TEMP: surface pipeline failures without crashing the GUI
            print(f"[TEMP FORECAST CHECK] Forecast pipeline failed: {error}")  # TEMP: console failure output
            QtWidgets.QMessageBox.critical(self, "Forecast Check Failed", str(error))  # TEMP: visible GUI failure

class BaseScreen(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("base-screen")
        self.setStyleSheet("#base-screen { background: transparent; }")

class DashboardScreen(BaseScreen):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller or DashboardController(SampleData())
        layout = QtWidgets.QVBoxLayout(self)


        # initialize the frame and layout for the dashboard content
        self.frame = QtWidgets.QFrame()
        self.dashboard_layout = QtWidgets.QHBoxLayout(self.frame)
        layout.addWidget(self.frame)

        # add the left layout for the summary and statistics
        self.left_frame = QtWidgets.QFrame()
        #self.left_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.left_layout = QtWidgets.QVBoxLayout(self.left_frame)
        self.dashboard_layout.addWidget(self.left_frame)

        # add the right layout for the map
        self.right_frame = QtWidgets.QFrame()
        self.right_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.right_layout = QtWidgets.QVBoxLayout(self.right_frame)
        self.right_frame.setFixedWidth(750)
        self.dashboard_layout.addWidget(self.right_frame)

        # add a combo box for selecting level of council (district, county)
        self.level_combo_box = QtWidgets.QComboBox()
        self.level_combo_box.addItems(["District", "County & Unitary"])
        self.left_layout.addWidget(self.level_combo_box)
        self.summary_table = TransparentTableWidget(
            ["Council / Ward", "Forecast Party", "Seats / Share"]
        )
        self.left_layout.addWidget(self.summary_table)

        self.vote_share_table = TransparentTableWidget(
            ["Party", "national Vote Share", "Seats"]
        )
        self.left_layout.addWidget(self.vote_share_table)

        self.populate_tables()

        boundary_path = Path(__file__).parent / "ward_boundaries.geojson"
        try:
            self.map_orchestrator = map_orchestrator.CouncilMapOrchestrator(
                str(boundary_path)
            )
            self.map_view = self.map_orchestrator.generate(
                self.controller.get_forecast_data()
            )
            self.right_layout.addWidget(self.map_view)
        except (OSError, ValueError, ImportError) as error:
            self.map_view = QtWidgets.QLabel(f"Map unavailable: {error}")
            self.map_view.setWordWrap(True)
            self.right_layout.addWidget(self.map_view)

    def populate_tables(self):
        forecast_data: pd.DataFrame = self.controller.get_forecast_data()
        self.summary_table.setRowCount(len(forecast_data))
        for row_index, (_, row) in enumerate(forecast_data.iterrows()):
            council_or_ward = row.get("council", row.get("ward_name", row.get("ward", "")))
            party = row.get("party_label", row.get("party", ""))
            seats_or_share = row.get("seats", row.get("final_forecast_share", ""))
            values = [str(council_or_ward), str(party), str(seats_or_share)]
            for column_index, value in enumerate(values):
                self.summary_table.setItem(
                    row_index,
                    column_index,
                    QtWidgets.QTableWidgetItem(value),
                )

        summary = self.controller.get_summary()
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

class ForecastScreen(BaseScreen):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = QtWidgets.QVBoxLayout(self)
        # Add more widgets and functionality for the Forecast screen here

class DataScreen(BaseScreen):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = QtWidgets.QVBoxLayout(self)
        # Add more widgets and functionality for the Data screen here

class AnalysisScreen(BaseScreen):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = QtWidgets.QVBoxLayout(self)
        # Add more widgets and functionality for the Analysis screen here

