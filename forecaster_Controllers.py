# IRP Computer Program
# Using Machine Learning & Statistical Analysis to Predict UK Local Election Results
# Ian Milburn
# created: 21/05/2026
# File for the controllers of the GUIs of the IRP Computer Program
import pandas as pd


def _get_forecast_data(data_source) -> pd.DataFrame:
    forecast = data_source.forecast
    result = forecast() if callable(forecast) else forecast
    if not isinstance(result, pd.DataFrame):
        raise TypeError("Forecast data source must return a pandas DataFrame.")
    return result

class DashboardController:
    def __init__(self, data_source):
        self.data_source = data_source

    def get_summary(self) -> pd.DataFrame:
        return self.data_source.get_summary()

    def get_forecast_data(self) -> pd.DataFrame:
        return _get_forecast_data(self.data_source)

    def get_council_summaries(self) -> pd.DataFrame:
        return self.data_source.get_council_summaries()

    def verify_winners(self):
        return self.data_source.verify_winners_loop()
    
class ForecastController:
    def __init__(self, data_source):
        self.data_source = data_source

    def get_summary(self) -> pd.DataFrame:
        return self.data_source.get_summary()

    def get_forecast_data(self) -> pd.DataFrame:
        return _get_forecast_data(self.data_source)

    def verify_winners(self):
        return self.data_source.verify_winners_loop()
    
    def get_current_data(self):
        return self.data_source.current_data

class DataManagerController:
    def __init__(self, data_source):
        self.data_source = data_source

    def get_summary(self) -> pd.DataFrame:
        return self.data_source.get_summary()

    def get_forecast_data(self) -> pd.DataFrame:
        return _get_forecast_data(self.data_source)
    
    def get_current_data(self):
        return self.data_source.current_data
    
class ScreenFactory:
    def __init__(self):
        self.registry = {}

    def register(self, name, screen_cls):
        self.registry[name] = screen_cls

    def create(self, name, *args, **kwargs):
        return self.registry[name](*args, **kwargs)