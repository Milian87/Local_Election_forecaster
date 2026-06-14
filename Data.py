import pandas as pd


class SampleData:
    def __init__(self):
        self.forecast = pd.DataFrame(
            [
                {"year": 2026, "council": "Sample Council", "ward": "North", "party": "Labour", "seats": 12},
                {"year": 2026, "council": "Sample Council", "ward": "North", "party": "Conservative", "seats": 10},
                {"year": 2026, "council": "Sample Council", "ward": "North", "party": "Liberal Democrats", "seats": 6},
                {"year": 2026, "council": "Sample Council", "ward": "North", "party": "Green Party", "seats": 4},
                {"year": 2026, "council": "Sample Council", "ward": "North", "party": "Reform UK", "seats": 8},
            ]
        )
        self.current_data = pd.DataFrame(
            [
                {"year": 2021, "council": "Sample Council", "ward": "North", "party": "Labour", "seats": 11},
                {"year": 2021, "council": "Sample Council", "ward": "North", "party": "Conservative", "seats": 11},
                {"year": 2021, "council": "Sample Council", "ward": "North", "party": "Liberal Democrats", "seats": 5},
                {"year": 2021, "council": "Sample Council", "ward": "North", "party": "Green Party", "seats": 3},
                {"year": 2021, "council": "Sample Council", "ward": "North", "party": "Reform UK", "seats": 9},
            ]
        )

    def get_summary(self):
        forecast_summary = self.forecast.groupby("party", as_index=False)["seats"].sum().rename(columns={"seats": "seats_forecast"})
        current_summary = self.current_data.groupby("party", as_index=False)["seats"].sum().rename(columns={"seats": "seats_current"})
        summary = forecast_summary.merge(current_summary, on="party", how="outer").fillna(0)
        summary["seat_difference"] = summary["seats_current"] - summary["seats_forecast"]
        return summary
