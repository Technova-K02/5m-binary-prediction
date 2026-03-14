#!/usr/bin/env python3
"""
Download high-frequency (1-minute) BTC price data from Binance from 2017 to now.
Structured for 5-minute price prediction: each row has OHLCV + optional target (price 5 min later).

Note: Free APIs do not offer true per-second history. This uses 1-minute candles (best free
granularity). For 5-min prediction, use 5 consecutive 1m bars as input and the next 5m close as target.
"""

import time
import argparse
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

import requests
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ProxyRotator:
    """Manages proxy rotation for requests."""
    
    def __init__(self, proxy_list: Optional[List[str]] = None):
        self.proxies = proxy_list or []
        self.current_index = 0
        self.failed_proxies = set()
        if self.proxies:
            logger.info(f"Initialized proxy rotator with {len(self.proxies)} proxies")
    
    def get_next_proxy(self) -> Optional[dict]:
        """Get next working proxy in rotation."""
        if not self.proxies:
            return None
        
        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
        if not available_proxies:
            logger.warning("All proxies have failed, resetting failed list")
            self.failed_proxies.clear()
            available_proxies = self.proxies
        
        proxy = available_proxies[self.current_index % len(available_proxies)]
        self.current_index += 1
        
        return {
            'http': proxy,
            'https': proxy
        }
    
    def mark_failed(self, proxy_dict: dict):
        """Mark a proxy as failed."""
        if proxy_dict and 'http' in proxy_dict:
            proxy = proxy_dict['http']
            self.failed_proxies.add(proxy)
            logger.warning(f"Marked proxy as failed: {proxy}")
    
    def get_random_proxy(self) -> Optional[dict]:
        """Get a random working proxy."""
        if not self.proxies:
            return None
        
        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
        if not available_proxies:
            self.failed_proxies.clear()
            available_proxies = self.proxies
        
        proxy = random.choice(available_proxies)
        return {
            'http': proxy,
            'https': proxy
        }


# Binance allows 1000 klines per request for 1m interval
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BATCH_SIZE = 1000  # max per request
RATE_LIMIT_DELAY = 0.2  # seconds between requests to avoid 429
MAX_RETRIES = 5
RETRY_DELAY = 5

# Binance BTCUSDT available from late 2017
DEFAULT_START = "2017-08-17"

# Global proxy rotator instance
proxy_rotator: Optional[ProxyRotator] = None


