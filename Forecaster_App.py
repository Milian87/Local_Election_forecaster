# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the main application logic for the election forecaster, including the GUI and application flow.

import sys
import traceback
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
            print("[FORECAST] Starting forecast worker...", flush=True)
            forecaster = Forecaster_1(use_xgboost=False)
            repository = Forecast_Repository(load_map=False)
            print(
                f"[FORECAST] Database backend: {type(repository.database).__name__}",
                flush=True,
            )
            print("[FORECAST] Loading election data...", flush=True)
            forecast_data = ForecastService(forecaster, repository).run_forecast()
            print(f"[FORECAST] Generated {len(forecast_data):,} forecast rows.", flush=True)
            saved_boundaries = repository.save_forecast_to_postgis(forecast_data)
            print(f"[FORECAST] Saved {saved_boundaries:,} divisions to PostGIS.", flush=True)
            if not forecast_data.empty:
                preview_columns = [
                    column for column in (
                        "wd_code",
                        "ward_name",
                        "party_label",
                        "final_forecast_share",
                    )
                    if column in forecast_data.columns
                ]
                print("[FORECAST] Preview:", flush=True)
                print(forecast_data[preview_columns].head(10).to_string(index=False), flush=True)
            self.completed.emit(forecaster)
        except Exception as error:
            print(f"[FORECAST] Failed: {error}", flush=True)
            traceback.print_exc()
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
        screen_widgets["Dashboard"].set_forecast_loading(True)
        self._start_forecast_worker(screen_widgets["Dashboard"])
        return self.app.exec()

    def _start_forecast_worker(self, dashboard: DashboardScreen) -> None:
        self.forecast_thread = QtCore.QThread()
        self.forecast_worker = ForecastWorker()

        self.forecast_worker.moveToThread(self.forecast_thread)

        self.forecast_thread.started.connect(self.forecast_worker.run)
        self.forecast_worker.completed.connect(
            dashboard.set_forecaster,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self.forecast_worker.failed.connect(
            self._show_forecast_error,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )

        self.forecast_worker.finished.connect(self.forecast_thread.quit)
        self.forecast_thread.finished.connect(self.forecast_worker.deleteLater)
        self.forecast_thread.finished.connect(self.forecast_thread.deleteLater)

        self.forecast_thread.start()

    def _show_forecast_error(self, message: str) -> None:
        self.main_window.screens["Dashboard"].set_forecast_loading(False) # type: ignore
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