"""공개 페이지 방문·퍼널 이벤트 기록."""
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import request, session
from sqlalchemy.exc import IntegrityError

from models import (KST, VISIT_EVENT_RETENTION_DAYS, ContentSync, DailyVisit, VisitEvent,
                    _today_kst, _utcnow, db)

def _session_key():
    """익명 세션 키. IP·UA는 저장하지 않는다."""
    key = session.get('sk')
    if not key:
        key = secrets.token_hex(8)
        session['sk'] = key
    return key


SOURCE_MAX_LEN = 40
_SOURCE_ALLOWED = re.compile(r'[^a-z0-9._-]')


def _visit_source():
    """방문 유입 경로. ?src= 파라미터가 있으면 그것을, 없으면 외부 Referer의 호스트를 쓴다.

    자기 사이트 안에서의 이동(Referer 호스트 == 요청 호스트)은 직접 유입('')으로 본다.
    """
    src = _SOURCE_ALLOWED.sub('', (request.args.get('src') or '').strip().lower())
    if src:
        return src[:SOURCE_MAX_LEN]
    try:
        host = (urlparse(request.referrer or '').hostname or '').lower()
    except ValueError:
        host = ''
    if host.startswith('www.'):
        host = host[4:]
    own_host = (request.host or '').split(':')[0].lower()
    if not host or host == own_host:
        return ''
    return _SOURCE_ALLOWED.sub('', host)[:SOURCE_MAX_LEN]


def record_event(stage, project_id=0, detail='', source=''):
    """이벤트 1건 기록. 중복(유니크 제약 위반)과 그 밖의 실패는 조용히 무시한다."""
    try:
        db.session.add(VisitEvent(
            session_key=_session_key(),
            stage=stage,
            project_id=int(project_id or 0),
            detail=detail or '',
            date=_today_kst(),
            source=source or '',
        ))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def prune_visit_events(retention_days=VISIT_EVENT_RETENTION_DAYS):
    """보관 기간이 지난 이벤트를 삭제한다. 하루 1회만 실제로 수행."""
    try:
        today = _today_kst()
        marker = db.session.get(ContentSync, 'visit_event_pruned_on')
        if marker is not None and marker.value == today:
            return 0

        cutoff = (datetime.now(KST).date() - timedelta(days=retention_days)).strftime('%Y-%m-%d')
        removed = VisitEvent.query.filter(VisitEvent.date < cutoff).delete(
            synchronize_session=False)
        if marker is None:
            marker = ContentSync(key='visit_event_pruned_on')
            db.session.add(marker)
        marker.value = today
        marker.applied_at = _utcnow()
        db.session.commit()
        return removed
    except Exception:
        db.session.rollback()
        return 0


def increment_daily_visit(today):
    """오늘 방문수를 1 올린다.

    읽고-더해-쓰기 대신 DB에서 count = count + 1 로 올려 동시 요청끼리 값을 잃지 않는다.
    첫 방문이 동시에 들어와 INSERT가 유니크 제약에 걸리면 이미 생긴 행을 UPDATE로 다시 올린다.
    """
    for _ in range(2):
        try:
            updated = DailyVisit.query.filter_by(date=today).update(
                {DailyVisit.count: db.func.coalesce(DailyVisit.count, 0) + 1},
                synchronize_session=False)
            if not updated:
                db.session.add(DailyVisit(date=today, count=1))
            db.session.commit()
            return True
        except IntegrityError:
            db.session.rollback()
    return False


def track_visit():
    """공개 페이지 방문 기록. 같은 세션은 하루 1회만 카운트.

    오늘 이미 기록한 세션이면 DB를 전혀 건드리지 않는다. 예전에는 새로고침마다
    정리 작업 조회 + 중복 INSERT(유니크 제약 위반 후 롤백)가 일어났다.
    """
    today = _today_kst()
    if session.get('visited_on') == today:
        return
    # 예전 방식(v_YYYY-MM-DD 키를 날마다 하나씩 추가)으로 쌓인 키를 치워 쿠키가 커지지 않게 한다.
    # 오늘 키가 있으면 오늘 방문수는 이미 올렸으므로 다시 올리지 않는다.
    legacy_counted = session.pop(f'v_{today}', None)
    for stale in [k for k in session if k.startswith('v_')]:
        session.pop(stale, None)
    session['visited_on'] = today
    prune_visit_events()
    try:
        record_event('visit', source=_visit_source())
        if not legacy_counted:
            increment_daily_visit(today)
    except Exception:
        db.session.rollback()
