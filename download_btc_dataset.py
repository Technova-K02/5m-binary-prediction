#!/usr/bin/env python3
"""
Download high-frequency (1-minute) BTC price data from Binance from 2017 to now.
Structured for 5-minute price prediction: each row has OHLCV + optional target (price 5 min later).

Note: Free APIs do not offer true per-second history. This uses 1-minute candles (best free
granularity). For 5-min prediction, use 5 consecutive 1m bars as input and the next 5m close as target.
"""

import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import pandas as pd
import numpy as np


# Binance allows 1000 klines per request for 1m interval
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BATCH_SIZE = 1000  # max per request
RATE_LIMIT_DELAY = 0.2  # seconds between requests to avoid 429
MAX_RETRIES = 5
RETRY_DELAY = 5

# Binance BTCUSDT available from late 2017
DEFAULT_START = "2017-08-17"


def fetch_klines(symbol: str, interval: str, start_ts: int, end_ts: int) -> list:
    """Fetch one batch of klines with retries."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ts,
        "endTime": end_ts,
        "limit": BATCH_SIZE,
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(BINANCE_KLINES_URL, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            raise RuntimeError(f"Failed to fetch klines after {MAX_RETRIES} attempts: {e}") from e
    return []


def download_btc_1m(
    start_date: str = DEFAULT_START,
    end_date: Optional[str] = None,
    symbol: str = "BTCUSDT",
    interval: str = "1m",
) -> pd.DataFrame:
    """
    Download 1-minute OHLCV from Binance from start_date to end_date (default: now).
    Returns DataFrame with columns: timestamp_utc, open, high, low, close, volume.
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ts = int(start_dt.timestamp() * 1000)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_ts = int(end_dt.timestamp() * 1000)
    else:
        end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)

    rows = []
    current_start = start_ts

    while current_start < end_ts:
        batch = fetch_klines(symbol, interval, current_start, end_ts)
        if not batch:
            break
        for k in batch:
            # Binance kline: [open_time, open, high, low, close, volume, close_time, ...]
            rows.append({
                "timestamp_utc": datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
        # Next batch: start after last candle's close time
        current_start = batch[-1][6] + 1
        time.sleep(RATE_LIMIT_DELAY)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(subset=["timestamp_utc"]).sort_values("timestamp_utc").reset_index(drop=True)
    return df


def add_5min_target(df: pd.DataFrame) -> pd.DataFrame:
    """Add column 'close_5m_later' for 5-minute-ahead prediction target."""
    if df.empty or len(df) < 2:
        return df
    df = df.copy()
    df["close_5m_later"] = df["close"].shift(-5)
    return df


def main():
    parser = argparse.ArgumentParser(description="Download BTC 1m dataset for 5-min prediction (2017–now).")
    parser.add_argument("--start", default=DEFAULT_START, help=f"Start date YYYY-MM-DD (default: {DEFAULT_START})")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--output-dir", default=".", type=Path, help="Output directory for CSV/Parquet")
    parser.add_argument("--format", choices=["csv", "parquet", "both"], default="both", help="Output format")
    parser.add_argument("--no-target", action="store_true", help="Do not add close_5m_later column")
    args = parser.parse_args()

    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading BTC 1m data from {args.start} to {args.end or 'now'}...")
    df = download_btc_1m(start_date=args.start, end_date=args.end)
    if df.empty:
        raise SystemExit("No data returned. Check dates and network.")

    if not args.no_target:
        df = add_5min_target(df)
        # Drop last 5 rows which have NaN target (only if we have enough rows)
        if len(df) > 5:
            df = df.iloc[:-5].copy()
        else:
            df = df.dropna(subset=["close_5m_later"]).copy()

    print(f"Downloaded {len(df):,} rows.")

    base = args.output_dir / "btc_1m_5min_prediction"
    if args.format in ("csv", "both"):
        path_csv = base.with_suffix(".csv")
        df.to_csv(path_csv, index=False)
        print(f"Saved CSV: {path_csv}")
    if args.format in ("parquet", "both"):
        try:
            path_pq = base.with_suffix(".parquet")
            df.to_parquet(path_pq, index=False)
            print(f"Saved Parquet: {path_pq}")
        except ImportError:
            print("Parquet save skipped (install pyarrow for Parquet support).")

    print("Done.")


if __name__ == "__main__":
    main()
