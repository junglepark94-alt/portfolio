# 어드민 포트폴리오 퍼널 대시보드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/admin`에 방문 → 프로젝트 섹션 도달 → 상세 열람 → 전환의 4단계 퍼널과 전환 내역·프로젝트 열람 랭킹을 보여주는 섹션을 추가한다.

**Architecture:** 신규 `VisitEvent` 테이블에 익명 세션 키 기반 이벤트를 적재한다. `visit`은 서버측 `track_visit()`에서, 나머지 세 단계는 공개 페이지 JS가 `POST /api/track`으로 보낸다. 집계는 `analytics.py`의 순수 함수가 담당하고, `admin_dashboard`가 7일·30일 두 벌을 만들어 `templates/_admin_funnel.html` 파셜에 넘긴다.

**Tech Stack:** Flask, Flask-SQLAlchemy, Flask-WTF(CSRFProtect), Jinja2, 바닐라 JS, pytest

## Global Constraints

- 단계 상수는 `FUNNEL_STAGES = ('visit', 'projects_view', 'project_detail', 'convert')`, 순위는 이 순서대로 1~4.
- `/api/track`이 받는 stage는 `TRACKABLE_STAGES = ('projects_view', 'project_detail', 'convert')`뿐. `visit`은 서버측 전용이며 위조 불가.
- 전환 종류는 `CONVERT_KINDS = ('resume', 'email', 'linkedin', 'github', 'blog', 'remember')`.
- `VisitEvent.project_id`는 NULL 대신 기본값 `0`, `detail`은 NULL 대신 기본값 `''`. NULL은 유니크 제약에서 서로 다른 값으로 취급되어 중복 억제가 깨진다.
- 저장하는 식별자는 익명 세션 키뿐. IP·User-Agent는 저장하지 않는다.
- 수집 실패는 항상 삼키고 `db.session.rollback()`. 통계 때문에 공개 페이지가 죽으면 안 된다.
- `/api/track`은 성공·무시·중복 모두 `204`를 반환한다.
- 보관 기간 `VISIT_EVENT_RETENTION_DAYS = 180`.
- 날짜 문자열은 모두 KST 기준 `YYYY-MM-DD` (`_today_kst()`).
- 테스트 실행: `python -m pytest tests/test_admin_funnel.py -v`

## File Structure

| 파일 | 책임 |
|---|---|
| `app.py` (수정) | `VisitEvent` 모델, `_session_key()`, `record_event()`, `prune_visit_events()`, `POST /api/track`, `admin_dashboard` 집계 호출 |
| `analytics.py` (신규) | 이벤트 튜플 → 퍼널/전환/랭킹 딕셔너리. 순수 함수, DB·Flask 비의존 |
| `templates/_admin_funnel.html` (신규) | 퍼널 섹션 마크업 + 전용 CSS + 기간 토글 JS |
| `templates/admin.html` (수정) | 파셜 `{% include %}` 한 줄 |
| `templates/index.html` (수정) | 카드 `data-pid`, 전환 링크 `data-convert` |
| `static/js/main.js` (수정) | `window.trackFunnel`, IntersectionObserver, 모달 훅, 전환 클릭 훅 |
| `tests/test_admin_funnel.py` (신규) | 전 계층 테스트 |

## 설계 대비 변경 1건

설계는 `#projects` 섹션 노출 **40%** 에서 `projects_view`를 기록한다고 했으나, 이 섹션은 뷰포트보다 높아 40%에 도달하지 않는 화면이 많다. 그 경우 2단계가 영구히 0이 되어 퍼널 전체가 무의미해진다. 따라서 **threshold 0.01(섹션이 화면에 들어오는 순간)** 로 구현한다.

---

### Task 1: VisitEvent 모델과 이벤트 기록 헬퍼

**Files:**
- Modify: `app.py` (import 구역, `track_visit()` 정의 위)
- Test: `tests/test_admin_funnel.py`

**Interfaces:**
- Consumes: 기존 `_today_kst()`, `db`, `session`
- Produces: `VisitEvent` 모델, `FUNNEL_STAGES`, `TRACKABLE_STAGES`, `CONVERT_KINDS`, `VISIT_EVENT_RETENTION_DAYS`, `_session_key() -> str`, `record_event(stage: str, project_id: int = 0, detail: str = '') -> bool`

- [ ] **Step 1: Write the failing test**

`tests/test_admin_funnel.py`를 새로 만든다.

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app import VisitEvent, _today_kst, db


def _ev(session_key, stage, project_id=0, detail=''):
    return VisitEvent(session_key=session_key, stage=stage, project_id=project_id,
                      detail=detail, date=_today_kst())


