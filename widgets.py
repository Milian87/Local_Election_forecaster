#Finance Tracker Version 3
# hand Coded version of the finance tracker, with a dashboard GUI and data visualization features.
# classes for GUI widgets and data management, using PySide6 for the GUI and Matplotlib for data visualization.
import PySide6.QtWidgets as QtWidgets
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtGui import QColor
import folium
import geopandas as gpd
import pandas as pd
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
import os
import uuid
from PySide6 import QtCore

blue_button_style = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #7ab2e2, stop:1 #3a6faa);
        color: white;
        border-radius: 16px;
        padding: 8px 6px;
        font-size: 12px;
        font-weight: bold;
        border: 1px solid #2d5a90;
        }
        QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #90c0f0, stop:1 #4a80bc);
        }
        QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a6faa, stop:1 #7ab2e2);
        }
        """
active_blue_button_style = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4a80bc, stop:1 #2d5a90);
        color: white;
        border-radius: 16px;
        padding: 8px 6px;
        font-size: 12px;
        font-weight: bold;
        border: 2px solid #1a3a5a;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #90c0f0, stop:1 #4a80bc);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a6faa, stop:1 #7ab2e2);
    }
    """
green_button_style = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #81c784, stop:1 #388e3c);  /* light green to deep green */
        color: white;
        border-radius: 16px;
        padding: 8px 6px;
        font-size: 12px;
        font-weight: bold;
        border: 1.5px solid #2e7d32;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #a5d6a7, stop:1 #43a047);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #388e3c, stop:1 #81c784);
    }
    """
red_button_style = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e57373, stop:1 #b71c1c);  /* light red to deep red */
        color: white;
        border-radius: 16px;
        padding: 8px 6px;
        font-size: 12px;
        font-weight: bold;
        border: 1.5px solid #7f1d1d;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ef9a9a, stop:1 #c62828);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #b71c1c, stop:1 #e57373);
    }
    """

class ButtonWidget:
    """
    Reusable component for creating styled buttons with callbacks.
    Supports custom styling and flexible positioning.
    """
    def __init__(self, parent_layout, text, callback=None, button_style="", tooltip=""):
        # Create the button
        self.button = QtWidgets.QPushButton(text)
        
        # Set custom style if provided
        if button_style:
            self.button.setStyleSheet(button_style)

        shadow = QGraphicsDropShadowEffect()
        self.button.setMinimumHeight(40)  # ensure minimum height for round ends
        self.button.setMaximumHeight(40)  # fix height for consistent roundness
        self.button.setMinimumWidth(100)  # ensure wide pill shape
        self.button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)  # ADDED: allow horizontal expansion for pill shape
        # REMOVED setMaximumWidth for flexibility
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.button.setGraphicsEffect(shadow)
        
        # Set tooltip if provided
        if tooltip:
            self.button.setToolTip(tooltip)
        
        # Connect callback if provided
        if callback:
            self.button.clicked.connect(callback)
        
        # Add to parent layout
        if parent_layout:
            parent_layout.addWidget(self.button)
    
    def connect(self, callback):
        """Connect or reconnect the button to a callback function"""
        self.button.clicked.connect(callback)
    
    def disconnect(self):
        """Disconnect all signals from the button"""
        self.button.clicked.disconnect()
    
    def set_text(self, text):
        """Update the button text"""
        self.button.setText(text)
    
    def set_enabled(self, enabled):
        """Enable or disable the button"""
        self.button.setEnabled(enabled)
    
    def set_style(self, style):
        """Update the button style"""
        self.button.setStyleSheet(style)
    
    def set_tooltip(self, tooltip):
        """Update the button tooltip"""
        self.button.setToolTip(tooltip)

