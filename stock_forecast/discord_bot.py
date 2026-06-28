"""
discord_bot.py ── 台股分析 Discord Bot
執行方式：
    python discord_bot.py

指令範例（在 Discord 頻道輸入）：
    !股票 2330
    !stock 2454
    !s 2330 6505        ← 一次分析多支
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import sys
from contextlib import redirect_stdout

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

# ── 載入 .env / hachi.env ─────────────────────────────────────────────────
load_dotenv("hachi.env")   # 優先讀取 hachi.env
load_dotenv()              # 若存在 .env 則再覆蓋（可選）

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()

# ── 匯入分析核心 ───────────────────────────────────────────────────────────
from main import analyze  # noqa: E402  (需在 load_dotenv 之後)

# ── ANSI 色碼去除（colorama 輸出轉純文字）──────────────────────────────────
_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _capture_analyze(ticker_id: str) -> str:
    """執行 analyze() 並以字串形式回傳終端輸出（已去除 ANSI 色碼）。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        analyze(ticker_id)
    return _strip_ansi(buf.getvalue())


# ── Discord Bot 設定 ───────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True  # 需要在 Developer Portal 開啟 Message Content Intent

# Windows 上 aiodns 會 DNS 逾時，改用 ThreadedResolver（走系統 DNS）
# Connector must be created inside the running event loop to avoid RuntimeError
class StockBot(commands.Bot):
    async def start(self, token: str, *, reconnect: bool = True) -> None:
        self.http.connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        await super().start(token, reconnect=reconnect)

bot = StockBot(command_prefix="!", intents=intents)

# ── 事件 ───────────────────────────────────────────────────────────────────

@bot.event
async def on_ready() -> None:
    print(f"✅ Bot 已上線：{bot.user}  (ID: {bot.user.id})")
    print("   指令前綴：!  |  可用指令：!股票 / !stock / !s")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return  # 忽略未知指令，避免雜訊
    await ctx.send(f"❌ 發生錯誤：{error}")


# ── 主要指令 ───────────────────────────────────────────────────────────────

@bot.command(name="股票", aliases=["stock", "s"])
async def stock_cmd(ctx: commands.Context, *tickers: str) -> None:
    """
    分析台股個股。
    用法：!股票 <代號> [代號2 ...]
    範例：!股票 2330
          !stock 2454 6505
    """
    if not tickers:
        await ctx.send(
            "❌ 請輸入股票代號，例如：\n"
            "`!股票 2330`\n"
            "`!stock 2454 6505`（多支同時查詢）"
        )
        return

    for tid in tickers:
        # 先送出等待訊息
        waiting_msg = await ctx.send(f"⏳ 正在分析 **{tid}**，請稍候…")

        try:
            loop = asyncio.get_event_loop()
            result: str = await loop.run_in_executor(None, _capture_analyze, tid)
        except ValueError as exc:
            await waiting_msg.edit(content=f"❌ 無法分析 **{tid}**：{exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            await waiting_msg.edit(content=f"❌ 分析 **{tid}** 時發生錯誤：{exc}")
            continue

        # 刪除等待訊息
        await waiting_msg.delete()

        # Discord 每則訊息上限 2000 字元；程式碼區塊留些空間
        CHUNK_SIZE = 1900
        chunks = [result[i : i + CHUNK_SIZE] for i in range(0, len(result), CHUNK_SIZE)]
        for chunk in chunks:
            if chunk.strip():
                await ctx.send(f"```\n{chunk}\n```")


@bot.command(name="說明", aliases=["help_tw", "指令"])
async def help_tw(ctx: commands.Context) -> None:
    """顯示指令說明。"""
    embed = discord.Embed(
        title="📈 台股分析 Bot 指令說明",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="查詢個股",
        value=(
            "`!股票 <代號>` — 分析單支股票\n"
            "`!stock <代號>` — 同上（英文別名）\n"
            "`!s <代號1> <代號2>` — 同時查詢多支\n\n"
            "**範例：**\n"
            "`!股票 2330` → 台積電\n"
            "`!s 2330 2454 6505`"
        ),
        inline=False,
    )
    embed.set_footer(text="資料來源：Yahoo Finance / MOPS / TWSE")
    await ctx.send(embed=embed)


# ── 啟動 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not BOT_TOKEN:
        sys.exit(
            "❌ 找不到 DISCORD_BOT_TOKEN！\n"
            "   請在專案根目錄建立 .env 檔，填入：\n"
            "   DISCORD_BOT_TOKEN=你的Bot Token"
        )
    bot.run(BOT_TOKEN)
