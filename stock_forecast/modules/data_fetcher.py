"""
modules/data_fetcher.py
負責從 yfinance、TWSE/TPEX 與 FinMind 抓取所有所需資料。
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

import config

warnings.filterwarnings("ignore")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}


class StockDataFetcher:
    """抓取台股所需的價格、財務、月營收及法人買賣超資料。"""

    def __init__(self, ticker_id: str) -> None:
        self.ticker_id: str = str(ticker_id).strip()
        self.ticker_symbol: Optional[str] = None
        self.yf_ticker: Optional[yf.Ticker] = None
        self.price_history: pd.DataFrame = pd.DataFrame()
        self.stock_info: dict = {}
        self.company_name: str = self.ticker_id
        self.current_price: Optional[float] = None        # 即時 / 最新收盤價
        self.monthly_revenue: Optional[dict] = None       # keys: monthly_yoy, ytd_yoy
        self.institutional_data: Optional[dict] = None    # 三大法人買賣超
        self.market_type: Optional[str] = None            # 'TWSE' or 'OTC'

    # ── 公開介面 ─────────────────────────────────────────────────────────────

    def fetch_all(self) -> "StockDataFetcher":
        """依序抓取全部資料，回傳 self 以支援鏈式呼叫。"""
        self._fetch_price_data()
        self._fetch_financial_info()
        self._fetch_monthly_revenue()
        self._fetch_institutional_data()
        return self

    # ── 私有：股價 ───────────────────────────────────────────────────────────

    def _fetch_price_data(self) -> None:
        """嘗試 .TW / .TWO 後綴抓取一年歷史股價，並設定即時股價。"""
        for suffix in config.SUFFIXES:
            symbol = f"{self.ticker_id}{suffix}"
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1y")
                if len(hist) >= 30:
                    self.yf_ticker = ticker
                    self.ticker_symbol = symbol
                    self.price_history = hist
                    self.market_type = "TWSE" if suffix == ".TW" else "OTC"
                    self.current_price = float(hist["Close"].iloc[-1])
                    return
            except Exception:
                continue

        raise ValueError(
            f"❌ 無法取得股票代號 {self.ticker_id} 的資料。\n"
            "   請確認代號是否正確（例如 2330、6505），以及網路連線是否正常。"
        )

    # ── 私有：財務資訊 ────────────────────────────────────────────────────────

    def _fetch_financial_info(self) -> None:
        """從 yfinance 取得財務指標，並嘗試更新即時股價。"""
        if self.yf_ticker is None:
            return
        try:
            info = self.yf_ticker.info or {}
            self.stock_info = info
            self.company_name = (
                info.get("longName") or info.get("shortName") or self.ticker_id
            )
            # 嘗試取得更即時的報價（currentPrice > regularMarketPrice > 歷史收盤）
            rt_price = info.get("currentPrice") or info.get("regularMarketPrice")
            if rt_price and float(rt_price) > 0:
                self.current_price = float(rt_price)
        except Exception:
            self.stock_info = {}

    # ── 私有：月營收 ──────────────────────────────────────────────────────────

    def _fetch_monthly_revenue(self) -> None:
        """先嘗試 MOPS，失敗再嘗試 FinMind。"""
        try:
            result = self._get_mops_revenue()
            if result:
                self.monthly_revenue = result
                return
        except Exception:
            pass

        try:
            result = self._get_finmind_revenue()
            if result:
                self.monthly_revenue = result
                return
        except Exception:
            pass

        self.monthly_revenue = None

    def _get_mops_revenue(self) -> Optional[dict]:
        """
        向 MOPS 查詢月營收，依序嘗試近 3 個月 × 上市/上櫃 共 6 次。
        回傳 dict(monthly_yoy, ytd_yoy) 或 None。
        """
        now = datetime.now()

        months_to_try: list[tuple[int, int]] = []
        for offset in range(1, 4):
            month = now.month - offset
            year  = now.year
            while month <= 0:
                month += 12
                year  -= 1
            months_to_try.append((year - 1911, month))

        urls = [config.MOPS_TWSE_URL, config.MOPS_OTC_URL]

        for roc_year, month in months_to_try:
            for url in urls:
                result = self._fetch_single_month(url, roc_year, month)
                if result:
                    return result
        return None

    def _fetch_single_month(
        self, url: str, roc_year: int, month: int
    ) -> Optional[dict]:
        """POST 單月查詢並解析 HTML 表格。"""
        headers = {
            "User-Agent": _HEADERS["User-Agent"],
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://mops.twse.com.tw/",
        }
        payload = {
            "encodeURIComponent": "1",
            "step": "1",
            "firstin": "1",
            "off": "1",
            "queryName": "co_id",
            "inpuType": "co_id",
            "co_id": self.ticker_id,
            "year": str(roc_year),
            "month": str(month).zfill(2),
        }
        try:
            resp = requests.post(
                url, data=payload, headers=headers, timeout=config.MOPS_TIMEOUT
            )
            if resp.status_code != 200:
                return None
            if "查無資料" in resp.text or len(resp.text) < 500:
                return None

            tables = pd.read_html(StringIO(resp.text), thousands=",")
            for df in tables:
                result = self._parse_revenue_table(df)
                if result:
                    return result
        except Exception:
            pass
        return None

    def _parse_revenue_table(self, df: pd.DataFrame) -> Optional[dict]:
        """從 MOPS HTML 表格解析 YoY 數值。"""
        try:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [
                    " ".join(str(c) for c in col if "Unnamed" not in str(c)).strip()
                    for col in df.columns
                ]
            df.columns = [str(c).strip() for c in df.columns]

            code_col = next(
                (c for c in df.columns if "代號" in c or "代碼" in c), None
            )
            if code_col is None:
                return None

            df[code_col] = df[code_col].astype(str).str.strip()
            row = df[df[code_col] == self.ticker_id]
            if row.empty:
                return None

            def _extract(keywords: list[str]) -> Optional[float]:
                col = next(
                    (c for c in df.columns if all(k in c for k in keywords)), None
                )
                if col is None:
                    return None
                try:
                    val = str(row[col].iloc[0]).replace(",", "").replace("%", "").strip()
                    return float(val)
                except (ValueError, TypeError):
                    return None

            monthly_yoy = _extract(["去年同月增減"])
            ytd_yoy = _extract(["前期比較增減"])

            if monthly_yoy is None:
                return None

            return {
                "monthly_yoy": monthly_yoy,
                "ytd_yoy": ytd_yoy,
            }
        except Exception:
            return None

    # ── FinMind 月營收備援 ────────────────────────────────────────────────────

    def _get_finmind_revenue(self) -> Optional[dict]:
        """
        透過 FinMind API 取得月營收並計算 YoY（MOPS 失敗時的備援）。
        資料集：TaiwanStockMonthRevenue（免費，600 次/小時）
        """
        start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        params = {
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": self.ticker_id,
            "start_date": start_date,
        }
        try:
            resp = requests.get(
                config.FINMIND_URL,
                params=params,
                headers=_HEADERS,
                timeout=config.FINMIND_TIMEOUT,
            )
            if resp.status_code != 200:
                return None
            js = resp.json()
            if js.get("status") != 200 or not js.get("data"):
                return None

            df = pd.DataFrame(js["data"])
            df["revenue_year"]  = df["revenue_year"].astype(int)
            df["revenue_month"] = df["revenue_month"].astype(int)
            df["revenue"]       = pd.to_numeric(df["revenue"], errors="coerce")
            df = df.dropna(subset=["revenue"]).sort_values(
                ["revenue_year", "revenue_month"]
            )

            if df.empty:
                return None

            # 最新一筆
            latest  = df.iloc[-1]
            ly, lm  = int(latest["revenue_year"]), int(latest["revenue_month"])
            cur_rev = float(latest["revenue"])

            # 去年同月
            prev_row = df[
                (df["revenue_year"] == ly - 1) & (df["revenue_month"] == lm)
            ]
            if prev_row.empty:
                return None
            prev_rev = float(prev_row.iloc[-1]["revenue"])
            if prev_rev == 0:
                return None

            monthly_yoy = (cur_rev / prev_rev - 1) * 100

            # 累計 YoY（今年 1 月至最新月 vs 去年同期）
            ytd_yoy: Optional[float] = None
            cur_ytd  = df[
                (df["revenue_year"] == ly) & (df["revenue_month"] <= lm)
            ]["revenue"].sum()
            prev_ytd = df[
                (df["revenue_year"] == ly - 1) & (df["revenue_month"] <= lm)
            ]["revenue"].sum()
            if prev_ytd > 0:
                ytd_yoy = (cur_ytd / prev_ytd - 1) * 100

            return {
                "monthly_yoy": monthly_yoy,
                "ytd_yoy":     ytd_yoy,
                "source":      "FinMind",
                "period":      f"{ly}/{lm:02d}",
            }
        except Exception:
            return None

    # ── 三大法人買賣超 ────────────────────────────────────────────────────────

    def _fetch_institutional_data(self) -> None:
        """嘗試從 TWSE/TPEX 抓取近期三大法人買賣超，失敗則嘗試 FinMind。"""
        today = datetime.now()
        for days_back in range(0, 8):
            date = today - timedelta(days=days_back)
            if date.weekday() >= 5:    # 跳過週末
                continue
            date_str = date.strftime("%Y%m%d")

            if self.market_type == "TWSE":
                result = self._fetch_twse_3insti(date_str)
            else:
                result = self._fetch_tpex_3insti(date_str)

            if result:
                self.institutional_data = result
                return

        # 備援：FinMind（TWSE/TPEX 均失敗時）
        try:
            result = self._fetch_finmind_3insti()
            if result:
                self.institutional_data = result
                return
        except Exception:
            pass

        self.institutional_data = None

    def _fetch_twse_3insti(self, date_str: str) -> Optional[dict]:
        """TWSE T86 三大法人買賣超（上市股票）。"""
        params = {
            "date": date_str,
            "selectType": "ALLBUT0999",
            "response": "json",
        }
        try:
            resp = requests.get(
                config.TWSE_3INSTI_URL,
                params=params,
                headers=_HEADERS,
                timeout=config.INSTI_TIMEOUT,
            )
            if resp.status_code != 200:
                return None
            js = resp.json()
            if js.get("stat") != "OK":
                return None

            fields = js.get("fields", [])
            rows   = js.get("data", [])

            def _fi(keywords: list[str]) -> int:
                for i, f in enumerate(fields):
                    if all(k in f for k in keywords):
                        return i
                return -1

            idx_foreign = _fi(["外陸資", "買賣超"])
            idx_trust   = _fi(["投信",   "買賣超"])
            idx_dealer  = _fi(["自營商", "買賣超股數"])
            # 退回 TWSE T86 固定欄位索引
            if idx_foreign < 0: idx_foreign = 4
            if idx_trust   < 0: idx_trust   = 7
            if idx_dealer  < 0: idx_dealer  = 8

            for row in rows:
                if str(row[0]).strip() != self.ticker_id:
                    continue
                return self._parse_insti_row(
                    row, idx_foreign, idx_trust, idx_dealer, date_str, "TWSE"
                )
        except Exception:
            pass
        return None

    def _fetch_tpex_3insti(self, date_str: str) -> Optional[dict]:
        """TPEX 三大法人買賣超（上櫃股票）。"""
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            roc_date = f"{dt.year - 1911}/{dt.month:02d}/{dt.day:02d}"
        except Exception:
            roc_date = ""

        params: dict = {
            "l": "zh-tw",
            "t": "D",
            "se": "EW",
            "stock": self.ticker_id,
            "o": "json",
            "s": "0,asc",
        }
        if roc_date:
            params["d"] = roc_date

        try:
            resp = requests.get(
                config.TPEX_3INSTI_URL,
                params=params,
                headers=_HEADERS,
                timeout=config.INSTI_TIMEOUT,
            )
            if resp.status_code != 200:
                return None
            js = resp.json()
            rows = js.get("aaData") or js.get("data") or []
            if not rows:
                return None
            return self._parse_tpex_insti_row(rows[0], date_str)
        except Exception:
            pass
        return None

    def _parse_insti_row(
        self,
        row: list,
        idx_foreign: int,
        idx_trust: int,
        idx_dealer: int,
        date_str: str,
        source: str,
    ) -> Optional[dict]:
        """解析 TWSE T86 中的單列資料為結構化 dict。"""
        def _num(idx: int) -> int:
            try:
                val = str(row[idx]).replace(",", "").replace(" ", "").strip()
                val = val.replace("－", "-").replace("−", "-")
                return int(float(val))
            except Exception:
                return 0

        foreign = _num(idx_foreign)
        trust   = _num(idx_trust)
        dealer  = _num(idx_dealer)
        total   = foreign + trust + dealer

        return {
            "date":    date_str,
            "source":  source,
            "foreign": foreign,
            "trust":   trust,
            "dealer":  dealer,
            "total":   total,
        }

    def _parse_tpex_insti_row(self, row: list, date_str: str) -> Optional[dict]:
        """
        解析 TPEX aaData 單列。
        欄位依序：代號, 名稱, 外資買超(千股), 外資買超(千元),
                  投信買超(千股), 投信買超(千元), 自營商買超(千股), 合計買超(千股)
        千股 × 1000 = 股。
        """
        def _num(idx: int, mul: int = 1) -> int:
            try:
                if idx >= len(row):
                    return 0
                val = str(row[idx]).replace(",", "").replace(" ", "").strip()
                val = val.replace("－", "-").replace("−", "-")
                return int(float(val)) * mul
            except Exception:
                return 0

        n = len(row)
        if n >= 9:
            foreign = _num(2, 1000)
            trust   = _num(4, 1000)
            dealer  = _num(6, 1000)
            total   = _num(8, 1000)
        elif n >= 6:
            foreign = _num(2)
            trust   = _num(3)
            dealer  = _num(4)
            total   = _num(5)
        else:
            return None

        return {
            "date":    date_str,
            "source":  "TPEX",
            "foreign": foreign,
            "trust":   trust,
            "dealer":  dealer,
            "total":   total,
        }

    # ── FinMind 三大法人備援 ──────────────────────────────────────────────────

    def _fetch_finmind_3insti(self) -> Optional[dict]:
        """
        透過 FinMind API 取得最新一日三大法人買賣超（TWSE/TPEX 失敗時備援）。
        資料集：TaiwanStockInstitutionalInvestorsBuySell
        """
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": self.ticker_id,
            "start_date": start_date,
        }
        try:
            resp = requests.get(
                config.FINMIND_URL,
                params=params,
                headers=_HEADERS,
                timeout=config.FINMIND_TIMEOUT,
            )
            if resp.status_code != 200:
                return None
            js = resp.json()
            if js.get("status") != 200 or not js.get("data"):
                return None

            df = pd.DataFrame(js["data"])
            if df.empty or "name" not in df.columns:
                return None

            latest_date = df["date"].max()
            df_day = df[df["date"] == latest_date]

            name_map = {
                "Foreign_Investor": "foreign",
                "Investment_Trust": "trust",
                "Dealer":           "dealer",
                "外資":              "foreign",
                "投信":              "trust",
                "自營商":            "dealer",
            }

            result: dict = {"foreign": 0, "trust": 0, "dealer": 0}
            for _, r in df_day.iterrows():
                key = name_map.get(str(r.get("name", "")))
                if key:
                    buy  = int(r.get("buy",  0) or 0)
                    sell = int(r.get("sell", 0) or 0)
                    result[key] = buy - sell

            result["total"]  = result["foreign"] + result["trust"] + result["dealer"]
            result["date"]   = str(latest_date)
            result["source"] = "FinMind"
            return result
        except Exception:
            return None

