# AGENTS.md

## Project Overview

이 프로젝트는 Google News RSS를 주기적으로 조회하여 특정 키워드의 새 뉴스가 발견되면 Telegram Bot으로 알림을 전송하는 Python 기반 뉴스 알림 봇이다.

주요 목표:

- Google News RSS 기반 뉴스 수집
- 키워드별 RSS URL 자동 생성
- 중복 기사 전송 방지
- Telegram Bot API를 이용한 실시간 알림
- `.env` 기반 비밀값 관리
- 로컬 실행 및 장시간 운영 가능
- 추후 Windows 작업 스케줄러, Linux systemd, Docker 실행까지 확장 가능

기본 예시 키워드:

- 두산로보틱스
- 레인보우로보틱스
- 삼성전자
- 두산에너빌리티

---

## Important Rules

반드시 다음 원칙을 따른다.

1. Telegram Bot Token, Chat ID, API Key 등 민감정보를 코드에 하드코딩하지 않는다.
2. 모든 민감정보는 `.env`에서 읽는다.
3. `.env`는 Git에 커밋하지 않는다.
4. RSS 파싱은 HTML 크롤링이 아니라 `feedparser`를 우선 사용한다.
5. Google News RSS URL은 직접 문자열 결합하지 말고 `urllib.parse.quote_plus` 또는 안전한 URL 인코딩을 사용한다.
6. 이미 전송한 기사는 메모리만이 아니라 로컬 저장소에도 기록한다.
7. 프로그램 재시작 후에도 같은 기사가 다시 전송되지 않도록 한다.
8. 네트워크 오류, RSS 파싱 오류, Telegram 전송 오류가 발생해도 프로그램 전체가 죽지 않도록 예외 처리한다.
9. 너무 짧은 주기로 Google News RSS를 요청하지 않는다. 기본 조회 주기는 60초 이상으로 한다.
10. 로그는 `print()`만 남발하지 말고 `logging` 모듈을 사용한다.

---

## Recommended Tech Stack

Python 3.11 이상을 기준으로 한다.

필수 패키지:

```bash
pip install feedparser requests python-dotenv
```

권장 패키지:

```bash
pip install pytest ruff
```

Telegram 전송은 단순성을 위해 우선 `requests`로 Telegram Bot API를 직접 호출한다.

비동기 처리가 꼭 필요한 경우가 아니면 `python-telegram-bot` 의존성을 추가하지 않는다.

---

## Expected Project Structure

가능하면 다음 구조를 유지한다.

```text
google-news-telegram-bot/
├── AGENTS.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── main.py
├── config.py
├── news.py
├── telegram_client.py
├── storage.py
├── utils.py
└── tests/
    ├── test_news.py
    └── test_storage.py
```

각 파일 역할:

### `main.py`

- 프로그램 진입점
- 설정 로드
- 반복 루프 실행
- RSS 조회
- 새 기사 필터링
- 텔레그램 전송 호출

### `config.py`

- `.env` 로드
- 환경변수 검증
- 키워드, 조회 주기, 언어/국가 설정 관리

### `news.py`

- Google News RSS URL 생성
- `feedparser`로 RSS 파싱
- 기사 객체 변환
- 키워드 필터링

### `telegram_client.py`

- Telegram Bot API 전송 담당
- `sendMessage` 호출
- 실패 시 예외 처리 및 로그 출력

### `storage.py`

- 이미 보낸 기사 링크 저장
- 기본은 JSON 파일 사용
- 추후 SQLite로 변경 가능하게 작성

### `utils.py`

- 공통 유틸리티
- 날짜 포맷
- 문자열 정리
- 링크 정규화 등

---

## Environment Variables

`.env.example` 파일에는 다음 항목을 포함한다.

```env
TELEGRAM_BOT_TOKEN=123456789:replace_with_your_token
TELEGRAM_CHAT_ID=123456789
NEWS_KEYWORDS=두산로보틱스,레인보우로보틱스
POLL_INTERVAL_SECONDS=60
GOOGLE_NEWS_HL=ko
GOOGLE_NEWS_GL=KR
GOOGLE_NEWS_CEID=KR:ko
SENT_STORE_PATH=sent_articles.json
SEND_EXISTING_ON_FIRST_RUN=false
```

