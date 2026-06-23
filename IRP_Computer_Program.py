# IRP Computer Program
# Using Machine Learning & Statistical Analysis to Predict UK Local Election Results
# Ian Milburn
# created: 21/05/2026
# File for the main running class of the IRP Computer Program
import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import matplotlib
from PySide6 import QtWidgets, QtCore, QtGui
from IRP_GUIs import DashboardGUI, ForecastGUI, DataManagerGUI
from widgets import ButtonWidget, blue_button_style, active_blue_button_style, red_button_style, green_button_style, FormRow, GaugeWidget
from Data import SampleData
from Controllers import DashboardController, ForecastController, DataManagerController, ScreenFactory


class IRPComputerProgram:
    def __init__(self):
        # Initialize the program
        self.data_source = SampleData()
        self.screen_name = "IRP Computer Program Main Dashboard"
        self.screen_titles = {
            "main": "IRP Computer Program - Dashboard",
            "data_collection": "Data Collection & Preprocessing",
            "model_training": "Model Training & Evaluation",
            "results_visualization": "Results Visualization & Analysis"
        }
        self.main_window = None
        self.factory = ScreenFactory()
        self.factory.register("Dashboard", DashboardGUI)
        self.factory.register("Forecasts", ForecastGUI)
        self.factory.register("Data Collection", DataManagerGUI)

        self.screen_configs = [
            {"name": "Dashboard", "controller": DashboardController(self.data_source), "label": "Dashboard"},
            {"name": "Forecasts", "controller": ForecastController(self.data_source), "label": "Forecasts"},
            {"name": "Data Collection", "controller": DataManagerController(self.data_source), "label": "Data Collection"},
            # Add new screens here without changing main logic
        ]

    def run(self):
        # Main method to run the program
        print("Welcome to the IRP Election Forecasting Computer Program!")
        # create an instance of the QApplication if it doesn't already exist
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication(sys.argv)
            self.owns_app = True
        else:
            self.owns_app = False
        
        # Set up the main window and show the dashboard
        self.main_window = QtWidgets.QMainWindow()
        self.main_window.setWindowTitle(self.screen_titles["main"])
        self.main_window.setWindowTitle("Election Forecaster")
        self.main_window.setMinimumSize(800, 600)

        # Set up backround with a layer 0 frame
        central_widget = QtWidgets.QWidget()
        self.main_window.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)

        # Add a Layer 1 vertical Control Panel on the left
        control_panel_widget = QtWidgets.QWidget()
        control_panel_widget.setFixedWidth(120)  # Set fixed width for the control panel
        control_panel_layout = QtWidgets.QVBoxLayout(control_panel_widget)

        # add buttons to the control panel
        # create a list of button labels and their corresponding styles
        self.buttons = {}
        # Define the button labels and their corresponding styles
        button_names = [
            "Dashboard",
            "Forecasts",
            "Boundaries",
            "Data Collection",
            "Model Training"
        ]
        # Create buttons in a loop and add them to the control panel
        for name in button_names:
            btn = ButtonWidget(
                control_panel_layout,
                name,
                lambda checked=False, n=name: self.change_screen(n), # Use a lambda to capture the current value of 'name' in the loop
                button_style=blue_button_style
                )
            self.buttons[name] = btn  # Optional: store for later use
        # Set the "Dashboard" button to active style by default
        if "Dashboard" in self.buttons:
            self.buttons["Dashboard"].set_style(active_blue_button_style)
        control_panel_layout.addStretch()

        # Add an exit button at the bottom of the control panel
        self.exit_button = ButtonWidget(control_panel_layout, "Exit", self.app.quit, button_style=red_button_style)

        # Add the control panel widget to the main layout
        main_layout.addWidget(control_panel_widget)

        # Add a Layer 1 frame for the main content area on the right
        self.content_area = QtWidgets.QFrame()
        self.content_area.setFrameShape(QtWidgets.QFrame.StyledPanel)
        main_layout.addWidget(self.content_area)

        # add a vertical layout to the content area
        right_layout = QtWidgets.QVBoxLayout()
        self.content_area.setLayout(right_layout)

        self.screens = {}
        for config in self.screen_configs:
            self.screens[config["name"]] = self.factory.create(
                config["name"],
                right_layout,
                controller=config["controller"],
                label_text=config["label"],
                main_window=self.main_window
            )
 
        # Add all Static Widgets to the screen (these are constantly visible on all screens)
        top_layout = QtWidgets.QHBoxLayout()
        right_layout.addLayout(top_layout)
        # add the app logo to the top left of the screen
        project_root = Path(__file__).resolve().parent
        logo_path = project_root / "logo" / "app logo2.pdf"
        if not logo_path.exists():
            logo_path = project_root / "logo" / "app logo.ico"
        logo_pixmap = QtGui.QPixmap(str(logo_path))
        if not logo_pixmap.isNull():
            logo_pixmap = logo_pixmap.scaled(125, 125, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        top_layout.addWidget(QtWidgets.QLabel(pixmap=logo_pixmap))
        # add the app title and datetime to the top of the screen in a vertical layout
        title_layout = QtWidgets.QVBoxLayout()
        top_layout.addLayout(title_layout)
        title_label = QtWidgets.QLabel("IRP Computer Program")
        title_label.setAlignment(QtCore.Qt.AlignLeft)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_layout.addWidget(title_label)
        top_layout.addStretch()  # Add a stretched label to push the datetime label to the left
        # add a stretched label to the title layout to push the datetime label to the left

        self.ui_title = QtWidgets.QLabel("Dashboard")  #<----------- find a way to make this dynamic based on the current screen
        self.ui_title.setAlignment(QtCore.Qt.AlignLeft)
        self.ui_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #555;")
        self.datetime_label = QtWidgets.QLabel(QtCore.QDateTime.currentDateTime().toString("dddd, MMMM d, yyyy - hh:mm:ss AP"))
        self.datetime_label.setAlignment(QtCore.Qt.AlignLeft)
        self.datetime_label.setStyleSheet("font-size: 14px; color: #777;")
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # Update every 1000 ms (1 second)
        title_layout.addWidget(self.ui_title)
        title_layout.addWidget(self.datetime_label)

        # create a stacked widget to hold the different screen contents
        self.stacked_widget = QtWidgets.QStackedWidget()
        right_layout.addWidget(self.stacked_widget)

        for name, screen in self.screens.items():
            widget = screen.frame if hasattr(screen, "frame") else screen
            self.stacked_widget.addWidget(widget)
        self.stacked_widget.setCurrentWidget(self.screens["Dashboard"].frame if hasattr(self.screens["Dashboard"], "frame") else self.screens["Dashboard"])
        print("Screens added to content stack")
        self.main_window.showMaximized()
        print("Main window shown")

        # Start the event loop if this class owns the QApplication
        if self.owns_app:
            self.app.exec()

    def update_time(self):
        current_time = QtCore.QDateTime.currentDateTime().toString("dddd, MMMM d, yyyy - hh:mm:ss AP")
        self.datetime_label.setText(current_time)

    def change_screen(self, screen_name):
        # Check if the screen exists
        if screen_name in self.screens:
            widget = self.screens[screen_name].frame if hasattr(self.screens[screen_name], "frame") else self.screens[screen_name]
            self.stacked_widget.setCurrentWidget(widget)
            self.ui_title.setText(screen_name)
            # Optionally, update button styles to show which is active
            for name, btn in self.buttons.items():
                if name == screen_name:
                    btn.set_style(active_blue_button_style)
                else:
                    btn.set_style(blue_button_style)
    
    def run_app(self):
        self.main_window.show()
        if self.owns_app:
            sys.exit(self.app.exec())

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = IRPComputerProgram()
    window.run()
    sys.exit(app.exec())