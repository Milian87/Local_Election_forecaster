# Election Forecaster
# By Ian Milburn
# This program forecasts the outcome of an election based on polling data and historical trends.
# It uses statistical models to predict the probability of each candidate winning,
# taking into account factors such as voter demographics, turnout rates, and recent polling results.
# Created: 26/8/2026

import os
import uuid
from pathlib import Path
import folium
import geopandas as gpd
import pandas as pd
import numpy as np
from PySide6 import QtCore
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

class BaseMapOrchestrator:
    def __init__(self, geojson_path=None):
        self.geojson_path = geojson_path
        self.gdf = None
        self.party_colors = {
            'Reform UK': '#00c3d9',
            'Liberal Democrats': '#FDBB30',
            'Green Party': '#00a85a',
            'Conservative': '#0087dc',
            'Labour': '#d50000',
            'Independent': "#F598E5",
            'Great Yarmouth First': '#000080',
            'Restore Britain': '#000080',
            'Default': '#bdbdbd'
        }

    def load_geodata(self):
        if self.geojson_path is None:
            raise ValueError("GeoJSON path is not set. Please provide a valid path to the GeoJSON file.")
        self.gdf = gpd.read_file(self.geojson_path)
        if self.gdf.crs is None:
            self.gdf = self.gdf.set_crs(epsg=4326)
        else:
            self.gdf = self.gdf.to_crs(epsg=4326)
        return self.gdf

    @staticmethod
    def _normalise_forecast(forecast_df):
        if forecast_df is None or forecast_df.empty:
            return pd.DataFrame(columns=["join_key", "winner", "share", "council_key"])

        required = {"party_label", "final_forecast_share"}
        missing = required.difference(forecast_df.columns)
        if missing:
            raise ValueError(f"Forecast data is missing required columns: {sorted(missing)}")

        join_column = next(
            (column for column in ("wd_code", "ward_code", "ward_name") if column in forecast_df.columns),
            None,
        )
        if join_column is None:
            raise ValueError("Forecast data needs wd_code, ward_code, or ward_name")

        council_column = next(
            (column for column in ("cc_code", "county_code", "council_code") if column in forecast_df.columns),
            None,
        )
        winner_indexes = forecast_df.groupby(join_column)["final_forecast_share"].idxmax()
        winners = forecast_df.loc[winner_indexes, [join_column, "party_label", "final_forecast_share"]]
        result = pd.DataFrame({
            "join_key": winners[join_column].astype(str).str.strip().str.upper(),
            "winner": winners["party_label"].astype(str),
            "share": pd.to_numeric(winners["final_forecast_share"], errors="coerce").fillna(0.0),
        })
        result["council_key"] = (
            forecast_df.loc[winner_indexes, council_column].astype(str).str.strip().str.upper()
            if council_column
            else ""
        )
        return result

    @staticmethod
    def _normalise_text(values):
        return (
            values.astype(str)
            .str.strip()
            .str.casefold()
            .str.replace(r"\s+(electoral\s+division|division|ed)$", "", regex=True)
            .str.replace(r"[^a-z0-9]", "", regex=True)
        )

    def _attach_forecast_winners(self, gdf, forecast_df, geography_columns):
        winners = self._normalise_forecast(forecast_df)
        gdf["winner"] = "Default"
        gdf["forecast_share"] = 0.0

        code_column = next((column for column in geography_columns if column in gdf.columns), None)
        name_column = next(
            (column for column in geography_columns if column in gdf.columns and column != code_column),
            None,
        )
        if code_column and not winners.empty:
            gdf["__join_key"] = gdf[code_column].astype(str).str.strip().str.upper()
            winners_by_code = winners.set_index("join_key")
            matched = gdf["__join_key"].isin(winners_by_code.index)
            gdf.loc[matched, "winner"] = gdf.loc[matched, "__join_key"].map(winners_by_code["winner"])
            gdf.loc[matched, "forecast_share"] = gdf.loc[matched, "__join_key"].map(winners_by_code["share"])

        if name_column and not winners.empty:
            unmatched = gdf["winner"].eq("Default")
            shape_names = self._normalise_text(gdf[name_column])
            winner_names = self._normalise_text(winners["join_key"])
            name_map = pd.Series(winners["winner"].to_numpy(), index=winner_names).groupby(level=0).first()
            share_map = pd.Series(winners["share"].to_numpy(), index=winner_names).groupby(level=0).first()
            gdf.loc[unmatched, "winner"] = shape_names[unmatched].map(name_map).fillna("Default")
            gdf.loc[unmatched, "forecast_share"] = shape_names[unmatched].map(share_map).fillna(0.0)

        return gdf

    def _get_party_color(self, party):
        return self.party_colors.get(party, self.party_colors["Default"])

    def _render_map(
        self,
        gdf_out,
        tooltip_fields,
        tooltip_aliases,
        fill_opacity=0.45,
        edge_weight=1.0,
        focus_geometry=None,
    ):
        m = folium.Map(location=[52.63, -1.5], zoom_start=6, tiles="OpenStreetMap")

        def style_function(feature):
            party = feature["properties"].get("winner", "Default")
            return {
                "fillColor": self._get_party_color(party),
                "color": "#3f3f3f",
                "weight": edge_weight,
                "fillOpacity": fill_opacity,
            }

        folium.GeoJson(
            gdf_out,
            style_function=style_function,
            highlight_function=lambda x: {"weight": 4, "color": "#000000", "fillOpacity": 0.8},
            tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases, localize=True),
        ).add_to(m)

        bounds_source = focus_geometry if focus_geometry is not None and not focus_geometry.empty else gdf_out
        if not bounds_source.empty and bounds_source.total_bounds is not None:
            minx, miny, maxx, maxy = bounds_source.total_bounds
            if np.isfinite([minx, miny, maxx, maxy]).all():
                m.fit_bounds([[miny, minx], [maxy, maxx]])

        html_path = os.path.abspath(os.path.join("data", "processed", f"live_map_{uuid.uuid4().hex}.html"))
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        m.save(html_path)

        view = QWebEngineView()
        view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        view.setUrl(QtCore.QUrl.fromLocalFile(html_path))
        return view

