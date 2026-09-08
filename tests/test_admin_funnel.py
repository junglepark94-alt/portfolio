import pytest
from sqlalchemy.exc import IntegrityError

from analytics import build_funnel_stats
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


def test_prune_removes_events_past_retention_once_a_day(portfolio_app):
    from app import prune_visit_events

    db.session.add(VisitEvent(session_key='old', stage='visit', project_id=0,
                              detail='', date='2020-01-01'))
    db.session.add(_ev('new', 'visit'))
    db.session.commit()

    assert prune_visit_events() == 1
    assert [r.session_key for r in VisitEvent.query.all()] == ['new']
    assert prune_visit_events() == 0


def test_prune_boundary_keeps_exact_cutoff_and_removes_one_day_older(portfolio_app):
    from datetime import datetime, timedelta

    from app import KST, prune_visit_events

    retention_days = 3
    today = datetime.now(KST).date()
    surviving_date = (today - timedelta(days=retention_days)).strftime('%Y-%m-%d')
    deleted_date = (today - timedelta(days=retention_days + 1)).strftime('%Y-%m-%d')

    db.session.add(VisitEvent(session_key='surviving', stage='visit', project_id=0,
                              detail='', date=surviving_date))
    db.session.add(VisitEvent(session_key='deleted', stage='visit', project_id=0,
                              detail='', date=deleted_date))
    db.session.commit()

    assert prune_visit_events(retention_days=retention_days) == 1
    assert [r.session_key for r in VisitEvent.query.all()] == ['surviving']
