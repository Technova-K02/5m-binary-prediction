# BTC 5-Minute Price Prediction Dataset

Downloads **high-frequency (1-minute)** Bitcoin price data from Binance from **2017** until now, structured for **5-minute price prediction**.

## Data granularity

- **Per-second data**: Free public APIs (including Binance) do not provide historical per-second OHLCV. This script uses **1-minute candles**, which is the finest free granularity. Each row is one minute (≈ one "second-like" sample per minute for modeling).
- The dataset is suitable for **5-minute-ahead price prediction**: each row includes `close_5m_later` as the target (close price 5 minutes ahead).

## Setup

```bash
pip install -r requirements.txt
```

## Usage

**Full dataset (2017 to today)** — can take 30–60+ minutes due to API rate limits:

```bash
python download_btc_dataset.py
```

**Custom date range:**

```bash
python download_btc_dataset.py --start 2017-08-17 --end 2025-03-12
```

**Options:**

- `--start YYYY-MM-DD` — Start date (default: 2017-08-17)
- `--end YYYY-MM-DD` — End date (default: today)
- `--output-dir DIR` — Where to save files (default: current directory)
- `--format csv|parquet|both` — Output format (default: both)
- `--no-target` — Do not add `close_5m_later` column

**Quick test (e.g. 2 days):**

```bash
python download_btc_dataset.py --start 2024-01-01 --end 2024-01-02
```

## Output

- **btc_1m_5min_prediction.csv** — Timestamp (UTC), open, high, low, close, volume, close_5m_later
- **btc_1m_5min_prediction.parquet** — Same data in Parquet (if `pyarrow` is installed)

## Requirements

- Python 3.8+
- Internet access (Binance public API, no API key needed)
