import pandas as pd





class SampleData:
    def __init__(self):
        # These rows use a real ward code from ward_boundaries.geojson so the
        # Dashboard can display a working map before live forecast data is connected.
        self.forecast = pd.DataFrame(
            [
                {"year": 2026, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Labour", "party_label": "Labour", "seats": 12, "final_forecast_share": 45.2},
                {"year": 2026, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Conservative", "party_label": "Conservative", "seats": 10, "final_forecast_share": 35.5},
                {"year": 2026, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Liberal Democrats", "party_label": "Liberal Democrats", "seats": 6, "final_forecast_share": 12.0},
                {"year": 2026, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Green Party", "party_label": "Green Party", "seats": 4, "final_forecast_share": 5.3},
                {"year": 2026, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Reform UK", "party_label": "Reform UK", "seats": 8, "final_forecast_share": 2.0},
            ]
        )
        self.current_data = pd.DataFrame(
            [
                {"year": 2021, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Labour", "seats": 11},
                {"year": 2021, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Conservative", "seats": 11},
                {"year": 2021, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Liberal Democrats", "seats": 5},
                {"year": 2021, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Green Party", "seats": 3},
                {"year": 2021, "council": "Norfolk County Council", "ward": "Airfield", "wd_code": "E05012321", "cc_code": "E10000020", "party": "Reform UK", "seats": 9},
            ]
        )

    def get_summary(self):
        forecast_summary = self.forecast.groupby("party", as_index=False)["seats"].sum().rename(columns={"seats": "seats_forecast"})
        current_summary = self.current_data.groupby("party", as_index=False)["seats"].sum().rename(columns={"seats": "seats_current"})
        summary = forecast_summary.merge(current_summary, on="party", how="outer").fillna(0)
        summary["seat_difference"] = summary["seats_forecast"] - summary["seats_current"]
        return summary

    def get_council_summaries(self):
        summary = self.get_summary()
        largest_gain = summary.loc[summary["seat_difference"].idxmax()]
        return pd.DataFrame(
            [{
                "council": self.forecast["council"].iloc[0],
                "party": largest_gain["party"],
                "seats_gained": largest_gain["seat_difference"],
            }]
        )
