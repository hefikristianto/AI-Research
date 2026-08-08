from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_4_1_ocr_benchmark.json"
)
GENERATOR_VERSION = "1.0.0"
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
PLOT_LEFT = 64
PLOT_RIGHT = 1048
AXIS_LEFT = 1050


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic synthetic price-axis fixtures for "
            "the E2.4.1 OCR benchmark. No model inference or trading "
            "outcome data is used."
        )
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="Registered E2.4.1 benchmark contract.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New local output directory under local_artifacts/.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Contract tidak ditemukan: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Contract JSON tidak valid: {path}: {error}") from error

    if not isinstance(payload, dict):
        raise ValueError(f"Contract harus berupa JSON object: {path}")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if contract.get("schema_version") != 1:
        errors.append("E2.4.1 schema_version harus 1.")
    if contract.get("experiment_id") != "E2.4.1":
        errors.append("experiment_id harus E2.4.1.")
    if contract.get("stage") != "OCR_BACKEND_AND_FIXTURE_BENCHMARK":
        errors.append("Stage E2.4.1 berubah.")
    if contract.get("training_performed") is not False:
        errors.append("Generator E2.4.1 tidak boleh melakukan training.")
    if contract.get("model_inference_performed") is not False:
        errors.append("Generator E2.4.1 tidak boleh menjalankan model inference.")
    if contract.get("trading_outcome_data_allowed") is not False:
        errors.append("E2.4.1 tidak boleh membaca outcome trading.")
    if contract.get("production_decision_changed") is not False:
        errors.append("E2.4.1 tidak boleh mengubah keputusan produksi.")

    holdout = contract.get("holdout_access", {})
    if any(bool(value) for value in holdout.values()):
        errors.append("Semua akses outcome/holdout E2.4.1 harus false.")

    fixture_contract = contract.get("fixture_contract", {})
    if fixture_contract.get("trade_outcome_fields_forbidden") is not True:
        errors.append("Field outcome trading harus dilarang pada fixture.")
    if fixture_contract.get("image_sha256_required") is not True:
        errors.append("SHA256 gambar fixture wajib dicatat.")
    return errors


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _theme_style(theme: str) -> dict[str, tuple[int, int, int]]:
    styles = {
        "LIGHT": {
            "background": (250, 250, 250),
            "grid": (224, 228, 232),
            "label": (35, 38, 42),
            "up": (8, 153, 129),
            "down": (214, 56, 71),
            "separator": (132, 136, 142),
        },
        "DARK": {
            "background": (16, 18, 22),
            "grid": (43, 47, 54),
            "label": (232, 235, 239),
            "up": (31, 190, 154),
            "down": (242, 72, 89),
            "separator": (92, 98, 108),
        },
        "CUSTOM": {
            "background": (9, 24, 48),
            "grid": (32, 58, 91),
            "label": (255, 216, 92),
            "up": (64, 196, 255),
            "down": (255, 114, 182),
            "separator": (104, 142, 181),
        },
    }
    return styles[theme]


def _format_price(pair: str, price: float, locale: str) -> str:
    decimals = 5 if pair == "GBPUSD" else 2
    if locale == "DOT_DECIMAL":
        if pair == "XAUUSD":
            return f"{price:,.{decimals}f}"
        return f"{price:.{decimals}f}"

    rendered = (
        f"{price:,.{decimals}f}"
        if pair == "XAUUSD"
        else f"{price:.{decimals}f}"
    )
    return rendered.translate(str.maketrans({",": ".", ".": ","}))


def _prices(pair: str, count: int) -> list[float]:
    if pair == "GBPUSD":
        start = 1.28000
        step = 0.00500
    else:
        start = 4100.00
        step = 20.00
    return [start - step * index for index in range(count)]


