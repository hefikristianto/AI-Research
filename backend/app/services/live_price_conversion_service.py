from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

CANONICAL_VALIDATOR_PATH = (
    PROJECT_ROOT
    / "ai"
    / "benchmarks"
    / "scripts"
    / "validate_yolo11s_conf025_pairs_ohlcv.py"
)


class CanonicalOHLCVPriceConversionService:
    MAPPING_MODE = (
        "CANONICAL_OHLCV_CANDLE_ANCHORED"
    )

    def __init__(self) -> None:
        self.validator = (
            self._load_validator_module()
        )

    @staticmethod
    def _load_validator_module() -> ModuleType:
        if not CANONICAL_VALIDATOR_PATH.exists():
            raise FileNotFoundError(
                "Canonical OHLCV validator tidak "
                "ditemukan: "
                f"{CANONICAL_VALIDATOR_PATH}"
            )

        spec = (
            importlib.util
            .spec_from_file_location(
                "ai_tdss_canonical_ohlcv_validator",
                CANONICAL_VALIDATOR_PATH,
            )
        )

        if (
            spec is None
            or spec.loader is None
        ):
            raise ImportError(
                "Gagal membuat module spec untuk "
                "canonical OHLCV validator."
            )

        module = (
            importlib.util
            .module_from_spec(spec)
        )

        spec.loader.exec_module(module)

        required_functions = [
            "x_to_index",
            "detect_local_ob_fvg",
        ]

        missing = [
            name
            for name in required_functions
            if not hasattr(module, name)
        ]

        if missing:
            raise AttributeError(
                "Fungsi canonical tidak lengkap: "
                + ", ".join(missing)
            )

        return module

    @staticmethod
    def _normalize_direction(
        value: Any,
    ) -> str:
        direction = str(
            value or "unknown"
        ).lower()

        if direction.startswith("bullish"):
            return "bullish"

        if direction.startswith("bearish"):
            return "bearish"

        return "unknown"

    @staticmethod
    def _prepare_canonical_window(
        chart_window: pd.DataFrame,
    ) -> pd.DataFrame:
        required = {
            "datetime",
            "open",
            "high",
            "low",
            "close",
        }

        missing = (
            required
            - set(chart_window.columns)
        )

        if missing:
            raise ValueError(
                "Kolom chart window tidak lengkap: "
                + ", ".join(
                    sorted(missing)
                )
            )

        window = (
            chart_window
            .copy()
            .reset_index(drop=True)
        )

        window["OPEN"] = window["open"]
        window["HIGH"] = window["high"]
        window["LOW"] = window["low"]
        window["CLOSE"] = window["close"]

        return window

    @staticmethod
    def _extract_x(
        setup: dict[str, Any],
        key: str,
    ) -> float | None:
        box = setup.get(
            key,
            {},
        )

        try:
            value = float(
                box.get("x")
            )

        except (
            AttributeError,
            TypeError,
            ValueError,
        ):
            return None

        if not 0.0 <= value <= 1.0:
            return None

        return value

    @staticmethod
    def _calculate_zone_status(
        window: pd.DataFrame,
        ob_index: int,
        fvg_index: int,
    ) -> dict[str, Any]:
        ob_candle = window.iloc[
            ob_index
        ]

        zone_low = float(
            ob_candle["low"]
        )

        zone_high = float(
            ob_candle["high"]
        )

        future = window.iloc[
            fvg_index + 1:
        ]

        touch_count = int(
            (
                future["low"].le(
                    zone_high
                )
                & future["high"].ge(
                    zone_low
                )
            ).sum()
        )

        if touch_count == 0:
            zone_status = "fresh"
            zone_score = 1.00
            fresh = True
            mitigated = False

        elif touch_count == 1:
            zone_status = (
                "partially_mitigated"
            )
            zone_score = 0.65
            fresh = False
            mitigated = True

        else:
            zone_status = "mitigated"
            zone_score = 0.25
            fresh = False
            mitigated = True

        return {
            "zone_low": zone_low,
            "zone_high": zone_high,
            "zone_mid": (
                zone_low + zone_high
            ) / 2.0,
            "touch_count": touch_count,
            "zone_touch_count": (
                touch_count
            ),
            "zone_status": zone_status,
            "zone_score": zone_score,
            "fresh": fresh,
            "zone_fresh": fresh,
            "mitigated": mitigated,
            "zone_mitigated": (
                mitigated
            ),
        }

    def convert(
        self,
        chart_window: pd.DataFrame,
        best_setup: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not best_setup:
            return {
                "status": "NO_SETUP",
                "mapping_mode": (
                    self.MAPPING_MODE
                ),
                "mapping_provisional": True,
                "reason": (
                    "Best setup belum tersedia."
                ),
            }

        if chart_window.empty:
            return {
                "status": "NO_CHART_WINDOW",
                "mapping_mode": (
                    self.MAPPING_MODE
                ),
                "mapping_provisional": True,
                "reason": (
                    "Chart window OHLCV kosong."
                ),
            }

        ob_x = self._extract_x(
            best_setup,
            "ob_bbox",
        )

        fvg_x = self._extract_x(
            best_setup,
            "fvg_bbox",
        )

        if ob_x is None:
            return {
                "status": "INVALID_OB_X",
                "mapping_mode": (
                    self.MAPPING_MODE
                ),
                "mapping_provisional": True,
                "reason": (
                    "Koordinat X order block "
                    "tidak valid."
                ),
            }

        window = (
            self._prepare_canonical_window(
                chart_window
            )
        )

        approx_ob_idx = int(
            self.validator.x_to_index(
                ob_x,
                len(window),
            )
        )

        approx_fvg_idx = None

        if fvg_x is not None:
            approx_fvg_idx = int(
                self.validator.x_to_index(
                    fvg_x,
                    len(window),
                )
            )

        detected = (
            self.validator
            .detect_local_ob_fvg(
                window,
                approx_ob_idx,
            )
        )

        if detected is None:
            return {
                "status": "NO_LOCAL_OB_FVG_MATCH",
                "mapping_mode": (
                    self.MAPPING_MODE
                ),
                "mapping_provisional": True,
                "ob_x": ob_x,
                "fvg_x": fvg_x,
                "approx_ob_idx": (
                    approx_ob_idx
                ),
                "approx_fvg_idx": (
                    approx_fvg_idx
                ),
                "reason": (
                    "Struktur OB-FVG lokal tidak "
                    "ditemukan di sekitar prediksi."
                ),
            }

        matched_ob_idx = int(
            detected["ob_idx"]
        )

        matched_fvg_idx = int(
            detected["fvg_idx"]
        )

        impulse_idx = int(
            detected["impulse_idx"]
        )

        detected_direction = (
            self._normalize_direction(
                detected.get(
                    "direction"
                )
            )
        )

        setup_direction = (
            self._normalize_direction(
                best_setup.get(
                    "setup_direction",
                    best_setup.get(
                        "direction"
                    ),
                )
            )
        )

        direction_match = (
            setup_direction
            == detected_direction
        )

        zone = (
            self._calculate_zone_status(
                window=window,
                ob_index=matched_ob_idx,
                fvg_index=matched_fvg_idx,
            )
        )

        distance_from_prediction = int(
            detected.get(
                "distance_from_prediction",
                abs(
                    matched_ob_idx
                    - approx_ob_idx
                ),
            )
        )

        search_radius = max(
            1,
            int(
                getattr(
                    self.validator,
                    "SEARCH_RADIUS",
                    5,
                )
            ),
        )

        distance_score = max(
            0.0,
            1.0
            - (
                distance_from_prediction
                / search_radius
            ),
        )

        local_score = max(
            0.0,
            min(
                1.0,
                float(
                    detected.get(
                        "local_score",
                        0.5,
                    )
                ),
            ),
        )

        mapping_confidence = (
            distance_score * 0.65
            + local_score * 0.35
        )

        ob_row = window.iloc[
            matched_ob_idx
        ]

        impulse_row = window.iloc[
            impulse_idx
        ]

        fvg_row = window.iloc[
            matched_fvg_idx
        ]

        result = {
            "status": (
                "MAPPED"
                if direction_match
                else "DIRECTION_MISMATCH"
            ),
            "mapping_mode": (
                self.MAPPING_MODE
            ),
            "mapping_provisional": (
                not direction_match
            ),
            "mapping_confidence": (
                mapping_confidence
            ),
            "setup_direction": (
                setup_direction
            ),
            "detected_direction": (
                detected_direction
            ),
            "direction_match": (
                direction_match
            ),
            "ob_x": ob_x,
            "fvg_x": fvg_x,
            "approx_ob_idx": (
                approx_ob_idx
            ),
            "approx_fvg_idx": (
                approx_fvg_idx
            ),
            "matched_ob_idx": (
                matched_ob_idx
            ),
            "matched_impulse_idx": (
                impulse_idx
            ),
            "matched_fvg_idx": (
                matched_fvg_idx
            ),
            "ob_index_error": abs(
                matched_ob_idx
                - approx_ob_idx
            ),
            "fvg_index_error": (
                abs(
                    matched_fvg_idx
                    - approx_fvg_idx
                )
                if approx_fvg_idx
                is not None
                else None
            ),
            "distance_from_prediction": (
                distance_from_prediction
            ),
            "local_score": (
                local_score
            ),
            "impulse_body_ratio": float(
                detected.get(
                    "impulse_body_ratio",
                    0.0,
                )
            ),
            "gap_size": float(
                detected.get(
                    "gap_size",
                    0.0,
                )
            ),
            "ob_datetime": (
                ob_row["datetime"]
                .isoformat()
            ),
            "impulse_datetime": (
                impulse_row["datetime"]
                .isoformat()
            ),
            "fvg_datetime": (
                fvg_row["datetime"]
                .isoformat()
            ),
            "ob_open": float(
                ob_row["open"]
            ),
            "ob_high": float(
                ob_row["high"]
            ),
            "ob_low": float(
                ob_row["low"]
            ),
            "ob_close": float(
                ob_row["close"]
            ),
            "invalidated": False,
            "invalidation_mode": (
                "CURRENT_CLOSE_VS_ATR_STOP_"
                "IN_RISK_LAYER"
            ),
            **zone,
        }

        if not direction_match:
            result["reason"] = (
                "Arah setup YOLO tidak cocok "
                "dengan struktur OHLCV lokal."
            )

        return result