class FormRow(QtWidgets.QWidget):
    """
    A reusable widget for one or more rows of form inputs (label + input).
    Accepts a list of fields (for one row) or a list of lists of fields (for multiple rows).
    """
    def __init__(self, fields, parent=None):
        super().__init__(parent)
        self.inputs = {}  # Store references to input widgets for later access
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)  # Add spacing between rows
        layout.setContentsMargins(0, 0, 0, 0)
        # If fields is a list of lists, treat each as a row
        if fields and isinstance(fields[0], list):
            for row in fields:
                row_layout = QtWidgets.QHBoxLayout()
                row_layout.setSpacing(0)
                row_layout.setContentsMargins(0, 0, 0, 0)
                for key, label_text, widget_class, options in row:
                    box = QtWidgets.QFrame()
                    box.setStyleSheet("background-color: transparent; border: none;")
                    box_layout = QtWidgets.QHBoxLayout(box)
                    box_layout.setSpacing(0)
                    box_layout.setContentsMargins(0, 0, 0, 0)
                    label = QtWidgets.QLabel(label_text)
                    input_widget = widget_class()
                    input_widget.setMinimumWidth(40)  # Ensure minimum width for better appearance
                    input_widget.setMaximumHeight(40)  # Match button height for consistency
                    self.inputs[key] = input_widget
                    input_widget.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 4px; padding: 4px;")
                    if isinstance(input_widget, QtWidgets.QComboBox) and "items" in options:
                        input_widget.addItems(options["items"])
                    if isinstance(input_widget, QtWidgets.QLineEdit) and "placeholder" in options:
                        input_widget.setPlaceholderText(options["placeholder"])

                    box_layout.addWidget(label)
                    box_layout.addWidget(input_widget)
                    row_layout.addWidget(box)
                layout.addLayout(row_layout)
        else:
            # Single row (original behavior)
            row_layout = QtWidgets.QHBoxLayout()
            row_layout.setSpacing(0)  # or 0 for even tighter
            row_layout.setContentsMargins(0, 0, 0, 0)
            for label_text, widget_class, options in fields:
                box = QtWidgets.QFrame()
                box.setStyleSheet("background-color: transparent; border: none;")
                box_layout = QtWidgets.QHBoxLayout(box)
                box_layout.setSpacing(0)
                box_layout.setContentsMargins(0, 0, 0, 0)
                label = QtWidgets.QLabel(options.get("label", ""))
                input_widget = widget_class()
                input_widget.setMinimumWidth(40)  # Ensure minimum width for better appearance
                input_widget.setMaximumHeight(40)  # Match button height for consistency
                self.inputs[label_text] = input_widget  # Store reference to input widget
                input_widget.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 4px; padding: 4px;")
                if isinstance(input_widget, QtWidgets.QComboBox) and "items" in options:
                    input_widget.addItems(options["items"])
                if isinstance(input_widget, QtWidgets.QLineEdit) and "placeholder" in options:
                    input_widget.setPlaceholderText(options["placeholder"])
                box_layout.addWidget(label)
                box_layout.addWidget(input_widget)
                row_layout.addWidget(box)
            layout.addLayout(row_layout)
        # add a stretch at the end of the layout to push the rows to the top

class TransactionEntryWidget(QtWidgets.QWidget):
    """A widget to display a single transaction entry, showing type, category, amount, account, and date."""
    def __init__(self, transaction_data, parent=None):
        HISTORY_HEADERS = ["Date", "Account", "Type", "Category", "Amount", "Running Balance", "Description"]
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Example: show type, category, amount, account, date
        layout.addWidget(QtWidgets.QLabel(transaction_data.get("type", "")))
        layout.addWidget(QtWidgets.QLabel(transaction_data.get("category", "")))
        layout.addWidget(QtWidgets.QLabel(f"£{transaction_data.get('amount', 0):.2f}"))
        layout.addWidget(QtWidgets.QLabel(transaction_data.get("account", "")))
        layout.addWidget(QtWidgets.QLabel(transaction_data.get("date", "")))

