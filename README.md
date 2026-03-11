# Topic Pitcher

경제 뉴스 발제를 위해 공개 반응 신호와 매체 확산 신호를 함께 랭킹하는 일일 시스템이다. 기본 소스는 `Reddit`, `Hacker News`, `Bluesky`, `Mastodon`, `Google News RSS`, `Google News KR`이며, 한국 독자 가중치를 위해 `Naver Blog/Cafe`, `Naver DataLab`, `Naver News Search`를 선택적으로 붙일 수 있다. `YOUTUBE_API_KEY`가 있으면 YouTube 조회수·좋아요·댓글도 반영한다.

최근 30일 안에 이미 보낸 유사 주제는 [data/topic_history.json](/Users/air/codes/topics/data/topic_history.json) 기준으로 피하고, 거시경제 일반론보다 구체적 현장·산업·소비 사례가 있는 토픽을 우선한다.

## 왜 이 소스를 썼나

| 소스 | 공개 지표 | 랭킹에서의 역할 |
| --- | --- | --- |
| Reddit | 업보트, 댓글수 | 독자 반응 강도를 가장 빠르게 확인 |
| Hacker News | 점수, 댓글수 | 기술·산업 구조 변화가 경제 이슈로 번질 조짐 포착 |
| Bluesky | 좋아요, 리포스트, 답글, 인용수 | 기사보다 먼저 도는 구체적 사례·현장 반응 포착 |
| Mastodon | 링크 공유 계정수, 공유 횟수 | 커뮤니티 안에서 급속히 퍼지는 기사 링크 포착 |
| Google News RSS | 다수 매체 노출 여부 | 특정 이슈가 여러 언론사에서 동시에 커지는지 확인 |
| Google News KR | 한국어 경제기사 확산도 | 한국 독자 접점이 높은 경제 토픽에 가중치 부여 |
| Naver Blog/Cafe API (옵션) | 검색 결과량, 최신 게시물 제목 | 한국 커뮤니티에서 붙는 생활경제·산업 화제 포착 |
| Naver DataLab (옵션) | 검색지수, 최근 상승폭 | 한국 독자 수요가 실제로 붙는지 보정 |
| Naver News Search API (옵션) | 한국 포털 뉴스 검색량 | 한국 독자 검색 관심을 추가 반영 |
| YouTube API (옵션) | 조회수, 좋아요, 댓글수 | 시청형 반응이 큰 경제 이슈 보강 |

## 편집 원칙

1. 같은 주제는 30일 안에 반복하지 않는다.
2. 추상적 거시지표보다 `공항 보안검색`, `반려동물 미용`, `폐로 작업`, `방산 공장`처럼 장면이 그려지는 사안을 우선한다.
3. 구체적 사례를 먼저 보여주고, 그 뒤에 금리·예산·산업구조 같은 큰 흐름을 붙인다.

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

`.env`는 실행 시 자동으로 읽는다. 로컬에서는 `export` 없이 `.env` 파일만 채워두면 된다.

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
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 선택. 네이버 뉴스·블로그·카페·DataLab을 붙일 때 필요
- `BLUESKY_BASE_URL`: 기본 `https://public.api.bsky.app`
- `BLUESKY_LIMIT`: 토픽당 검색 게시물 수. 기본 5
- `MASTODON_BASE_URLS`: 기본 `https://mastodon.social`
- `MASTODON_LIMIT`: 인스턴스당 링크 트렌드 수. 기본 10
- `TOPIC_LOOKBACK_HOURS`: 기본 48시간
- `REDDIT_SUBREDDITS`: 기본 경제·투자·주택·기술 서브레딧 묶음
- `GOOGLE_NEWS_KR_HL`, `GOOGLE_NEWS_KR_GL`, `GOOGLE_NEWS_KR_CEID`: 한국판 구글뉴스 로케일

## 원격 스케줄

GitHub Actions 워크플로는 [daily-topic-pitch.yml](/Users/air/codes/topics/.github/workflows/daily-topic-pitch.yml)에 있다. `cron: "30 23 * * *"` 는 UTC 기준 23:30이며, 한국 시간으로는 매일 오전 8시 30분이다.

발송이 끝나면 최신 발제 이력은 [data/topic_history.json](/Users/air/codes/topics/data/topic_history.json)에 기록되고, 워크플로가 그 파일을 자동 커밋해 다음 런에서 재사용한다.

필수 GitHub Secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `YOUTUBE_API_KEY` (선택)
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (선택)

## 검증

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
