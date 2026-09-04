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
from forecaster_Controllers import DashboardController
from forecaster_forecast_service import (Forecaster_1, Forecast_Repository, ForecastService)
from forecaster_GUI import DashboardScreen, ForecastScreen, AnalysisScreen, MainWindow

class ForecastApp:
    def __init__(self, screens=None):
        self.screens = screens or {"Dashboard": DashboardScreen, "Forecast": ForecastScreen, "Analysis": AnalysisScreen, "Data": DataScreen}
        self.app = None
        self.main_window = None

    def run(self):
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        forecaster = Forecaster_1(use_xgboost=False)
        repository = Forecast_Repository()
        forecast_service = ForecastService(forecaster, repository)

        forecast_service.run_forecast()

        dashboard_controller = DashboardController(forecaster)
        screen_widgets = {
            "Dashboard": DashboardScreen(controller=dashboard_controller),
            "Forecast": ForecastScreen(controller=dashboard_controller),
            "Analysis": AnalysisScreen(),
            "Data": DataScreen(),
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