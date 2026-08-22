import sys
import requests
import warnings
import math
import re
import json
import os
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QComboBox,
    QScrollArea
)

from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter("ignore", InsecureRequestWarning)

WATER_LEVEL_URL = "https://pasig-marikina-tullahanffws.pagasa.dost.gov.ph/water/main_list.do"
RAINFALL_URL = "https://pasig-marikina-tullahanffws.pagasa.dost.gov.ph/rainfall/map_list.do"
WATER_HISTORY_URL = "https://pasig-marikina-tullahanffws.pagasa.dost.gov.ph/water/history_list.do"

# UPDATED: Switched from unencrypted http:// to secure https:// for mobile compliance
GEO_LOCATION_URL = "https://ipapi.co/json/"

UPDATE_INTERVAL = 60000  # 1 Minute
CACHE_FILE = "water_history_cache.json"


def safe_float(value):
    """Safely extracts a float from strings containing extra non-numeric characters like '13.01(*)'."""
    if value is None:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", str(value))
    return float(match.group()) if match else None


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two geographical points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        
        # REMOVED: Window flags like FramelessWindowHint and WindowStaysOnTopHint
        # Mobile operating systems manage windows, borders, and overlays natively.

        self.stations_data = {}      # { station_name: station_dict }
        self.rainfall_stations = []  # List of rainfall station dicts
        self.current_station_name = None
        self.water_history = []      # List of (datetime_obj, water_level)
        self.rain_history = []
        self.history_loaded = False

        self.create_ui()
        self.load_local_cache()

        # Load stations & detect location
        self.init_station_selection()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(UPDATE_INTERVAL)

    # REMOVED: Desktop mousePressEvent, mouseMoveEvent, and mouseReleaseEvent
    # Drag-to-move is not applicable on touchscreens and interferes with scrolling.

    def make_card(self, object_name):
        card = QFrame()
        card.setObjectName(object_name)
        card.setFrameShape(QFrame.StyledPanel)
        return card

    def make_section_title(self, text):
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def create_ui(self):
        # Root Window Layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # UPDATED: Wrap content in a QScrollArea for mobile screen compatibility
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: #0f172a; }")

        # Container inside Scroll Area
        self.main_container = QFrame()
        self.main_container.setObjectName("mainContainer")

        self.layout = QVBoxLayout(self.main_container)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)

        scroll_area.setWidget(self.main_container)
        root_layout.addWidget(scroll_area)

        # Header Section
        header = QHBoxLayout()
        header.setSpacing(10)

        self.title_label = QLabel("⚡ PAGASA MONITOR")
        self.title_label.setObjectName("appTitle")

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("closeButton")
        self.close_button.clicked.connect(self.close)

        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.close_button)

        self.layout.addLayout(header)

        # Station Selector Dropdown & Title
        station_box = QVBoxLayout()
        station_box.setSpacing(6)

        selector_header = QHBoxLayout()
        selector_label = QLabel("📍 SELECT STATION:")
        selector_label.setObjectName("sectionTitle")

        self.auto_loc_btn = QPushButton("🎯 Auto-Detect")
        self.auto_loc_btn.setObjectName("autoLocBtn")
        self.auto_loc_btn.clicked.connect(self.auto_detect_location)

        selector_header.addWidget(selector_label)
        selector_header.addStretch()
        selector_header.addWidget(self.auto_loc_btn)

        station_box.addLayout(selector_header)

        self.station_combo = QComboBox()
        self.station_combo.setObjectName("stationCombo")
        self.station_combo.currentTextChanged.connect(self.on_station_changed)
        station_box.addWidget(self.station_combo)

        self.layout.addLayout(station_box)

        # CURRENT SITUATION CARD
        self.situation_card = self.make_card("situationCard")
        situation_layout = QVBoxLayout(self.situation_card)
        situation_layout.setContentsMargins(16, 16, 16, 16)
        situation_layout.setSpacing(6)

        situation_layout.addWidget(self.make_section_title("📌 CURRENT SITUATION"))

        self.situation_headline = QLabel("✅ NO FLOOD ALARM")
        self.situation_headline.setObjectName("situationHeadline")

        self.situation_body = QLabel(
            "The river is below the station's alarm levels.\n"
            "The water level is currently stable.\n"
            "Continue monitoring. Conditions can change quickly during heavy rain."
        )
        self.situation_body.setObjectName("situationBody")
        self.situation_body.setWordWrap(True)

        situation_layout.addWidget(self.situation_headline)
        situation_layout.addWidget(self.situation_body)

        self.layout.addWidget(self.situation_card)

        # RIVER WATER LEVEL CARD
        self.water_card = self.make_card("waterCard")
        water_layout = QVBoxLayout(self.water_card)
        water_layout.setContentsMargins(16, 16, 16, 16)
        water_layout.setSpacing(6)

        water_layout.addWidget(self.make_section_title("🌊 RIVER WATER LEVEL"))

        water_main = QHBoxLayout()

        self.water_value_label = QLabel("--.-- m")
        self.water_value_label.setObjectName("waterValue")

        self.trend_label = QLabel("➡️ STABLE")
        self.trend_label.setObjectName("trendValue")
        self.trend_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        water_main.addWidget(self.water_value_label, 1)
        water_main.addWidget(self.trend_label)
        water_layout.addLayout(water_main)

        # Historical Delta summary
        self.history_summary_label = QLabel("📊 Past Changes: 1hr: -- | 3hr: --")
        self.history_summary_label.setObjectName("historySummary")
        water_layout.addWidget(self.history_summary_label)

        self.prediction_plain_label = QLabel("🔮 Third Alarm Prediction: Waiting for data...")
        self.prediction_plain_label.setObjectName("predictionPlain")
        self.prediction_plain_label.setWordWrap(True)
        water_layout.addWidget(self.prediction_plain_label)

        self.layout.addWidget(self.water_card)

        # RAIN INFORMATION CARD
        self.rain_card = self.make_card("rainCard")
        rain_layout = QVBoxLayout(self.rain_card)
        rain_layout.setContentsMargins(16, 16, 16, 16)
        rain_layout.setSpacing(8)

        rain_layout.addWidget(self.make_section_title("🌧️ RECENT RAINFALL"))

        rain_main = QHBoxLayout()

        rain_left = QVBoxLayout()
        self.rain_last_hour_label = QLabel("📏 Rainfall (1hr): --.- mm")
        self.rain_last_hour_label.setObjectName("rainLastHour")

        self.rain_status_headline = QLabel("🌤️ RAIN: UNLIKELY")
        self.rain_status_headline.setObjectName("rainStatusHeadline")

        self.rain_details_label = QLabel("No rainfall detected in recent updates.")
        self.rain_details_label.setObjectName("rainDetails")
        self.rain_details_label.setWordWrap(True)

        rain_left.addWidget(self.rain_last_hour_label)
        rain_left.addWidget(self.rain_status_headline)
        rain_left.addWidget(self.rain_details_label)

        rain_main.addLayout(rain_left, 1)

        self.rain_value_icon = QLabel("☁️")
        self.rain_value_icon.setObjectName("rainIcon")
        self.rain_value_icon.setAlignment(Qt.AlignCenter)

        rain_main.addWidget(self.rain_value_icon)
        rain_layout.addLayout(rain_main)

        self.layout.addWidget(self.rain_card)

        # Footer
        self.update_label = QLabel("🕒 Last update: --")
        self.update_label.setObjectName("updateLabel")
        self.update_label.setAlignment(Qt.AlignRight)
        self.layout.addWidget(self.update_label)

        # Stylesheet
        self.setStyleSheet("""
            QFrame#mainContainer {
                background-color: #0f172a;
                border: none;
            }

            QFrame#situationCard, QFrame#waterCard, QFrame#rainCard {
                background-color: rgba(30, 41, 59, 0.85);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }

            QComboBox#stationCombo {
                background-color: rgba(15, 23, 42, 0.9);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 15px;
                font-weight: 700;
            }

            QComboBox#stationCombo::drop-down {
                border: 0px;
            }

            QComboBox#stationCombo QAbstractItemView {
                background-color: #0f172a;
                color: #ffffff;
                selection-background-color: #38bdf8;
                selection-color: #000000;
            }

            QPushButton#autoLocBtn {
                background: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            }

            QPushButton#autoLocBtn:hover {
                background: #38bdf8;
                color: #000000;
            }

            QLabel#appTitle {
                color: #38bdf8;
                font-size: 18px;
                font-weight: 800;
                letter-spacing: 1px;
            }

            QPushButton#closeButton {
                background: rgba(255, 255, 255, 0.08);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 15px;
                font-size: 16px;
                width: 32px;
                height: 32px;
            }

            QPushButton#closeButton:hover {
                background: #ef4444;
                color: #ffffff;
            }

            QLabel#sectionTitle {
                color: #38bdf8;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1.2px;
            }

            QLabel#situationHeadline {
                color: #10b981;
                font-size: 19px;
                font-weight: 800;
                margin-top: 2px;
            }

            QLabel#situationBody {
                color: #cbd5e1;
                font-size: 13px;
                line-height: 1.4;
            }

            QLabel#waterValue {
                color: #ffffff;
                font-size: 34px;
                font-weight: 800;
            }

            QLabel#trendValue {
                color: #0ea5e9;
                font-size: 18px;
                font-weight: 800;
            }

            QLabel#historySummary {
                color: #94a3b8;
                font-size: 12px;
                font-weight: 600;
            }

            QLabel#predictionPlain {
                color: #e2e8f0;
                font-size: 13px;
                font-weight: 600;
                background: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 8px;
            }

            QLabel#rainLastHour {
                color: #cbd5e1;
                font-size: 14px;
            }

            QLabel#rainStatusHeadline {
                color: #ffffff;
                font-size: 17px;
                font-weight: 800;
            }

            QLabel#rainDetails {
                color: #94a3b8;
                font-size: 12px;
            }

            QLabel#rainIcon {
                font-size: 36px;
            }

            QLabel#updateLabel {
                color: #64748b;
                font-size: 11px;
            }
        """)

    def get_alarm_levels(self, station):
        """Dynamically extracts Alarm 1, 2, and 3 thresholds from PAGASA station data."""
        if not station or not isinstance(station, dict):
            return None, None, None

        st_lower = {str(k).lower(): v for k, v in station.items() if v is not None}

        def find_value(key_list, pattern=None):
            for k in key_list:
                if k in st_lower:
                    val = safe_float(st_lower[k])
                    if val is not None and val > 0:
                        return val

            if pattern:
                for k, v in st_lower.items():
                    if re.search(pattern, k):
                        val = safe_float(v)
                        if val is not None and val > 0:
                            return val
            return None

        al3_keys = [
            "al3", "alrm3", "al3_wl", "alrm_wl3", "alrmwl3", "al3wl", 
            "evac_wl", "evacwl", "evacuation", "alarm3", "critical_level",
            "crit_wl", "critwl", "critical", "crit", "evac", "wl_al3", "wl_alrm3"
        ]
        al2_keys = [
            "al2", "alrm2", "al2_wl", "alrm_wl2", "alrmwl2", "al2wl", 
            "warn_wl", "warnwl", "warning", "alarm2", "warn", "wl_al2", "wl_alrm2"
        ]
        al1_keys = [
            "al1", "alrm1", "al1_wl", "alrm_wl1", "alrmwl1", "al1wl", 
            "alert_wl", "alertwl", "alert", "alarm1", "wl_al1", "wl_alrm1"
        ]

        al3 = find_value(al3_keys, r"(al.*3|evac|crit)")
        al2 = find_value(al2_keys, r"(al.*2|warn)")
        al1 = find_value(al1_keys, r"(al.*1|alert)")

        if al3 is None and al2 is not None:
            al3 = al2 + 1.0
        if al2 is None and al1 is not None and al3 is not None:
            al2 = (al1 + al3) / 2.0
        if al1 is None and al2 is not None:
            al1 = max(0.0, al2 - 1.0)

        return al1, al2, al3

    def save_local_cache(self):
        """Saves current water history to local file."""
        if not self.current_station_name or not self.water_history:
            return
        try:
            cache_data = {}
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    cache_data = json.load(f)

            serialized = [(ts.isoformat(), wl) for ts, wl in self.water_history]
            cache_data[self.current_station_name] = serialized

            with open(CACHE_FILE, "w") as f:
                json.dump(cache_data, f)
        except Exception as e:
            print("Failed to save local water cache:", e)

    def load_local_cache(self):
        """Loads cached water history from local file."""
        if not os.path.exists(CACHE_FILE):
            return
        try:
            with open(CACHE_FILE, "r") as f:
                cache_data = json.load(f)
                if self.current_station_name in cache_data:
                    raw_list = cache_data[self.current_station_name]
                    parsed = []
                    cutoff = datetime.now() - timedelta(hours=12)
                    for ts_str, wl in raw_list:
                        ts = datetime.fromisoformat(ts_str)
                        if ts >= cutoff:
                            parsed.append((ts, wl))
                    parsed.sort(key=lambda x: x[0])
                    self.water_history = parsed
        except Exception as e:
            print("Failed to load local water cache:", e)

    def fetch_all_water_stations(self):
        """Fetches all stations dynamically from PAGASA API."""
        try:
            cache_buster = int(datetime.now().timestamp() * 1000)
            res = requests.get(
                WATER_LEVEL_URL, params={"_": cache_buster}, timeout=10, verify=False
            )
            res.raise_for_status()
            stations = res.json()
            self.stations_data = {
                s.get("obsnm", "Unknown"): s for s in stations if s.get("obsnm")
            }
            return True
        except Exception as e:
            print("Error fetching water stations list:", e)
            return False

    def init_station_selection(self):
        """Populates combo box and sets the closest or default station."""
        if self.fetch_all_water_stations():
            self.station_combo.blockSignals(True)
            self.station_combo.clear()
            self.station_combo.addItems(sorted(self.stations_data.keys()))
            self.station_combo.blockSignals(False)

            closest = self.get_nearest_station_by_ip()
            selected = None
            if closest and closest in self.stations_data:
                selected = closest
            elif "Sto Nino" in self.stations_data:
                selected = "Sto Nino"

            if selected:
                self.current_station_name = selected
                self.station_combo.setCurrentText(selected)
                self.load_local_cache()
                self.load_historical_water_data()

            self.update_data()

    def get_nearest_station_by_ip(self):
        """Finds closest PAGASA water station based on current device IP location."""
        try:
            res = requests.get(GEO_LOCATION_URL, timeout=5).json()
            # ipapi.co returns 'latitude' and 'longitude' keys
            user_lat = res.get("latitude") or res.get("lat")
            user_lon = res.get("longitude") or res.get("lon")

            if user_lat and user_lon:
                min_dist = float("inf")
                closest_name = None

                for name, data in self.stations_data.items():
                    try:
                        st_lat = safe_float(data.get("lat"))
                        st_lon = safe_float(data.get("lon"))
                        if not st_lat or not st_lon:
                            continue
                        dist = haversine_distance(user_lat, user_lon, st_lat, st_lon)
                        if dist < min_dist:
                            min_dist = dist
                            closest_name = name
                    except (ValueError, TypeError):
                        continue

                return closest_name
        except Exception as e:
            print("Location detection failed:", e)
        return None

    def auto_detect_location(self):
        """Manual trigger for auto-location button."""
        closest = self.get_nearest_station_by_ip()
        if closest and closest in self.stations_data:
            self.station_combo.setCurrentText(closest)

    def on_station_changed(self, new_station_name):
        if new_station_name and new_station_name in self.stations_data:
            self.current_station_name = new_station_name
            self.water_history.clear()
            self.rain_history.clear()
            self.history_loaded = False
            self.load_local_cache()
            self.load_historical_water_data()
            self.update_data()

    def load_historical_water_data(self):
        if not self.current_station_name:
            return

        station = self.stations_data.get(self.current_station_name)
        if not station:
            return

        station_code = station.get("obscd") or station.get("obs_code") or station.get("obsCd")
        now = datetime.now()

        candidates = [
            (WATER_HISTORY_URL, {"obscd": station_code, "days": 3}),
            (WATER_HISTORY_URL, {"obsnm": self.current_station_name, "days": 3}),
            (WATER_HISTORY_URL, {"obscd": station_code}),
            (WATER_HISTORY_URL, {"obsnm": self.current_station_name}),
            (WATER_LEVEL_URL, {"obscd": station_code, "history": "true"}),
        ]

        for url, params in candidates:
            if not any(v for v in params.values()):
                continue
            try:
                params["_"] = int(now.timestamp() * 1000)
                res = requests.get(url, params=params, timeout=8, verify=False)
                if res.status_code != 200:
                    continue

                data = res.json()
                if isinstance(data, dict):
                    for key in ("data", "list", "rows", "result", "history"):
                        if isinstance(data.get(key), list):
                            data = data[key]
                            break

                if not isinstance(data, list):
                    continue

                parsed = []
                for item in data:
                    if not isinstance(item, dict):
                        continue

                    name = str(item.get("obsnm") or item.get("station") or "")
                    if name and name.lower() != self.current_station_name.lower():
                        if self.current_station_name.lower() not in name.lower() and name.lower() not in self.current_station_name.lower():
                            continue

                    level = safe_float(
                        item.get("wl") if item.get("wl") is not None
                        else item.get("waterLevel") if item.get("waterLevel") is not None
                        else item.get("water_level") if item.get("water_level") is not None
                        else item.get("level")
                    )
                    if level is None:
                        continue

                    raw_time = (
                        item.get("ymdhm") or item.get("datetime")
                        or item.get("dateTime") or item.get("obsdt")
                        or item.get("time") or item.get("date")
                    )

                    timestamp = None
                    if raw_time:
                        raw_time = str(raw_time).strip()
                        for fmt in (
                            "%Y%m%d%H%M%S", "%Y%m%d%H%M",
                            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                            "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
                        ):
                            try:
                                timestamp = datetime.strptime(raw_time, fmt)
                                break
                            except ValueError:
                                pass

                    if timestamp is None:
                        continue

                    parsed.append((timestamp, level))

                if parsed:
                    existing_dict = {ts: wl for ts, wl in self.water_history}
                    for ts, wl in parsed:
                        existing_dict[ts] = wl

                    combined = sorted(existing_dict.items(), key=lambda x: x[0])
                    cutoff = now - timedelta(hours=12)
                    self.water_history = [i for i in combined if i[0] >= cutoff]
                    self.save_local_cache()
                    self.history_loaded = True
                    return

            except Exception as e:
                print("Historical water data attempt failed:", e)

        self.history_loaded = True

    def fetch_rainfall_list(self):
        now = datetime.now()
        time_offsets = [0, 10, 20]
        cache_buster = int(now.timestamp() * 1000)

        for offset in time_offsets:
            obs_time = now - timedelta(minutes=offset)
            obs_time = obs_time.replace(minute=(obs_time.minute // 10) * 10, second=0, microsecond=0)
            ymdhm = obs_time.strftime("%Y%m%d%H%M")

            try:
                res = requests.get(
                    RAINFALL_URL,
                    params={"ymdhm": ymdhm, "basin": "", "_": cache_buster},
                    timeout=8,
                    verify=False,
                )
                if res.status_code == 200:
                    data = res.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        self.rainfall_stations = data
                        return data
            except Exception as e:
                print(f"Rainfall attempt offset {offset} failed:", e)

        try:
            res = requests.get(RAINFALL_URL, params={"_": cache_buster}, timeout=8, verify=False)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list):
                    self.rainfall_stations = data
                    return data
        except Exception as e:
            print("Fallback rainfall query failed:", e)

        return []

    def get_nearest_rainfall_station(self, water_station):
        rf_list = self.fetch_rainfall_list()
        if not rf_list or not water_station:
            return None

        w_name = water_station.get("obsnm", "").lower()
        for rf in rf_list:
            rf_name = rf.get("obsnm", "").lower()
            if w_name in rf_name or rf_name in w_name:
                return rf

        try:
            w_lat = safe_float(water_station.get("lat"))
            w_lon = safe_float(water_station.get("lon"))

            if not w_lat or not w_lon:
                return rf_list[0] if rf_list else None

            min_dist = float("inf")
            nearest_rf = None

            for rf in rf_list:
                rf_lat = safe_float(rf.get("lat"))
                rf_lon = safe_float(rf.get("lon"))
                if not rf_lat or not rf_lon:
                    continue
                dist = haversine_distance(w_lat, w_lon, rf_lat, rf_lon)
                if dist < min_dist:
                    min_dist = dist
                    nearest_rf = rf

            return nearest_rf or (rf_list[0] if rf_list else None)
        except Exception as e:
            print("Error finding nearest rainfall station:", e)
            return rf_list[0] if rf_list else None

    def add_water_history(self, water_level):
        now = datetime.now()
        if self.water_history:
            last_time, last_level = self.water_history[-1]
            if (now - last_time).total_seconds() < 30 and abs(last_level - water_level) < 0.001:
                return

        self.water_history.append((now, water_level))
        cutoff = now - timedelta(hours=12)
        self.water_history = [i for i in self.water_history if i[0] >= cutoff]
        self.save_local_cache()

    def get_water_level_delta(self, hours_ago):
        if not self.water_history or len(self.water_history) < 2:
            return None

        now = self.water_history[-1][0]
        target_time = now - timedelta(hours=hours_ago)
        current_level = self.water_history[-1][1]

        closest = min(self.water_history[:-1], key=lambda item: abs((item[0] - target_time).total_seconds()))
        time_diff = abs((closest[0] - target_time).total_seconds())

        if time_diff > (hours_ago * 1800 + 1800):
            return None

        return current_level - closest[1]

    def calculate_water_dynamics(self):
        if len(self.water_history) < 2:
            return 0.0, 0.0

        recent_samples = [s for s in self.water_history if (self.water_history[-1][0] - s[0]).total_seconds() <= 3600]
        if len(recent_samples) < 2:
            recent_samples = self.water_history[-5:]

        t0 = recent_samples[0][0]
        xs = [(ts - t0).total_seconds() / 3600.0 for ts, _ in recent_samples]
        ys = [level for _, level in recent_samples]

        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denom = sum((x - mean_x) ** 2 for x in xs)

        velocity = (sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom) if denom > 0 else 0.0

        older_samples = [s for s in self.water_history if 3600 < (self.water_history[-1][0] - s[0]).total_seconds() <= 10800]
        if len(older_samples) >= 2:
            t_old0 = older_samples[0][0]
            xs_old = [(ts - t_old0).total_seconds() / 3600.0 for ts, _ in older_samples]
            ys_old = [level for _, level in older_samples]
            mean_x_old = sum(xs_old) / len(xs_old)
            mean_y_old = sum(ys_old) / len(ys_old)
            denom_old = sum((x - mean_x_old) ** 2 for x in xs_old)

            old_velocity = (sum((x - mean_x_old) * (y - mean_y_old) for x, y in zip(xs_old, ys_old)) / denom_old) if denom_old > 0 else 0.0
            time_delta_hr = (self.water_history[-1][0] - older_samples[-1][0]).total_seconds() / 3600.0

            acceleration = (velocity - old_velocity) / time_delta_hr if time_delta_hr > 0 else 0.0
        else:
            acceleration = 0.0

        return velocity, acceleration

    def add_rain_history(self, rainfall):
        now = datetime.now()
        self.rain_history.append((now, rainfall))
        cutoff = now - timedelta(hours=3)
        self.rain_history = [i for i in self.rain_history if i[0] >= cutoff]

    def get_recent_rain_average(self, minutes=60):
        if not self.rain_history:
            return 0.0

        cutoff = datetime.now() - timedelta(minutes=minutes)
        values = [val for ts, val in self.rain_history if ts >= cutoff]
        return sum(values) / len(values) if values else 0.0

    def predict_critical_level(self, water_level, critical_level, rainfall):
        if critical_level is None:
            return "🔮 3rd Alarm: No threshold value provided in PAGASA API for this station"

        if water_level is None:
            return f"🔮 3rd Alarm ({critical_level:.2f} m): WAITING FOR DATA"

        if water_level >= critical_level:
            return f"🚨 3rd ALARM SURPASSED ({water_level:.2f} m >= {critical_level:.2f} m)"

        if len(self.water_history) < 2:
            return f"⏳ 3rd Alarm ({critical_level:.2f} m): Gathering historical trend..."

        velocity, accel = self.calculate_water_dynamics()
        recent_rain = self.get_recent_rain_average(60)
        distance = critical_level - water_level

        if velocity <= 0 and accel <= 0:
            if water_level >= (critical_level - 1.0) and (rainfall >= 7.5 or recent_rain >= 7.5):
                return (
                    f"🔮 3rd Alarm ({critical_level:.2f} m): ⚠️ POSSIBLE IF RUNOFF SURGES\n"
                    f"Current: {water_level:.2f} m | Trend: Falling/Stable ({velocity:+.2f} m/hr) | Rain: {rainfall:.1f} mm/hr"
                )
            return (
                f"🔮 3rd Alarm ({critical_level:.2f} m): 🟢 UNLIKELY UNDER CURRENT TREND\n"
                f"Current: {water_level:.2f} m | Trend: {velocity:+.2f} m/hr | Rain: {rainfall:.1f} mm/hr"
            )

        hours_to_critical = None
        if abs(accel) > 0.001:
            disc = velocity**2 + 2 * accel * distance
            if disc >= 0:
                t1 = (-velocity + math.sqrt(disc)) / accel
                t2 = (-velocity - math.sqrt(disc)) / accel
                valid_t = [t for t in (t1, t2) if t > 0]
                if valid_t:
                    hours_to_critical = min(valid_t)

        if hours_to_critical is None and velocity > 0:
            hours_to_critical = distance / velocity

        if hours_to_critical is None or hours_to_critical > 24:
            return (
                f"🔮 3rd Alarm ({critical_level:.2f} m): 🟢 LOW RISK (> 24 hours)\n"
                f"Current: {water_level:.2f} m (+{velocity:.2f} m/hr) | Gap: {distance:.2f} m"
            )

        eta = datetime.now() + timedelta(hours=hours_to_critical)

        if hours_to_critical <= 1:
            risk = "🔴 CRITICAL RISK (< 1 hour)"
        elif hours_to_critical <= 3:
            risk = "🟠 HIGH RISK (1–3 hours)"
        elif hours_to_critical <= 6:
            risk = "🟡 MODERATE RISK (3–6 hours)"
        else:
            risk = "🟢 LOW RISK (> 6 hours)"

        accel_str = f" | Accel: {accel:+.2f} m/hr²" if abs(accel) > 0.01 else ""
        return (
            f"🔮 3rd Alarm ({critical_level:.2f} m) Prediction: {risk}\n"
            f"Current: {water_level:.2f} m (+{velocity:.2f} m/hr{accel_str}) | Gap: {distance:.2f} m | ETA: ~{hours_to_critical:.1f} hr ({eta.strftime('%I:%M %p')})"
        )

    def update_data(self):
        self.fetch_all_water_stations()

        station = self.stations_data.get(self.current_station_name)
        if not station:
            self.update_label.setText(
                f"🕒 Last update: {datetime.now().strftime('%I:%M:%S %p')} (Station data unavailable)"
            )
            return

        water_level = safe_float(
            station.get("wl") if station.get("wl") is not None
            else station.get("waterLevel") if station.get("waterLevel") is not None
            else station.get("water_level") if station.get("water_level") is not None
            else station.get("level")
        )

        al1, al2, al3 = self.get_alarm_levels(station)

        if water_level is not None:
            self.add_water_history(water_level)
            self.water_value_label.setText(f"{water_level:.2f} m")
        else:
            self.water_value_label.setText("--.-- m")

        d1 = self.get_water_level_delta(1)
        d3 = self.get_water_level_delta(3)
        d1_str = f"{d1:+.2f}m" if d1 is not None else "--"
        d3_str = f"{d3:+.2f}m" if d3 is not None else "--"
        self.history_summary_label.setText(f"📊 Past Changes: 1hr: {d1_str} | 3hr: {d3_str}")

        velocity, accel = self.calculate_water_dynamics()
        if velocity > 0.05:
            self.trend_label.setText(f"⬆️ RISING (+{velocity:.2f} m/h)")
            self.trend_label.setStyleSheet("color: #ef4444;")
        elif velocity < -0.05:
            self.trend_label.setText(f"⬇️ FALLING ({velocity:.2f} m/h)")
            self.trend_label.setStyleSheet("color: #10b981;")
        else:
            self.trend_label.setText("➡️ STABLE")
            self.trend_label.setStyleSheet("color: #0ea5e9;")

        rf_station = self.get_nearest_rainfall_station(station)
        rainfall = 0.0
        if rf_station:
            rf_val = safe_float(
                rf_station.get("rf") or rf_station.get("rf1h") or rf_station.get("rn") or rf_station.get("val")
            )
            if rf_val is not None:
                rainfall = rf_val

        self.add_rain_history(rainfall)
        self.rain_last_hour_label.setText(f"📏 Rainfall (1hr): {rainfall:.1f} mm")

        if rainfall >= 15.0:
            self.rain_status_headline.setText("🌧️ HEAVY RAIN")
            self.rain_status_headline.setStyleSheet("color: #ef4444;")
            self.rain_value_icon.setText("⛈️")
            self.rain_details_label.setText("Heavy rainfall in progress. High risk of river level surge.")
        elif rainfall >= 7.5:
            self.rain_status_headline.setText("🌦️ MODERATE RAIN")
            self.rain_status_headline.setStyleSheet("color: #f59e0b;")
            self.rain_value_icon.setText("🌧️")
            self.rain_details_label.setText("Moderate rainfall observed nearby.")
        elif rainfall > 0.0:
            self.rain_status_headline.setText("🌦️ LIGHT RAIN")
            self.rain_status_headline.setStyleSheet("color: #38bdf8;")
            self.rain_value_icon.setText("🌦️")
            self.rain_details_label.setText("Light rain detected.")
        else:
            self.rain_status_headline.setText("🌤️ NO RAIN")
            self.rain_status_headline.setStyleSheet("color: #ffffff;")
            self.rain_value_icon.setText("☁️")
            self.rain_details_label.setText("No rainfall detected in recent updates.")

        prediction_msg = self.predict_critical_level(water_level, al3, rainfall)
        self.prediction_plain_label.setText(prediction_msg)

        if water_level is not None:
            if al3 is not None and water_level >= al3:
                self.situation_headline.setText("🚨 3RD ALARM - EVACUATION")
                self.situation_headline.setStyleSheet("color: #ef4444;")
                self.situation_body.setText(
                    f"Water level ({water_level:.2f} m) reached or exceeded 3rd Alarm ({al3:.2f} m).\n"
                    "Immediate evacuation may be required! Follow local authority guidelines."
                )
            elif al2 is not None and water_level >= al2:
                al3_text = f"{al3:.2f} m" if al3 is not None else "N/A"
                self.situation_headline.setText("⚠️ 2ND ALARM - WARNING")
                self.situation_headline.setStyleSheet("color: #f59e0b;")
                self.situation_body.setText(
                    f"Water level ({water_level:.2f} m) reached 2nd Alarm ({al2:.2f} m).\n"
                    f"3rd Alarm threshold is {al3_text}. Prepare for possible evacuation."
                )
            elif al1 is not None and water_level >= al1:
                al3_text = f"{al3:.2f} m" if al3 is not None else "N/A"
                self.situation_headline.setText("🟡 1ST ALARM - ALERT")
                self.situation_headline.setStyleSheet("color: #eab308;")
                self.situation_body.setText(
                    f"Water level ({water_level:.2f} m) reached 1st Alarm ({al1:.1f} m).\n"
                    f"Monitor river levels closely. 3rd Alarm threshold is {al3_text}."
                )
            else:
                al1_text = f"{al1:.2f} m" if al1 is not None else "N/A"
                al3_text = f"{al3:.2f} m" if al3 is not None else "N/A"
                self.situation_headline.setText("✅ NO FLOOD ALARM")
                self.situation_headline.setStyleSheet("color: #10b981;")
                self.situation_body.setText(
                    f"Water level ({water_level:.2f} m) is below 1st Alarm ({al1_text}).\n"
                    f"3rd Alarm threshold for this station is {al3_text}. Conditions stable."
                )

        self.update_label.setText(f"🕒 Last update: {datetime.now().strftime('%I:%M:%S %p')}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Overlay()
    window.show()
    sys.exit(app.exec_())