def test_duplicate_event_rows_are_rejected(portfolio_app):
    db.session.add(_ev('s1', 'convert', detail='resume'))
    db.session.commit()

    db.session.add(_ev('s1', 'convert', detail='resume'))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    assert VisitEvent.query.count() == 1


def test_different_projects_are_separate_rows(portfolio_app):
    db.session.add(_ev('s1', 'project_detail', project_id=1))
    db.session.add(_ev('s1', 'project_detail', project_id=2))
    db.session.commit()

    assert VisitEvent.query.count() == 2


def test_index_records_one_visit_event_per_session(client):
    client.get('/')
    client.get('/')

    assert VisitEvent.query.filter_by(stage='visit').count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_funnel.py -v`
Expected: FAIL — `ImportError: cannot import name 'VisitEvent' from 'app'`

- [ ] **Step 3: Write minimal implementation**

`app.py` 상단 import 블록의 `import threading` 다음 줄에 추가한다.

```python
import secrets
```

`app.py`의 `def track_visit():` 정의 **바로 위**에 상수와 모델을 추가한다.

```python
FUNNEL_STAGES = ('visit', 'projects_view', 'project_detail', 'convert')
TRACKABLE_STAGES = ('projects_view', 'project_detail', 'convert')
CONVERT_KINDS = ('resume', 'email', 'linkedin', 'github', 'blog', 'remember')
VISIT_EVENT_RETENTION_DAYS = 180


class VisitEvent(db.Model):
    """퍼널 단계별 익명 이벤트. 세션당 (stage, project_id, detail) 조합 1회."""
    __tablename__ = 'visit_event'
    id = db.Column(db.Integer, primary_key=True)
    session_key = db.Column(db.String(16), index=True, nullable=False)
    stage = db.Column(db.String(24), index=True, nullable=False)
    project_id = db.Column(db.Integer, default=0, nullable=False)
    detail = db.Column(db.String(32), default='', nullable=False)
    date = db.Column(db.String(10), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('session_key', 'stage', 'project_id', 'detail',
                            name='uq_visit_event_session_stage'),
    )


def _session_key():
    """익명 세션 키. IP·UA는 저장하지 않는다."""
    key = session.get('sk')
    if not key:
        key = secrets.token_hex(8)
        session['sk'] = key
    return key


def record_event(stage, project_id=0, detail=''):
    """이벤트 1건 기록. 중복(유니크 제약 위반)과 그 밖의 실패는 조용히 무시한다."""
    try:
        db.session.add(VisitEvent(
            session_key=_session_key(),
            stage=stage,
            project_id=int(project_id or 0),
            detail=detail or '',
            date=_today_kst(),
        ))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False
```

`track_visit()`의 본문 첫 줄(`try:` 바로 다음)에 방문 이벤트 기록을 추가한다. 일자별 조기 반환보다 **앞에** 두어야 세션 생애 1회가 기록된다.

```python
def track_visit():
    """공개 페이지 방문 기록. 같은 세션은 하루 1회만 카운트."""
    try:
        record_event('visit')
        today = _today_kst()
```

(이하 기존 본문은 그대로 둔다.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_funnel.py -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 기존 테스트 전부 통과

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_admin_funnel.py
git commit -m "feat: record anonymous funnel visit events"
```

---

### Task 2: /api/track 수집 엔드포인트

**Files:**
- Modify: `app.py` (`@app.route('/api/youtube')` 정의 위)
- Test: `tests/test_admin_funnel.py`

**Interfaces:**
- Consumes: Task 1의 `record_event()`, `TRACKABLE_STAGES`, `CONVERT_KINDS`; 기존 `_rate_limited()`, `_client_ip()`, `csrf`
- Produces: `POST /api/track` — JSON 본문 `{stage, project_id, detail}`, 항상 `204`

- [ ] **Step 1: Write the failing test**

`tests/test_admin_funnel.py` 끝에 추가한다.

```python
def test_track_endpoint_records_once_and_ignores_unknown_stage(client):
    assert client.post('/api/track', json={'stage': 'projects_view'}).status_code == 204
    client.post('/api/track', json={'stage': 'projects_view'})
    assert client.post('/api/track', json={'stage': 'admin_wipe'}).status_code == 204

    assert [r.stage for r in VisitEvent.query.all()] == ['projects_view']


def test_track_endpoint_rejects_forged_visit_stage(client):
    client.post('/api/track', json={'stage': 'visit'})

    assert VisitEvent.query.filter_by(stage='visit').count() == 0


def test_track_endpoint_rejects_unknown_convert_kind(client):
    client.post('/api/track', json={'stage': 'convert', 'detail': 'bitcoin'})

    assert VisitEvent.query.count() == 0


def test_track_endpoint_scrubs_irrelevant_fields(client):
    client.post('/api/track', json={'stage': 'convert', 'detail': 'resume', 'project_id': 7})

    row = VisitEvent.query.one()
    assert (row.stage, row.detail, row.project_id) == ('convert', 'resume', 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_funnel.py -k track -v`
