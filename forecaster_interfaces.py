# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026
# This file contains the interface definitions for the data uploader, machine learning model, and database connection.

from abc import ABC, abstractmethod
import pandas as pd

class Data_Uploader_Interface(ABC):
    @abstractmethod
    def __init__(self, data_source):
        pass

    @abstractmethod
    def read_data(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def preprocess_data(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def send_data(self) -> pd.DataFrame:
        pass

class MachineLearningInterface(ABC):
    @abstractmethod
    def __init__(self, model_type):
        pass

    @abstractmethod
    def train_model(self, training_data):
        pass

    @abstractmethod
    def evaluate_model(self, test_data):
        pass

    @abstractmethod
    def predict(self, input_data):
        pass

class iDatabaseInterface(ABC):
    @abstractmethod
    def __init__(self, connection_string):
        pass

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def fetch_dataframe(self, query: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def execute_many(self, statement: str, parameters: list[dict]) -> None:
        pass