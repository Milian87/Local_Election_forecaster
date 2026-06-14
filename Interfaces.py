# IRP Computer Program
# Using Machine Learning & Statistical Analysis to Predict UK Local Election Results
# Ian Milburn
# created: 21/05/2026
# File for the interface classes of the IRP Computer Program

from abc import ABC, abstractmethod
class ScreenInterface(ABC):
    @abstractmethod
    def __init__(self, parent_layout, controller, label_text, main_window=None):
        pass

    @abstractmethod
    def setup_ui(self):
        pass