Expected: FAIL — 라우트가 없어 404가 오므로 첫 `assert ... == 204`에서 실패

- [ ] **Step 3: Write minimal implementation**

`app.py`의 `@app.route('/api/youtube')` 정의 **바로 위**에 추가한다.

```python
@app.route('/api/track', methods=['POST'])
@csrf.exempt
def api_track():
    """공개 페이지 퍼널 이벤트 수집. 성공·무시·중복 모두 204."""
    if _rate_limited(f'track:{_client_ip()}', max_hits=60, window=60):
        return ('', 204)

    data = request.get_json(silent=True) or {}
    stage = str(data.get('stage') or '')
    if stage not in TRACKABLE_STAGES:
        return ('', 204)

    detail = str(data.get('detail') or '')
    if stage == 'convert':
        if detail not in CONVERT_KINDS:
            return ('', 204)
    else:
        detail = ''

    try:
        project_id = int(data.get('project_id') or 0)
    except (TypeError, ValueError):
        project_id = 0
    if stage != 'project_detail':
        project_id = 0

    record_event(stage, project_id, detail)
    return ('', 204)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_funnel.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_admin_funnel.py
git commit -m "feat: add the public funnel tracking endpoint"
```

---

### Task 3: analytics.py 집계 함수

**Files:**
- Create: `analytics.py`
- Test: `tests/test_admin_funnel.py`

**Interfaces:**
- Consumes: 없음 (DB·Flask 비의존 순수 모듈)
- Produces:
  - `FUNNEL_LABELS: list[tuple[str, str]]`
  - `CONVERT_LABELS: dict[str, str]`
  - `build_funnel_stats(events, project_titles, top_n=8) -> dict`
    - `events`: `(session_key, stage, project_id, detail)` 튜플의 이터러블
    - `project_titles`: `{project_id: title}`
    - 반환: `{'steps': [{'stage','label','count','width','rate'}], 'overall': float, 'conversions': [{'kind','label','count'}], 'ranking': [{'project_id','title','count'}], 'sessions': int}`
    - `steps[0]['rate']`는 `None` (기준 단계)

- [ ] **Step 1: Write the failing test**

`tests/test_admin_funnel.py` 상단 import에 아래 한 줄을 더한다.

```python
from analytics import build_funnel_stats
```

그리고 파일 끝에 추가한다.

```python
def test_funnel_is_monotonic_when_a_stage_is_missing():
    events = [
        ('s1', 'visit', 0, ''),
        ('s1', 'project_detail', 3, ''),   # projects_view 유실
        ('s2', 'visit', 0, ''),
    ]

    stats = build_funnel_stats(events, {3: '프로젝트 A'})

    counts = [s['count'] for s in stats['steps']]
    assert counts == [2, 1, 1, 0]
    assert counts == sorted(counts, reverse=True)
    assert stats['steps'][0]['rate'] is None
    assert stats['steps'][1]['rate'] == 50.0
    assert stats['sessions'] == 2


def test_widths_are_relative_to_the_first_stage():
    events = [
        ('s1', 'visit', 0, ''), ('s1', 'projects_view', 0, ''),
        ('s2', 'visit', 0, ''), ('s3', 'visit', 0, ''), ('s4', 'visit', 0, ''),
    ]

    stats = build_funnel_stats(events, {})

    assert [s['width'] for s in stats['steps']] == [100.0, 25.0, 0.0, 0.0]


def test_conversion_breakdown_counts_unique_sessions():
    events = [
        ('s1', 'visit', 0, ''), ('s1', 'convert', 0, 'resume'),
        ('s2', 'visit', 0, ''), ('s2', 'convert', 0, 'resume'),
        ('s2', 'convert', 0, 'email'),
    ]

    stats = build_funnel_stats(events, {})

    assert stats['conversions'][0] == {'kind': 'resume', 'label': '이력서 다운로드', 'count': 2}
    assert stats['conversions'][1] == {'kind': 'email', 'label': '이메일', 'count': 1}
    assert stats['overall'] == 100.0


def test_ranking_labels_a_deleted_project_and_respects_top_n():
    events = [('s1', 'visit', 0, ''), ('s1', 'project_detail', 99, ''),
              ('s1', 'project_detail', 1, ''), ('s2', 'project_detail', 1, '')]

    stats = build_funnel_stats(events, {1: '프로젝트 A'}, top_n=1)
    assert stats['ranking'] == [{'project_id': 1, 'title': '프로젝트 A', 'count': 2}]

    full = build_funnel_stats(events, {1: '프로젝트 A'})
    assert full['ranking'][1] == {'project_id': 99, 'title': '삭제됨 (#99)', 'count': 1}


def test_empty_input_is_all_zero():
    stats = build_funnel_stats([], {})

    assert [s['count'] for s in stats['steps']] == [0, 0, 0, 0]
    assert [s['width'] for s in stats['steps']] == [0.0, 0.0, 0.0, 0.0]
    assert stats['overall'] == 0.0
    assert stats['sessions'] == 0
    assert stats['conversions'] == []
    assert stats['ranking'] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_funnel.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analytics'`