class HistoryTableWidget(QtWidgets.QTableWidget):
    def __init__(self, headers=None, parent=None):
        super().__init__(parent)# add a card to display the transaction history
        if headers is None:
            headers = ["Date", "Account", "Type", "Category", "Amount", "Running Balance", "Description"]
        history_card = QtWidgets.QFrame()
        history_card.setStyleSheet("background-color: #ffffff; border-radius: 10px; padding: 10px;")
        history_layout = QtWidgets.QVBoxLayout(history_card)
        history_label = QtWidgets.QLabel("Transaction History")
        history_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        history_layout.addWidget(history_label)
        self.history_table = QtWidgets.QTableWidget()
        self.history_table.setColumnCount(len(headers))
        self.history_table.setHorizontalHeaderLabels(headers)
        header = self.history_table.horizontalHeader()
        header.setVisible(True)
        header.setStyleSheet(
            "QHeaderView::section {"
            "color: #222;"
            "background: #f5f5f5;"
            "font-size: 12px;"
            "font-weight: normal;"
            "padding: 5px 0px;"
            "border: 1px solid #ddd;"
            "}"
        )
        header.setFixedHeight(50)
        self.history_table.setStyleSheet("QTableWidget::item { color: black; }")
        for col in range(len(headers)):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
        self.history_table.show()
        self.history_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # add the history table to the history card
        history_layout.addWidget(self.history_table)

class Map:
    def __init__(self, map_frame):
        self.map_frame = map_frame
        self.web_map_view = None  # This will hold the QWebEngineView instance

    def create_map(self, ward_shp_path=None, oa_shp_path=None, forecast_df=None):
        # 1. Create the Folium Map Object (Centered on England with a moderate zoom level)
        # You can style this using standard OpenStreetMap tiles
        m = folium.Map(location=[52.75, 0.40], zoom_start=10, tiles="OpenStreetMap")
        gdf_wards = gpd.GeoDataFrame()

        # 2. Add Wards / County Divisions Layer if provided
        if ward_shp_path and os.path.exists(ward_shp_path):
            print(f"[MAP ENGINE] Processing Ward Boundary File: {os.path.basename(ward_shp_path)}")
            # Read vector boundary file (GeoJSON/SHP/etc.) and normalize to WGS84 for Folium.
            gdf_wards = gpd.read_file(ward_shp_path)
            gdf_wards = gdf_wards[gdf_wards.geometry.notna()].copy()
            if gdf_wards.crs is not None:
                gdf_wards = gdf_wards.to_crs(epsg=4326)
            else:
                print("[MAP ENGINE] WARNING: Ward CRS missing; treating as EPSG:4326.")

            # ---- OPTIMIZATION FILTER ----
            # Checks if ONS columns exist, filtering boundaries down to local council area
            # This shaves your map data processing down from 7,000+ national entries to just your local region!
            if 'LAD25NM' in gdf_wards.columns:
                gdf_wards = gdf_wards[gdf_wards['LAD25NM'] == "King's Lynn and West Norfolk"]
                print("Checked for LAD25NM column")
            elif 'LAD24NM' in gdf_wards.columns:
                gdf_wards = gdf_wards[gdf_wards['LAD24NM'] == "King's Lynn and West Norfolk"]
                print("Checked for LAD24NM column")
            elif 'LAD23NM' in gdf_wards.columns:
                gdf_wards = gdf_wards[gdf_wards['LAD23NM'] == "King's Lynn and West Norfolk"]
                print("Checked for LAD23NM column")
            # -----------------------------
            print(f"[MAP ENGINE] Loaded {len(gdf_wards):,} ward boundaries for mapping.")
            print("Sample ward names in the dataset:\n", gdf_wards['WD25NM'].unique()[:16])

            if gdf_wards.empty:
                print("[MAP ENGINE] WARNING: No valid ward geometries found. Skipping ward layer.")
            else:
                # Inject interactive boundaries with tooltips
                tooltip_field = None
                for candidate in ['WD25NM', 'WD24NM', 'WD23NM']:
                    if candidate in gdf_wards.columns:
                        tooltip_field = candidate
                        break
                if tooltip_field is None and len(gdf_wards.columns) > 1:
                    tooltip_field = gdf_wards.columns[1]
            
                party_colors = {
                    "Conservative": "#1f4e79",
                    "Labour": "#d7191c",
                    "Liberal Democrats": "#fdbf11",
                    "Green Party": "#33a02c",
                    "Reform UK": "#00b7eb",
                }
                winner_by_ward = {}

                if isinstance(forecast_df, pd.DataFrame) and not forecast_df.empty:
                    required_cols = {"ward", "party", "seats"}
                    if required_cols.issubset(set(forecast_df.columns)):
                        winners = forecast_df[["ward", "party", "seats"]].copy()
                        winners["seats"] = pd.to_numeric(winners["seats"], errors="coerce").fillna(0)
                        winners = winners.sort_values("seats", ascending=False).drop_duplicates("ward")
                        winner_by_ward = dict(zip(winners["ward"], winners["party"]))

                gdf_wards["winning_party"] = gdf_wards[tooltip_field].map(winner_by_ward).fillna("No data")

                def style_fn(feature):
                    props = feature.get("properties", {})
                    ward_name = props.get(tooltip_field)
                    winner = winner_by_ward.get(ward_name)
                    return {
                        'fillColor': party_colors.get(winner, '#9e9e9e'),
                        'color': '#1f1f1f',
                        'weight': 1.8,
                        'opacity': 1.0,
                        'fillOpacity': 0.45
                    }

                geojson_kwargs = {
                    "name": "Electoral Wards",
                    "style_function": style_fn,
                    "highlight_function": lambda x: {
                        'weight': 3,
                        'color': '#000000',
                        'opacity': 1.0,
                        'fillOpacity': 0.65,
                    },
                }
                if tooltip_field:
                    geojson_kwargs["tooltip"] = folium.GeoJsonTooltip(
                        fields=[tooltip_field, "winning_party"],
                        aliases=['Division:', 'Winning Party:'],
                        localize=True
                    )

                folium.GeoJson(gdf_wards, **geojson_kwargs).add_to(m)
                ward_bounds = gdf_wards.total_bounds.tolist()
                m.fit_bounds([[ward_bounds[1], ward_bounds[0]], [ward_bounds[3], ward_bounds[2]]])

                if winner_by_ward:
                    legend_html = """
                    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999; background: white; border: 2px solid #555; border-radius: 8px; padding: 10px; font-size: 12px;">
                        <div style="font-weight: bold; margin-bottom: 6px;">Winning Party</div>
                        <div><span style="display:inline-block;width:10px;height:10px;background:#1f4e79;margin-right:6px;"></span>Conservative</div>
                        <div><span style="display:inline-block;width:10px;height:10px;background:#d7191c;margin-right:6px;"></span>Labour</div>
                        <div><span style="display:inline-block;width:10px;height:10px;background:#fdbf11;margin-right:6px;"></span>Liberal Democrats</div>
                        <div><span style="display:inline-block;width:10px;height:10px;background:#33a02c;margin-right:6px;"></span>Green Party</div>
                        <div><span style="display:inline-block;width:10px;height:10px;background:#00b7eb;margin-right:6px;"></span>Reform UK</div>
                        <div><span style="display:inline-block;width:10px;height:10px;background:#9e9e9e;margin-right:6px;"></span>No data</div>
                    </div>
                    """
                    m.get_root().html.add_child(folium.Element(legend_html))

