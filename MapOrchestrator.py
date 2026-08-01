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

class MapOrchestrator:
    def __init__(self, target_geojson_path: str):
        self.base_path = target_geojson_path
        self.gdf = gpd.read_file(self.base_path)
        if self.gdf.crs is not None:
            self.gdf = self.gdf.to_crs(epsg=4326)
        self.gdf = self._apply_local_2026_overrides(self.gdf)
        # Define high-contrast hexagonal color codes for the 2026 seat map viewports
        self.party_colors = {
            'Reform UK': '#00c3d9',
            'Liberal Democrats': '#FDBB30',
            'Green Party': '#00a85a',
            'Conservative': '#0087dc',
            'Labour': '#d50000',
            'Independent': "#F598E5",
            'Great Yarmouth First': '#000080',
            'Default': '#bdbdbd'
        }

    def _get_party_color(self, party_label):
        return self.party_colors.get(party_label, self.party_colors['Default'])

    def _discover_local_2026_override_shapefiles(self):
        base_path = Path(self.base_path).resolve()
        data_root = next((p for p in [base_path.parent] + list(base_path.parents) if p.name.lower() == 'data'), None)
        if data_root is None:
            return []

        local_root = data_root / '2026 Boundaries'
        if not local_root.is_dir():
            return []

        candidates_by_stem = {}
        for shp in local_root.rglob('*.shp'):
            name = shp.name.lower()
            if '_pw_' in name:
                continue
            if any(tok in name for tok in ['proposal', 'final', '_f_ed_', '_ed_polys', 'electoral_division']):
                stem = shp.stem.lower()
                existing = candidates_by_stem.get(stem)
                # Prefer shallower paths (top-level file copies) when duplicates exist.
                if existing is None or len(shp.parts) < len(existing.parts):
                    candidates_by_stem[stem] = shp
        return sorted(candidates_by_stem.values())

    def _normalize_override_layer(self, override_gdf: gpd.GeoDataFrame, source_name: str) -> gpd.GeoDataFrame:
        normalized = override_gdf.copy()
        source_lower = source_name.lower()

        if 'norfolk' in source_lower:
            council_hint = 'norfolk'
        elif 'essex' in source_lower:
            council_hint = 'essex'
        elif 'shropshire' in source_lower:
            council_hint = 'shropshire'
        elif 'suffolk' in source_lower:
            council_hint = 'suffolk'
        else:
            council_hint = 'unknown'

        normalized['__source_override'] = source_name
        normalized['__source_council_hint'] = council_hint

        name_candidates = [
            'CED26NM', 'CED25NM', 'WD26NM', 'WD25NM', 'Division_n',
            'Divison_na', 'WardName', 'Ward_name', 'Name'
        ]
        name_col = next((c for c in name_candidates if c in normalized.columns), None)
        if name_col is not None:
            normalized['CED25NM'] = normalized[name_col].astype(str)
        elif 'CED25NM' not in normalized.columns:
            normalized['CED25NM'] = [f"{source_name} Division {i + 1}" for i in range(len(normalized))]

        code_candidates = ['CED26CD', 'CED25CD', 'WD26CD', 'WD25CD', 'NCC_CODE']
        code_col = next((c for c in code_candidates if c in normalized.columns), None)
        if code_col is not None:
            normalized['CED25CD'] = normalized[code_col].astype(str)
        elif 'CED25CD' not in normalized.columns:
            normalized['CED25CD'] = [f"OVR-{source_name.upper()}-{i + 1:04d}" for i in range(len(normalized))]

        return normalized

    def _apply_local_2026_overrides(self, base_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        override_files = self._discover_local_2026_override_shapefiles()
        if not override_files:
            return base_gdf

        merged = base_gdf.copy()
        total_replaced = 0
        total_added = 0

        for shp_path in override_files:
            try:
                override = gpd.read_file(shp_path)
                if override.empty:
                    continue
                if override.crs is not None:
                    override = override.to_crs(merged.crs)

                source_name = shp_path.stem
                override = self._normalize_override_layer(override, source_name)

                merged_metric = merged if merged.crs and merged.crs.to_epsg() == 27700 else merged.to_crs(epsg=27700)
                override_metric = override if override.crs and override.crs.to_epsg() == 27700 else override.to_crs(epsg=27700)
                coverage_union = override_metric.geometry.union_all()

                if coverage_union is not None and not coverage_union.is_empty:
                    replace_mask = merged_metric.geometry.centroid.within(coverage_union)
                    replaced_count = int(replace_mask.sum())
                else:
                    replace_mask = pd.Series(False, index=merged.index)
                    replaced_count = 0

                merged = merged.loc[~replace_mask].copy()
                merged = pd.concat([merged, override], ignore_index=True)

                total_replaced += replaced_count
                total_added += len(override)
                print(f"[MAP ENGINE] Applied local 2026/proposed override: {shp_path.name} (replaced {replaced_count}, added {len(override)})")
            except Exception as exc:
                print(f"[MAP ENGINE] Skipped override {shp_path.name}: {exc}")

        if total_added:
            print(f"[MAP ENGINE] Local 2026 overlay summary: replaced {total_replaced} base divisions, added {total_added} override divisions.")

        return merged

    def generate_live_viewport(self, forecast_df: pd.DataFrame, view_mode: str = "ward") -> QWebEngineView:
        if forecast_df is None or forecast_df.empty:
            view = QWebEngineView()
            view.setHtml("<h3 style='font-family: sans-serif; padding: 16px;'>No forecast data available.</h3>")
            return view

        # 1. Clean data replication
        gdf = self.gdf.copy()
        
        # 🔍 DYNAMIC COLUMN LOOKUP
        gdf_cols = gdf.columns.tolist()
        gdf_join_col = next((c for c in gdf_cols if c.upper() in ['CED26CD', 'CED25CD', 'CED24CD', 'WD25CD', 'WD26CD', 'WD_CODE', 'GSS_CODE', 'ID']), None)
        gdf_name_col = next((c for c in gdf_cols if c.upper() in ['CED26NM', 'CED25NM', 'CED24NM', 'WD25NM', 'WD26NM', 'WARD_NAME', 'NAME', 'DIVISION']), gdf_cols[0])

        df_cols = forecast_df.columns.tolist()
        df_join_col = next((c for c in df_cols if c in ['wd_code', 'ward_code']), 'wd_code')
        df_party_col = next((c for c in df_cols if c in ['party_label', 'party_name']), 'party_label')
        df_share_col = next((c for c in df_cols if c in ['final_forecast_share', 'predicted_party_share']), 'final_forecast_share')
        df_council_col = next((c for c in df_cols if c in ['cc_code', 'county_code']), 'cc_code')
        df_name_col = next((c for c in df_cols if c in ['ward_name', 'division_name', 'name']), None)

        # 2. Extract and Prepare winner matrix
        idx_winners = forecast_df.groupby(df_join_col)[df_share_col].idxmax()
        winners_cols = [df_join_col, df_party_col, df_share_col, df_council_col]
        if df_name_col:
            winners_cols.append(df_name_col)
        winners_df = forecast_df.loc[idx_winners, winners_cols].copy()

        # Prefer code-level joins where possible for complete national coverage.
        winners_df['__join_code'] = winners_df[df_join_col].astype(str).str.strip().str.upper()
        if gdf_join_col:
            gdf['__join_code'] = gdf[gdf_join_col].astype(str).str.strip().str.upper()
            gdf = gdf.merge(
                winners_df[['__join_code', df_party_col, df_share_col, df_council_col]],
                on='__join_code',
                how='left'
            )

        total_shapes = len(gdf)
        code_matched = int(gdf[df_party_col].notna().sum()) if df_party_col in gdf.columns else 0
        text_matched = code_matched
        fuzzy_matched = code_matched

        # Text alignment fallback, using explicit ward names when available.
        if df_name_col:
            winners_df['__clean_name'] = winners_df[df_name_col].fillna(winners_df[df_join_col].astype(str))
        else:
            winners_df['__clean_name'] = winners_df[df_join_col].astype(str)

        def normalize_string(series):
            return (series.astype(str).str.strip().str.lower()
                    .str.replace(r'\s+(electoral\s+division|division|ed)$', '', regex=True)
                    .str.replace(r'&', ' and ', regex=True)
                    .str.replace(r'[^a-z0-9]', '', regex=True))

        gdf['__shape_join_key'] = normalize_string(gdf[gdf_name_col])
        winners_df['__text_join_key'] = normalize_string(winners_df['__clean_name'])

        # 3. Fallback text merge for any unmatched shapes after code join
        fallback_df = winners_df[[df_party_col, df_share_col, df_council_col, '__text_join_key']].copy()
        key_counts = fallback_df['__text_join_key'].value_counts()
        unique_keys = set(key_counts[key_counts == 1].index)
        ambiguous_keys = set(key_counts[key_counts > 1].index)
        fallback_unique = fallback_df[fallback_df['__text_join_key'].isin(unique_keys)].copy()
        fallback_map = fallback_unique.set_index('__text_join_key')

        unmatched_mask = gdf[df_party_col].isna()
        if unmatched_mask.any():
            for idx, row in gdf[unmatched_mask].iterrows():
                key = row['__shape_join_key']
                if key in fallback_map.index:
                    gdf.loc[idx, df_party_col] = fallback_map.at[key, df_party_col]
                    gdf.loc[idx, df_share_col] = fallback_map.at[key, df_share_col]
                    gdf.loc[idx, df_council_col] = fallback_map.at[key, df_council_col]
        text_matched = int(gdf[df_party_col].notna().sum()) if df_party_col in gdf.columns else code_matched

        # 🎯 MANUAL OVERRIDE DICTIONARY (Fixes stubborn Norfolk Proposal names)
        # Format: "shapefile_normalized_key": "database_normalized_key"
        exception_map = {
            "draytonandhorsford": "drayton & horsford",
            "narandwisseyvalleys": "nar & wissey valley",
            "watlingtonandthefens": "watlington & the fens",
            "launditch": "launditch division",
            "fakenhamandtheraynhams": "fakenham & the raynhams",

            # Add any other strings that show up as 'Default' in your map
        }
        
        # Apply manual overrides for non-matching keys
        for shape_key, db_key in exception_map.items():
            if shape_key in gdf['__shape_join_key'].values:
                # Find matching row in winners_df for the database key
                model_match = winners_df[winners_df['__text_join_key'] == normalize_string(pd.Series([db_key])).iloc[0]]
                if not model_match.empty:
                    idx = gdf[gdf['__shape_join_key'] == shape_key].index
                    gdf.loc[idx, df_party_col] = str(model_match.iloc[0][df_party_col])
                    gdf.loc[idx, df_share_col] = float(model_match.iloc[0][df_share_col])
                    gdf.loc[idx, df_council_col] = str(model_match.iloc[0][df_council_col])

        # 🔍 FUZZY FALLBACK (Now assignment-safe)
        unmatched_mask = gdf[df_party_col].isna()
        if unmatched_mask.any() and not winners_df.empty:
            import difflib

            # Build hint->cc_code mapping from already matched rows in overrides.
            hint_to_cc = {}
            if '__source_council_hint' in gdf.columns and df_council_col in gdf.columns:
                matched_hint = gdf[gdf[df_council_col].notna()].copy()
                matched_hint = matched_hint[matched_hint['__source_council_hint'] != 'unknown']
                if not matched_hint.empty:
                    hint_mode = (
                        matched_hint.groupby('__source_council_hint')[df_council_col]
                        .agg(lambda s: s.value_counts().index[0])
                    )
                    hint_to_cc = hint_mode.to_dict()

            # Build council-region footprints from matched geometry to spatially infer council context.
            cc_regions = None
            if df_council_col in gdf.columns and gdf[df_council_col].notna().any():
                cc_regions = gdf[gdf[df_council_col].notna()].dissolve(by=df_council_col)[['geometry']]

            generic_tokens = {'valley', 'valleys', 'north', 'south', 'east', 'west', 'central'}
            
            for idx, row in gdf[unmatched_mask].iterrows():
                shape_key = row['__shape_join_key']

                target_cc = None
                if '__source_council_hint' in gdf.columns:
                    hint = row.get('__source_council_hint', 'unknown')
                    target_cc = hint_to_cc.get(hint)

                if target_cc is None and cc_regions is not None and not cc_regions.empty:
                    point = row.geometry.representative_point()
                    containing = cc_regions[cc_regions.geometry.contains(point)]
                    if not containing.empty:
                        target_cc = containing.index[0]

                if target_cc is not None:
                    scoped_df = winners_df[winners_df[df_council_col] == target_cc]
                else:
                    scoped_df = winners_df

                scoped_keys = scoped_df['__text_join_key'].value_counts()
                scoped_unique_keys = set(scoped_keys[scoped_keys == 1].index) & unique_keys
                if not scoped_unique_keys:
                    continue

                available_db_keys = sorted(scoped_unique_keys)
                # Skip low-information names that commonly collide across councils.
                token_count = sum(token in shape_key for token in generic_tokens)
                cutoff = 0.93 if token_count > 0 else 0.88
                matches = difflib.get_close_matches(shape_key, available_db_keys, n=1, cutoff=cutoff)
                if matches:
                    model_row = fallback_map.loc[matches[0]]
                    gdf.loc[idx, df_party_col] = str(model_row[df_party_col])
                    gdf.loc[idx, df_share_col] = float(model_row[df_share_col])
                    gdf.loc[idx, df_council_col] = str(model_row[df_council_col])
        fuzzy_matched = int(gdf[df_party_col].notna().sum()) if df_party_col in gdf.columns else text_matched

        if df_party_col not in gdf.columns:
            gdf[df_party_col] = 'Default'
        if df_share_col not in gdf.columns:
            gdf[df_share_col] = 0.0
        gdf[df_party_col] = gdf[df_party_col].fillna('Default')
        gdf[df_share_col] = pd.to_numeric(gdf[df_share_col], errors='coerce').fillna(0.0)

        print(
            f"[MAP ENGINE] Match coverage: code={code_matched}/{total_shapes}, "
            f"text={text_matched}/{total_shapes}, fuzzy={fuzzy_matched}/{total_shapes}, "
            f"ambiguous_name_keys={len(ambiguous_keys)}"
        )

        # Initialize baseline map (auto-fit to all available boundaries).
        m = folium.Map(location=[52.63, -1.5], zoom_start=6, tiles="OpenStreetMap")

        if view_mode == "council":
            # 🏢 DASHBOARD VIEW: Dissolve ward boundaries into higher-tier council shapes
            dissolve_gdf = gdf.dropna(subset=[df_council_col]).copy()
            if not dissolve_gdf.empty:
                gdf_out = dissolve_gdf.dissolve(by=df_council_col, aggfunc={
                    df_party_col: lambda x: x.value_counts().index[0] if not x.empty else 'Default',
                    df_share_col: 'mean'
                }).reset_index()
                tooltip_fields = [df_party_col]
                tooltip_aliases = ['Dominant Party:']
                fill_opacity = 0.60
                edge_weight = 2.5
            else:
                gdf_out = gdf
                tooltip_fields = [gdf_name_col, df_party_col]
                tooltip_aliases = ['Division:', 'Projected Winner:']
                fill_opacity = 0.45
                edge_weight = 1.0
        else:
            # 🔮 FORECASTS UI VIEW: Maintain fine-grained ward-level geometries
            gdf_out = gdf
            tooltip_fields = [gdf_name_col, df_party_col, df_share_col]
            tooltip_aliases = ['Division:', 'Projected Winner:', 'Vote Share (%):']
            fill_opacity = 0.45
            edge_weight = 1.0

        # Apply custom coloring map function based on localized structural winners
        def style_function(feature):
            party = feature['properties'].get(df_party_col, 'Default')
            return {
                'fillColor': self._get_party_color(party),
                'color': '#3f3f3f',
                'weight': edge_weight,
                'fillOpacity': fill_opacity
            }

        folium.GeoJson(
            gdf_out,
            style_function=style_function,
            highlight_function=lambda x: {'weight': 4, 'color': '#000000', 'fillOpacity': 0.8},
            tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases, localize=True)
        ).add_to(m)

        if not gdf_out.empty and gdf_out.total_bounds is not None:
            minx, miny, maxx, maxy = gdf_out.total_bounds
            if np.isfinite([minx, miny, maxx, maxy]).all():
                m.fit_bounds([[miny, minx], [maxy, maxx]])

        # 4. Render output to a unique instance workspace temp file cache
        html_map_path = os.path.abspath(os.path.join("data", "processed", f"live_map_{uuid.uuid4().hex}.html"))
        os.makedirs(os.path.dirname(html_map_path), exist_ok=True)
        m.save(html_map_path)

        # 5. Package components directly back into the PySide6 Web View template wrapper
        view = QWebEngineView()
        view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        view.setUrl(QtCore.QUrl.fromLocalFile(html_map_path))
        return view