- [ ] **Step 3: Write minimal implementation**

`analytics.py`를 새로 만든다.

```python
"""어드민 퍼널 대시보드 집계.

DB와 Flask에 의존하지 않는 순수 함수만 둔다. app.py가 이벤트 튜플을 넘긴다.
"""

FUNNEL_LABELS = [
    ('visit', '방문'),
    ('projects_view', '프로젝트 섹션 도달'),
    ('project_detail', '프로젝트 상세 열람'),
    ('convert', '전환 (이력서·연락)'),
]

CONVERT_LABELS = {
    'resume': '이력서 다운로드',
    'email': '이메일',
    'linkedin': '링크드인',
    'github': '깃허브',
    'blog': '블로그',
    'remember': '리멤버',
}


def _pct(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


def build_funnel_stats(events, project_titles, top_n=8):
    """이벤트 튜플에서 퍼널·전환 내역·프로젝트 랭킹을 만든다.

    단계 값은 stage별 단순 카운트가 아니라 '그 단계 이상 도달한 세션 수'다.
    단순 카운트는 projects_view가 유실된 세션 때문에 3단계가 2단계보다
    커지는 역전을 만들 수 있다. 누적 정의는 단조 감소를 보장한다.
    """
    ranks = {stage: i + 1 for i, (stage, _) in enumerate(FUNNEL_LABELS)}
    best = {}
    converts = {}
    projects = {}

    for session_key, stage, project_id, detail in events:
        rank = ranks.get(stage)
        if rank is None:
            continue
        if rank > best.get(session_key, 0):
            best[session_key] = rank
        if stage == 'convert' and detail:
            converts.setdefault(detail, set()).add(session_key)
        if stage == 'project_detail' and project_id:
            projects.setdefault(project_id, set()).add(session_key)

    steps = []
    previous = None
    for i, (stage, label) in enumerate(FUNNEL_LABELS, start=1):
        count = sum(1 for rank in best.values() if rank >= i)
        steps.append({
            'stage': stage,
            'label': label,
            'count': count,
            'width': 0.0,
            'rate': None if previous is None else _pct(count, previous),
        })
        previous = count

    top = steps[0]['count']
    for step in steps:
        step['width'] = _pct(step['count'], top)

    conversions = sorted(
        [{'kind': kind, 'label': CONVERT_LABELS.get(kind, kind), 'count': len(keys)}
         for kind, keys in converts.items()],
        key=lambda row: (-row['count'], row['kind']),
    )

    ranking = sorted(
        [{'project_id': pid,
          'title': project_titles.get(pid) or '삭제됨 (#%d)' % pid,
          'count': len(keys)}
         for pid, keys in projects.items()],
        key=lambda row: (-row['count'], row['project_id']),
    )[:top_n]

    return {
        'steps': steps,
        'overall': _pct(steps[-1]['count'], top),
        'conversions': conversions,
        'ranking': ranking,
        'sessions': len(best),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_funnel.py -v`
Expected: PASS — 12 passed

- [ ] **Step 5: Commit**

```bash
git add analytics.py tests/test_admin_funnel.py
git commit -m "feat: add funnel aggregation for the admin dashboard"
```

---

### Task 4: 보관 기간 정리

**Files:**
- Modify: `app.py` (Task 1에서 추가한 `record_event()` 아래)
- Test: `tests/test_admin_funnel.py`

