# IRP Computer Program
# Using Machine Learning & Statistical Analysis to Predict UK Local Election Results
# Ian Milburn
# created: 21/05/2026
# File for the GUI components of the IRP Computer Program

import os
from pathlib import Path
from PySide6 import QtCore
import folium
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
import PySide6.QtWidgets as QtWidgets
from widgets import ButtonWidget, blue_button_style, active_blue_button_style, red_button_style, Map, green_button_style, FormRow, GaugeWidget
from Data import SampleData
from Controllers import DashboardController
from Interfaces import ScreenInterface
from GlobalState import map_orchestrator

# Inside your GUI class:
map_orchestrator = map_orchestrator
web_map_view = map_orchestrator.generate_live_viewport(...)


def _resolve_division_boundary_path(project_root: Path) -> Path:
    """
    Resolve an England-wide divisions layer first, then fall back safely.
    """
    data_root = project_root / "data"

    for year in ("2026", "2025"):
        official_candidate = (
            data_root
            / f"County Electoral Division (May {year}) Boundaries EN BFE"
            / f"CED_MAY_{year}_EN_BFC.shp"
        )
        if official_candidate.is_file():
            print(f"[MAP ENGINE] Using official England-wide CED boundary layer: {official_candidate.name}")
            return official_candidate

    all_shapefiles = list(data_root.rglob("*.shp"))
    england_candidates = []
    for path in all_shapefiles:
        path_lower = str(path).lower()
        name_lower = path.name.lower()
        if "england" in path_lower and any(tok in name_lower for tok in ["ced", "division", "county"]):
            england_candidates.append(path)
    if england_candidates:
        chosen = sorted(england_candidates)[0]
        print(f"[MAP ENGINE] Fallback to England-wide discovered layer: {chosen.name}")
        return chosen

    for path in all_shapefiles:
        if "ced" in path.name.lower():
            print(f"[MAP ENGINE] Fallback to generic CED layer: {path.name}")
            return path

    return project_root / "county_divisions.geojson"

