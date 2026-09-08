# 어드민 포트폴리오 퍼널 대시보드 — 설계

작성일: 2026-09-08

## 배경

`/admin` 대시보드에는 현재 방문 통계 카드 하나만 있다. 원천 데이터는
`DailyVisit`(날짜별 카운트, 세션당 하루 1회)뿐이라 "방문자가 얼마나 왔나"는
알 수 있어도 "얼마나 깊이 봤나"는 알 수 없다.

공개 페이지는 단일 페이지 구조이고, 방문자의 행동 지점은 네 곳이다.
히어로 진입 → 프로젝트 섹션 도달 → 프로젝트 상세 모달 열람 →
이력서 다운로드 또는 연락 링크 클릭. 이 경로의 이탈 지점을 보이게 만드는 것이
이 작업의 목적이다.

따라서 이 작업은 대시보드 추가가 아니라 **이벤트 수집 · 집계 · 시각화**
세 계층을 새로 만드는 일이다.

## 목표

- `/admin`에 4단계 퍼널 섹션을 추가한다.
- 단계별 이탈뿐 아니라 그 원인을 좁힐 수 있는 보조 지표(전환 내역,
  프로젝트별 열람 랭킹)를 함께 보여준다.
- 공개 페이지의 동작과 안정성에 영향을 주지 않는다.

## 범위 밖

- 일자별 전환율 추이 그래프. 표본이 하루 한 자릿수인 구간에서는 0%와 100%만
  튀어 오독을 유발한다. 데이터가 쌓인 뒤 별도로 검토한다.
- 방문자 개인 식별, IP·User-Agent 저장, 외부 애널리틱스 연동.
- 과거 데이터 소급 집계. 원천 이벤트가 존재하지 않아 불가능하다.

## 알려진 한계

대시보드는 배포 시점부터 쌓이는 데이터만 보여준다. 배포 직후 며칠간은 사실상
비어 있으므로, 카드 헤더에 집계 시작일을 표기하고 데이터가 없을 때는 빈 상태
문구를 노출한다.

## 데이터 모델

`DailyVisit`은 누적 카운터로 그대로 유지한다. 신규 테이블을 추가한다.

```
VisitEvent
  id           PK
  session_key  str(16)   익명 세션 키 (secrets.token_hex(8), 쿠키 세션에 보관)
  stage        str(24)   visit | projects_view | project_detail | convert
  project_id   int       기본값 0 (stage=project_detail일 때만 의미 있음)
  detail       str(32)   기본값 '' (stage=convert일 때 전환 종류)
  date         str(10)   YYYY-MM-DD, KST 기준. 기간 필터용
  created_at   datetime
  UNIQUE(session_key, stage, project_id, detail)
```

`project_id`와 `detail`은 NULL을 쓰지 않고 `0` / `''`을 기본값으로 둔다.
NULL은 유니크 제약에서 서로 다른 값으로 취급되어 SQLite와 PostgreSQL 양쪽에서
중복 억제가 조용히 깨진다. 기본값을 주면 세션당 단계별 1회, 프로젝트별 1회,
전환 종류별 1회가 DB 레벨에서 보장된다.

`project_id`에 외래 키는 걸지 않는다. 프로젝트가 삭제되어도 과거 집계가
사라지면 안 되기 때문이다. 삭제된 프로젝트는 표시 단계에서 처리한다.

전환 종류(`detail`) 화이트리스트: `resume`, `email`, `linkedin`, `github`,
`blog`, `remember`.

## 수집 경로

- `visit` — 기존 `track_visit()` 안에서 `DailyVisit` 증가와 함께 서버측 기록.
  JS가 필요 없다.
- 나머지 세 단계 — `POST /api/track`에 `navigator.sendBeacon`으로 전송.
  - `projects_view`: `#projects` 섹션에 `IntersectionObserver`, 40% 노출 시 1회
  - `project_detail`: 프로젝트 모달이 열릴 때 해당 project id와 함께
  - `convert`: 이력서 링크와 연락 카드 클릭 (히어로·컨택 섹션 양쪽)

세션 키는 `secrets.token_hex(8)`로 만들어 Flask 세션에 보관한다. 저장되는 값은
이 익명 키뿐이고 IP와 User-Agent는 남기지 않는다. IP는 지금처럼 레이트리밋
메모리에서만 쓴다.

