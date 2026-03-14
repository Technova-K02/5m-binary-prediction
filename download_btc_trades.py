#!/usr/bin/env python3
"""
Download historical trade data from Binance public data.
Trade-by-trade data is more granular than second-level OHLCV.

Binance provides monthly ZIP files with all trades.
Available at: https://data.binance.vision/
"""

import logging
import argparse
import requests
from pathlib import Path
from datetime import datetime, timedelta
import zipfile
import io
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Binance public data URLs
BASE_URL = "https://data.binance.vision/data/spot/monthly/trades"


def get_available_months(symbol: str, start_year: int = 2023, end_date: datetime = None):
    """Generate list of year-month combinations to download."""
    if end_date is None:
        end_date = datetime.now()
    
    months = []
    current = datetime(start_year, 1, 1)
    
    while current <= end_date:
        months.append((current.year, current.month))
        # Move to next month
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)
    
    return months


def download_month_trades(symbol: str, year: int, month: int, output_dir: Path) -> bool:
    """Download trades for a specific month."""
    # Format: BTCUSDT-trades-2024-01.zip
    filename = f"{symbol}-trades-{year:04d}-{month:02d}.zip"
    url = f"{BASE_URL}/{symbol}/{filename}"
    
    logger.info(f"Downloading {filename}...")
    
    try:
        response = requests.get(url, timeout=300)
        
        if response.status_code == 404:
            logger.warning(f"File not found: {filename} (may not be available yet)")
            return False
        
        response.raise_for_status()
        
        # Extract ZIP in memory
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # Should contain one CSV file
            csv_files = [f for f in z.namelist() if f.endswith('.csv')]
            if not csv_files:
                logger.error(f"No CSV file found in {filename}")
                return False
            
            csv_filename = csv_files[0]
            logger.info(f"Extracting {csv_filename}...")
            
            # Read CSV
            with z.open(csv_filename) as f:
                df = pd.read_csv(f, names=[
                    'trade_id', 'price', 'quantity', 'quote_quantity',
                    'timestamp', 'is_buyer_maker', 'is_best_match'
                ])
            
            # Convert timestamp to datetime
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Save to output directory
            output_file = output_dir / f"{symbol}_trades_{year:04d}_{month:02d}.csv"
            df.to_csv(output_file, index=False)
            
            logger.info(f"Saved {len(df):,} trades to {output_file}")
            logger.info(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            
            return True
            
    except requests.RequestException as e:
        logger.error(f"Failed to download {filename}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error processing {filename}: {e}")
        return False


def aggregate_to_seconds(trades_file: Path, output_file: Path):
    """Aggregate trade data to second-level OHLCV."""
    logger.info(f"Aggregating {trades_file} to second-level OHLCV...")
    
    df = pd.read_csv(trades_file)
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Round to seconds
    df['second'] = df['datetime'].dt.floor('S')
    
    # Aggregate to OHLCV per second
    ohlcv = df.groupby('second').agg({
        'price': ['first', 'max', 'min', 'last'],
        'quantity': 'sum',
        'trade_id': 'count'
    }).reset_index()
    
    # Flatten column names
    ohlcv.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'num_trades']
    
    ohlcv.to_csv(output_file, index=False)
    logger.info(f"Saved {len(ohlcv):,} seconds of OHLCV to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Download Binance historical trade data (trade-by-trade)."
    )
    parser.add_argument(
        "--symbol", 
        default="BTCUSDT", 
        help="Trading pair symbol (default: BTCUSDT)"
    )
    parser.add_argument(
        "--start-year", 
        type=int, 
        default=2023, 
        help="Start year (default: 2023)"
    )
    parser.add_argument(
        "--start-month",
        type=int,
        default=1,
        help="Start month (default: 1)"
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
        help="End year (default: current year)"
    )
    parser.add_argument(
        "--end-month",
        type=int,
        default=None,
        help="End month (default: current month)"
    )
    parser.add_argument(
        "--output-dir", 
        type=Path, 
        default="trades_data",
        help="Output directory (default: trades_data)"
    )
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="Also create second-level OHLCV aggregations"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine end date
    if args.end_year and args.end_month:
        end_date = datetime(args.end_year, args.end_month, 1)
    else:
        end_date = datetime.now()
    
    start_date = datetime(args.start_year, args.start_month, 1)
    
    logger.info(f"Downloading {args.symbol} trades from {start_date.strftime('%Y-%m')} to {end_date.strftime('%Y-%m')}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info("")
    logger.info("Note: Binance provides monthly files. Recent months may not be available yet.")
    logger.info("Typically, data is available up to 1-2 months ago.")
    logger.info("")
    
    # Get list of months to download
    months = get_available_months(args.symbol, args.start_year, end_date)
    
    # Filter by start month
    months = [(y, m) for y, m in months if datetime(y, m, 1) >= start_date]
    
    logger.info(f"Will attempt to download {len(months)} monthly files...")
    
    successful = 0
    failed = 0
    
    for year, month in months:
        if download_month_trades(args.symbol, year, month, args.output_dir):
            successful += 1
            
            # Optionally aggregate to seconds
            if args.aggregate:
                trades_file = args.output_dir / f"{args.symbol}_trades_{year:04d}_{month:02d}.csv"
                ohlcv_file = args.output_dir / f"{args.symbol}_ohlcv_1s_{year:04d}_{month:02d}.csv"
                try:
                    aggregate_to_seconds(trades_file, ohlcv_file)
                except Exception as e:
                    logger.error(f"Failed to aggregate {trades_file}: {e}")
        else:
            failed += 1
    
    logger.info("")
    logger.info(f"Download complete!")
    logger.info(f"Successful: {successful} files")
    logger.info(f"Failed/Not available: {failed} files")
    
    if successful > 0:
        logger.info("")
        logger.info("Trade data columns:")
        logger.info("  - trade_id: Unique trade identifier")
        logger.info("  - price: Trade price")
        logger.info("  - quantity: Trade quantity (in base asset)")
        logger.info("  - quote_quantity: Trade quantity (in quote asset)")
        logger.info("  - timestamp: Unix timestamp in milliseconds")
        logger.info("  - datetime: Human-readable timestamp")
        logger.info("  - is_buyer_maker: True if buyer is maker")
        logger.info("  - is_best_match: True if trade is best price match")


if __name__ == "__main__":
    main()
