from pathlib import Path
import pandas as pd

BASE_DIR = Path("ai/datasets/raw/ohlcv")
OUTPUT_DIR = Path("ai/datasets/metadata")
OUTPUT_FILE = OUTPUT_DIR / "ohlcv_validation_report.csv"

EXPECTED_COLUMNS = [
    "<DATE>",
    "<TIME>",
    "<OPEN>",
    "<HIGH>",
    "<LOW>",
    "<CLOSE>",
    "<TICKVOL>",
    "<VOL>",
    "<SPREAD>",
]

TIMEFRAME_MINUTES = {
    "M5": 5,
    "M15": 15,
    "H1": 60,
    "H4": 240,
}


def validate_file(file_path: Path):
    parts = file_path.parts

    # Expected path:
    # ai/datasets/raw/ohlcv/{PAIR}/{TIMEFRAME}/{YEAR}/{FILE}.csv
    pair = file_path.parents[2].name
    timeframe = file_path.parents[1].name
    year = file_path.parents[0].name

    result = {
        "pair": pair,
        "timeframe": timeframe,
        "year": year,
        "file_name": file_path.name,
        "rows": 0,
        "columns_valid": False,
        "date_min": "",
        "date_max": "",
        "missing_ohlc": 0,
        "invalid_ohlc": 0,
        "duplicate_datetime": 0,
        "status": "failed",
        "notes": "",
    }

    try:
        df = pd.read_csv(file_path, sep="\\t")

        result["rows"] = len(df)
        result["columns_valid"] = list(df.columns) == EXPECTED_COLUMNS

        if not result["columns_valid"]:
            result["notes"] = "Invalid column structure"
            return result

        df["datetime"] = pd.to_datetime(
            df["<DATE>"] + " " + df["<TIME>"],
            format="%Y.%m.%d %H:%M:%S",
            errors="coerce",
        )

        result["date_min"] = df["datetime"].min()
        result["date_max"] = df["datetime"].max()

        ohlc_cols = ["<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>"]

        result["missing_ohlc"] = int(df[ohlc_cols].isna().sum().sum())

        invalid_ohlc = df[
            (df["<HIGH>"] < df["<LOW>"])
            | (df["<OPEN>"] <= 0)
            | (df["<HIGH>"] <= 0)
            | (df["<LOW>"] <= 0)
            | (df["<CLOSE>"] <= 0)
        ]

        result["invalid_ohlc"] = len(invalid_ohlc)
        result["duplicate_datetime"] = int(df["datetime"].duplicated().sum())

        if result["rows"] == 0:
            result["status"] = "failed"
            result["notes"] = "Empty file"
        elif result["missing_ohlc"] > 0:
            result["status"] = "warning"
            result["notes"] = "Missing OHLC values"
        elif result["invalid_ohlc"] > 0:
            result["status"] = "warning"
            result["notes"] = "Invalid OHLC values"
        elif result["duplicate_datetime"] > 0:
            result["status"] = "warning"
            result["notes"] = "Duplicate datetime found"
        else:
            result["status"] = "valid"
            result["notes"] = "OK"

    except Exception as e:
        result["status"] = "failed"
        result["notes"] = str(e)

    return result


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(BASE_DIR.rglob("*.csv"))

    if not files:
        print("No CSV files found.")
        return

    reports = []

    for file_path in files:
        print(f"Validating: {file_path}")
        reports.append(validate_file(file_path))

    report_df = pd.DataFrame(reports)
    report_df.to_csv(OUTPUT_FILE, index=False)

    print()
    print("Validation finished.")
    print(f"Total files: {len(files)}")
    print(f"Report saved to: {OUTPUT_FILE}")
    print()
    print(report_df["status"].value_counts())


if __name__ == "__main__":
    main()