**Interfaces:**
- Consumes: Task 1의 `VisitEvent`, `VISIT_EVENT_RETENTION_DAYS`; 기존 `ContentSync`, `KST`, `_today_kst()`
- Produces: `prune_visit_events(retention_days=VISIT_EVENT_RETENTION_DAYS) -> int` — 삭제한 행 수. 같은 날 두 번째 호출은 `0`

- [ ] **Step 1: Write the failing test**

`tests/test_admin_funnel.py` 끝에 추가한다.

```python
def test_prune_removes_events_past_retention_once_a_day(portfolio_app):
    from app import prune_visit_events

    db.session.add(VisitEvent(session_key='old', stage='visit', project_id=0,
                              detail='', date='2020-01-01'))
    db.session.add(_ev('new', 'visit'))
    db.session.commit()

    assert prune_visit_events() == 1
    assert [r.session_key for r in VisitEvent.query.all()] == ['new']
    assert prune_visit_events() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_funnel.py -k prune -v`
Expected: FAIL — `ImportError: cannot import name 'prune_visit_events' from 'app'`

- [ ] **Step 3: Write minimal implementation**

`app.py`의 `record_event()` 아래에 추가한다.

```python
def prune_visit_events(retention_days=VISIT_EVENT_RETENTION_DAYS):
    """보관 기간이 지난 이벤트를 삭제한다. 하루 1회만 실제로 수행."""
    today = _today_kst()
    marker = db.session.get(ContentSync, 'visit_event_pruned_on')
    if marker is not None and marker.value == today:
        return 0

    cutoff = (datetime.now(KST).date() - timedelta(days=retention_days)).strftime('%Y-%m-%d')
    try:
        removed = VisitEvent.query.filter(VisitEvent.date < cutoff).delete(
            synchronize_session=False)
        if marker is None:
            marker = ContentSync(key='visit_event_pruned_on')
            db.session.add(marker)
        marker.value = today
        marker.applied_at = datetime.utcnow()
        db.session.commit()
        return removed
    except Exception:
        db.session.rollback()
        return 0
```

`ContentSync`는 `app.py` 뒤쪽(462행 부근)에 정의되어 있다. 함수 본문에서만 참조하므로 정의 순서는 문제되지 않는다.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_funnel.py -v`
Expected: PASS — 13 passed

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_admin_funnel.py
git commit -m "feat: prune funnel events past the retention window"
```

---

### Task 5: 어드민 대시보드 배선과 퍼널 섹션

**Files:**
- Modify: `app.py` (import 구역, `admin_dashboard()` 1055-1085행 부근)
- Create: `templates/_admin_funnel.html`
- Modify: `templates/admin.html` (방문 통계 카드를 닫는 `</div>` 다음)
- Test: `tests/test_admin_funnel.py`

**Interfaces:**
- Consumes: Task 3의 `build_funnel_stats()`, Task 4의 `prune_visit_events()`, Task 1의 `VisitEvent`
- Produces: `admin.html` 템플릿 컨텍스트에 `funnel` (`{'7': stats, '30': stats}`)과 `funnel_meta` (`{'since': str}`) 추가

- [ ] **Step 1: Write the failing test**

`tests/test_admin_funnel.py` 끝에 추가한다.

```python
def _login(client):
    with client.session_transaction() as sess:
        sess['logged_in'] = True


def test_admin_dashboard_requires_login(client):
    assert client.get('/admin').status_code == 302


def test_admin_dashboard_renders_the_empty_funnel(client):
    _login(client)

    html = client.get('/admin').get_data(as_text=True)

    assert '포트폴리오 퍼널' in html
    assert '아직 수집된 이벤트가 없습니다' in html


def test_admin_dashboard_renders_collected_funnel_data(client, portfolio_app):
    from app import Project

    project = Project.query.first()
    db.session.add_all([
        _ev('s1', 'visit'),
        _ev('s1', 'projects_view'),
        _ev('s1', 'project_detail', project_id=project.id),
        _ev('s1', 'convert', detail='resume'),
        _ev('s2', 'visit'),
    ])
    db.session.commit()
    _login(client)

    html = client.get('/admin').get_data(as_text=True)

    assert '프로젝트 상세 열람' in html
    assert '이력서 다운로드' in html
    assert '프로젝트별 열람' in html
    assert '아직 수집된 이벤트가 없습니다' not in html
    assert '아직 열람 기록이 없습니다' not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_funnel.py -k admin -v`
Expected: FAIL — `assert '포트폴리오 퍼널' in html`

- [ ] **Step 3: Write minimal implementation**

**3-1.** `app.py` 상단 import 블록의 `import threading` 다음 줄에 추가한다.