def _draw_fixture(
    *,
    output_path: Path,
    pair: str,
    platform: str,
    theme: str,
    locale: str,
    variant: str,
) -> list[dict[str, Any]]:
    style = _theme_style(theme)
    image = Image.new(
        "RGB",
        (IMAGE_WIDTH, IMAGE_HEIGHT),
        color=style["background"],
    )
    draw = ImageDraw.Draw(image)

    for y in range(80, 681, 100):
        draw.line(
            (PLOT_LEFT, y, PLOT_RIGHT, y),
            fill=style["grid"],
            width=1,
        )

    candle_width = 7 if platform == "TRADINGVIEW" else 5
    for index, x in enumerate(range(PLOT_LEFT + 12, PLOT_RIGHT - 8, 18)):
        center = 330 + ((index * 37) % 220) - 110
        body_half = 8 + (index % 4) * 3
        wick = 16 + (index % 5) * 3
        color = style["up"] if index % 3 else style["down"]
        draw.line(
            (x, center - wick, x, center + wick),
            fill=color,
            width=2,
        )
        draw.rectangle(
            (
                x - candle_width // 2,
                center - body_half,
                x + candle_width // 2,
                center + body_half,
            ),
            fill=color,
        )

    draw.line(
        (AXIS_LEFT, 0, AXIS_LEFT, IMAGE_HEIGHT - 1),
        fill=style["separator"],
        width=2,
    )

    label_font = _font(23 if platform == "TRADINGVIEW" else 21)
    y_centers = [90, 190, 290, 390, 490, 590]
    prices = _prices(pair, len(y_centers))
    if variant == "CROPPED":
        y_centers = y_centers[2:4]
        prices = prices[2:4]

    ticks: list[dict[str, Any]] = []
    for index, (y_center, price) in enumerate(zip(y_centers, prices)):
        if variant == "PERCENT":
            text = f"{5 - index}.0%"
        else:
            text = _format_price(pair, price, locale)

        bbox = draw.textbbox((0, 0), text, font=label_font)
        text_height = bbox[3] - bbox[1]
        draw.line(
            (AXIS_LEFT, y_center, AXIS_LEFT + 9, y_center),
            fill=style["separator"],
            width=1,
        )
        draw.text(
            (AXIS_LEFT + 14, y_center - text_height / 2),
            text,
            fill=style["label"],
            font=label_font,
        )
        ticks.append(
            {
                "text": text,
                "price": price,
                "y_center": float(y_center),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=False)
    return ticks


def _fixture_entry(
    *,
    output_dir: Path,
    fixture_id: str,
    pair: str,
    timeframe: str,
    platform: str,
    theme: str,
    locale: str,
    variant: str,
) -> dict[str, Any]:
    image_path = output_dir / "images" / f"{fixture_id}.png"
    ticks = _draw_fixture(
        output_path=image_path,
        pair=pair,
        platform=platform,
        theme=theme,
        locale=locale,
        variant=variant,
    )

    expected_status = (
        "CALIBRATED" if variant == "VALID" else "FAIL_CLOSED"
    )
    expected_reason_codes: list[str] = []
    scale_mode = "LINEAR"
    if variant == "CROPPED":
        expected_reason_codes = [
            "INSUFFICIENT_VALID_PRICE_TICKS",
            "PRICE_AXIS_CROPPED_OR_TOO_NARROW",
        ]
    elif variant == "PERCENT":
        expected_reason_codes = ["PERCENT_PRICE_AXIS_DETECTED"]
    elif variant == "LOG":
        scale_mode = "LOG"
        expected_reason_codes = ["LOG_PRICE_AXIS_UNSUPPORTED"]

    return {
        "fixture_id": fixture_id,
        "fixture_source": "DETERMINISTIC_SYNTHETIC",
        "external_reviewed": False,
        "image_path": image_path.relative_to(output_dir).as_posix(),
        "image_sha256": file_sha256(image_path),
        "pair": pair,
        "timeframe": timeframe,
        "platform": platform,
        "theme": theme,
        "locale": locale,
        "scale_mode": scale_mode,
        "variant": variant,
        "expected_status": expected_status,
        "expected_reason_codes": expected_reason_codes,
        "expected_axis_region": [
            AXIS_LEFT,
            0,
            IMAGE_WIDTH,
            IMAGE_HEIGHT,
        ],
        "expected_plot_right_pixel": PLOT_RIGHT,
        "ground_truth_ticks": ticks,
        "tick_metric_eligible": variant in {"VALID", "CROPPED"},
        "outcome_data_used": False,
    }


def build_fixture_manifest(
    contract: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    fixtures: list[dict[str, Any]] = []
    timeframes = ["M5", "M15", "H1", "H4"]
    index = 0

    for pair in ("GBPUSD", "XAUUSD"):
        for platform in ("TRADINGVIEW", "MT5"):
            for theme in ("LIGHT", "DARK", "CUSTOM"):
                for locale in ("DOT_DECIMAL", "COMMA_DECIMAL"):
                    timeframe = timeframes[index % len(timeframes)]
                    fixture_id = "_".join(
                        (
                            "SYN",
                            pair,
                            platform,
                            theme,
                            locale,
                            timeframe,
                        )
                    )
                    fixtures.append(
                        _fixture_entry(
                            output_dir=output_dir,
                            fixture_id=fixture_id,
                            pair=pair,
                            timeframe=timeframe,
                            platform=platform,
                            theme=theme,
                            locale=locale,
                            variant="VALID",
                        )
                    )
                    index += 1

    negative_specs = [
        ("GBPUSD", "TRADINGVIEW", "LIGHT", "CROPPED"),
        ("GBPUSD", "MT5", "DARK", "CROPPED"),
        ("XAUUSD", "TRADINGVIEW", "CUSTOM", "CROPPED"),
        ("XAUUSD", "MT5", "LIGHT", "CROPPED"),
        ("GBPUSD", "TRADINGVIEW", "DARK", "PERCENT"),
        ("XAUUSD", "MT5", "CUSTOM", "PERCENT"),
        ("GBPUSD", "MT5", "CUSTOM", "LOG"),
        ("XAUUSD", "TRADINGVIEW", "LIGHT", "LOG"),
    ]
    for offset, (pair, platform, theme, variant) in enumerate(negative_specs):
        locale = "DOT_DECIMAL" if offset % 2 == 0 else "COMMA_DECIMAL"
        timeframe = timeframes[(index + offset) % len(timeframes)]
        fixture_id = "_".join(
            (
                "SYN_NEGATIVE",
                pair,
                platform,
                theme,
                variant,
                timeframe,
            )
        )
        fixtures.append(
            _fixture_entry(
                output_dir=output_dir,
                fixture_id=fixture_id,
                pair=pair,
                timeframe=timeframe,
                platform=platform,
                theme=theme,
                locale=locale,
                variant=variant,
            )
        )

    fixture_contract = contract["fixture_contract"]
    return {
        "schema_version": fixture_contract["manifest_schema_version"],
        "experiment_id": "E2.4.1",
        "fixture_set_id": "E2_4_1_SYNTHETIC_BASELINE_V1",
        "generator_version": GENERATOR_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixture_root": ".",
        "trading_outcome_data_used": False,
        "production_decision_changed": False,
        "fixtures": fixtures,
    }


def run(args: argparse.Namespace) -> Path:
    contract = read_json(args.contract)
    errors = validate_contract(contract)
    if errors:
        raise ValueError("Contract E2.4.1 INVALID: " + "; ".join(errors))

    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / "e2_4_1_fixture_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(
            "Manifest fixture sudah ada. Gunakan output directory baru: "
            f"{manifest_path}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_fixture_manifest(contract, output_dir)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Fixtures: {len(manifest['fixtures'])}")
    print(f"Manifest: {manifest_path}")
    print(f"Images: {output_dir / 'images'}")
    return manifest_path


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
