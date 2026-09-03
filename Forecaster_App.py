# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the main application logic for the election forecaster, including the GUI and application flow.

import sys
from pathlib import Path
from PySide6 import QtCore, QtGui
import PySide6.QtWidgets as QtWidgets
from forecaster_Controllers import DashboardController
from Data import SampleData
from forecaster_GUI import DataScreen
from forecaster_data import MySQLDatabase
from widgets import (
    ButtonWidget,
    active_blue_button_style,
    blue_button_style,
    red_button_style,
)
from widgets import TransparentTableWidget
from forecaster_GUI import DashboardScreen, ForecastScreen, AnalysisScreen, MainWindow

class ForecastApp:
    def __init__(self, screens=None):
        self.screens = screens or {"Dashboard": DashboardScreen, "Forecast": ForecastScreen, "Analysis": AnalysisScreen, "Data": DataScreen}
        self.app = None
        self.main_window = None

    def run(self):
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        screen_widgets = {
            name: screen() if isinstance(screen, type) else screen
            for name, screen in self.screens.items()
        }
        self.main_window = MainWindow(screen_widgets)
        self.main_window.showMaximized()
        return self.app.exec()


if __name__ == "__main__":
    # connect to the database
   ## db = MySQLDatabase(connection_string=None)

    ForecastApp().run()

    # disconnect from the database
   ## db.disconnect()