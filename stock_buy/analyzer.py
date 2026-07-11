"""
analyzer.py — 股票技術分析引擎

評分系統 (總分 12 分，6 項指標各 2 分):
  1. RSI (相對強弱指標)    — 超賣買入機會
  2. MACD                  — 黃金交叉多頭信號
  3. 均線排列 (MA20/MA60)  — 趨勢方向確認
  4. 成交量分析            — 量能支撐
  5. KD 隨機指標           — 超賣反彈信號
  6. 布林通道              — 跌破下軌機會

評分建議:
  🔥 10-12 強力買入
  📈  7-9  建議買入
  👀  5-6  值得關注
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands

logger = logging.getLogger(__name__)


def _calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算所有技術指標並附加到 DataFrame。"""
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # RSI (14日)
    df["rsi"] = RSIIndicator(close=close, window=14).rsi()

    # MACD (12, 26, 9)
    macd_ind = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd_ind.macd()
    df["macd_signal"] = macd_ind.macd_signal()

    # 簡單移動平均線
    df["sma20"] = SMAIndicator(close=close, window=20).sma_indicator()
    df["sma60"] = SMAIndicator(close=close, window=60).sma_indicator()

    # 布林通道 (20日, 2倍標準差)
    bb = BollingerBands(close=close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()

    # KD 隨機指標 (14, 3)
    stoch = StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # 20日均量
    df["vol_ma20"] = df["Volume"].rolling(window=20).mean()

    return df


def _score_stock(df: pd.DataFrame, settings: dict) -> dict:
    """
    根據技術指標對股票評分。
    回傳 {'score': int, 'signals': list[str]}
    """
    if len(df) < 2:
        return {"score": 0, "signals": []}

    score = 0
    signals = []

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(latest["Close"])

    # ── 1. RSI 分析 (0-2 分) ──────────────────────────────
    rsi = latest["rsi"]
    if pd.notna(rsi):
        rsi = float(rsi)
        if rsi < settings["rsi_oversold"]:
            score += 2
            signals.append(f"RSI超賣({rsi:.1f})")
        elif rsi < settings["rsi_low"]:
            score += 1
            signals.append(f"RSI偏低({rsi:.1f})")

    # ── 2. MACD 分析 (0-2 分) ─────────────────────────────
    macd = latest["macd"]
    macd_sig = latest["macd_signal"]
    prev_macd = prev["macd"]
    prev_macd_sig = prev["macd_signal"]

    if all(pd.notna(v) for v in [macd, macd_sig, prev_macd, prev_macd_sig]):
        macd, macd_sig = float(macd), float(macd_sig)
        prev_macd, prev_macd_sig = float(prev_macd), float(prev_macd_sig)
        if prev_macd < prev_macd_sig and macd > macd_sig:
            score += 2
            signals.append("MACD黃金交叉")
        elif macd > macd_sig:
            score += 1
            signals.append("MACD多頭")

    # ── 3. 均線排列分析 (0-2 分) ──────────────────────────
    sma20 = latest["sma20"]
    sma60 = latest["sma60"]

    if pd.notna(sma20) and pd.notna(sma60):
        sma20, sma60 = float(sma20), float(sma60)
        if close > sma20 and sma20 > sma60:
            score += 2
            signals.append("均線多頭排列")
        elif close > sma20:
            score += 1
            signals.append("站上MA20")

    # ── 4. 成交量分析 (0-2 分) ────────────────────────────
    vol = float(latest["Volume"])
    vol_ma = latest["vol_ma20"]

    if pd.notna(vol_ma) and float(vol_ma) > 0:
        ratio = vol / float(vol_ma)
        if ratio >= settings["volume_surge"]:
            score += 2
            signals.append(f"爆量({ratio:.1f}x)")
        elif ratio >= settings["volume_increase"]:
            score += 1
            signals.append(f"量增({ratio:.1f}x)")

    # ── 5. KD 隨機指標分析 (0-2 分) ──────────────────────
    k = latest["stoch_k"]
    d = latest["stoch_d"]
    prev_k = prev["stoch_k"]
    prev_d = prev["stoch_d"]

    if all(pd.notna(v) for v in [k, d, prev_k, prev_d]):
        k, d = float(k), float(d)
        prev_k, prev_d = float(prev_k), float(prev_d)
        if k < 20 and prev_k <= prev_d and k > d:
            score += 2
            signals.append(f"KD超賣交叉(K={k:.1f})")
        elif k < 30:
            score += 1
            signals.append(f"KD超賣(K={k:.1f})")

    # ── 6. 布林通道分析 (0-2 分) ──────────────────────────
    bb_lower = latest["bb_lower"]
    bb_upper = latest["bb_upper"]

    if pd.notna(bb_lower):
        bb_lower = float(bb_lower)
        if close < bb_lower:
            score += 2
            signals.append("跌破布林下軌")
        elif pd.notna(bb_upper):
            bb_upper = float(bb_upper)
            band_width = bb_upper - bb_lower
            if band_width > 0:
                bb_pos = (close - bb_lower) / band_width
                if bb_pos < 0.25:
                    score += 1
                    signals.append("接近布林下軌")

    return {"score": score, "signals": signals}


def _extract_ticker_df(raw_data: pd.DataFrame, ticker: str, n_tickers: int) -> Optional[pd.DataFrame]:
    """從 yfinance 下載結果中擷取單一股票的 OHLCV DataFrame。"""
    if n_tickers == 1:
        return raw_data.copy()

    # 多股票下載 — group_by='ticker' 模式
    try:
        df = raw_data[ticker]
        if isinstance(df, pd.DataFrame) and "Close" in df.columns:
            return df.copy()
    except (KeyError, TypeError):
        pass

    # 備用: MultiIndex xs 方式 (group_by='column' 模式)
    try:
        df = raw_data.xs(ticker, level=1, axis=1)
        if isinstance(df, pd.DataFrame) and "Close" in df.columns:
            return df.copy()
    except (KeyError, TypeError):
        pass

    return None


def analyze_stocks(stocks: Dict[str, str], market: str, settings: dict) -> List[dict]:
    """
    批次分析股票清單，回傳依評分排序的推薦結果。

    Args:
        stocks:   { ticker: 中文名稱 } 字典
        market:   'TW' 或 'US'
        settings: config.SETTINGS 設定

    Returns:
        依評分降序排列的推薦清單 (score >= min_score，最多 max_recommendations 檔)
    """
    results = []
    tickers = list(stocks.keys())

    if not tickers:
        return []

    # ── 批次下載歷史資料 ────────────────────────────────────
    logger.info(f"[{market}] 下載 {len(tickers)} 檔股票資料中...")
    try:
        raw_data = yf.download(
            tickers if len(tickers) > 1 else tickers[0],
            period=settings["data_period"],
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
    except Exception as exc:
        logger.error(f"[{market}] 資料下載失敗: {exc}")
        return []

    # ── 逐一分析 ────────────────────────────────────────────
    for ticker, name in stocks.items():
        try:
            df = _extract_ticker_df(raw_data, ticker, len(tickers))
            if df is None:
                logger.debug(f"[{market}] {ticker}: 無法取得資料")
                continue

            df = df.dropna(subset=["Close", "Volume"])
            if len(df) < 65:
                logger.debug(f"[{market}] {ticker}: 資料不足 ({len(df)} 筆)")
                continue

            df = _calculate_indicators(df)
            result = _score_stock(df, settings)

            if result["score"] < settings["min_score"]:
                continue

            latest = df.iloc[-1]
            prev_close = float(df.iloc[-2]["Close"])
            price = float(latest["Close"])
            change_pct = (price - prev_close) / prev_close * 100

            rsi_val = latest["rsi"]

            results.append({
                "ticker": ticker,
                "name": name,
                "market": market,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "volume": int(latest["Volume"]),
                "score": result["score"],
                "signals": result["signals"],
                "rsi": round(float(rsi_val), 1) if pd.notna(rsi_val) else None,
            })

        except Exception as exc:
            logger.error(f"[{market}] {ticker} ({name}) 分析失敗: {exc}")
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[: settings["max_recommendations"]]