def fetch_klines(symbol: str, interval: str, start_ts: int, end_ts: int) -> list:
    """Fetch one batch of klines with retries and proxy rotation."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ts,
        "endTime": end_ts,
        "limit": BATCH_SIZE,
    }
    
    current_proxy = None
    for attempt in range(MAX_RETRIES):
        try:
            # Get proxy if rotator is configured
            if proxy_rotator and proxy_rotator.proxies:
                current_proxy = proxy_rotator.get_next_proxy()
                logger.debug(f"Using proxy: {current_proxy.get('http', 'None') if current_proxy else 'None'}")
            
            logger.debug(f"Fetching klines batch (attempt {attempt + 1}/{MAX_RETRIES})")
            r = requests.get(BINANCE_KLINES_URL, params=params, proxies=current_proxy, timeout=30)
            
            # Check for specific error codes
            if r.status_code == 451:
                logger.error("HTTP 451: Binance API is unavailable (possibly blocked in your region)")
                if not proxy_rotator or not proxy_rotator.proxies:
                    logger.error("Possible solutions:")
                    logger.error("  1. Use --proxy-file to specify a list of proxies")
                    logger.error("  2. Use a VPN to access from a different region")
                    logger.error("  3. Try Binance US API if you're in the US")
                # Mark proxy as failed and try next one
                if current_proxy and proxy_rotator:
                    proxy_rotator.mark_failed(current_proxy)
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Trying different proxy...")
                    time.sleep(RETRY_DELAY)
                    continue
                raise RuntimeError("Binance API returned 451 (Unavailable For Legal Reasons). Try using proxies with --proxy-file")
            
            r.raise_for_status()
            
            # Try to parse JSON
            try:
                data = r.json()
            except ValueError as json_err:
                logger.warning(f"JSON decode error (attempt {attempt + 1}/{MAX_RETRIES}): {json_err}")
                logger.debug(f"Response text (first 500 chars): {r.text[:500]}")
                # Mark proxy as failed - likely returning bad data
                if current_proxy and proxy_rotator:
                    proxy_rotator.mark_failed(current_proxy)
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Trying different proxy...")
                    time.sleep(RETRY_DELAY)
                    continue
                raise RuntimeError(f"Failed to parse JSON after {MAX_RETRIES} attempts") from json_err
            
            logger.debug(f"Successfully fetched {len(data)} klines")
            return data
            
        except requests.exceptions.ProxyError as e:
            logger.warning(f"Proxy error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if current_proxy and proxy_rotator:
                proxy_rotator.mark_failed(current_proxy)
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Trying different proxy...")
                time.sleep(RETRY_DELAY)
                continue
            logger.error(f"Failed to fetch klines after {MAX_RETRIES} attempts")
            raise RuntimeError(f"Failed to fetch klines after {MAX_RETRIES} attempts: {e}") from e
        
        except requests.exceptions.Timeout as e:
            logger.warning(f"Request timeout (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if current_proxy and proxy_rotator:
                proxy_rotator.mark_failed(current_proxy)
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Trying different proxy...")
                time.sleep(RETRY_DELAY)
                continue
            logger.error(f"Failed to fetch klines after {MAX_RETRIES} attempts")
            raise RuntimeError(f"Failed to fetch klines after {MAX_RETRIES} attempts: {e}") from e
            
        except requests.RequestException as e:
            logger.warning(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
                continue
            logger.error(f"Failed to fetch klines after {MAX_RETRIES} attempts")
            raise RuntimeError(f"Failed to fetch klines after {MAX_RETRIES} attempts: {e}") from e
    return []


def save_chunk(df: pd.DataFrame, output_dir: Path, chunk_num: int, file_format: str, add_target: bool = True):
    """Save a chunk of data to file."""
    if df.empty:
        return
    
    # Add target if requested
    if add_target:
        df = add_5min_target(df)
        # Drop rows with NaN target
        rows_before = len(df)
        if len(df) > 5:
            df = df.iloc[:-5].copy()
        else:
            df = df.dropna(subset=["close_5m_later"]).copy()
        rows_dropped = rows_before - len(df)
        if rows_dropped > 0:
            logger.info(f"Chunk {chunk_num}: Dropped {rows_dropped} rows with NaN target")
    
    if df.empty:
        logger.warning(f"Chunk {chunk_num} is empty after processing")
        return
    
    # Log date range for this chunk
    start_date = df['timestamp_utc'].iloc[0]
    end_date = df['timestamp_utc'].iloc[-1]
    logger.info(f"Chunk {chunk_num}: {len(df):,} rows from {start_date} to {end_date}")
    
    # Save files
    base = output_dir / f"btc_1m_5min_prediction_chunk_{chunk_num:03d}"
    
    if file_format in ("csv", "both"):
        path_csv = base.with_suffix(".csv")
        df.to_csv(path_csv, index=False)
        logger.info(f"Chunk {chunk_num}: Saved CSV to {path_csv}")
    
    if file_format in ("parquet", "both"):
        try:
            path_pq = base.with_suffix(".parquet")
            df.to_parquet(path_pq, index=False)
            logger.info(f"Chunk {chunk_num}: Saved Parquet to {path_pq}")
        except ImportError:
            logger.warning("Parquet save skipped (install pyarrow for Parquet support)")


def download_btc_1m(
    start_date: str = DEFAULT_START,
    end_date: Optional[str] = None,
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    output_dir: Optional[Path] = None,
    file_format: str = "both",
    chunk_size: int = 500000,
    add_target: bool = True,
) -> pd.DataFrame:
    """
    Download 1-minute OHLCV from Binance from start_date to end_date (default: now).
    Saves data in chunks if output_dir is provided.
    Returns DataFrame with columns: timestamp_utc, open, high, low, close, volume.
    """
    logger.info(f"Starting download for {symbol} with {interval} interval")
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ts = int(start_dt.timestamp() * 1000)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_ts = int(end_dt.timestamp() * 1000)
        logger.info(f"Date range: {start_date} to {end_date}")
    else:
        end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        logger.info(f"Date range: {start_date} to now")

    rows = []
    current_start = start_ts
    batch_count = 0
    chunk_num = 1
    total_saved = 0

    while current_start < end_ts:
        batch = fetch_klines(symbol, interval, current_start, end_ts)
        if not batch:
            logger.warning("Received empty batch, stopping download")
            break
        batch_count += 1
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
        
        # Save chunk if we've reached the chunk size
        if output_dir and len(rows) >= chunk_size:
            df_chunk = pd.DataFrame(rows)
            df_chunk = df_chunk.drop_duplicates(subset=["timestamp_utc"]).sort_values("timestamp_utc").reset_index(drop=True)
            save_chunk(df_chunk, output_dir, chunk_num, file_format, add_target)
            total_saved += len(df_chunk)
            chunk_num += 1
            rows = []  # Clear rows for next chunk
        
        # Next batch: start after last candle's close time
        current_start = batch[-1][6] + 1
        
        if batch_count % 10 == 0:
            logger.info(f"Downloaded {batch_count} batches ({len(rows) + total_saved:,} rows total)")
        
        time.sleep(RATE_LIMIT_DELAY)

    logger.info(f"Completed download: {batch_count} batches")
    
    # Save any remaining rows as final chunk
    if output_dir and rows:
        df_chunk = pd.DataFrame(rows)
        df_chunk = df_chunk.drop_duplicates(subset=["timestamp_utc"]).sort_values("timestamp_utc").reset_index(drop=True)
        save_chunk(df_chunk, output_dir, chunk_num, file_format, add_target)
        total_saved += len(df_chunk)
        rows = []
    
    # Return combined dataframe if not saving chunks
    df = pd.DataFrame(rows)
    if df.empty and total_saved == 0:
        logger.warning("DataFrame is empty after download")
        return df
    
    if not df.empty:
        initial_count = len(df)
        df = df.drop_duplicates(subset=["timestamp_utc"]).sort_values("timestamp_utc").reset_index(drop=True)
        duplicates_removed = initial_count - len(df)
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate rows")
    
    if total_saved > 0:
        logger.info(f"Total rows saved across {chunk_num} chunks: {total_saved:,}")
    
    return df


def add_5min_target(df: pd.DataFrame) -> pd.DataFrame:
    """Add column 'close_5m_later' for 5-minute-ahead prediction target."""
    if df.empty or len(df) < 2:
        logger.warning("DataFrame too small to add 5-minute target")
        return df
    logger.info("Adding 5-minute prediction target column")
    df = df.copy()
    df["close_5m_later"] = df["close"].shift(-5)
    return df


def load_proxies_from_file(filepath: Path) -> List[str]:
    """Load proxy list from file (one proxy per line)."""
    try:
        with open(filepath, 'r') as f:
            proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        logger.info(f"Loaded {len(proxies)} proxies from {filepath}")
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies from {filepath}: {e}")
        return []


def main():
    global proxy_rotator
    
    parser = argparse.ArgumentParser(description="Download BTC 1m dataset for 5-min prediction (2017–now).")
    parser.add_argument("--start", default=DEFAULT_START, help=f"Start date YYYY-MM-DD (default: {DEFAULT_START})")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--output-dir", default=".", type=Path, help="Output directory for CSV/Parquet")
    parser.add_argument("--format", choices=["csv", "parquet", "both"], default="both", help="Output format")
    parser.add_argument("--no-target", action="store_true", help="Do not add close_5m_later column")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose (DEBUG) logging")
    parser.add_argument("--proxy-file", type=Path, help="File containing proxy list (one per line, format: http://host:port)")
    parser.add_argument("--proxy", action="append", help="Single proxy to use (can be specified multiple times)")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Setup proxy rotator
    proxies = []
    if args.proxy_file:
        proxies.extend(load_proxies_from_file(args.proxy_file))
    if args.proxy:
        proxies.extend(args.proxy)
        logger.info(f"Added {len(args.proxy)} proxies from command line")
    
    if proxies:
        proxy_rotator = ProxyRotator(proxies)
    else:
        logger.info("No proxies configured, using direct connection")

    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {args.output_dir}")

    logger.info(f"Downloading BTC 1m data from {args.start} to {args.end or 'now'}...")
    logger.info(f"Data will be saved in chunks of 500,000 rows")
    
    df = download_btc_1m(
        start_date=args.start, 
        end_date=args.end,
        output_dir=args.output_dir,
        file_format=args.format,
        chunk_size=500000,
        add_target=not args.no_target
    )
    
    if df.empty:
        logger.info("All data saved in chunks")
    else:
        logger.info(f"Remaining data in memory: {len(df):,} rows")

    logger.info("Download complete!")


if __name__ == "__main__":
    main()
