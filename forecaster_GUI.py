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

        self.model_selector = QtWidgets.QComboBox()
        self.model_selector.addItem("Delta Model", "Delta Model")
        self.model_selector.addItem("Softmax Model", "Softmax Model")
        self.model_selector.setToolTip("Choose the forecast model")
        layout.addWidget(self.model_selector)

        self.date_selector = QtWidgets.QComboBox()
        for label, year in (
            ("2019 election", 2019),
            ("2021 election", 2021),
            ("2022 election", 2022),
            ("2023 election", 2023),
            ("2024 election", 2024),
            ("2025 election", 2025),
            ("16 April 2026", 2026),
            ("23 April 2026", 2026),
            ("30 April 2026", 2026),
            ("7 May 2026", 2026),
            ("8 May 2026", 2026),
            ("15 May 2026", 2026),
            ("22 May 2026", 2026),
            ("29 May 2026", 2026),
            ("5 June 2026", 2026),
            ("12 June 2026", 2026),
            ("19 June 2026", 2026),
            ("26 June 2026", 2026),
            ("3 July 2026", 2026),
            ("10 July 2026", 2026),
            ("17 July 2026", 2026),
            ("24 July 2026", 2026),
            ("31 July 2026", 2026),
            ("Tomorrow", 2027),
        ):
            self.date_selector.addItem(label, year)
        self.date_selector.setCurrentIndex(self.date_selector.count() - 1)
        self.date_selector.setToolTip("Choose the election date to forecast or backtest")
        layout.addWidget(self.date_selector)

        self.reforecast_button = QtWidgets.QPushButton("Reforecast")
        self.reforecast_button.setToolTip("Run the selected forecast model")
        self.reforecast_button.setStyleSheet(blue_button_style)
        layout.addWidget(self.reforecast_button)

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
        self.right_layout = QtWidgets.QStackedLayout(self.right_frame)
        self.right_layout.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackAll)
        self.right_frame.setFixedWidth(750)
        self.dashboard_layout.addWidget(self.right_frame)

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
        self.right_layout.addWidget(self.forecast_loading_label)
        self.right_layout.setAlignment(
            self.forecast_loading_label,
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter,
        )

        # add a combo box for selecting level of council (district, county)
        self.level_combo_box = QtWidgets.QComboBox()
        self.level_combo_box.addItems(["District", "County & Unitary"])
        self.left_layout.addWidget(self.level_combo_box)
        self.summary_table = TransparentTableWidget(
            ["Council", "Current Largest Party", "Forecasted Winner", "Seats Gained"]
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
        self.forecast_loading_label.raise_()

class ForecastScreen(BaseScreen):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = QtWidgets.QVBoxLayout(self)

        # initialize the frame and layout for the Forecast content
        self.frame = QtWidgets.QFrame()
        self.Forecast_layout = QtWidgets.QHBoxLayout(self.frame)
        layout.addWidget(self.frame)

        # add the left layout for the summary and statistics
        self.left_frame = QtWidgets.QFrame()
        #self.left_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.left_layout = QtWidgets.QVBoxLayout(self.left_frame)
        self.Forecast_layout.addWidget(self.left_frame)

        
        # add the right layout for the map and ward's forecast table
        self.right_frame = QtWidgets.QFrame()
        self.right_frame.setStyleSheet("background: transparent;")
        self.right_layout = QtWidgets.QVBoxLayout(self.right_frame)
        self.right_frame.setFixedWidth(750)
        self.Forecast_layout.addWidget(self.right_frame)

        # add an upper section for the forecast map
        self.map_container = QtWidgets.QFrame()
        self.map_container.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.map_layout = QtWidgets.QVBoxLayout(self.map_container)
        self.right_layout.addWidget(self.map_container, 3)

        # add a lower section for the ward's forecast table
        self.ward_forecast_container = QtWidgets.QFrame()
        self.ward_forecast_container.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.ward_forecast_layout = QtWidgets.QVBoxLayout(self.ward_forecast_container)
        self.right_layout.addWidget(self.ward_forecast_container, 2)

        self.ward_forecast_table = TransparentTableWidget(
            ["Candidate", "Party", "Current Share", "Forecast Share"]
        )
        self.ward_forecast_layout.addWidget(self.ward_forecast_table)

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

        # add a combo box for selecting level of council (district, county)
        self.level_combo_box = QtWidgets.QComboBox()
        self.level_combo_box.addItems(["District", "County & Unitary"])
        self.left_layout.addWidget(self.level_combo_box)
        self.council_selector = QtWidgets.QComboBox()
        self.council_selector.addItem("All councils", "")
        self.council_selector.setToolTip("Filter divisions and focus the map by council")
        self.council_selector.currentIndexChanged.connect(self._council_selection_changed)
        self.left_layout.addWidget(self.council_selector)
        self.summary_table = TransparentTableWidget(
            ["Council", "Current Largest Party", "Forecasted Winner", "Seats Gained"]
        )
        # add a left section for the list of divisions, incumbant cllr, forecast winner
        self.left_layout.addWidget(self.summary_table, 1)
        self.summary_table.cellClicked.connect(self._focus_map_from_table)
        self.vote_share_table = TransparentTableWidget(
            ["Party", "National Vote Share", "Seats"]
        )
        self.vote_share_table.setVisible(False)

        #self.populate_tables()

        self.map_view = None
        #self.refresh_map()

    def populate_tables(self):
        division_forecasts = self.controller.get_division_forecasts() # type: ignore
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
        self.summary_table.setColumnCount(5)
        self.summary_table.setHorizontalHeaderLabels(
            ["Council", "Division", "Current Councillor", "Incumbent Party", "Forecasted Party"]
        )
        self.summary_table.setRowCount(len(division_forecasts))
        self.ward_forecast_table.setRowCount(0)
        for row_index, (_, row) in enumerate(division_forecasts.iterrows()):
            values = [
                str(row["council"]),
                str(row["division"]),
                str(row["current_councillor"]),
                str(row["incumbent_party"]),
                str(row["forecasted_party"]),
            ]
            for column_index, value in enumerate(values):
                self.summary_table.setItem(row_index, column_index, QtWidgets.QTableWidgetItem(value))

        self.summary_table.resizeColumnsToContents()

        self._division_forecasts = division_forecasts

    def _council_selection_changed(self) -> None:
        selected_council = self.council_selector.currentData()
        all_divisions = self.controller.get_division_forecasts() # type: ignore
        if selected_council:
            filtered = all_divisions[
                all_divisions["council"].astype(str).str.strip() == str(selected_council).strip()
            ].copy()
        else:
            filtered = all_divisions

        self._division_forecasts = filtered
        self.summary_table.setRowCount(len(filtered))
        for row_index, (_, row) in enumerate(filtered.iterrows()):
            values = [
                str(row["council"]),
                str(row["division"]),
                str(row["current_councillor"]),
                str(row["incumbent_party"]),
                str(row["forecasted_party"]),
            ]
            for column_index, value in enumerate(values):
                self.summary_table.setItem(
                    row_index,
                    column_index,
                    QtWidgets.QTableWidgetItem(value),
                )
        self.summary_table.resizeColumnsToContents()
        self.refresh_map(focus_council=selected_council or None)

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
        results = self.controller.get_council_results(council_name) # type: ignore
        self.ward_forecast_table.setHorizontalHeaderLabels(
            ["Party", "Current Seats", "Forecast Seats", "Seats Gained"]
        )
        self.ward_forecast_table.setColumnCount(4)
        self.ward_forecast_table.setRowCount(len(results))
        for row_index, (_, row) in enumerate(results.iterrows()):
            values = [
                str(row["party"]),
                str(int(row["current_seats"])),
                str(int(row["forecast_seats"])),
                f"{int(row['seats_gained']):+d}",
            ]
            for column_index, value in enumerate(values):
                self.ward_forecast_table.setItem(
                    row_index,
                    column_index,
                    QtWidgets.QTableWidgetItem(value),
                )
        self.ward_forecast_table.resizeColumnsToContents()

    def populate_division_results(self, division_code: str) -> None:
        results = self.controller.get_division_results(division_code) # type: ignore
        self.ward_forecast_table.setHorizontalHeaderLabels(
            ["Candidate", "Party", "Current Share", "Forecast Share"]
        )
        self.ward_forecast_table.setColumnCount(4)
        if results.empty:
            self.ward_forecast_table.setRowCount(0)
            return

        results = results.sort_values("final_forecast_share", ascending=False)
        self.ward_forecast_table.setRowCount(len(results))
        for row_index, (_, row) in enumerate(results.iterrows()):
            values = [
                str(row.get("candidate_name", "")),
                str(row.get("party_label", "")),
                f"{float(row.get('party_vote_share', 0.0)):.1f}%",
                f"{float(row.get('final_forecast_share', 0.0)):.1f}%",
            ]
            for column_index, value in enumerate(values):
                self.ward_forecast_table.setItem(
                    row_index,
                    column_index,
                    QtWidgets.QTableWidgetItem(value),
                )
        self.ward_forecast_table.resizeColumnsToContents()

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

        boundary_path = (
            Path(__file__).parent
            / "data"
            / "County Electoral Division (May 2025) Boundaries EN BFE"
            / "CED_MAY_2025_EN_BFC.shp"
        )
        try:
            self.map_orchestrator = map_orchestrator.WardMapOrchestrator(str(boundary_path))
            self.map_view = self.map_orchestrator.generate(
                self.controller.get_county_and_unitary_forecast(), # type: ignore
                focus_division=focus_division,
                focus_council=focus_council,
            )
        except (OSError, ValueError, ImportError) as error:
            self.map_view = QtWidgets.QLabel(f"Map unavailable: {error}")
            self.map_view.setWordWrap(True)
        self.map_layout.addWidget(self.map_view)
        self.forecast_loading_label.setVisible(False)

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

