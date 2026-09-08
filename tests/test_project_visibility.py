from app import Project, db


def _login(client):
    with client.session_transaction() as sess:
        sess['logged_in'] = True


def test_hidden_project_is_left_out_of_public_pages_but_listed_in_admin(client, portfolio_app):
    with portfolio_app.app_context():
        project = Project.query.first()
        project.is_hidden = True
        db.session.commit()
        pid = project.id
        title = project.title
        title_en = project.title_en

    assert title not in client.get('/').get_data(as_text=True)
    assert title_en not in client.get('/en').get_data(as_text=True)

    _login(client)
    admin_html = client.get('/admin').get_data(as_text=True)
    assert title in admin_html
    assert f'/admin/project/{pid}/toggle-hidden' in admin_html
    assert '숨김' in admin_html


def test_toggle_hidden_requires_login_and_flips_visibility(client, portfolio_app):
    with portfolio_app.app_context():
        pid = Project.query.first().id

    assert client.post(f'/admin/project/{pid}/toggle-hidden').status_code in (302, 401, 403)
    with portfolio_app.app_context():
        assert not db.session.get(Project, pid).is_hidden

    _login(client)
    res = client.post(f'/admin/project/{pid}/toggle-hidden')
    assert res.status_code == 302
    with portfolio_app.app_context():
        assert db.session.get(Project, pid).is_hidden is True

    client.post(f'/admin/project/{pid}/toggle-hidden')
    with portfolio_app.app_context():
        assert db.session.get(Project, pid).is_hidden is False