실제 `.env`는 사용자가 직접 생성한다.

---

## Google News RSS Rules

Google News RSS URL 형식은 다음을 기준으로 한다.

```text
https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko
```

키워드 정확도를 높이려면 검색어를 따옴표로 감싼다.

예시:

```text
"두산로보틱스"
```

Python에서는 반드시 URL 인코딩한다.

```python
from urllib.parse import quote_plus

query = quote_plus('"두산로보틱스"')

url = (
    f"https://news.google.com/rss/search?"
    f"q={query}&hl=ko&gl=KR&ceid=KR:ko"
)
```

---

## Article Data Model

기사 데이터는 최소 다음 필드를 가진 dict 또는 dataclass로 다룬다.

```python
{
    "title": str,
    "link": str,
    "published": str | None,
    "source": str | None,
    "keyword": str
}
```

가능하면 dataclass 사용을 선호한다.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Article:
    title: str
    link: str
    published: str | None
    source: str | None
    keyword: str
```

---

## Duplicate Detection Rules

중복 판정 기준은 우선 `link`를 사용한다.

단, Google News RSS 링크는 리다이렉트 링크일 수 있으므로 다음 중 하나를 선택한다.

1. 단순 버전: `entry.link` 전체를 저장
2. 개선 버전: 제목 + 언론사 + 발행시간 해시 저장
3. 고급 버전: 실제 원문 URL 추출 후 저장

초기 구현은 단순 버전으로 충분하다.

저장 파일 예시:

```json
{
  "sent_links": [
    "https://news.google.com/rss/articles/..."
  ]
}
```

---

## Telegram Message Format

텔레그램 메시지는 읽기 쉽게 구성한다.

기본 포맷:

```text
📰 [키워드] 기사 제목

언론사: source
시간: published

링크
```

예시:

```text
📰 [두산로보틱스] 두산로보틱스, 다시 10만원대 올라섰다

언론사: CBC뉴스
시간: Fri, 08 May 2026 00:21:22 GMT

https://news.google.com/rss/articles/...
```

Markdown 파싱 오류를 줄이기 위해 초기 구현에서는 Telegram `parse_mode`를 사용하지 않는다.

---

## Polling Behavior

기본 조회 주기는 60초다.

반복 루프는 다음 방식으로 작성한다.

```python
while True:
    try:
        run_once()
    except Exception:
        logger.exception("Unexpected error in main loop")

    time.sleep(poll_interval)
```

첫 실행 시 기존 RSS에 있는 모든 기사를 한꺼번에 전송하지 않도록 옵션을 둔다.

권장 정책:

- 첫 실행 시 기존 기사들은 저장만 하고 전송하지 않는다.
- 이후 새로 발견된 기사만 전송한다.

환경변수로 제어 가능하게 한다.

```env
SEND_EXISTING_ON_FIRST_RUN=false
```

---

## Error Handling

다음 오류를 반드시 처리한다.

- `.env` 누락
- Telegram Bot Token 누락
- Chat ID 누락
- RSS 요청 실패
- RSS 파싱 결과 없음
- Telegram API 400/401/403/429/500 오류
- 저장 파일 손상
- 네트워크 타임아웃

Telegram 전송 시 timeout을 지정한다.

```python
requests.post(url, data=payload, timeout=10)
```

429 Too Many Requests가 발생하면 로그를 남기고 다음 루프로 넘어간다.

---

## Logging Rules

`logging` 모듈을 사용한다.

기본 형식:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
```

로그에 Telegram Bot Token 전체를 출력하지 않는다.

민감정보는 마스킹한다.

---

## Code Style

- 함수는 작게 작성한다.
- 하나의 함수가 RSS 조회, 파싱, 전송, 저장을 모두 담당하지 않게 한다.
- 타입 힌트를 사용한다.
- 외부 I/O 함수는 timeout과 예외 처리를 포함한다.
- 테스트 가능한 순수 함수를 우선 작성한다.
- 전역변수 남용을 피한다.

---

## Testing Requirements

가능하면 다음 테스트를 작성한다.

