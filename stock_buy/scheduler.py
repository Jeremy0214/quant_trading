"""
scheduler.py — 每日定時排程執行器

使用方式:
  python scheduler.py

會在啟動時立即執行一次，之後每天依 .env 中 SCHEDULE_TIME 設定的時間自動執行。
預設時間: 09:00 (台灣時間)

按 Ctrl+C 可停止排程。
"""

import logging
import os
import time

import schedule
from dotenv import load_dotenv

from main import run_analysis

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "09:00").strip()


def main():
    logger.info("=" * 55)
    logger.info("  股票投顧排程啟動")
    logger.info(f"  每日執行時間: {SCHEDULE_TIME} (本機時間)")
    logger.info("  按 Ctrl+C 停止排程")
    logger.info("=" * 55)

    # 立即執行一次
    logger.info("▶ 啟動時立即執行一次分析...")
    run_analysis()

    # 設定每日定時任務
    schedule.every().day.at(SCHEDULE_TIME).do(run_analysis)
    logger.info(f"⏰ 已設定每日 {SCHEDULE_TIME} 自動執行")

    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # 每 30 秒檢查一次排程
        except KeyboardInterrupt:
            logger.info("⏹ 排程已停止。")
            break
        except Exception as exc:
            logger.error(f"排程執行錯誤: {exc}")
            time.sleep(60)


if __name__ == "__main__":
    main()
