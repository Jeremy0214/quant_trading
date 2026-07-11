"""
main.py — 股票投顧主程式

使用方式:
  python main.py           立即執行一次分析並傳送 Discord 推薦
  python scheduler.py      每日定時自動執行 (依 .env 中 SCHEDULE_TIME 設定)

Webhook 設定:
  將你的 Discord Webhook URL 貼入 webhook.txt 即可，一行一個 URL。
  其餘設定 (排程時間、最低評分) 請修改 .env。
"""

import logging
import os
import sys

from dotenv import load_dotenv

from analyzer import analyze_stocks
from config import SETTINGS, TW_STOCKS, US_STOCKS
from discord_notifier import send_discord_recommendations

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _load_webhook_urls() -> list:
    """
    讀取所有 Discord Webhook URL。
    webhook.txt 中每行一個 URL，支援傳送到多個頻道。
    優先順序：webhook.txt > .env 中的 DISCORD_WEBHOOK_URL
    """
    urls = []
    webhook_file = os.path.join(os.path.dirname(__file__), "webhook.txt")
    if os.path.exists(webhook_file):
        with open(webhook_file, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith("#") and not url.startswith("https://discord.com/api/webhooks/YOUR"):
                    urls.append(url)

    # 備用：從環境變數讀取
    if not urls:
        env_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        if env_url:
            urls.append(env_url)

    return urls


def run_analysis() -> bool:
    """執行完整的股票分析流程並傳送 Discord 推薦。回傳是否成功。"""

    webhook_urls = _load_webhook_urls()
    if not webhook_urls:
        logger.error("❌ 尚未設定 Discord Webhook URL！")
        logger.error("   請在 webhook.txt 中貼上你的 Webhook URL（每行一個）。")
        sys.exit(1)

    # 允許透過 .env 覆蓋最低評分門檻
    try:
        min_score = int(os.getenv("MIN_SCORE", SETTINGS["min_score"]))
        SETTINGS["min_score"] = min_score
    except ValueError:
        pass

    logger.info("=" * 55)
    logger.info("  股票投顧分析開始")
    logger.info("=" * 55)

    # 台股分析
    logger.info("📊 分析台股 Top 50 中...")
    tw_results = analyze_stocks(TW_STOCKS, market="TW", settings=SETTINGS)
    logger.info(f"   → 符合條件台股：{len(tw_results)} 檔")

    # 美股分析
    logger.info("📊 分析美股 Top 50 中...")
    us_results = analyze_stocks(US_STOCKS, market="US", settings=SETTINGS)
    logger.info(f"   → 符合條件美股：{len(us_results)} 檔")

    # 傳送到所有 Discord Webhook
    logger.info(f"📨 傳送推薦至 {len(webhook_urls)} 個 Discord Webhook...")
    results = [send_discord_recommendations(url, tw_results, us_results) for url in webhook_urls]
    success = all(results)

    if success:
        logger.info("✅ 分析完成，推薦已成功傳送！")
    else:
        failed = sum(1 for r in results if not r)
        logger.error(f"❌ {failed}/{len(webhook_urls)} 個 Webhook 傳送失敗，請確認 URL 是否正確。")

    return success


if __name__ == "__main__":
    run_analysis()
