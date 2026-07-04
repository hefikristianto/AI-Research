from pathlib import Path
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt

RAW_DIR = Path("ai/datasets/raw/ohlcv")
CHART_DIR = Path("ai/datasets/raw/charts")
METADATA_PATH = Path("ai/datasets/metadata/chart_image_metadata.csv")

WINDOW_SIZE = 100
STEP_SIZE = 100
MAX_IMAGES_PER_FILE = 50

TIMEFRAME_SESSION = {
    "M5": "intraday",
    "M15": "intraday",
    "H1": "intraday",
    "H4": "swing",
}


def prepare_dataframe(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(file_path, sep="\t")

    df["datetime"] = pd.to_datetime(
        df["<DATE>"] + " " + df["<TIME>"],
        format="%Y.%m.%d %H:%M:%S",
        errors="coerce",
    )

    df = df.dropna(subset=["datetime"])

    df = df.rename(
        columns={
            "<OPEN>": "Open",
            "<HIGH>": "High",
            "<LOW>": "Low",
            "<CLOSE>": "Close",
            "<TICKVOL>": "Volume",
        }
    )

    df = df[["datetime", "Open", "High", "Low", "Close", "Volume"]]
    df = df.set_index("datetime")

    return df


def generate_images(file_path: Path):
    year = file_path.parents[0].name
    timeframe = file_path.parents[1].name
    pair = file_path.parents[2].name

    output_dir = CHART_DIR / pair / timeframe / year
    output_dir.mkdir(parents=True, exist_ok=True)

    df = prepare_dataframe(file_path)

    generated = []

    total_rows = len(df)

    if total_rows < WINDOW_SIZE:
        print(f"Skipped {file_path.name}: not enough rows")
        return generated

    image_count = 0

    for start in range(0, total_rows - WINDOW_SIZE, STEP_SIZE):
        if image_count >= MAX_IMAGES_PER_FILE:
            break

        end = start + WINDOW_SIZE
        chunk = df.iloc[start:end]

        start_time = chunk.index[0].strftime("%Y%m%d_%H%M%S")
        image_name = f"{pair.lower()}_{timeframe.lower()}_{year}_{start_time}_{image_count + 1:04d}.png"
        output_path = output_dir / image_name

        mpf.plot(
            chunk,
            type="candle",
            volume=False,
            axisoff=True,
            style="charles",
            savefig=dict(fname=str(output_path), dpi=120, bbox_inches="tight", pad_inches=0),
        )

        generated.append(
            {
                "image_id": image_name.replace(".png", "").upper(),
                "file_name": image_name,
                "pair": pair,
                "timeframe": timeframe,
                "year": year,
                "start_datetime": chunk.index[0],
                "end_datetime": chunk.index[-1],
                "session": TIMEFRAME_SESSION.get(timeframe, "unknown"),
                "news_category": "unclassified",
                "trend": "unclassified",
                "volatility": "unclassified",
                "source": "generated_from_ohlcv",
                "status": "raw_chart",
                "notes": f"Generated from {file_path.name}",
            }
        )

        image_count += 1

    return generated


def main():
    files = sorted(RAW_DIR.rglob("*.csv"))

    metadata_rows = []

    for file_path in files:
        print(f"Generating chart images from: {file_path}")
        rows = generate_images(file_path)
        metadata_rows.extend(rows)

    metadata_df = pd.DataFrame(metadata_rows)

    metadata_df.to_csv(METADATA_PATH, index=False)

    print()
    print("Chart generation finished.")
    print(f"Total generated images: {len(metadata_rows)}")
    print(f"Metadata saved to: {METADATA_PATH}")


if __name__ == "__main__":
    main()