class CouncilMapOrchestrator(BaseMapOrchestrator):
    @staticmethod
    def _lookup_path() -> Path | None:
        root = Path(__file__).parent / "data"
        candidates = [
            root / "csv" / "Ward_to_LAD_to_County_to_County_Electoral_Division_(May_2026)_Lookup_for_England.csv",
            root / "csv" / "Ward_to_LAD_to_County_to_County_Electoral_Division_(May_2025)_Lookup_for_England.csv",
        ]
        return next((path for path in candidates if path.is_file()), None)

    def generate(self, forecast_df):
        gdf = self.load_geodata()
        division_code_column = next(
            (column for column in ("CED26CD", "CED25CD") if column in gdf.columns),
            None,
        )
        if division_code_column and not any(
            column in gdf.columns for column in ("CTY25NM", "LAD25NM", "CTY26NM", "LAD26NM")
        ):
            lookup_path = self._lookup_path()
            if lookup_path is not None:
                lookup = pd.read_csv(lookup_path, low_memory=False)
                code_column = "CED26CD" if "CED26CD" in lookup.columns else "CED25CD"
                use_columns = [column for column in (
                    code_column, "CTY26CD", "CTY26NM", "LAD26CD", "LAD26NM",
                    "CTY25CD", "CTY25NM", "LAD25CD", "LAD25NM"
                ) if column in lookup.columns]
                lookup = lookup[use_columns].drop_duplicates(code_column)
                gdf = gdf.merge(
                    lookup,
                    left_on=division_code_column,
                    right_on=code_column,
                    how="left",
                    suffixes=("", "_lookup"),
                )
        gdf = self._attach_forecast_winners(
            gdf,
            forecast_df,
            ("WD26CD", "WD26NM", "WD25CD", "WD25NM", "CED25CD", "CED25NM"),
        )
        county_name_column = next(
            (column for column in ("CTY26NM", "CTY25NM") if column in gdf.columns),
            None,
        )
        unitary_name_column = next(
            (column for column in ("LAD26NM", "LAD25NM") if column in gdf.columns),
            None,
        )
        if county_name_column is None and unitary_name_column is None:
            return self._render_map(
                gdf,
                tooltip_fields=[division_code_column, "winner", "forecast_share"],
                tooltip_aliases=["Division:", "Projected Winner:", "Vote Share:"],
                fill_opacity=0.45,
                edge_weight=1.0,
            )

        gdf["__council_name"] = (
            gdf[county_name_column].replace("", pd.NA).fillna(gdf[unitary_name_column])
            if county_name_column and unitary_name_column
            else gdf[county_name_column or unitary_name_column]
        )
        council_column = "__council_name"

        winner_by_council = gdf.groupby(council_column)["winner"].agg(
            lambda values: values[values != "Default"].mode().iat[0]
            if not values[values != "Default"].empty
            else "Default"
        )
        share_by_council = gdf.groupby(council_column)["forecast_share"].mean()
        gdf_out = gdf.dissolve(by=council_column, as_index=False)
        gdf_out["winner"] = gdf_out[council_column].map(winner_by_council).fillna("Default")
        gdf_out["forecast_share"] = gdf_out[council_column].map(share_by_council).fillna(0.0)

        return self._render_map(
            gdf_out,
            tooltip_fields=[council_column, "winner", "forecast_share"],
            tooltip_aliases=["Council:", "Projected Winner:", "Average Vote Share:"],
            fill_opacity=0.60,
            edge_weight=2.5,
        )

class WardMapOrchestrator(BaseMapOrchestrator):
    def generate(self, forecast_df, focus_division=None, focus_council=None):
        gdf = self.load_geodata()
        gdf = self._attach_forecast_winners(
            gdf,
            forecast_df,
            ("WD26CD", "WD26NM", "WD25CD", "WD25NM", "CED25CD", "CED25NM"),
        )
        ward_name_column = next(
            (column for column in ("WD26NM", "WD25NM", "CED25NM", "NAME") if column in gdf.columns),
            None,
        )
        if ward_name_column is None:
            raise ValueError("Ward map data needs a WD25NM, CED25NM, or NAME column")

        focus_geometry = None
        if focus_division:
            division_code = str(focus_division).strip().upper()
            division_columns = [
                column for column in ("WD26CD", "WD25CD", "CED25CD") if column in gdf.columns
            ]
            focus_geometry = gdf[
                gdf[division_columns].astype(str).apply(
                    lambda values: values.str.strip().str.upper().eq(division_code).any(),
                    axis=1,
                )
            ] if division_columns else gdf.iloc[0:0]
        elif focus_council:
            council_columns = [
                column for column in ("CTY25NM", "CTY26NM", "LAD25NM", "LAD26NM")
                if column in gdf.columns
            ]
            target_council = self._normalise_text(pd.Series([focus_council])).iloc[0]
            focus_geometry = gdf[
                gdf[council_columns].apply(
                    lambda values: self._normalise_text(values).eq(target_council).any(),
                    axis=1,
                )
            ] if council_columns else gdf.iloc[0:0]

        return self._render_map(
            gdf,
            tooltip_fields=[ward_name_column, "winner", "forecast_share"],
            tooltip_aliases=["Ward:", "Projected Winner:", "Vote Share:"],
            fill_opacity=0.45,
            edge_weight=1.0,
            focus_geometry=focus_geometry,
        )