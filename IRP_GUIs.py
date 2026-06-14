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

class BaseScreen(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Common screen setup can be done here, such as setting background color, fonts, etc.
        self.setStyleSheet("background-color: #f0f0f0; border-radius: 10px;")


class DashboardGUI(BaseScreen):
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

        # add a level 3 horizontal summary frame and layout to the top of the left side of the dashboard
        self.summary_frame1 = self.create_overall_summary()
        self.left_layout.addWidget(self.summary_frame1)

        # add a level 3 horizontal summary frame and layout to the bottom of the left side of the dashboard
        self.summary_frame2 = self.create_detailed_summary()
        self.left_layout.addWidget(self.summary_frame2)


        # add a level 3 horizontal summary frame and layout to hold a map on the right side of the dashboard
        self.map_frame = QtWidgets.QFrame()
        self.map_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 10px;")
        self.map_layout = QtWidgets.QHBoxLayout(self.map_frame)
        self.right_layout.addWidget(self.map_frame)
        
        # Use the workspace GeoJSON directly (single-file boundary source).
        project_root = Path(__file__).resolve().parent
        ward_geojson_path = project_root / "county_divisions.geojson"

        if not ward_geojson_path.is_file():
            print(f"[ERROR] Ward boundary GeoJSON not found: {ward_geojson_path}")
        else:
            print(f"[SUCCESS] Ward boundary GeoJSON found: {ward_geojson_path}")

        # Optional OA layer is disabled when running from a single GeoJSON input.
        oa_shp_path = None

        
        # add a map widget to the map frame to display the predicted election results by ward (placeholder for now)
        maps = Map(self.map_frame)
        self.web_map_view = maps.create_map(
            ward_shp_path=str(ward_geojson_path),
            oa_shp_path=oa_shp_path,
            forecast_df=self.controller.get_forecast_data()
        )
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
        self.map_layout = QtWidgets.QHBoxLayout(self.map_frame)
        self.right_layout.addWidget(self.map_frame)
        # Use the same county division boundaries as the dashboard to avoid an empty map layer.
        project_root = Path(__file__).resolve().parent
        ward_geojson_path = project_root / "county_divisions.geojson"
        oa_shp_path = None

        # add a map widget to the map frame to display the predicted election results by ward (placeholder for now)
        maps= Map(self.map_frame)
        self.web_map_view = maps.create_map(
            ward_shp_path=str(ward_geojson_path),
            oa_shp_path=oa_shp_path,
            forecast_df=self.controller.get_forecast_data()
        )
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