# Open widgets.py and replace Section 3 inside create_map with this updated logic:

        # 3. Add Output Areas Layer if provided (rendered with micro-borders)
        if oa_shp_path and os.path.exists(oa_shp_path):
            print(f"[MAP ENGINE] Processing Output Area Boundary File: {os.path.basename(oa_shp_path)}")
            gdf_oa = gpd.read_file(oa_shp_path)

            # Ensure both geographic layers share the exact same spatial coordinate system
            if not gdf_wards.empty:
                print("[MAP ENGINE] Aligning projections for target area isolation...")
                gdf_oa = gdf_oa.to_crs(gdf_wards.crs)
                
                print("[MAP ENGINE] Running adaptive geometric layout intersection...")
                try:
                    # Fallback A: Try an optimized quick intersection clip mask
                    gdf_oa = gpd.clip(gdf_oa, gdf_wards)
                except Exception:
                    try:
                        # Fallback B: Spatial Join fallback if the index matrix fails to align
                        gdf_oa = gpd.sjoin(gdf_oa, gdf_wards, how="inner", predicate="intersects")
                        if 'index_right' in gdf_oa.columns:
                            gdf_oa = gdf_oa.drop(columns=['index_right'])
                    except Exception:
                        print("[MAP ENGINE] Index mismatch handled. Building explicit bounding box envelope...")
                        from shapely.geometry import box
                        
                        # Extract bounding box parameters securely
                        xmin, ymin, xmax, ymax = gdf_wards.total_bounds
                        
                        # Create an explicit bounding box geometry to completely bypass .cx float bugs
                        bbox_poly = box(xmin, ymin, xmax, ymax)
                        
                        # Filter down the output areas to only include shapes that intersect our bounding envelope
                        gdf_oa = gdf_oa[gdf_oa.geometry.intersects(bbox_poly)].copy()

            # SAFETY CHECK: Only push to Folium canvas if valid shapes exist
            if not gdf_oa.empty:
                oa_cols = gdf_oa.columns.tolist()
                target_oa_field = 'OA21CD' if 'OA21CD' in oa_cols else (oa_cols[0] if len(oa_cols) > 0 else None)
                
                print(f"[MAP ENGINE] Success! Filtered {len(gdf_oa):,} micro-local Output Areas for display.")
                print("names of wards in the map:\n", gdf_wards['WD25NM'].unique())
                if target_oa_field:
                    folium.GeoJson(
                        gdf_oa,
                        name="Output Areas (Census)",
                        style_function=lambda x: {
                            'fillColor': '#8f8',
                            'color': '#2e7d32',
                            'weight': 0.5,
                            'fillOpacity': 0.1
                        },
                        tooltip=folium.GeoJsonTooltip(fields=[target_oa_field], aliases=['OA Code:'])
                    ).add_to(m)
            else:
                print("[MAP ENGINE] WARNING: Boundary filters returned 0 rows. Bypassing layer.")

        # 4. Save map file to a unique workspace cache path per view instance.
        # This avoids one screen overwriting another screen's rendered map.
        html_map_path = os.path.abspath(
            os.path.join("data", "processed", f"temp_map_{uuid.uuid4().hex}.html")
        )
        os.makedirs(os.path.dirname(html_map_path), exist_ok=True)
        m.save(html_map_path)
        print(f"[MAP ENGINE] Saved map HTML: {html_map_path}")

        # 5. Build and populate the QtWebEngineView viewport
        self.web_map_view = QWebEngineView()
        self.web_map_view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.web_map_view.setUrl(QtCore.QUrl.fromLocalFile(html_map_path))

        # Clear active layouts and lock widget dimensions natively
        if self.map_frame.layout() is None:
            self.map_layout = QtWidgets.QVBoxLayout(self.map_frame)
            self.map_layout.setContentsMargins(0, 0, 0, 0)

        return self.web_map_view
        
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QFont
from PySide6.QtCore import Qt, QRectF