## 엔드포인트

`POST /api/track`

앱 전역에 `CSRFProtect`가 걸려 있어 공개 POST는 기본적으로 차단된다.
`@csrf.exempt`를 적용하고 다음으로 방어한다.

- 기존 `_rate_limited(ip, max_hits=60, window=60)`
- `stage`는 `projects_view`, `project_detail`, `convert`만 받는다. `visit`은
  서버측에서만 기록하며 이 엔드포인트로는 위조할 수 없다.
- `detail`도 화이트리스트로 대조하고, 미일치 값은 조용히 무시한다.
- 응답은 성공·무시·중복 모두 `204`. 수집 여부를 외부에 노출하지 않는다.

실패는 `track_visit()`과 동일하게 삼키고 `db.session.rollback()`을 호출한다.
유니크 제약 위반(`IntegrityError`)은 정상적인 중복이므로 조용히 무시한다.
통계 때문에 공개 페이지가 죽어서는 안 된다.

## 보관 기간

180일이 지난 행은 기존 `_marker_version` / `_set_marker` 패턴을 사용해
하루 1회 정리한다.

## 집계 로직

집계 함수는 `analytics.py` 신규 모듈에 둔다. `app.py`가 이미 72KB로 커져 있고,
모델과 세션을 인자로 받는 순수 함수로 두면 순환 import를 피하면서 단위 테스트가
쉬워진다.

단계 값은 stage별 단순 카운트가 아니라 **그 단계 이상 도달한 세션 수**로
정의한다.

```
rank: visit=1, projects_view=2, project_detail=3, convert=4
세션별 max_rank를 구한 뒤, 단계 i의 값 = (max_rank >= i 인 세션 수)
```

단순 카운트를 쓰면 `projects_view` 없이 `project_detail`만 기록된 세션
(스크롤 이벤트 유실, 딥링크 진입) 때문에 3단계가 2단계보다 커지는 역전이 생겨
퍼널이 깨진다. 누적 정의는 단조 감소를 구조적으로 보장한다.

함께 계산하는 값:

- 단계별 전환율: 각 단계 ÷ 직전 단계
- 전체 전환율: 최종 단계 ÷ 방문
- 전환 내역: `detail`별 고유 세션 수
- 프로젝트 랭킹: `project_id`별 고유 세션 수 상위 8개.
  현재 존재하지 않는 id는 `삭제됨 (#id)`로 표기한다.

기간은 7일과 30일 두 가지이며 퍼널·전환 내역·랭킹 모두 선택된 기간에 연동된다.

## UI

방문 통계 카드 바로 아래에 `admin-section-card` 하나를 추가한다.
`templates/admin.html`이 이미 389줄에 인라인 style·script를 포함하고 있으므로,
새 마크업은 `templates/_admin_funnel.html` 파셜로 분리하고 `{% include %}` 한다.

- 7일 / 30일 토글은 기존 `.range-btn` 클래스를 그대로 사용한다. 서버가 두 기간
  데이터를 모두 렌더하고 JS는 표시만 전환한다. 기존 방문 차트와 동일한 방식이라
  추가 요청이 발생하지 않는다.
- 퍼널은 SVG 없이 CSS 폭 비율 기반 가로 막대 4행으로 그린다.
  각 행은 단계명, 고유 세션 수, 직전 단계 대비 전환율을 보여준다.
  반응형 처리가 단순하다.
- 카드 헤더에 집계 시작일을 표기한다.
- 이벤트가 하나도 없으면 "아직 수집된 이벤트가 없습니다" 빈 상태를 노출한다.

## 테스트

`tests/test_admin_funnel.py`를 추가하고 기존 `tests/conftest.py` 픽스처를
재사용한다.

1. 같은 세션이 같은 이벤트를 두 번 보내면 행이 1개만 생긴다.
2. 화이트리스트 밖 `stage`는 `204`를 반환하되 행을 만들지 않는다.
3. `projects_view` 없이 `project_detail`만 있는 세션도 2단계 집계에 포함되어
   퍼널이 단조 감소한다.
4. `/admin`은 비로그인 접근이 계속 차단되고, 로그인하면 퍼널 섹션이 렌더된다.
5. 삭제된 프로젝트 id가 랭킹에서 안전하게 표시된다.
