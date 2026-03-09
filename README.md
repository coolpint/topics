# Topic Pitcher

경제 뉴스 발제를 위해 공개 반응 신호와 매체 확산 신호를 함께 랭킹하는 일일 시스템이다. 기본 소스는 `Reddit` 업보트·댓글, `Hacker News` 점수·댓글수, `Google News RSS`의 매체 확산도이며, 한국 독자 가중치를 위해 `Google News KR`을 기본 포함한다. `YOUTUBE_API_KEY`가 있으면 YouTube 조회수·좋아요·댓글도 반영하고, `NAVER_CLIENT_ID`와 `NAVER_CLIENT_SECRET`이 있으면 네이버 뉴스 검색량까지 합산한다.

## 왜 이 소스를 썼나

| 소스 | 공개 지표 | 랭킹에서의 역할 |
| --- | --- | --- |
| Reddit | 업보트, 댓글수 | 독자 반응 강도를 가장 빠르게 확인 |
| Hacker News | 점수, 댓글수 | 기술·산업 구조 변화가 경제 이슈로 번질 조짐 포착 |
| Google News RSS | 다수 매체 노출 여부 | 특정 이슈가 여러 언론사에서 동시에 커지는지 확인 |
| Google News KR | 한국어 경제기사 확산도 | 한국 독자 접점이 높은 경제 토픽에 가중치 부여 |
| Naver News Search API (옵션) | 한국 포털 뉴스 검색량 | 한국 독자 검색 관심을 추가 반영 |
| YouTube API (옵션) | 조회수, 좋아요, 댓글수 | 시청형 반응이 큰 경제 이슈 보강 |

## 현재 기준 추천 발제 5개

2026년 3월 9일 기준 스냅샷은 [docs/initial-topic-brief-2026-03-09.md](/Users/air/codes/topics/docs/initial-topic-brief-2026-03-09.md)에 정리했다. 실데이터로 한 번 돌린 초기 우선순위는 아래 순서를 권장한다.

1. 유가 급등과 인플레이션 재점화
2. AI 데이터센터 전력·설비투자 경쟁
3. 중국 성장목표와 내수·부동산 회복성
4. 미국 고용 둔화와 연준 금리 딜레마
5. 주택·모기지 금리의 변곡점

## 실행 방법

```bash
cp .env.example .env
PYTHONPATH=src python3 -m topic_pitcher
```

JSON 디버그 출력:

```bash
PYTHONPATH=src python3 -m topic_pitcher --json
```

텔레그램 전송:

```bash
PYTHONPATH=src python3 -m topic_pitcher --send-telegram
```

## 환경 변수

- `TELEGRAM_BOT_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 채널 아이디 또는 `@channel_name`
- `YOUTUBE_API_KEY`: 선택. YouTube 통계를 쓸 때만 필요
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 선택. 네이버 뉴스 검색량을 붙일 때 필요
- `TOPIC_LOOKBACK_HOURS`: 기본 48시간
- `REDDIT_SUBREDDITS`: 기본 경제·투자·주택·기술 서브레딧 묶음
- `GOOGLE_NEWS_KR_HL`, `GOOGLE_NEWS_KR_GL`, `GOOGLE_NEWS_KR_CEID`: 한국판 구글뉴스 로케일

## 원격 스케줄

GitHub Actions 워크플로는 [daily-topic-pitch.yml](/Users/air/codes/topics/.github/workflows/daily-topic-pitch.yml)에 있다. `cron: "30 23 * * *"` 는 UTC 기준 23:30이며, 한국 시간으로는 매일 오전 8시 30분이다.

필수 GitHub Secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `YOUTUBE_API_KEY` (선택)
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (선택)

## 검증

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
