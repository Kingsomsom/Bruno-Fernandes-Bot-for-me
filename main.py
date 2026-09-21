"""
브루노 페르난데스 개인 비서 봇
맨유의 캡틴이 장 개장/중간/마감 시 중요한 정보를 전달합니다.

환경 변수:
- DISCORD_BOT_TOKEN
- DISCORD_OWNER_ID
- GROQ_API_KEY
- WEATHER_API_KEY
"""

import discord
from discord.ext import tasks, commands
import asyncio
from datetime import datetime, timedelta
import pytz
import yfinance as yf
import os
import time
import aiohttp
import math
import json
from groq import Groq

# ==================== 환경 변수 ====================
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
OWNER_USER_ID = int(os.environ.get("DISCORD_OWNER_ID", "0"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "945QCTKWFPYZF7U4FWR6SPBPH")
# ===================================================

# 보고 시간 설정 (hour, minute)
REPORT_TIMES = [(9, 30), (12, 0), (15, 30)]

# 시간대별 레이블 (인사말 생성용)
TIME_LABELS = {
    (9, 30):  "오전 (09:30) 장 개장 보고",
    (12, 0):  "점심 (12:00) 중간 점검 보고",
    (15, 30): "오후 (15:30) 장 마감 보고",
}

# 시간대별 알림 헤더
TIME_HEADERS = {
    (9, 30):  "🔔 장이 열렸습니다! (09:30)",
    (12, 0):  "📊 중간 점검입니다! (12:00)",
    (15, 30): "🔕 장이 마감되었습니다! (15:30)",
}

# 주식 종목
DOMESTIC_STOCKS = {
    "삼성전자":   "005930.KS",
    "SK하이닉스": "000660.KS",
}
OVERSEAS_STOCKS = {}


class BrunoFernandesBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.owner_id = OWNER_USER_ID
        self.kst = pytz.timezone("Asia/Seoul")

        # 이전 보고 가격 저장 {ticker: price}
        self.prev_report_prices = {}

    async def setup_hook(self):
        self.daily_report_task.start()
        print("브루노 페르난데스 봇이 준비되었습니다!")

    async def on_ready(self):
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"🎯 {self.user.name} 로그인 완료!")
        print(f"⚽ Owner ID: {self.owner_id}")
        print(f"⏰ 보고 시간: 매일 08시, 14시, 20시 (KST)")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ── 뉴스 ──────────────────────────────────────────
    async def get_news(self):
        """국제뉴스 3개 + 반도체뉴스 3개 RSS로 수집"""
        import xml.etree.ElementTree as ET

        result = "## 📰 뉴스\n"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        # 국제뉴스 - Google News 한국어 국제 섹션
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
                    headers=headers, timeout=10
                ) as res:
                    if res.status == 200:
                        text = await res.text()
                        root = ET.fromstring(text)
                        items = root.findall(".//item")[:3]
                        result += "**🌍 국제뉴스**\n"
                        for i, item in enumerate(items, 1):
                            title = item.find("title")
                            link  = item.find("link")
                            if title is not None:
                                t = title.text.split(" - ")[0].strip()
                                l = link.text.strip() if link is not None else ""
                                result += f"{i}. [{t}]({l})\n"
                    else:
                        result += f"**🌍 국제뉴스**\n⚠️ 데이터 접근 실패 ({res.status})\n"
        except Exception as e:
            result += f"**🌍 국제뉴스**\n⚠️ 수집 실패\n"
            print(f"  └─ 국제뉴스 오류: {e}")

        result += "\n"

        # 반도체뉴스 - Google News RSS
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://news.google.com/rss/search?q=반도체&hl=ko&gl=KR&ceid=KR:ko",
                    headers=headers, timeout=10
                ) as res:
                    if res.status == 200:
                        text = await res.text()
                        root = ET.fromstring(text)
                        items = root.findall(".//item")[:3]
                        result += "**💾 반도체뉴스**\n"
                        for i, item in enumerate(items, 1):
                            title = item.find("title")
                            link  = item.find("link")
                            if title is not None:
                                t = title.text.split(" - ")[0].strip()
                                l = link.text.strip() if link is not None else ""
                                result += f"{i}. [{t}]({l})\n"
                    else:
                        result += f"**💾 반도체뉴스**\n⚠️ 데이터 접근 실패 ({res.status})\n"
        except Exception as e:
            result += f"**💾 반도체뉴스**\n⚠️ 수집 실패\n"
            print(f"  └─ 반도체뉴스 오류: {e}")

        return result.strip()

    
    async def get_busan_weather(self):
        weather_dict = {
            "Clear": "맑음 ☀️",
            "Cloudy": "흐림 ☁️",
            "Overcast": "매우 흐림 🌫️",
            "Partially cloudy": "구름 조금 ⛅",
            "Rain": "비 ☔",
            "Snow": "눈 ❄️",
        }
        base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        url = f"{base_url}/Busan,KR/yesterday/today?unitGroup=metric&key={WEATHER_API_KEY}&contentType=json"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=20) as response:
                    if response.status != 200:
                        return f"⚠️ 날씨 데이터 접근 실패 (코드: {response.status})"
                    data = await response.json()
                    days = data.get("days", [])
                    if len(days) < 2:
                        return "⚠️ 기상 데이터 부족"

                    yesterday = days[0]
                    today     = days[1]

                    t_max = today.get("tempmax")
                    t_min = today.get("tempmin")
                    t_raw = today.get("conditions", "Clear").split(",")[0].strip()
                    t_desc = weather_dict.get(t_raw, t_raw)

                    y_max = yesterday.get("tempmax")
                    y_raw = yesterday.get("conditions", "Clear").split(",")[0].strip()
                    y_desc = weather_dict.get(y_raw, y_raw)

                    diff = round(t_max - y_max, 1)
                    diff_str = f"({diff:+.1f}°C)" if diff != 0 else "(변동 없음)"

                    result  = "## 🌤️ 부산 날씨\n"
                    result += f"┣ 오늘: {t_max}°C / {t_min}°C ({t_desc})\n"
                    result += f"┣ 어제: {y_max}°C ({y_desc})\n"
                    result += f"┗ 변동: **{diff_str}**"
                    return result
            except Exception as e:
                print(f"🚨 날씨 오류: {e}")
        return "❌ 날씨 데이터 수집 실패"

    # ── 주식 한 종목 데이터 ───────────────────────────
    def _get_ticker_data(self, ticker):
        """(현재가, 시가, 전날종가) 반환. 실패 시 None"""
        try:
            t = yf.Ticker(ticker)
            # 오늘 1분봉으로 시가 가져오기
            intraday = t.history(period="1d", interval="1m")
            intraday = intraday.dropna()
            open_price = intraday["Open"].iloc[0] if len(intraday) > 0 else None
            current    = intraday["Close"].iloc[-1] if len(intraday) > 0 else None

            # 전날 종가
            daily = t.history(period="5d", interval="1d").dropna()
            prev_close = daily["Close"].iloc[-2] if len(daily) >= 2 else None

            if current is None or math.isnan(current):
                current = prev_close  # 장 마감 후엔 전날 종가로 대체

            return current, open_price, prev_close
        except Exception as e:
            print(f"  └─ {ticker} 데이터 오류: {e}")
            return None, None, None

    # ── 투자 섹션 ─────────────────────────────────────
    def get_investment_info(self, is_closing: bool = False):
        """환율 + 국내주식 + 해외주식 통합 섹션"""
        result = "## 💹 투자\n"

        # 1. 환율
        try:
            hist = yf.Ticker("KRW=X").history(period="5d").dropna()
            if len(hist) >= 2:
                rate = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                change = rate - prev
                pct = (change / prev) * 100
                emoji = "📈" if change >= 0 else "📉"
                result += f"{emoji} **USD/KRW**: ₩{rate:,.2f} (전날 ₩{prev:,.2f} / {change:+.2f}, {pct:+.2f}%)\n"
            else:
                result += "⚠️ **USD/KRW**: 데이터 부족\n"
        except Exception as e:
            result += "⚠️ **USD/KRW**: 정보 없음\n"
            print(f"  └─ 환율 오류: {e}")

        # 2. 국내주식
        result += "\n"
        for name, ticker in DOMESTIC_STOCKS.items():
            current, open_price, prev_close = self._get_ticker_data(ticker)
            if current is None:
                result += f"⚠️ **{name}**: 정보 없음\n"
                continue

            emoji = "📈" if (prev_close and current >= prev_close) else "📉"
            result += f"{emoji} **{name}**: ₩{current:,.0f}\n"

            if prev_close:
                diff = current - prev_close
                pct  = (diff / prev_close) * 100
                result += f"  ┣ 전날 종가: ₩{prev_close:,.0f} ({diff:+.0f}, {pct:+.2f}%)\n"

            if open_price and not math.isnan(open_price):
                result += f"  ┣ 시가: ₩{open_price:,.0f}\n"

            # 이전 보고 대비
            if ticker in self.prev_report_prices:
                prev_rep = self.prev_report_prices[ticker]
                diff_rep = current - prev_rep
                pct_rep  = (diff_rep / prev_rep) * 100
                result += f"  ┗ 이전 보고: ₩{prev_rep:,.0f} ({diff_rep:+.0f}, {pct_rep:+.2f}%)\n"

            # 20시 마감 보고: 시가 vs 종가 요약
            if is_closing and open_price and not math.isnan(open_price):
                day_diff = current - open_price
                day_pct  = (day_diff / open_price) * 100
                day_emoji = "📈" if day_diff >= 0 else "📉"
                result += f"  ┗ 📌 오늘 하루: 시가 ₩{open_price:,.0f} → 종가 ₩{current:,.0f} ({day_emoji}{day_diff:+.0f}, {day_pct:+.2f}%)\n"

            # 현재 보고 가격 저장
            self.prev_report_prices[ticker] = current

        # 3. 해외주식
        result += "\n"
        for name, ticker in OVERSEAS_STOCKS.items():
            current, open_price, prev_close = self._get_ticker_data(ticker)
            if current is None:
                result += f"⚠️ **{name}**: 정보 없음\n"
                continue

            emoji = "📈" if (prev_close and current >= prev_close) else "📉"
            result += f"{emoji} **{name}**: ${current:,.2f}\n"

            if prev_close:
                diff = current - prev_close
                pct  = (diff / prev_close) * 100
                result += f"  ┣ 전날 종가: ${prev_close:,.2f} ({diff:+.2f}, {pct:+.2f}%)\n"

            if open_price and not math.isnan(open_price):
                result += f"  ┣ 시가: ${open_price:,.2f}\n"

            if ticker in self.prev_report_prices:
                prev_rep = self.prev_report_prices[ticker]
                diff_rep = current - prev_rep
                pct_rep  = (diff_rep / prev_rep) * 100
                result += f"  ┗ 이전 보고: ${prev_rep:,.2f} ({diff_rep:+.2f}, {pct_rep:+.2f}%)\n"

            if is_closing and open_price and not math.isnan(open_price):
                day_diff = current - open_price
                day_pct  = (day_diff / open_price) * 100
                day_emoji = "📈" if day_diff >= 0 else "📉"
                result += f"  ┗ 📌 오늘 하루: 시가 ${open_price:,.2f} → 종가 ${current:,.2f} ({day_emoji}{day_diff:+.2f}, {day_pct:+.2f}%)\n"

            self.prev_report_prices[ticker] = current

        return result.strip()

    # ── Groq 인사말 생성 ──────────────────────────────
    async def generate_greeting_and_closing(self, hour: int, weather_summary: str, weekday: str):
        if not GROQ_API_KEY:
            return self._fallback_greeting(hour), self._fallback_closing(hour)

        time_label = TIME_LABELS.get(hour, f"{hour}시 보고")
        prompt = f"""당신은 브루노 페르난데스입니다. 맨체스터 유나이티드의 캡틴으로서 '맹구'라는 부하직원에게 정기 브리핑을 전달합니다.
지금은 {weekday} {time_label}입니다. 부산 날씨는 {weather_summary}입니다.

아래 두 가지를 각각 한 줄씩, 브루노 페르난데스 특유의 카리스마 있고 약간 권위적이지만 팀워크를 강조하는 말투로 작성하세요.
- 인사말: 이 시간대와 날씨, 요일에 어울리는 자연스러운 인사 (맹구를 호칭으로 사용)
- 클로징: 브리핑을 마무리하는 짧은 한 마디

중요: 반드시 순수한 한국어로만 작성하세요. 영어, 키릴 문자, 기타 외국어를 절대 섞지 마세요.
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.
{{"greeting": "인사말 내용", "closing": "클로징 내용"}}"""

        try:
            client = Groq(api_key=GROQ_API_KEY)
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=256,
                )
            )
            raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
            data = json.loads(raw)
            return data["greeting"], data["closing"]
        except Exception as e:
            print(f"⚠️ Groq API 실패: {e} → 기본 인사말 사용")
            return self._fallback_greeting(hour), self._fallback_closing(hour)

    def _fallback_greeting(self, hour: int) -> str:
        fallbacks = {
            9:  "맹구, 장이 열렸습니다. 오늘 하루도 차질 없이 시작합시다.",
            12: "맹구, 오후 점검 시간입니다. 현재 흐름을 확인해 주십시오.",
            15: "맹구, 오늘 장이 마감되었습니다. 최종 보고를 확인해 주십시오.",
        }
        return fallbacks.get(hour, f"맹구, {hour}시 정기 보고입니다.")

    def _fallback_closing(self, hour: int) -> str:
        fallbacks = {
            9:  "좋은 출발입니다. 오늘도 승리를 향해 전진합시다!",
            12: "후반전도 집중력을 유지합시다.",
            15: "수고하셨습니다. 내일도 함께 싸웁시다.",
        }
        return fallbacks.get(hour, "이상으로 브리핑을 마칩니다.")

    # ── 리포트 전송 ───────────────────────────────────
    async def send_daily_report(self, report_time: tuple = None):
        try:
            if not self.owner_id:
                print("❌ OWNER_ID 미설정")
                return

            user = await self.fetch_user(self.owner_id)
            now  = datetime.now(self.kst)
            if report_time is None:
                report_time = (now.hour, now.minute)

            weekdays = ["월요일","화요일","수요일","목요일","금요일","토요일","일요일"]
            weekday  = weekdays[now.weekday()]
            date_str = f"{now.year}년 {now.month}월 {now.day}일 {weekday}"

            is_closing = (report_time == (15, 30))

            # 날씨
            busan_weather_raw = await self.get_busan_weather()
            weather_summary = "정보 없음"
            for line in busan_weather_raw.splitlines():
                if "오늘:" in line:
                    weather_summary = line.replace("┣", "").replace("오늘:", "").strip()
                    break

            # 인사말 (hour만 넘김)
            today_greeting, today_closing = await self.generate_greeting_and_closing(
                hour=report_time[0], weather_summary=weather_summary, weekday=weekday
            )

            # 헤더
            time_header = TIME_HEADERS.get(report_time, f"⏰ {report_time[0]}:{report_time[1]:02d} 보고")
            divider = "─" * 30 + "\n"

            report  = f"# {time_header}\n"
            report += f"## 📅 {date_str} 브리핑\n"
            report += f"{today_greeting}\n"

            sections = [
                busan_weather_raw,
                self.get_investment_info(is_closing=is_closing),
                await self.get_news(),
            ]

            for section in sections:
                clean = section.strip()
                if not clean:
                    continue
                report += f"\n{divider}{clean}\n"

            report += f"\n{divider}\n"
            report += f"_{today_closing}_\n\u17b5"

            await user.send(report)
            print(f"✅ [{now.strftime('%H:%M:%S')}] {time_header} 전송 완료")

        except Exception as e:
            print(f"❌ send_daily_report 오류: {e}")

    # ── 스케줄러 ──────────────────────────────────────
    @tasks.loop(minutes=1)
    async def daily_report_task(self):
        now = datetime.now(self.kst)
        current = (now.hour, now.minute)
        if current in REPORT_TIMES:
            print(f"\n⏰ 정기 보고: {now.hour}:{now.minute:02d}!")
            await self.send_daily_report(report_time=current)
            await asyncio.sleep(60)

    @daily_report_task.before_loop
    async def before_daily_report_task(self):
        await self.wait_until_ready()
        now = datetime.now(self.kst)
        future_times = [
            now.replace(hour=h, minute=m, second=0, microsecond=0)
            for h, m in REPORT_TIMES
        ]
        next_report = next((t for t in future_times if t > now), None)
        if not next_report:
            next_report = future_times[0] + timedelta(days=1)

        wait_seconds = (next_report - now).total_seconds()
        h = int(wait_seconds // 3600)
        m = int((wait_seconds % 3600) // 60)
        print(f"⏱️ 스케줄러 활성화 (1일 3회: 09:30, 12:00, 15:30)")
        print(f"  → 다음 보고({next_report.strftime('%H:%M')})까지: {h}시간 {m}분 남음")


# ── 봇 인스턴스 ───────────────────────────────────────
bot = BrunoFernandesBot()


@bot.command(name="테스트")
async def test_report(ctx):
    if ctx.author.id == OWNER_USER_ID:
        await ctx.send("📤 테스트 리포트 준비 중...")
        await bot.send_daily_report()
        await ctx.send("✅ DM으로 전송되었습니다!")
    else:
        await ctx.send("⛔ Owner만 사용 가능합니다.")


@bot.command(name="상태")
async def status(ctx):
    if ctx.author.id == OWNER_USER_ID:
        now = datetime.now(bot.kst)
        future_times = [
            now.replace(hour=h, minute=m, second=0, microsecond=0)
            for h, m in REPORT_TIMES
        ]
        next_report = next((t for t in future_times if t > now), None)
        if not next_report:
            next_report = future_times[0] + timedelta(days=1)

        wait = (next_report - now).total_seconds()
        h = int(wait // 3600)
        m = int((wait % 3600) // 60)

        msg  = "**🤖 브루노 페르난데스 봇 상태**\n\n"
        msg += f"✅ 봇 상태: 정상 작동 중\n"
        msg += f"🕐 현재 시각: {now.strftime('%Y-%m-%d %H:%M:%S')} (KST)\n"
        msg += f"⏰ 다음 리포트: {next_report.strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"⏱️ 남은 시간: {h}시간 {m}분\n"
        msg += f"👤 Owner ID: `{bot.owner_id}`"
        await ctx.send(msg)
    else:
        await ctx.send("⛔ Owner만 사용 가능합니다.")


@bot.command(name="도움말")
async def help_command(ctx):
    msg  = "**⚽ 브루노 페르난데스 봇 명령어**\n\n"
    msg += "**`!테스트`** - 즉시 리포트 받기 (Owner 전용)\n"
    msg += "**`!상태`** - 봇 상태 확인 (Owner 전용)\n"
    msg += "**`!도움말`** - 이 메시지 보기\n\n"
    msg += "_매일 09:30, 12:00, 15:30에 자동으로 DM 전송됩니다._"
    await ctx.send(msg)


# ── Flask Keep-Alive ──────────────────────────────────
from flask import Flask
from threading import Thread

app = Flask("")

@app.route("/")
def home():
    return "브루노 페르난데스 봇이 실행 중입니다! ⚽"

def run():
    port = 8080
    try:
        print(f"📡 포트 {port} 웹 서버 개방...")
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        print(f"⚠️ 웹 서버 오류: {e}")

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()


if __name__ == "__main__":
    if not BOT_TOKEN or OWNER_USER_ID == 0:
        print("❌ 설정 오류: 환경 변수를 확인하십시오.")
        exit(1)

    print("🏟️ 웹 서버 가동 중...")
    keep_alive()

    print("⏳ 포트 개방 대기 중 (10초)...")
    time.sleep(10)

    print("\n⚽ 브루노 페르난데스, 올드 트래포드에 출근합니다!\n")
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        print(f"\n❌ 봇 가동 실패: {e}")