### `test_news.py`

- 키워드가 RSS URL에 올바르게 인코딩되는지 확인
- RSS entry가 Article 객체로 변환되는지 확인

### `test_storage.py`

- 저장 파일이 없을 때 빈 set 반환
- 링크 저장 후 다시 로드 가능
- 손상된 JSON 파일 처리

테스트 실행:

```bash
pytest
```

Lint 실행:

```bash
ruff check .
```

---

## README Requirements

`README.md`에는 다음 내용을 포함한다.

1. 프로젝트 설명
2. 설치 방법
3. Telegram BotFather로 봇 만드는 방법
4. Chat ID 확인 방법
5. `.env` 작성 예시
6. 실행 방법
7. Windows에서 실행하는 방법
8. Linux에서 백그라운드 실행하는 방법
9. 자주 발생하는 오류
10. 주의사항

---

## Minimal Implementation Goal

처음 Codex가 구현해야 할 최소 기능은 다음이다.

1. `.env`에서 설정 읽기
2. `NEWS_KEYWORDS`를 쉼표로 분리
3. 각 키워드에 대해 Google News RSS URL 생성
4. `feedparser`로 기사 목록 읽기
5. 이전에 보낸 링크와 비교
6. 새 기사만 Telegram으로 전송
7. 전송 성공한 링크 저장
8. 60초마다 반복

---

## Do Not Implement Initially

초기 버전에서는 다음 기능을 만들지 않는다.

- 웹 대시보드
- DB 서버 연동
- Redis
- Celery
- FastAPI 서버
- Docker Compose
- AI 요약
- 감성 분석
- 주가 자동 매매
- 증권 추천 판단

단, 사용자가 명시적으로 요청하면 별도 브랜치 또는 별도 단계로 추가한다.

---

## Security Notes

이 프로젝트는 뉴스 알림 봇이지 투자 판단 봇이 아니다.

따라서 다음 문구를 README 또는 코드 주석에 포함한다.

```text
이 봇은 뉴스 알림 용도이며 투자 판단, 매수/매도 추천을 제공하지 않습니다.
```

Telegram Bot Token이 노출되면 즉시 BotFather에서 토큰을 재발급해야 한다.

---

## Suggested First Codex Task

Codex가 처음 수행할 작업은 다음 순서로 한다.

1. 프로젝트 파일 구조 생성
2. `requirements.txt` 작성
3. `.env.example` 작성
4. `config.py` 작성
5. `news.py` 작성
6. `telegram_client.py` 작성
7. `storage.py` 작성
8. `main.py` 작성
9. `README.md` 작성
10. 간단한 테스트 작성

---

## Acceptance Criteria

구현 완료 기준:

- `python main.py` 실행 가능
- `.env` 누락 시 친절한 오류 메시지 출력
- Google News RSS에서 기사 조회 가능
- 새 기사만 Telegram으로 전송
- 재실행해도 이미 보낸 기사는 다시 보내지 않음
- 네트워크 오류 발생 시 프로그램이 종료되지 않음
- README만 보고 사용자가 실행 가능

---

## Example Command

```bash
python main.py
```

예상 로그:

```text
2026-05-08 12:00:00 [INFO] config - Loaded 2 keywords
2026-05-08 12:00:01 [INFO] news - Fetched 10 articles for keyword: 두산로보틱스
2026-05-08 12:00:02 [INFO] telegram - Sent article: 두산로보틱스, 다시 10만원대 올라섰다
2026-05-08 12:00:02 [INFO] storage - Saved 1 new sent link
```

---

## Suggested Initial Codex Prompt

```text
이 저장소의 AGENTS.md를 기준으로 Google News RSS 기반 Telegram 뉴스 알림 봇을 구현해줘.

요구사항:
- Python 기반
- .env 기반 설정 관리
- Google News RSS 사용
- feedparser 사용
- Telegram Bot API 연동
- 중복 기사 전송 방지
- logging 사용
- README 작성
- requirements.txt 작성
- 테스트 코드 포함

초기 버전은 단순하고 안정적으로 구현하고,
웹 UI나 DB 서버는 포함하지 않는다.
```