class BaseScreen(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Common screen setup can be done here, such as setting background color, fonts, etc.
        self.setStyleSheet("background-color: #f0f0f0; border-radius: 10px;")


class DashboardGUI(BaseScreen):
    def __init__(self, parent_layout, controller, label_text, main_window=None):
        super().__init__()
        self.controller = controller
        
        # Initialize the Dashboard GUI Main Layout Frame Workspace
        self.frame = QtWidgets.QFrame()
        self.frame.setStyleSheet("background-color: #f0f0f0; border-radius: 10px;")
        self.dashboard_layout = QtWidgets.QHBoxLayout(self.frame)
        parent_layout.addWidget(self.frame)

        # Left Column Layout Frame (Summary Cards & Statistical Tables)
        self.left_frame = QtWidgets.QFrame()
        self.left_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.left_layout = QtWidgets.QVBoxLayout(self.left_frame)
        self.dashboard_layout.addWidget(self.left_frame)
        
        # Right Column Layout Frame (Viewport Canvas Allocation)
        self.right_frame = QtWidgets.QFrame()
        self.right_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.right_layout = QtWidgets.QVBoxLayout(self.right_frame)
        self.right_frame.setFixedWidth(750)
        self.dashboard_layout.addWidget(self.right_frame)

        # Populate Left Column Interface Dashboard Panels
        self.summary_frame1 = self.create_overall_summary()
        self.left_layout.addWidget(self.summary_frame1)

        self.summary_frame2 = self.create_detailed_summary()
        self.left_layout.addWidget(self.summary_frame2)

        # Allocate Viewport Frame Container for the Map Engine
        self.map_frame = QtWidgets.QFrame()
        self.map_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 10px;")
        self.map_layout = QtWidgets.QHBoxLayout(self.map_frame)
        self.right_layout.addWidget(self.map_frame)
        
        # Build absolute reference paths to your regional vector boundary layers
        project_root = Path(__file__).resolve().parent
        boundary_path = str(_resolve_division_boundary_path(project_root))

        # 🚀 HOOK INTO THE NEW MAP ENGINE (DISSOLVED COUNCIL MODE)
        try:
            from MapOrchestrator import MapOrchestrator
            self.map_orchestrator = MapOrchestrator(boundary_path)
            
            # Fetch live prediction frames and dissolve geometries to council-level outlines
            self.web_map_view = self.map_orchestrator.generate_live_viewport(
                forecast_df=self.controller.get_forecast_data(),
                view_mode="council"
            )
        except Exception as e:
            print(f"❌ [GUI ERROR] Dashboard council map initialization failed: {e}")
            # Structural fallback to standard placeholder labels if data dependencies miss
            self.web_map_view = QtWidgets.QLabel(f"Map Rendering Error:\n{e}")
            self.web_map_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.map_layout.addWidget(self.web_map_view)

    def create_overall_summary(self):
        # create a level 3 vertical summary frame and layout to the top of the left side of the dashboard
        self.summary_frame1 = QtWidgets.QFrame()
        self.summary_frame1.setStyleSheet("background-color: #f9f9f9; border-radius: 10px;")
        self.summary_layout1 = QtWidgets.QVBoxLayout(self.summary_frame1)
        # add summary labels to the summary layout
        self.summary_label1 = QtWidgets.QLabel("Overall Summary: Local Election Forecast")
        # set the font size and weight of the summary label for better visibility
        font = self.summary_label1.font()
        font.setPointSize(12)
        font.setBold(True)
        self.summary_label1.setFont(font)

        self.summary_layout1.addWidget(self.summary_label1)
        # add a level 4 horizontal frame and layout to hold summary statistics in the overall summary frame
        self.summary_stats_frame = QtWidgets.QFrame()
        self.summary_stats_layout = QtWidgets.QHBoxLayout(self.summary_stats_frame)
        self.summary_layout1.addWidget(self.summary_stats_frame)

        # add a level 5 vertical frame and layout to hold the dropdown menu
        self.dropdown_frame = QtWidgets.QFrame()
        self.dropdown_layout = QtWidgets.QVBoxLayout(self.dropdown_frame)
        self.summary_stats_layout.addWidget(self.dropdown_frame)
        self.dropdown_layout.setAlignment(QtCore.Qt.AlignTop)  # Align dropdown to the top of the summary stats frame 
        # add a dropdown menu to the overall summary frame to select different councils and update the summary statistics accordingly
        self.council_dropdown = QtWidgets.QComboBox()
        self.council_dropdown.addItems(["All Councils", "Council A", "Council B", "Council C"])
        self.dropdown_layout.addWidget(self.council_dropdown)
        # add a table widget to the overall summary frame to display summary statistics
        self.summary_table = QtWidgets.QTableWidget()
        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels(["Party", "Current Seats", "Predicted Seats", "Difference"])
        # use the controller to get the summary data
        forecast_summary = self.controller.get_summary()
        # populate the table with the pd dataframe values from forecast_summary
        self.summary_table.setRowCount(len(forecast_summary))
        for i, row in forecast_summary.iterrows():
            self.summary_table.setItem(i, 0, QtWidgets.QTableWidgetItem(row["party"]))
            self.summary_table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(row["seats_forecast"])))
            self.summary_table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(row["seats_current"])))
            self.summary_table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(row["seat_difference"])))
        # set the lines between rows to be visible for better readability
        self.summary_table.setShowGrid(True)
        self.summary_stats_layout.addWidget(self.summary_table)

        # add a pie chart widget to the dropdown frame to display the predicted vote share for each party (placeholder for now)
        self.seat_share_chart = QtWidgets.QLabel("Vote Share Chart Placeholder")
        # Set the font size and weight of the seat share chart and swingometer label for better visibility
        font = self.seat_share_chart.font()
        font.setPointSize(9)
        font.setBold(True)
        self.seat_share_chart.setFont(font)
        self.dropdown_layout.addWidget(self.seat_share_chart)
        self.seat_share_chart.setAlignment(QtCore.Qt.AlignCenter)
        # add a circle shape to act as a placeholder for the pie chart
        self.seat_share_chart = QtWidgets.QLabel("Vote Share\nChart\nPlaceholder")
        self.seat_share_chart.setAlignment(QtCore.Qt.AlignCenter)
        self.seat_share_chart.setFixedSize(150, 150)  # Set width and height to the same value
        self.seat_share_chart.setStyleSheet("""
            border-radius: 75px;         /* Half of width/height for a perfect circle */
            background-color: #f88;      /* Light red background */
            color: #555;                 /* Text color */
            font-size: 14px;
            border: 2px solid #bbb;      /* Optional: add a border */
        """)
        self.dropdown_layout.addWidget(self.seat_share_chart)
        # add a swingometer widget to the dropdown frame to display the predicted swing for each party (placeholder for now)
        self.swingometer_title = QtWidgets.QLabel("Swingometer Placeholder")
        self.swingometer_title.setFont(font)
        self.swingometer_title.setAlignment(QtCore.Qt.AlignCenter)
        self.dropdown_layout.addWidget(self.swingometer_title)
        # add a circle shape to act as a placeholder for the swingometer
        self.swingometer = QtWidgets.QLabel("Swingometer\nPlaceholder")
        self.swingometer.setAlignment(QtCore.Qt.AlignCenter)
        self.dropdown_layout.addWidget(self.swingometer)
        self.swingometer.setFixedSize(150, 150)  # Set width and height to the same value
        self.swingometer.setStyleSheet("""
            border-radius: 75px;         /* Half of width/height for a perfect circle */
            background-color: #8f8;      /* Light green background */
            color: #555;                 /* Text color */
            font-size: 14px;
            border: 2px solid #bbb;      /* Optional: add a border */
        """)
        self.dropdown_layout.addWidget(self.swingometer)
        # return the overall summary frame to be added to the dashboard layout
        return self.summary_frame1

    def create_detailed_summary(self):
        # create a level 3 vertical summary frame and layout to the top of the left side of the dashboard
        self.summary_frame2 = QtWidgets.QFrame()
        self.summary_frame2.setStyleSheet("background-color: #f9f9f9; border-radius: 10px;")
        self.summary_layout2 = QtWidgets.QVBoxLayout(self.summary_frame2)
        # add summary labels to the summary layout
        self.summary_label2 = QtWidgets.QLabel("Detailed Summary: Local Election Forecast")
        # set the font size and weight of the summary label for better visibility
        font = self.summary_label2.font()
        font.setPointSize(12)
        font.setBold(True)
        self.summary_label2.setFont(font)
        self.summary_layout2.addWidget(self.summary_label2)
        # add a level 4 horizontal frame and layout to hold summary statistics in the detailed summary frame
        self.summary_stats_frame2 = QtWidgets.QFrame()
        self.summary_stats_layout2 = QtWidgets.QHBoxLayout(self.summary_stats_frame2)
        self.summary_layout2.addWidget(self.summary_stats_frame2)

        # add a level 5 vertical frame and layout to hold the confidence dial
        self.confidence_dial_frame = QtWidgets.QFrame()
        self.confidence_dial_layout = QtWidgets.QVBoxLayout(self.confidence_dial_frame)
        self.summary_stats_layout2.addWidget(self.confidence_dial_frame)
        # add a label for the confidence dial
        self.confidence_dial_label = QtWidgets.QLabel("Model Confidence")
        self.confidence_dial_label.setFont(font)
        self.confidence_dial_label.setAlignment(QtCore.Qt.AlignCenter)
        self.confidence_dial_layout.addWidget(self.confidence_dial_label)

        # add a circle shape to act as a placeholder for the confidence dial
        self.confidence_dial = GaugeWidget(x=125, y=125)
        self.confidence_dial.set_value(85)  # Set an initial value for the gauge
        self.confidence_dial_layout.addWidget(self.confidence_dial)
        # add a stretch to push the confidence dial to the top of the detailed summary frame
        self.confidence_dial_layout.addStretch()

        # add the confidence dial to the detailed summary layout
        self.summary_stats_layout2.addWidget(self.confidence_dial_frame)
        # add a table widget to the detailed summary frame to display summary statistics
        self.summary_table = QtWidgets.QTableWidget()
        self.summary_table.setColumnCount(5)
        self.summary_table.setHorizontalHeaderLabels(["Party Emblem", "Division", "Councillor Name", "Current Party", "Predicted Party"])
        # set the lines between rows to be visible for better readability
        self.summary_table.setShowGrid(True)
        self.summary_stats_layout2.addWidget(self.summary_table)
        return self.summary_frame2
    
