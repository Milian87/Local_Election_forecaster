# IRP Computer Program
# Using Machine Learning & Statistical Analysis to Predict UK Local Election Results
# Ian Milburn
# created: 21/05/2026
# File for the controllers of the GUIs of the IRP Computer Program

class DashboardController:
    def __init__(self, data_source):
        self.data_source = data_source

    def get_summary(self):
        return self.data_source.get_summary()

    def get_forecast_data(self):
        return self.data_source.forecast
    
class ForecastController:
    def __init__(self, data_source):
        self.data_source = data_source

    def get_forecast_data(self):
        return self.data_source.forecast
    
    def get_current_data(self):
        return self.data_source.current_data

class DataManagerController:
    def __init__(self, data_source):
        self.data_source = data_source

    def get_forecast_data(self):
        return self.data_source.forecast
    
    def get_current_data(self):
        return self.data_source.current_data
    
class ScreenFactory:
    def __init__(self):
        self.registry = {}

    def register(self, name, screen_cls):
        self.registry[name] = screen_cls

    def create(self, name, *args, **kwargs):
        return self.registry[name](*args, **kwargs)