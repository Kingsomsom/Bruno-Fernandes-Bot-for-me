"""
브루노 페르난데스 개인 비서 봇 (Replit 버전)
맨유의 캡틴이 매일 중요한 정보를 전달합니다.

Replit에서 실행하기:
1. Secrets에 DISCORD_BOT_TOKEN, DISCORD_OWNER_ID, GROQ_API_KEY 추가
2. "Run" 버튼 클릭
"""

import discord
from discord.ext import tasks, commands
import asyncio
from datetime import datetime, timedelta
import pytz
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import os
import time
import aiohttp
from groq import Groq

# ==================== Replit 환경 변수 설정 ====================
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
OWNER_USER_ID = int(os.environ.get("DISCORD_OWNER_ID", "0"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
# ===============================================================

# 시간대별 레이블 (Claude 프롬프트에 컨텍스트로 전달)
TIME_LABELS = {
    0: "자정 (00시) 보고",
    6: "이른 아침 (06시) 보고",
    12: "점심 (12시) 보고",
    18: "저녁 (18시) 보고",
}


class BrunoFernandesBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.owner_id = OWNER_USER_ID
        self.kst = pytz.timezone("Asia/Seoul")
        self.weather_cache = {}

    # ✅ [버그1 수정] setup_hook에서 호출하는 이름을 daily_report_task로 통일
    async def setup_hook(self):
        """봇 시작 시 실행"""
        self.daily_report_task.start()
        print("브루노 페르난데스 봇이 준비되었습니다!")

    # ✅ [버그1 수정] on_ready가 __init__ 안에 중첩되어 있던 것을 클래스 메서드로 이동
    async def on_ready(self):
        """봇 로그인 완료 시"""
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"🎯 {self.user.name} 로그인 완료!")
        print(f"⚽ Owner ID: {self.owner_id}")
        print(f"⏰ 일일 리포트 시간: 매일 오전 9시 (KST)")
        print(f"🌐 Replit에서 실행 중")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ✅ [버그1 수정] get_busan_weather도 클래스 메서드로 올바르게 위치
    async def get_busan_weather(self):
        api_key = "945QCTKWFPYZF7U4FWR6SPBPH"
        location = "Busan,KR"

        weather_dict = {
            "Clear": "맑음 ☀️",
            "Cloudy": "흐림 ☁️",
            "Overcast": "매우 흐림 🌫️",
            "Partially cloudy": "구름 조금 ⛅",
            "Rain": "비 ☔",
            "Snow": "눈 ❄️",
        }

        base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        url = f"{base_url}/{location}/yesterday/today?unitGroup=metric&key={api_key}&contentType=json"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=20) as response:
                    if response.status != 200:
                        print(f"❌ API 서버 응답 코드 에러: {response.status}")
                        return f"\n⚠️ 데이터 센터 접근 실패 (코드: {response.status})\n"

                    data = await response.json()

                    days = data.get("days", [])
                    if len(days) < 2:
                        return "\n⚠️ 기상 데이터 부족 (어제/오늘 데이터 없음)\n"

                    yesterday = days[0]
                    today = days[1]

                    t_max, t_min = today.get("tempmax"), today.get("tempmin")
                    t_raw = today.get("conditions", "Clear").split(",")[0].strip()
                    t_desc = weather_dict.get(t_raw, t_raw)

                    y_max, y_min = yesterday.get("tempmax"), yesterday.get("tempmin")
                    y_raw = yesterday.get("conditions", "Clear").split(",")[0].strip()
                    y_desc = weather_dict.get(y_raw, y_raw)

                    diff_max = round(t_max - y_max, 1)
                    diff_str = (
                        f"({diff_max:+.1f}°C)" if diff_max != 0 else "(변동 없음)"
                    )

                    result = f"## 📊 기상 대조 (부산)\n"
                    result += f"┣ 오늘: {t_max}°C / {t_min}°C ({t_desc})\n"
                    result += f"┣ 어제: {y_max}°C / {y_min}°C ({y_desc})\n"
                    result += f"┗ 변동: **{diff_str}**"

                    return result
            except Exception as e:
                print(f"🚨 [CRITICAL ERROR] 시스템 마비: {e}")

        return "\n❌ 데이터 수집 프로세스 최종 실패.\n"

    def get_investment_info(self):
        """환율 + 국내주식 + 해외주식 통합 투자 섹션"""
        result = "## 💹 투자\n"

        # 1. 환율
        try:
            usdkrw = yf.Ticker("KRW=X")
            hist = usdkrw.history(period="5d")
            if len(hist) >= 2:
                rate = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                change = rate - prev
                pct = (change / prev) * 100
                emoji = "📈" if change >= 0 else "📉"
                result += f"{emoji} **USD/KRW**: ₩{rate:,.2f} (전날 ₩{prev:,.2f} / {change:+.2f}, {pct:+.2f}%)\n"
            else:
                result += f"⚠️ **USD/KRW**: 데이터 부족\n"
        except Exception as e:
            result += f"⚠️ **USD/KRW**: 정보 없음\n"
            print(f"  └─ 환율 오류: {e}")

        # 2. 국내주식
        domestic = {
            "삼성전자": "005930.KS",
            "삼성전자(우)": "005935.KS",
            "SK하이닉스": "000660.KS",
            "ACE KRX금현물": "411060.KS",
        }
        result += "\n"
        for name, ticker in domestic.items():
            try:
                hist = yf.Ticker(ticker).history(period="5d", interval="1d")
                hist = hist.dropna()
                if len(hist) >= 2:
                    price = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2]
                    import math

                    if math.isnan(price):
                        price = prev
                        result += f"➖ **{name}**: ₩{price:,.0f} (장 마감, 전날 종가)\n"
                    else:
                        change = price - prev
                        pct = (change / prev) * 100
                        emoji = "📈" if change >= 0 else "📉"
                        result += f"{emoji} **{name}**: ₩{price:,.0f} (전날 ₩{prev:,.0f} / {change:+.0f}, {pct:+.2f}%)\n"
                else:
                    result += f"⚠️ **{name}**: 데이터 부족\n"
            except Exception as e:
                result += f"⚠️ **{name}**: 정보 없음\n"
                print(f"  └─ {name} 오류: {e}")

        # 3. 해외주식
        overseas = {
            "알파벳": "GOOGL",
        }
        result += "\n"
        for name, ticker in overseas.items():
            try:
                hist = yf.Ticker(ticker).history(period="5d", interval="1d")
                hist = hist.dropna()
                if len(hist) >= 2:
                    price = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2]
                    import math

                    if math.isnan(price):
                        result += f"➖ **{name}**: ${prev:,.2f} (장 마감, 전날 종가)\n"
                    else:
                        change = price - prev
                        pct = (change / prev) * 100
                        emoji = "📈" if change >= 0 else "📉"
                        result += f"{emoji} **{name}**: ${price:,.2f} (전날 ${prev:,.2f} / {change:+.2f}, {pct:+.2f}%)\n"
                else:
                    result += f"⚠️ **{name}**: 데이터 부족\n"
            except Exception as e:
                result += f"⚠️ **{name}**: 정보 없음\n"
                print(f"  └─ {name} 오류: {e}")

        return result.strip()

    async def generate_greeting_and_closing(
        self, hour: int, weather_summary: str, weekday: str
    ) -> tuple[str, str]:
        """Groq API로 시간대·날씨·요일에 맞는 인사말과 클로징 생성"""

        if not GROQ_API_KEY:
            print("⚠️ GROQ_API_KEY 없음 → 기본 인사말 사용")
            return self._fallback_greeting(hour), self._fallback_closing()

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
            import json

            client = Groq(api_key=GROQ_API_KEY)
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=256,
                )
            )
            raw = (
                response.choices[0]
                .message.content.strip()
                .replace("```json", "")
                .replace("```", "")
            )
            data = json.loads(raw)
            return data["greeting"], data["closing"]

        except Exception as e:
            print(f"⚠️ Groq API 인사말 생성 실패: {e} → 기본 인사말 사용")
            return self._fallback_greeting(hour), self._fallback_closing()

    def _fallback_greeting(self, hour: int) -> str:
        """API 실패 시 시간대별 기본 인사말"""
        fallbacks = {
            0: "자정입니다, 맹구. 늦은 시간에도 보고를 확인해 주십시오.",
            6: "좋은 아침입니다, 맹구. 오늘 하루도 차질 없이 시작합시다.",
            12: "점심 시간입니다, 맹구. 오후 브리핑을 확인해 주십시오.",
            18: "저녁입니다, 맹구. 하루를 마무리하기 전 보고 내용을 확인해 주세요.",
        }
        return fallbacks.get(hour, f"맹구, {hour}시 정기 보고입니다.")

    def _fallback_closing(self) -> str:
        """API 실패 시 기본 클로징"""
        return "이상으로 브리핑을 마칩니다. 수고하셨습니다."

    async def send_daily_report(self):
        """일일 리포트 전송"""
        try:
            if not self.owner_id:
                print("❌ 오류: OWNER_ID가 설정되지 않았습니다.")
                return

            user = await self.fetch_user(self.owner_id)

            now = datetime.now(self.kst)
            weekdays = [
                "월요일",
                "화요일",
                "수요일",
                "목요일",
                "금요일",
                "토요일",
                "일요일",
            ]
            weekday = weekdays[now.weekday()]
            date_str = f"{now.year}년 {now.month}월 {now.day}일 {weekday}"

            # 날씨 먼저 수집 (인사말 생성에 컨텍스트로 활용)
            busan_weather_raw = await self.get_busan_weather()

            # 날씨 요약 텍스트 추출 (Claude 프롬프트용 한 줄 요약)
            weather_summary = "정보 없음"
            for line in busan_weather_raw.splitlines():
                if "오늘:" in line:
                    weather_summary = line.replace("┣", "").replace("오늘:", "").strip()
                    break

            # Claude API로 시간대·날씨·요일 맞춤 인사말 생성
            today_greeting, today_closing = await self.generate_greeting_and_closing(
                hour=now.hour,
                weather_summary=weather_summary,
                weekday=weekday,
            )

            report = f"# 📅 {date_str} 브리핑\n"
            report += f"{today_greeting}\n"

            divider = "─" * 30 + "\n"

            sections = [
                busan_weather_raw,
                self.get_investment_info(),
            ]

            for section in sections:
                clean_section = section.strip()
                if not clean_section:
                    continue
                report += f"\n{divider}{clean_section}\n"

            report += f"\n{divider}\n"
            report += f"_{today_closing}_\n\u17b5"

            await user.send(report)
            print(f"✅ [{now.strftime('%H:%M:%S')}] 리포트 전송 완료")

        except Exception as e:
            print(f"❌ send_daily_report 내부 오류: {e}")

    # ✅ [버그2+3 수정] daily_report_task로 이름 통일, send_daily_report 밖으로 꺼냄
    @tasks.loop(minutes=1)
    async def daily_report_task(self):
        """설정된 시간(06, 12, 18, 00시)에 리포트 전송"""
        now = datetime.now(self.kst)
        report_times = [0, 6, 12, 18]

        if now.hour in report_times and now.minute == 0:
            print(f"\n⏰ 정기 보고 알람: {now.hour}시 정각! 리포트 발송 중...")
            await self.send_daily_report()
            await asyncio.sleep(60)

    # ✅ [버그3 수정] before_loop도 send_daily_report 밖으로 꺼냄
    @daily_report_task.before_loop
    async def before_daily_report_task(self):
        """봇 시작 시 다음 가장 가까운 보고 시간까지 대기 상태 출력"""
        await self.wait_until_ready()

        now = datetime.now(self.kst)
        report_times = [0, 6, 12, 18]

        future_times = [
            now.replace(hour=t, minute=0, second=0, microsecond=0) for t in report_times
        ]
        next_report = next((t for t in future_times if t > now), None)

        if not next_report:
            next_report = future_times[0] + timedelta(days=1)

        wait_seconds = (next_report - now).total_seconds()
        hours = int(wait_seconds // 3600)
        minutes = int((wait_seconds % 3600) // 60)

        print(f"⏱️ 정기 보고 스케줄러 활성화 (1일 4회: 06, 12, 18, 00시)")
        print(f"  → 다음 보고({next_report.hour}시)까지: {hours}시간 {minutes}분 남음")


# 봇 인스턴스 생성
bot = BrunoFernandesBot()


@bot.command(name="테스트")
async def test_report(ctx):
    """테스트용 리포트 즉시 전송"""
    if ctx.author.id == OWNER_USER_ID:
        await ctx.send("📤 테스트 리포트를 준비 중입니다...")
        await bot.send_daily_report()
        await ctx.send("✅ 테스트 리포트가 DM으로 전송되었습니다!")
    else:
        await ctx.send("⛔ 이 명령어는 Owner만 사용할 수 있습니다.")


@bot.command(name="상태")
async def status(ctx):
    """봇 상태 확인"""
    if ctx.author.id == OWNER_USER_ID:
        now = datetime.now(bot.kst)
        report_times = [0, 6, 12, 18]

        future_times = [
            now.replace(hour=t, minute=0, second=0, microsecond=0) for t in report_times
        ]
        next_report = next((t for t in future_times if t > now), None)
        if not next_report:
            next_report = future_times[0] + timedelta(days=1)

        wait_seconds = (next_report - now).total_seconds()
        hours = int(wait_seconds // 3600)
        minutes = int((wait_seconds % 3600) // 60)

        status_msg = f"**🤖 브루노 페르난데스 봇 상태**\n\n"
        status_msg += f"✅ 봇 상태: 정상 작동 중\n"
        status_msg += f"🕐 현재 시각: {now.strftime('%Y-%m-%d %H:%M:%S')} (KST)\n"
        status_msg += f"⏰ 다음 리포트: {next_report.strftime('%Y-%m-%d %H:%M:%S')}\n"
        status_msg += f"⏱️ 남은 시간: {hours}시간 {minutes}분\n"
        # ✅ [버그4 수정] CURRENT_TONE 미정의 변수 제거
        status_msg += f"👤 Owner ID: `{bot.owner_id}`"

        await ctx.send(status_msg)
    else:
        await ctx.send("⛔ 이 명령어는 Owner만 사용할 수 있습니다.")


@bot.command(name="도움말")
async def help_command(ctx):
    """도움말"""
    help_msg = f"**⚽ 브루노 페르난데스 봇 명령어**\n\n"
    help_msg += f"**`!테스트`** - 즉시 리포트 받기 (Owner 전용)\n"
    help_msg += f"**`!상태`** - 봇 상태 확인 (Owner 전용)\n"
    help_msg += f"**`!도움말`** - 이 메시지 보기\n\n"
    help_msg += f"_매일 06, 12, 18, 00시에 자동으로 일일 리포트가 DM으로 전송됩니다._"

    await ctx.send(help_msg)


# Replit Keep-Alive
from flask import Flask
from threading import Thread

app = Flask("")


@app.route("/")
def home():
    return "브루노 페르난데스 봇이 실행 중입니다! ⚽"


def run():
    port = 5000
    try:
        print(f"📡 [통신] 포트 {port}에서 웹 서버를 개방합니다...")
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        print(f"⚠️ 웹 서버 실행 중 오류 발생: {e}")


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()


if __name__ == "__main__":
    if not BOT_TOKEN or OWNER_USER_ID == 0:
        print("❌ 설정 오류: 환경 변수를 확인하십시오.")
        exit(1)

    print("🏟️ [라커룸] 웹 서버 가동 중...")
    keep_alive()

    print("⏳ 포트 개방 대기 중 (10초)...")
    time.sleep(10)

    print("\n⚽ [입장] 브루노 페르난데스, 올드 트래포드에 출근합니다!\n")
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        print(f"\n❌ 봇 가동 실패: {e}")