class ForecastGUI(BaseScreen):
    def __init__(self, parent_layout, controller, label_text, main_window=None):
        super().__init__()
        self.controller = controller
        
        # Initialize the Forecasts Main UI Grid Workspace Framework
        self.frame = QtWidgets.QFrame()
        self.frame.setStyleSheet("background-color: #f0f0f0; border-radius: 10px;")
        self.dashboard_layout = QtWidgets.QHBoxLayout(self.frame)
        parent_layout.addWidget(self.frame)

        # Left Sidebar Column Frame Allocation
        self.left_frame = QtWidgets.QFrame()
        self.left_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.left_layout = QtWidgets.QVBoxLayout(self.left_frame)
        self.dashboard_layout.addWidget(self.left_frame)
        
        # Right Viewport Map Canvas Layout Frame Allocation
        self.right_frame = QtWidgets.QFrame()
        self.right_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.right_layout = QtWidgets.QVBoxLayout(self.right_frame)
        self.right_frame.setFixedWidth(750)
        self.dashboard_layout.addWidget(self.right_frame)

        # Allocate Viewport Frame Container for the Map Engine
        self.map_frame = QtWidgets.QFrame()
        self.map_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 10px;")
        self.map_layout = QtWidgets.QHBoxLayout(self.map_frame)
        self.right_layout.addWidget(self.map_frame)
        
        project_root = Path(__file__).resolve().parent
        boundary_path = str(_resolve_division_boundary_path(project_root))

        # 🚀 HOOK INTO THE NEW MAP ENGINE (EXPLICIT WARD/DIVISION MODE)
        try:
            from MapOrchestrator import MapOrchestrator
            self.map_orchestrator = MapOrchestrator(boundary_path)
            
            # Maintain structural fine-grained ward shapes for detailed regional target filtering
            self.web_map_view = self.map_orchestrator.generate_live_viewport(
                forecast_df=self.controller.get_forecast_data(),
                view_mode="ward"
            )
        except Exception as e:
            print(f"❌ [GUI ERROR] Forecast ward map initialization failed: {e}")
            self.web_map_view = QtWidgets.QLabel(f"Map Rendering Error:\n{e}")
            self.web_map_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.map_layout.addWidget(self.web_map_view)

