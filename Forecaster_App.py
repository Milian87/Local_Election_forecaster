# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the main application logic for the election forecaster, including the GUI and application flow.

import sys
from PySide6 import QtCore
import PySide6.QtWidgets as QtWidgets
from forecaster_Controllers import DashboardController
from forecaster_forecast_service import (Forecaster_1, Forecast_Repository, ForecastService)
from forecaster_GUI import AnalysisScreen, DashboardScreen, DataScreen, ForecastScreen, MainWindow


class ForecastWorker(QtCore.QObject):
    completed = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    finished = QtCore.Signal()

    @QtCore.Slot()
    def run(self) -> None:
        try:
            forecaster = Forecaster_1(use_xgboost=False)
            ForecastService(forecaster, Forecast_Repository(load_map=False)).run_forecast()
            self.completed.emit(forecaster)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

class ForecastApp:
    def __init__(self, screens=None):
        self.screens = screens or {"Dashboard": DashboardScreen, "Forecast": ForecastScreen, "Analysis": AnalysisScreen, "Data": DataScreen}
        self.app = None
        self.main_window = None

    def run(self):
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        screen_widgets = {
            "Dashboard": DashboardScreen(),
            "Forecast": ForecastScreen(),
            "Analysis": AnalysisScreen(),
            "Data": DataScreen(),
        }

        self.main_window = MainWindow(screen_widgets)
        self.main_window.showMaximized()
        self._start_forecast_worker(screen_widgets["Dashboard"])
        return self.app.exec()

    def _start_forecast_worker(self, dashboard: DashboardScreen) -> None:
        self.forecast_thread = QtCore.QThread(self.app)
        self.forecast_worker = ForecastWorker()
        self.forecast_worker.moveToThread(self.forecast_thread)
        self.forecast_thread.started.connect(self.forecast_worker.run)
        self.forecast_worker.completed.connect(dashboard.set_forecaster)
        self.forecast_worker.failed.connect(self._show_forecast_error)
        self.forecast_worker.finished.connect(self.forecast_thread.quit)
        self.forecast_worker.finished.connect(self.forecast_worker.deleteLater)
        self.forecast_thread.finished.connect(self.forecast_thread.deleteLater)
        self.forecast_thread.start()

    def _show_forecast_error(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(
            self.main_window,
            "Forecast Unavailable",
            f"The dashboard is showing sample data because the forecast failed:\n{message}",
        )


if __name__ == "__main__":
    # connect to the database
   ## db = MySQLDatabase(connection_string=None)

    ForecastApp().run()

    # disconnect from the database
   ## db.disconnect()