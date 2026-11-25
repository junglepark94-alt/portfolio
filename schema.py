"""테이블 생성, 수동 컬럼 마이그레이션, 초기 데이터."""
import json
import os
import re
import secrets

from flask import current_app
from sqlalchemy import Text, inspect

from content_sync import (apply_profile_fixes_once, run_boot_network_tasks,
                          start_boot_network_tasks, sync_canonical_content_once)
from models import Admin, Profile, Project, db

# 나중에 추가된 컬럼들. create_all()은 이미 있는 테이블에 컬럼을 더하지 않으므로 직접 추가한다.
# 시작할 때마다 실제 컬럼 목록과 비교해 없는 것만 실행한다.
ADD_COLUMN_MIGRATIONS = [
    "ALTER TABLE project ADD COLUMN image_filename VARCHAR(300) DEFAULT ''",
    "ALTER TABLE project ADD COLUMN detail_text TEXT DEFAULT ''",
    "ALTER TABLE project ADD COLUMN links_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN education_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN awards_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN skills_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN tools_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN resume_filename VARCHAR(300) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN og_image_url VARCHAR(500) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN open_to_work BOOLEAN DEFAULT FALSE",
    "ALTER TABLE project ADD COLUMN kpi VARCHAR(300) DEFAULT ''",
    "ALTER TABLE project ADD COLUMN my_role VARCHAR(200) DEFAULT ''",
    "ALTER TABLE project ADD COLUMN category VARCHAR(100) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN profile_image_filename VARCHAR(300) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN language_scores_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN remember_url VARCHAR(300) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN phone VARCHAR(40) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN name_en VARCHAR(80) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN role_en VARCHAR(120) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN tagline_en TEXT DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN about_text_en TEXT DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN experience_en_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN education_en_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN awards_en_json TEXT DEFAULT '[]'",
    "ALTER TABLE profile ADD COLUMN skills_en VARCHAR(500) DEFAULT ''",
    "ALTER TABLE profile ADD COLUMN tools_en_json TEXT DEFAULT '[]'",
    "ALTER TABLE project ADD COLUMN links_en_json TEXT DEFAULT '[]'",
    "ALTER TABLE project ADD COLUMN title_en VARCHAR(120) DEFAULT ''",
    "ALTER TABLE project ADD COLUMN description_en TEXT DEFAULT ''",
    "ALTER TABLE project ADD COLUMN detail_text_en TEXT DEFAULT ''",
    "ALTER TABLE project ADD COLUMN kpi_en TEXT DEFAULT ''",
    "ALTER TABLE project ADD COLUMN my_role_en VARCHAR(200) DEFAULT ''",
    "ALTER TABLE project ADD COLUMN category_en VARCHAR(100) DEFAULT ''",
    "ALTER TABLE gallery_item ADD COLUMN title_en VARCHAR(200) DEFAULT ''",
    "ALTER TABLE project ADD COLUMN is_hidden BOOLEAN DEFAULT FALSE",
    "ALTER TABLE visit_event ADD COLUMN source VARCHAR(40) DEFAULT ''",
]
_ADD_COLUMN_RE = re.compile(r'ALTER TABLE (\w+) ADD COLUMN (\w+)')


def _missing_column_migrations(conn):
    """ADD_COLUMN_MIGRATIONS 중 아직 DB에 없는 컬럼의 ALTER 문만 돌려준다."""
    inspector = inspect(conn)
    existing = {}
    pending = []
    for sql in ADD_COLUMN_MIGRATIONS:
        table, column = _ADD_COLUMN_RE.match(sql).groups()
        if table not in existing:
            existing[table] = ({c['name'] for c in inspector.get_columns(table)}
                               if inspector.has_table(table) else None)
        if existing[table] is not None and column not in existing[table]:
            pending.append(sql)
    return pending


def _widen_kpi_column(conn):
    """project.kpi를 VARCHAR(300)에서 TEXT로 넓힌다. PostgreSQL에서, 아직 TEXT가 아닐 때만."""
    if conn.dialect.name != 'postgresql':
        return
    kpi = next((c for c in inspect(conn).get_columns('project') if c['name'] == 'kpi'), None)
    if kpi is not None and not isinstance(kpi["type"], Text):
        conn.execute(db.text("ALTER TABLE project ALTER COLUMN kpi TYPE TEXT"))
        conn.commit()


