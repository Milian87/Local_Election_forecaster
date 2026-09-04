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
            ["Council", "Largest Seat Gain", "Seats Gained"]
        )
        self.left_layout.addWidget(self.summary_table)

        self.vote_share_table = TransparentTableWidget(
            ["Party", "national Vote Share", "Seats"]
        )
        self.left_layout.addWidget(self.vote_share_table)

        self.populate_tables()

        self.map_view = None
        self.refresh_map()

    def populate_tables(self):
        summary = self.controller.get_summary()
        council_summaries = self.controller.get_council_summaries()
        self.summary_table.setRowCount(len(council_summaries))
        for row_index, (_, row) in enumerate(council_summaries.iterrows()):
            values = [
                str(row["council"]),
                str(row["party"]),
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

    @QtCore.Slot(object)
    def set_forecaster(self, forecaster) -> None:
        self.set_controller(DashboardController(forecaster))

    def refresh_map(self) -> None:
        if self.map_view is not None:
            self.right_layout.removeWidget(self.map_view)
            self.map_view.deleteLater()

        boundary_path = (
            Path(__file__).parent
            / "data"
            / "County Electoral Division (May 2025) Boundaries EN BFE"
            / "CED_MAY_2025_EN_BFC.shp"
        )
        try:
            self.map_orchestrator = map_orchestrator.CouncilMapOrchestrator(str(boundary_path))
            self.map_view = self.map_orchestrator.generate(
                self.controller.get_county_and_unitary_forecast()
            )
        except (OSError, ValueError, ImportError) as error:
            self.map_view = QtWidgets.QLabel(f"Map unavailable: {error}")
            self.map_view.setWordWrap(True)
        self.right_layout.addWidget(self.map_view)

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

