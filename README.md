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

**Using proxies (if Binance is blocked in your region):**

```bash
# Using a proxy file
python download_btc_dataset.py --proxy-file proxies.txt

# Using command-line proxies
python download_btc_dataset.py --proxy http://proxy1.com:8080 --proxy http://proxy2.com:3128

# Combine with other options
python download_btc_dataset.py --proxy-file proxies.txt --start 2024-01-01 --verbose
```

**Options:**

- `--start YYYY-MM-DD` — Start date (default: 2017-08-17)
- `--end YYYY-MM-DD` — End date (default: today)
- `--output-dir DIR` — Where to save files (default: current directory)
- `--format csv|parquet|both` — Output format (default: both)
- `--no-target` — Do not add `close_5m_later` column
- `--proxy-file FILE` — File containing proxy list (one per line)
- `--proxy URL` — Single proxy URL (can be used multiple times)
- `--verbose` or `-v` — Enable detailed debug logging

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


## Troubleshooting

### HTTP 451 Error (Binance API Blocked)

If you see "451 Client Error", Binance API is blocked in your region. Solutions:

1. **Use proxies** (recommended):
   - Create a `proxies.txt` file with one proxy per line (see `proxies.txt.example`)
   - Get free proxies from proxy-list.download, free-proxy-list.net, or proxyscrape.com
   - Run: `python download_btc_dataset.py --proxy-file proxies.txt`

2. **Use a VPN** to connect from a different region

3. **Use paid proxy services** for better reliability (Bright Data, Smartproxy, Oxylabs)

### Proxy Format

Proxies should be in the format:
- `http://host:port`
- `http://username:password@host:port`
- `socks5://host:port` (requires `requests[socks]`)