class DataManagerGUI(BaseScreen):
    def __init__(self, parent_layout, controller, label_text, main_window=None):
        super().__init__()
        self.controller = controller
        # Initialize the Dashboard GUI
        # Create the Level 1 Horizontal frame and layout
        self.frame = QtWidgets.QFrame()
        self.frame.setStyleSheet("background-color: #f0f0f0; border-radius: 10px;")
        self.dashboard_layout = QtWidgets.QHBoxLayout(self.frame)
        parent_layout.addWidget(self.frame)

        # create a level 2 vertical frame and layout for the left side of the dashboard
        self.left_frame = QtWidgets.QFrame()
        self.left_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.left_layout = QtWidgets.QVBoxLayout(self.left_frame)
        self.dashboard_layout.addWidget(self.left_frame)
        # create a level 2 vertical frame and layout for the right side of the dashboard
        self.right_frame = QtWidgets.QFrame()
        self.right_frame.setStyleSheet("background-color: #ffffff; border-radius: 10px;")
        self.right_layout = QtWidgets.QVBoxLayout(self.right_frame)
        # make the right frame to be a set width for better visualization of the map and summary statistics
        self.right_frame.setFixedWidth(750)
        self.dashboard_layout.addWidget(self.right_frame)

        # add a level 3 horizontal summary frame and layout to hold a map on the right side of the dashboard
        self.map_frame = QtWidgets.QFrame()
        self.map_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 10px;")