```python
from analytics import build_funnel_stats
```

**3-2.** `admin_dashboard()`에서 `visit_stats = {...}` 딕셔너리 정의 다음, `return render_template(...)` 앞에 추가한다.

```python
    # 퍼널 통계: 7일 / 30일 두 벌을 한 번에 렌더하고 화면에서 토글한다
    prune_visit_events()
    titles = {p.id: p.title for p in projects}
    funnel = {}
    for span in (7, 30):
        since = (today - timedelta(days=span - 1)).strftime('%Y-%m-%d')
        rows = db.session.query(
            VisitEvent.session_key, VisitEvent.stage,
            VisitEvent.project_id, VisitEvent.detail,
        ).filter(VisitEvent.date >= since).all()
        funnel[str(span)] = build_funnel_stats(rows, titles)
    funnel_meta = {'since': db.session.query(db.func.min(VisitEvent.date)).scalar() or '-'}
```

**3-3.** 같은 함수의 `return render_template(...)`을 아래로 교체한다.

```python
    return render_template('admin.html', projects=projects, profile=profile,
                           gallery_items=gallery_items, db_info=db_info,
                           visit_stats=visit_stats, funnel=funnel,
                           funnel_meta=funnel_meta)
```

**3-4.** `templates/_admin_funnel.html`을 새로 만든다.

```html
{# 포트폴리오 퍼널 — admin.html에서 include #}
<div class="admin-section-card">
  <div class="asc-header">
    <div>
      <div class="asc-label">포트폴리오 퍼널</div>
      <div class="asc-summary">방문 → 프로젝트 섹션 → 상세 열람 → 전환 · 집계 시작 {{ funnel_meta.since }}</div>
    </div>
    <div class="chart-range" role="group" aria-label="퍼널 기간 선택">
      <button type="button" class="range-btn funnel-range-btn" data-frange="7">7일</button>
      <button type="button" class="range-btn funnel-range-btn is-active" data-frange="30">30일</button>
    </div>
  </div>

  <div class="funnel-body">
    {% for key in ['7', '30'] %}
    {% set f = funnel[key] %}
    <div class="funnel-pane" data-frange="{{ key }}"{% if key == '7' %} hidden{% endif %}>
      {% if f.sessions == 0 %}
      <p class="funnel-empty">아직 수집된 이벤트가 없습니다.</p>
      {% else %}
      <ol class="funnel-steps">
        {% for s in f.steps %}
        <li class="funnel-step">
          <div class="fs-head">
            <span class="fs-label">{{ s.label }}</span>
            <span class="fs-count">{{ s.count }}<span class="fs-unit">세션</span></span>
          </div>
          <div class="fs-bar"><span style="width:{{ s.width }}%"></span></div>
          <div class="fs-rate">{% if s.rate is none %}기준{% else %}직전 대비 {{ s.rate }}%{% endif %}</div>
        </li>
        {% endfor %}
      </ol>
      <p class="funnel-overall">방문 대비 최종 전환율 <strong>{{ f.overall }}%</strong></p>

      <div class="funnel-grid">
        <section>
          <h4 class="funnel-h">전환 내역</h4>
          {% if f.conversions %}
          <table class="funnel-table">
            <tbody>
              {% for c in f.conversions %}
              <tr><td>{{ c.label }}</td><td class="num">{{ c.count }}</td></tr>
              {% endfor %}
            </tbody>
          </table>
          {% else %}
          <p class="funnel-empty">아직 전환이 없습니다.</p>
          {% endif %}
        </section>
        <section>
          <h4 class="funnel-h">프로젝트별 열람</h4>
          {% if f.ranking %}
          <table class="funnel-table">
            <tbody>
              {% for r in f.ranking %}
              <tr><td>{{ r.title }}</td><td class="num">{{ r.count }}</td></tr>
              {% endfor %}
            </tbody>
          </table>
          {% else %}
          <p class="funnel-empty">아직 열람 기록이 없습니다.</p>
          {% endif %}
        </section>
      </div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
</div>

<style>
  .funnel-body { padding:1.5rem; }
  .funnel-empty { color:var(--muted); font-size:0.86rem; margin:0.4rem 0; }
  .funnel-steps { list-style:none; margin:0 0 1rem; padding:0; }
  .funnel-step + .funnel-step { margin-top:0.9rem; }
  .fs-head { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:0.35rem; }
  .fs-label { font-size:0.88rem; color:var(--text-2); }
  .fs-count { font-size:1.15rem; font-weight:700; color:var(--text); letter-spacing:-0.01em; }
  .fs-unit { font-size:0.72rem; font-weight:500; color:var(--muted); margin-left:0.22rem; }
  .fs-bar { background:var(--bg); border:1px solid var(--border); border-radius:6px; height:14px; overflow:hidden; }
  .fs-bar > span { display:block; height:100%; background:var(--accent); border-radius:5px 0 0 5px; transition:width .25s; }
  .fs-rate { font-size:0.75rem; color:var(--muted); margin-top:0.28rem; }
  .funnel-overall { font-size:0.86rem; color:var(--text-2); margin:0 0 1.5rem; }
  .funnel-overall strong { color:var(--accent); }
  .funnel-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:1.25rem; }
  .funnel-h { font-size:0.82rem; font-weight:600; color:var(--text-2); margin:0 0 0.5rem; }
  .funnel-table { width:100%; border-collapse:collapse; font-size:0.84rem; }
  .funnel-table td { padding:0.42rem 0; border-bottom:1px solid var(--border); color:var(--text-2); }
  .funnel-table td.num { text-align:right; font-weight:600; color:var(--text); width:4rem; }
  @media (max-width:640px) { .funnel-grid { grid-template-columns:1fr; } }
</style>

<script>
  (function () {
    const btns = document.querySelectorAll('.funnel-range-btn');
    if (!btns.length) return;
    btns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const range = btn.dataset.frange;
        btns.forEach(function (other) { other.classList.toggle('is-active', other === btn); });
        document.querySelectorAll('.funnel-pane').forEach(function (pane) {
          pane.hidden = pane.dataset.frange !== range;
        });
      });
    });
  })();
</script>
```