class GaugeWidget(QWidget):
    def __init__(self, min_value=0, max_value=100, value=0, parent=None, x=200, y=200):
        super().__init__(parent)
        self.min_value = min_value
        self.max_value = max_value
        self.value = value
        self.textsize = 0.16*x
        self.setMinimumSize(x, y)
        self.setMaximumSize(x, y)

    def set_value(self, value):
        self.value = value
        self.update()  # Triggers a repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(10, 10, self.width()-20, self.height()-20)

        # Draw background arc
        pen = QPen(Qt.lightGray, 15)
        painter.setPen(pen)
        painter.drawArc(rect, 45*16, 270*16)

        # Draw value arc
        pen.setColor(Qt.blue)
        painter.setPen(pen)
        span_angle = int(270 * (self.value - self.min_value) / (self.max_value - self.min_value))
        painter.drawArc(rect, 45*16, -span_angle*16)

        # Draw value text
        painter.setPen(Qt.black)
        font = QFont("Arial", int(self.textsize), QFont.Bold)
        painter.setFont(font)
        value_str = f"{self.value}%"
        painter.drawText(rect, Qt.AlignCenter | Qt.AlignTop, value_str)



# Usage in your GUI:
# gauge = GaugeWidget(x=125, y=125)
# layout.addWidget(gauge)
# gauge.set_value(24)  # To update the value dynamically