def init_db(background_network_tasks=True):
    db.create_all()
    # 신규 컬럼 마이그레이션
    with db.engine.connect() as conn:
        for sql in _missing_column_migrations(conn):
            conn.execute(db.text(sql))
            conn.commit()
            print(f"[schema] {sql}")
        _widen_kpi_column(conn)

        # image_filename → project_image 테이블 마이그레이션
        old_imgs = conn.execute(db.text(
            "SELECT id, image_filename FROM project WHERE image_filename IS NOT NULL AND image_filename != ''"
        )).fetchall()
        for row in old_imgs:
            exists = conn.execute(db.text(
                "SELECT 1 FROM project_image WHERE project_id = :pid LIMIT 1"
            ), {'pid': row[0]}).fetchone()
            if not exists:
                conn.execute(db.text(
                    "INSERT INTO project_image (project_id, filename, is_main, sort_order) VALUES (:pid, :fn, TRUE, 0)"
                ), {'pid': row[0], 'fn': row[1]})
        conn.commit()

        # github_url / demo_url → links_json 자동 마이그레이션
        rows = conn.execute(db.text(
            "SELECT id, github_url, demo_url, links_json FROM project"
        )).fetchall()
        for row in rows:
            links_val = row[3]
            if links_val and links_val != '[]':
                continue  # 이미 마이그레이션됨
            links = []
            if row[1]:
                links.append({'label': 'GitHub', 'url': row[1]})
            if row[2]:
                links.append({'label': 'Demo', 'url': row[2]})
            if links:
                conn.execute(
                    db.text("UPDATE project SET links_json = :lj WHERE id = :id"),
                    {'lj': json.dumps(links, ensure_ascii=False), 'id': row[0]}
                )

        # skills → skills_json 마이그레이션
        p_rows = conn.execute(db.text("SELECT id, skills, skills_json FROM profile")).fetchall()
        for row in p_rows:
            if row[2] and row[2] != '[]':
                continue
            if row[1]:
                sj = json.dumps(
                    [{'name': s.strip(), 'level': '중'} for s in row[1].split(',') if s.strip()],
                    ensure_ascii=False
                )
                conn.execute(db.text("UPDATE profile SET skills_json = :sj WHERE id = :id"),
                             {'sj': sj, 'id': row[0]})
        conn.commit()
    if not Admin.query.first():
        _admin_pw = os.environ.get('ADMIN_PASSWORD')
        if not _admin_pw:
            if current_app.config.get('IS_PRODUCTION'):
                _admin_pw = secrets.token_urlsafe(12)
                print("=" * 60)
                print("WARNING: ADMIN_PASSWORD is not set.")
                print("Generated a random admin password (set ADMIN_PASSWORD to control it):")
                print("  admin /", _admin_pw)
                print("=" * 60)
            else:
                _admin_pw = 'changeme123!'  # 로컬 개발 전용
        admin = Admin(username='admin')
        admin.set_password(_admin_pw)
        db.session.add(admin)
        db.session.commit()
        print("Admin account created (username: admin).")

    if not Profile.query.first():
        p = Profile(
            name='홍길동',
            role='마케팅 & 콘텐츠 기획자',
            tagline='데이터를 기반으로 콘텐츠 전략을 설계하고,\n브랜드와 소비자를 연결하는 마케터입니다.',
            about_text='빙그레(BINGGRAE)에서 콘텐츠 기획 및 마케팅 업무를 담당하고 있습니다.\n브랜드 커뮤니케이션, 사내 OJT 멘토링, AI 기반 업무 자동화에 이르기까지 다양한 영역에서 실무 경험을 쌓았습니다.',
            skills='콘텐츠 기획,마케팅 전략,데이터 분석,Python / Flask,AI 도구 활용,PPT / Word',
            email='your@email.com',
            experience_json='[{"company":"빙그레 (BINGGRAE)","period":"2022.03 – 현재","role":"마케팅 / 콘텐츠 기획","bullets":["브랜드 콘텐츠 기획 및 채널별 소재 제작 관리","사내 사보(뉴스레터) 기획·편집 총괄","신입사원 OJT 멘토(지도사원) 운영","AI 기반 업무 자동화 도구 도입 및 운영"]}]'
        )
        db.session.add(p)
        db.session.commit()

    if not Project.query.first():
        samples = [
            Project(
                title='빙그레 사보 자동화 시스템',
                description='사내 뉴스레터 초안 작성 및 포맷팅을 AI 기반으로 자동화한 내부 도구. 작성 시간 70% 단축.',
                tech_stack='Python, Flask, OpenAI API, python-docx',
                period='2024.08 – 2024.10',
                order=1
            ),
            Project(
                title='마케팅 콘텐츠 대시보드',
                description='캠페인 성과 지표를 시각화하고 팀원 간 콘텐츠 피드백을 통합 관리하는 내부 플랫폼.',
                tech_stack='Python, Flask, SQLite, Chart.js',
                period='2024.03 – 2024.07',
                order=2
            ),
        ]
        db.session.add_all(samples)
        db.session.commit()

    try:
        sync_canonical_content_once()
    except Exception as exc:  # 문안 동기화 실패가 서버 부팅을 막아서는 안 된다
        db.session.rollback()
        print(f"[content-sync] skipped: {exc!r}")
    try:
        apply_profile_fixes_once()
    except Exception as exc:
        db.session.rollback()
        print(f"[profile-fix] skipped: {exc!r}")
    if background_network_tasks:
        start_boot_network_tasks()
    else:
        run_boot_network_tasks()
