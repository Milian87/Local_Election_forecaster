# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the main application logic for the election forecaster, including the GUI and application flow.

import sys
import traceback
import re
from pathlib import Path
from PySide6 import QtCore
import PySide6.QtWidgets as QtWidgets
from forecaster_Controllers import DashboardController
from forecaster_forecast_service import (Forecaster_1, Forecaster_2, Forecast_Repository, ForecastService)
from forecaster_GUI import AnalysisScreen, DashboardScreen, DataScreen, ForecastScreen, MainWindow


class ForecastWorker(QtCore.QObject):
    completed = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    finished = QtCore.Signal()

    @QtCore.Slot()
    def __init__(self, compositional=False, target_date="2026-09-21", target_label="Tomorrow"):
        super().__init__()
        self.compositional = compositional
        self.target_date = target_date
        self.target_label = target_label

    @QtCore.Slot()
    def run(self) -> None:
        try:
            print("[FORECAST] Starting forecast worker...", flush=True)
            forecaster = (
                Forecaster_2(target_year=int(self.target_date[:4]))
                if self.compositional
                else Forecaster_1(use_xgboost=False, target_year=int(self.target_date[:4]))
            )
            forecaster.model_name = "Softmax Model" if self.compositional else "Delta Model" # pyright: ignore[reportAttributeAccessIssue]
            repository = Forecast_Repository(load_map=False)
            print(
                f"[FORECAST] Database backend: {type(repository.database).__name__}",
                flush=True,
            )
            print("[FORECAST] Loading election data...", flush=True)
            forecast_data = ForecastService(forecaster, repository).run_forecast(self.target_date)
            print(f"[FORECAST] Generated {len(forecast_data):,} forecast rows.", flush=True)
            forecasts_folder = Path(__file__).parent / "Forecasts"
            forecasts_folder.mkdir(parents=True, exist_ok=True)
            model_slug = re.sub(r"[^a-z0-9]+", "_", forecaster.model_name.lower()).strip("_") # pyright: ignore[reportAttributeAccessIssue]
            date_slug = re.sub(r"[^a-z0-9]+", "_", self.target_label.lower()).strip("_")
            csv_path = forecasts_folder / f"forecast_{date_slug}_{model_slug}.csv"
            forecaster.save_forecast_to_csv(csv_path) # pyright: ignore[reportArgumentType]
            print(f"[FORECAST] Saved CSV: {csv_path}", flush=True)
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
        self.main_window.set_reforecast_callback(self._reforecast)
        self.main_window.set_forecaster_label("Delta Model - Tomorrow")
        screen_widgets["Dashboard"].set_forecast_loading(True)
        screen_widgets["Forecast"].set_forecast_loading(True)
        self.main_window.set_reforecast_enabled(False)
        self._start_forecast_worker(
            screen_widgets["Dashboard"],
            screen_widgets["Forecast"],
            target_label="Tomorrow",
        )
        return self.app.exec()

    def _reforecast(self, model_name: str, target_date: str, target_label: str) -> None:
        dashboard = self.main_window.screens["Dashboard"] # type: ignore
        forecast = self.main_window.screens["Forecast"] # type: ignore
        dashboard.set_forecast_loading(True)
        forecast.set_forecast_loading(True)
        self.main_window.set_reforecast_enabled(False) # type: ignore
        self._start_forecast_worker(
            dashboard,
            forecast,
            compositional=model_name == "Softmax Model",
            target_date=target_date,
            target_label=target_label,
        )

    def _start_forecast_worker(
        self,
        dashboard: DashboardScreen,
        forecast: ForecastScreen,
        compositional=False,
        target_date="2026-09-21",
        target_label="Tomorrow",
    ) -> None:
        self.forecast_thread = QtCore.QThread()
        self.forecast_worker = ForecastWorker(
            compositional=compositional,
            target_date=target_date,
            target_label=target_label,
        )

        self.forecast_worker.moveToThread(self.forecast_thread)

        self.forecast_thread.started.connect(self.forecast_worker.run)
        self.forecast_worker.completed.connect(
            dashboard.set_forecaster,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self.forecast_worker.completed.connect(
            forecast.set_forecaster,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self.forecast_worker.completed.connect(
            lambda forecaster: self.main_window.set_forecaster_label( # type: ignore
                getattr(forecaster, "model_name", "Delta Model")
                + f" - {target_label}"
            ),
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self.forecast_worker.failed.connect(
            self._show_forecast_error,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )

        self.forecast_worker.finished.connect(self.forecast_thread.quit)
        self.forecast_thread.finished.connect(self.forecast_worker.deleteLater)
        self.forecast_thread.finished.connect(self.forecast_thread.deleteLater)
        self.forecast_thread.finished.connect(
            lambda: self.main_window.set_reforecast_enabled(True) # type: ignore
        )

        self.forecast_thread.start()

    def _show_forecast_error(self, message: str) -> None:
        self.main_window.screens["Dashboard"].set_forecast_loading(False) # type: ignore
        self.main_window.screens["Forecast"].set_forecast_loading(False) # type: ignore
        self.main_window.set_reforecast_enabled(True) # type: ignore
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