**3-5.** `templates/admin.html`에서 방문 통계 카드(`<!-- 방문 통계 -->` 주석으로 시작하는 `admin-section-card`)를 닫는 `</div>` 다음 줄에 include를 넣는다. 카드 바로 뒤에 오는 `<style>` 블록보다 **앞**이다.

```html
  {% include "_admin_funnel.html" %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_funnel.py -v`
Expected: PASS — 16 passed

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 전부 통과

- [ ] **Step 6: Commit**

```bash
git add app.py templates/_admin_funnel.html templates/admin.html tests/test_admin_funnel.py
git commit -m "feat: show the portfolio funnel on the admin dashboard"
```

---

### Task 6: 공개 페이지 이벤트 수집

**Files:**
- Modify: `templates/index.html` (45행 히어로 이력서 버튼, 207행 카드 태그, 285·294·302·311·320·329행 연락 카드)
- Modify: `static/js/main.js` (`openModal()` 내부, 파일 끝)
- Test: `tests/test_admin_funnel.py`

**Interfaces:**
- Consumes: Task 2의 `POST /api/track`
- Produces: `window.trackFunnel(stage, {project_id, detail})`, 카드의 `data-pid`, 전환 링크의 `data-convert`

- [ ] **Step 1: Write the failing test**

`tests/test_admin_funnel.py` 끝에 추가한다.

```python
def test_public_page_exposes_tracking_hooks(client):
    html = client.get('/').get_data(as_text=True)

    assert 'data-pid=' in html
    assert 'data-convert="email"' in html
    assert 'data-convert="resume"' in html


def test_main_js_sends_all_three_client_stages():
    js = open('static/js/main.js', encoding='utf-8').read()

    assert "'/api/track'" in js
    assert 'window.trackFunnel' in js
    assert "track('projects_view')" in js
    assert "'project_detail'" in js
    assert "'convert'" in js
    assert 'IntersectionObserver' in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_funnel.py -k "hooks or three_client" -v`
Expected: FAIL — `assert 'data-pid=' in html`

- [ ] **Step 3: Write minimal implementation**

**3-1.** `templates/index.html` 207행 `<article class="project-card ...">`의 속성 목록에서 `data-title` 앞에 한 줄 추가한다.

```html
        data-pid="{{ p.id }}"
```

**3-2.** 같은 파일 45행 히어로 이력서 버튼에 `data-convert="resume"`를 넣는다.

```html
          <a href="{{ url_for('serve_resume') }}" class="btn btn-resume" target="_blank" data-convert="resume">{{ 'Download Resume ↓' if en else '이력서 다운로드 ↓' }}</a>
```

**3-3.** 연락 카드 6개에 각각 `data-convert` 속성을 추가한다. `class="contact-card reveal"` 바로 뒤에 넣는다.

