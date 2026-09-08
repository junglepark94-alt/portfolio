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
