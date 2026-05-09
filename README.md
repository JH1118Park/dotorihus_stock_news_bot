# Google News Telegram Bot

Google News RSS를 주기적으로 조회해서 지정한 키워드의 새 뉴스가 발견되면 Telegram Bot으로 알림을 보내는 Python 기반 뉴스 알림 봇입니다.

이 봇은 뉴스 알림 용도이며 투자 판단, 매수/매도 추천을 제공하지 않습니다.

https://t.me/+Y2v0hUL6Dws4MTBl

## 주요 기능

- Google News RSS 검색 URL 자동 생성
- `feedparser` 기반 RSS 파싱
- `.env` 기반 Telegram Bot Token, Chat ID 관리
- 검색 실행 시각 기준 최근 1시간 이내 발행된 새 기사만 Telegram으로 전송
- 이미 보낸 기사 링크를 JSON 파일에 저장
- 재실행 후에도 중복 기사 전송 방지
- 네트워크, RSS, Telegram 오류 발생 시 로깅 후 계속 실행

## 설치

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux 또는 macOS에서는 다음처럼 가상환경을 활성화합니다.

```bash
source .venv/bin/activate
```

## Telegram 봇 만들기

1. Telegram에서 `@BotFather`를 검색합니다.
2. `/newbot` 명령을 보냅니다.
3. 봇 이름과 사용자 이름을 입력합니다.
4. 발급된 Bot Token을 `.env`의 `TELEGRAM_BOT_TOKEN`에 넣습니다.

Bot Token이 노출되면 즉시 BotFather에서 토큰을 재발급해야 합니다.

## Chat ID 확인

1. 만든 봇에게 아무 메시지나 보냅니다.
2. 브라우저에서 아래 주소를 엽니다.

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

3. 응답 JSON의 `message.chat.id` 값을 `.env`의 `TELEGRAM_CHAT_ID`에 넣습니다.

그룹 채팅에 보내려면 봇을 그룹에 초대한 뒤 그룹에서 메시지를 보내고 같은 방식으로 Chat ID를 확인합니다.

## 환경변수

`.env.example`을 참고해서 프로젝트 루트에 `.env` 파일을 만듭니다.

```env
TELEGRAM_BOT_TOKEN=123456789:replace_with_your_token
TELEGRAM_CHAT_ID=123456789
NEWS_KEYWORDS=두산로보틱스,레인보우로보틱스
BANNED_KEYWORDS=야구,축구,농구
POLL_INTERVAL_SECONDS=60
GOOGLE_NEWS_HL=ko
GOOGLE_NEWS_GL=KR
GOOGLE_NEWS_CEID=KR:ko
SENT_STORE_PATH=sent_articles.json
SEND_EXISTING_ON_FIRST_RUN=false
NIGHTLY_DIGEST_ENABLED=true
NIGHTLY_DIGEST_START_HOUR=22
NIGHTLY_DIGEST_SEND_HOUR=7
```

`SEND_EXISTING_ON_FIRST_RUN=false`이면 첫 실행 때 이미 RSS에 있는 기사는 저장만 하고 전송하지 않습니다. 이후 새로 발견되는 기사만 전송합니다.

`BANNED_KEYWORDS` is optional. Articles are skipped when any banned keyword is
found in the article title, source, or matched search keyword.

### Nightly digest

By default, articles found from 22:00 until before 07:00 are saved to
`sent_articles.json` as `pending_articles` instead of being sent immediately.
At 07:00 or the first polling run after 07:00, the bot sends the queued articles
as one batch and then marks them as sent.

```env
NIGHTLY_DIGEST_ENABLED=true
NIGHTLY_DIGEST_START_HOUR=22
NIGHTLY_DIGEST_SEND_HOUR=7
```

Set `NIGHTLY_DIGEST_ENABLED=false` to send articles immediately at all hours.

## 실행

```bash
python main.py
```

정상 실행 시 키워드별 RSS를 조회하고, 새 기사 발견 시 Telegram으로 메시지를 전송합니다.
RSS에 과거 기사가 섞여 있어도 검색 실행 시각 기준 최근 1시간 이내에 발행된 기사만 전송합니다.

실행 로그는 콘솔에 출력되는 동시에 실행 시작 시각 기준 파일명으로 `docs/logs/` 아래에 저장됩니다.

```text
docs/logs/news_bot_20260508_124117.log
```

## Windows에서 장시간 실행

PowerShell에서 다음처럼 실행할 수 있습니다.

```powershell
cd E:\source\news_bot
.\.venv\Scripts\Activate.ps1
python main.py
```

장시간 운영은 Windows 작업 스케줄러에 위 명령을 등록하는 방식으로 확장할 수 있습니다.

## Linux에서 백그라운드 실행

간단한 테스트 운영은 `nohup`을 사용할 수 있습니다.

```bash
cd /path/to/news_bot
source .venv/bin/activate
nohup python main.py > news_bot.log 2>&1 &
```

운영 환경에서는 systemd 서비스로 등록하는 것을 권장합니다.

## 테스트와 린트

```bash
pytest
ruff check .
```

## 자주 발생하는 오류

- `.env` 누락: `.env.example`을 복사해서 실제 값을 입력하세요.
- `TELEGRAM_BOT_TOKEN is required`: BotFather에서 받은 토큰을 넣어야 합니다.
- `TELEGRAM_CHAT_ID is required`: 봇에게 메시지를 보낸 뒤 `getUpdates`로 Chat ID를 확인하세요.
- Telegram 401: 토큰이 잘못되었거나 폐기된 토큰입니다.
- Telegram 403: 봇이 채팅방에서 차단되었거나 그룹 권한이 부족합니다.
- Telegram 429: 요청이 너무 많습니다. 다음 루프에서 다시 시도합니다.
- RSS 결과 없음: 키워드가 너무 구체적이거나 Google News에 최근 결과가 없을 수 있습니다.
- 손상된 `sent_articles.json`: 프로그램이 경고 로그를 남기고 빈 저장소로 시작합니다.

## 주의사항

- `.env`는 Git에 커밋하지 마세요.
- 너무 짧은 조회 주기를 사용하지 마세요. 이 프로젝트는 최소 60초를 강제합니다.
- Telegram 메시지는 Markdown `parse_mode`를 사용하지 않아 제목의 특수문자로 인한 전송 오류를 줄입니다.

## 텔레그램 방 아이디 확인
- https://api.telegram.org/botxxxxxxxxxx/getUpdates