| 행 | 링크 | 추가할 속성 |
|---|---|---|
| 285 | `mailto:{{ profile.email }}` | `data-convert="email"` |
| 294 | `profile.linkedin_url` | `data-convert="linkedin"` |
| 302 | `profile.remember_url` | `data-convert="remember"` |
| 311 | `profile.github_url` | `data-convert="github"` |
| 320 | `profile.blog_url` | `data-convert="blog"` |
| 329 | `url_for('serve_resume')` | `data-convert="resume"` |

예를 들어 285행은 아래가 된다.

```html
      <a href="mailto:{{ profile.email }}" class="contact-card reveal" data-convert="email">
```

**3-4.** `static/js/main.js`의 `openModal(card)` 함수에서 `const d = card.dataset;` 다음 줄에 추가한다.

```js
    if (window.trackFunnel) {
      window.trackFunnel('project_detail', { project_id: parseInt(d.pid || '0', 10) });
    }
```

**3-5.** `static/js/main.js` **맨 끝**에 수집 블록을 추가한다.

```js
/* ── 퍼널 이벤트 수집 ──────────────────────────────────── */
(function () {
  const sent = new Set();

  function track(stage, opts) {
    const o = opts || {};
    const key = stage + ':' + (o.project_id || 0) + ':' + (o.detail || '');
    if (sent.has(key)) return;
    sent.add(key);

    const body = JSON.stringify({
      stage: stage,
      project_id: o.project_id || 0,
      detail: o.detail || ''
    });
    try {
      const blob = new Blob([body], { type: 'application/json' });
      if (navigator.sendBeacon && navigator.sendBeacon('/api/track', blob)) return;
    } catch (e) { /* sendBeacon 미지원 → fetch로 폴백 */ }
    fetch('/api/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body,
      keepalive: true
    }).catch(function () {});
  }

  window.trackFunnel = track;

  // 프로젝트 섹션은 뷰포트보다 높을 수 있어 threshold를 크게 잡으면
  // 영영 발화하지 않는다. 화면에 들어오는 순간 1회만 기록한다.
  const section = document.getElementById('projects');
  if (section && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          track('projects_view');
          io.disconnect();
        }
      });
    }, { threshold: 0.01 });
    io.observe(section);
  }

  document.querySelectorAll('[data-convert]').forEach(function (el) {
    el.addEventListener('click', function () {
      track('convert', { detail: el.dataset.convert });
    });
  });
})();
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_funnel.py -v`
Expected: PASS — 18 passed

- [ ] **Step 5: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: 전부 통과 (특히 `tests/test_public_portfolio.py`)

- [ ] **Step 6: Commit**

```bash
git add templates/index.html static/js/main.js tests/test_admin_funnel.py
git commit -m "feat: send funnel stage events from the public page"
```

---

### Task 7: 브라우저에서 실제 동작 확인

**Files:** 없음 (검증 전용)

**Interfaces:**
- Consumes: Task 1~6 전부

- [ ] **Step 1: 로컬 서버 기동**

`.claude/launch.json`이 없으면 아래 내용으로 만든다.

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "portfolio",
      "runtimeExecutable": "python",
      "runtimeArgs": ["wsgi.py"],
      "port": 8080
    }
  ]
}
```

Browser pane의 `preview_start`로 `portfolio`를 띄운다. Bash로 서버를 띄우지 않는다.

- [ ] **Step 2: 공개 페이지에서 퍼널 3단계 발생시키기**

`/`를 열고 프로젝트 섹션까지 스크롤 → 프로젝트 카드 클릭으로 모달 열기 → 모달을 닫고 연락 섹션의 이메일 카드 클릭.

`read_network_requests`로 `/api/track` 요청이 3건(`projects_view`, `project_detail`, `convert`) 발생하고 모두 `204`인지 확인한다. `read_console_messages`로 에러가 없는지 확인한다.

- [ ] **Step 3: 어드민에서 확인**

`/admin/login`에서 로그인한 뒤 `/admin`으로 이동. 퍼널 4단계 막대가 단조 감소하는지, 전환 내역에 "이메일"이, 프로젝트별 열람에 클릭한 프로젝트 제목이 나오는지 확인한다. 7일/30일 토글을 눌러 두 패널이 서로 전환되는지 확인한다.

- [ ] **Step 4: 스크린샷으로 증빙 남기기**

`computer {action: "screenshot"}`로 퍼널 섹션을 캡처해 `SendUserFile`로 사용자에게 보낸다.

- [ ] **Step 5: 남은 변경이 있으면 커밋**

```bash
git status --short
```

`.claude/launch.json`을 새로 만들었다면 커밋한다.

```bash
git add .claude/launch.json
git commit -m "chore: add the local preview launch config"
```
