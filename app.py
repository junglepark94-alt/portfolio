from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')

_db_url = os.environ.get('DATABASE_URL', '')
# Railway/Heroku는 postgres:// 를 제공하지만 SQLAlchemy 1.4+는 postgresql:// 필요
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

_is_production = bool(os.environ.get('PORT'))  # Railway는 PORT를 주입함
_using_sqlite = not _db_url or _db_url.startswith('sqlite')

if _using_sqlite:
    _db_url = 'sqlite:///portfolio.db'
    if _is_production:
        print("=" * 60)
        print("WARNING: DATABASE_URL is not set. Using SQLite.")
        print("Data WILL be lost on every redeploy!")
        print("Set DATABASE_URL in Railway environment variables.")
        print("=" * 60)

app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
print(f"[DB] engine={'SQLite (ephemeral!)' if _using_sqlite else 'PostgreSQL'}")
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def save_uploaded_image(file):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return None
    filename = f"project_{int(time.time())}.{ext}"
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename

db = SQLAlchemy(app)

# ── Models ──────────────────────────────────────────────

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tech_stack = db.Column(db.String(250))
    github_url = db.Column(db.String(300))
    demo_url = db.Column(db.String(300))
    period = db.Column(db.String(80))
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    image_filename = db.Column(db.String(300), default='')  # 레거시
    detail_text = db.Column(db.Text, default='')
    links_json = db.Column(db.Text, default='[]')
    kpi = db.Column(db.String(300), default='')
    my_role = db.Column(db.String(200), default='')
    category = db.Column(db.String(100), default='')
    images = db.relationship('ProjectImage', backref='project',
                             cascade='all, delete-orphan',
                             order_by='ProjectImage.sort_order, ProjectImage.id',
                             lazy='select')

    @property
    def main_image(self):
        m = next((i for i in self.images if i.is_main), None)
        return m or (self.images[0] if self.images else None)

    @property
    def links(self):
        import json as _json
        try:
            return _json.loads(self.links_json or '[]')
        except Exception:
            return []

    @property
    def tech_list(self):
        return [t.strip() for t in self.tech_stack.split(',') if t.strip()]


class ProjectImage(db.Model):
    __tablename__ = 'project_image'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    is_main = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)


class GalleryItem(db.Model):
    __tablename__ = 'gallery_item'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    image_filename = db.Column(db.String(300), nullable=False)
    links_json = db.Column(db.Text, default='[]')
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def links(self):
        import json as _j
        try: return _j.loads(self.links_json or '[]')
        except: return []


class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Profile(db.Model):
    """싱글톤 — 항상 id=1 레코드만 사용"""
    id = db.Column(db.Integer, primary_key=True)
    # Hero
    name = db.Column(db.String(80), default='홍길동')
    role = db.Column(db.String(120), default='마케팅 & 콘텐츠 기획자')
    tagline = db.Column(db.Text, default='데이터를 기반으로 콘텐츠 전략을 설계하고,\n브랜드와 소비자를 연결하는 마케터입니다.')
    # About
    about_text = db.Column(db.Text, default='')
    skills = db.Column(db.String(500), default='콘텐츠 기획,마케팅 전략,데이터 분석,Python / Flask,AI 도구 활용,PPT / Word')
    # Contact
    email = db.Column(db.String(200), default='')
    linkedin_url = db.Column(db.String(300), default='')
    github_url = db.Column(db.String(300), default='')
    # Experience (자유 텍스트 JSON 대신 간단히 YAML-like 문자열)
    # 추가 SNS
    blog_url = db.Column(db.String(300), default='')
    # 경력 (JSON string: list of {company, period, role, bullets})
    experience_json = db.Column(db.Text, default='[]')
    # 학력 [{school, major, degree, period}]
    education_json = db.Column(db.Text, default='[]')
    # 수상내역 [{title, org, year}]
    awards_json = db.Column(db.Text, default='[]')
    # 핵심 역량 with 레벨 [{name, level}]  level: 상|중|하
    skills_json = db.Column(db.Text, default='[]')
    # 스킬/툴 [{name, level}]
    tools_json = db.Column(db.Text, default='[]')
    # 이력서 PDF
    resume_filename = db.Column(db.String(300), default='')
    # Open Graph 이미지 URL
    og_image_url = db.Column(db.String(500), default='')
    # 이직 검토 중 배지
    open_to_work = db.Column(db.Boolean, default=False)

    @property
    def skill_list(self):
        return [s.strip() for s in self.skills.split(',') if s.strip()]

    @property
    def skills_with_level(self):
        import json as _j
        try:
            return _j.loads(self.skills_json or '[]')
        except Exception:
            return []

    @property
    def tools(self):
        import json as _j
        try:
            return _j.loads(self.tools_json or '[]')
        except Exception:
            return []

    @property
    def experience(self):
        import json
        try:
            return json.loads(self.experience_json or '[]')
        except Exception:
            return []

    @property
    def education(self):
        import json as _j
        try:
            return _j.loads(self.education_json or '[]')
        except Exception:
            return []

    @property
    def awards(self):
        import json as _j
        try:
            return _j.loads(self.awards_json or '[]')
        except Exception:
            return []


# ── DB Init ─────────────────────────────────────────────

def init_db():
    db.create_all()
    # 신규 컬럼 마이그레이션 (SQLite는 IF NOT EXISTS 미지원 → try/except)
    with db.engine.connect() as conn:
        for sql in [
            "ALTER TABLE project ADD COLUMN image_filename VARCHAR(300) DEFAULT ''",
            "ALTER TABLE project ADD COLUMN detail_text TEXT DEFAULT ''",
            "ALTER TABLE project ADD COLUMN links_json TEXT DEFAULT '[]'",
            # project_image 테이블은 create_all()이 처리하므로 ALTER 불필요
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
        ]:
            try:
                conn.execute(db.text(sql))
                conn.commit()
            except Exception:
                conn.rollback()

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
        import json as _json
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
                    {'lj': _json.dumps(links, ensure_ascii=False), 'id': row[0]}
                )

        # skills → skills_json 마이그레이션
        p_rows = conn.execute(db.text("SELECT id, skills, skills_json FROM profile")).fetchall()
        for row in p_rows:
            if row[2] and row[2] != '[]':
                continue
            if row[1]:
                sj = _json.dumps(
                    [{'name': s.strip(), 'level': '중'} for s in row[1].split(',') if s.strip()],
                    ensure_ascii=False
                )
                conn.execute(db.text("UPDATE profile SET skills_json = :sj WHERE id = :id"),
                             {'sj': sj, 'id': row[0]})
        conn.commit()
    if not Admin.query.first():
        admin = Admin(username='admin')
        admin.set_password(os.environ.get('ADMIN_PASSWORD', 'changeme123!'))
        db.session.add(admin)
        db.session.commit()
        print("Admin created. Password:", os.environ.get('ADMIN_PASSWORD', 'changeme123!'))

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


# ── Context Processor ────────────────────────────────────

@app.context_processor
def inject_globals():
    try:
        p = db.session.get(Profile, 1)
    except Exception:
        p = None
    return {'profile': p}


# ── Public Routes ────────────────────────────────────────

@app.route('/')
def index():
    projects = Project.query.order_by(Project.order, Project.created_at.desc()).all()
    gallery_items = GalleryItem.query.order_by(GalleryItem.sort_order, GalleryItem.created_at).all()
    profile = db.session.get(Profile, 1)
    return render_template('index.html', projects=projects, gallery_items=gallery_items, profile=profile)


# ── Admin Auth ───────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        admin = Admin.query.filter_by(username=request.form['username']).first()
        if admin and admin.check_password(request.form['password']):
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')


@app.route('/admin/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ── Admin CRUD ───────────────────────────────────────────

@app.route('/admin')
@login_required
def admin_dashboard():
    projects = Project.query.order_by(Project.order, Project.created_at.desc()).all()
    profile = db.session.get(Profile, 1)
    gallery_items = GalleryItem.query.order_by(GalleryItem.sort_order, GalleryItem.created_at).all()
    db_info = {
        'engine': 'SQLite ⚠️ (재배포 시 데이터 소멸)' if _using_sqlite else 'PostgreSQL ✅',
        'warning': _using_sqlite and _is_production,
    }
    return render_template('admin.html', projects=projects, profile=profile,
                           gallery_items=gallery_items, db_info=db_info)


@app.route('/admin/profile', methods=['GET', 'POST'])
@login_required
def profile_edit():
    import json
    profile = db.session.get(Profile, 1)
    if request.method == 'POST':
        profile.name = request.form.get('name', '')
        profile.role = request.form.get('role', '')
        profile.tagline = request.form.get('tagline', '')
        profile.about_text = request.form.get('about_text', '')
        profile.email = request.form.get('email', '')
        profile.linkedin_url = request.form.get('linkedin_url', '')
        profile.github_url = request.form.get('github_url', '')
        profile.blog_url = request.form.get('blog_url', '')
        profile.og_image_url = request.form.get('og_image_url', '')
        profile.open_to_work = bool(request.form.get('open_to_work'))

        # 이력서 PDF 업로드
        resume_file = request.files.get('resume_file')
        if resume_file and resume_file.filename:
            ext = resume_file.filename.rsplit('.', 1)[-1].lower() if '.' in resume_file.filename else ''
            if ext == 'pdf':
                filename = f"resume_{int(time.time())}.pdf"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                resume_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                profile.resume_filename = filename

        # 핵심 역량 (단순 목록)
        profile.skills = request.form.get('skills', '')

        # 스킬/툴 (with level)
        tool_names  = request.form.getlist('tool_name')
        tool_levels = request.form.getlist('tool_level')
        tools = [{'name': n.strip(), 'level': l}
                 for n, l in zip(tool_names, tool_levels) if n.strip()]
        profile.tools_json = json.dumps(tools, ensure_ascii=False)

        # 학력
        edu_schools  = request.form.getlist('edu_school')
        edu_majors   = request.form.getlist('edu_major')
        edu_degrees  = request.form.getlist('edu_degree')
        edu_periods  = request.form.getlist('edu_period')
        education = [{'school': s.strip(), 'major': edu_majors[i].strip() if i < len(edu_majors) else '',
                      'degree': edu_degrees[i].strip() if i < len(edu_degrees) else '',
                      'period': edu_periods[i].strip() if i < len(edu_periods) else ''}
                     for i, s in enumerate(edu_schools) if s.strip()]
        profile.education_json = json.dumps(education, ensure_ascii=False)

        # 수상내역
        award_titles = request.form.getlist('award_title')
        award_orgs   = request.form.getlist('award_org')
        award_years  = request.form.getlist('award_year')
        awards = [{'title': t.strip(), 'org': award_orgs[i].strip() if i < len(award_orgs) else '',
                   'year': award_years[i].strip() if i < len(award_years) else ''}
                  for i, t in enumerate(award_titles) if t.strip()]
        profile.awards_json = json.dumps(awards, ensure_ascii=False)

        # 경력 파싱: 폼에서 배열로 받기
        companies = request.form.getlist('exp_company')
        periods   = request.form.getlist('exp_period')
        roles     = request.form.getlist('exp_role')
        bullets   = request.form.getlist('exp_bullets')  # 각 항목은 줄바꿈으로 구분
        experience = []
        for i, company in enumerate(companies):
            if company.strip():
                experience.append({
                    'company': company.strip(),
                    'period': periods[i].strip() if i < len(periods) else '',
                    'role': roles[i].strip() if i < len(roles) else '',
                    'bullets': [b.strip() for b in bullets[i].split('\n') if b.strip()] if i < len(bullets) else [],
                })
        profile.experience_json = json.dumps(experience, ensure_ascii=False)

        db.session.commit()
        flash('프로필이 저장되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('profile_form.html', profile=profile)


@app.route('/admin/project/new', methods=['GET', 'POST'])
@login_required
def project_new():
    if request.method == 'POST':
        import json as _json
        labels = request.form.getlist('link_label')
        urls   = request.form.getlist('link_url')
        links  = [{'label': l.strip(), 'url': u.strip()}
                  for l, u in zip(labels, urls) if l.strip() and u.strip()]
        kpi_items = request.form.getlist('kpi_item')
        kpi = '\n'.join(i.strip() for i in kpi_items if i.strip())
        img = save_uploaded_image(request.files.get('image'))
        p = Project(
            title=request.form['title'],
            description=request.form['description'],
            tech_stack=request.form['tech_stack'],
            github_url='',
            demo_url='',
            period=request.form.get('period', ''),
            order=int(request.form.get('order', 0)),
            detail_text=request.form.get('detail_text', ''),
            image_filename=img or '',
            links_json=_json.dumps(links, ensure_ascii=False),
            kpi=kpi,
            my_role=request.form.get('my_role', ''),
            category=request.form.get('category', ''),
        )
        db.session.add(p)
        db.session.commit()
        flash('프로젝트가 추가되었습니다. 아래에서 이미지를 추가하세요.')
        return redirect(url_for('project_edit', pid=p.id))
    return render_template('project_form.html', project=None)


@app.route('/admin/project/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
def project_edit(pid):
    p = Project.query.get_or_404(pid)
    if request.method == 'POST':
        import json as _json
        labels = request.form.getlist('link_label')
        urls   = request.form.getlist('link_url')
        links  = [{'label': l.strip(), 'url': u.strip()}
                  for l, u in zip(labels, urls) if l.strip() and u.strip()]
        p.title = request.form['title']
        p.description = request.form['description']
        p.tech_stack = request.form['tech_stack']
        p.period = request.form.get('period', '')
        p.order = int(request.form.get('order', 0))
        p.detail_text = request.form.get('detail_text', '')
        p.links_json = _json.dumps(links, ensure_ascii=False)
        kpi_items = request.form.getlist('kpi_item')
        p.kpi = '\n'.join(i.strip() for i in kpi_items if i.strip())
        p.my_role = request.form.get('my_role', '')
        p.category = request.form.get('category', '')
        db.session.commit()
        flash('프로젝트가 수정되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('project_form.html', project=p)


@app.route('/admin/project/<int:pid>/delete', methods=['POST'])
@login_required
def project_delete(pid):
    p = Project.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash('프로젝트가 삭제되었습니다.')
    return redirect(url_for('admin_dashboard'))


@app.route('/resume')
def serve_resume():
    profile = db.session.get(Profile, 1)
    if not profile or not profile.resume_filename:
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], profile.resume_filename,
                               as_attachment=True, download_name='resume.pdf')


# ── Gallery CRUD ────────────────────────────────────────

def _save_gallery_image(request):
    import base64 as _b64, json as _j
    cropped = request.form.get('cropped_data')
    if cropped and ',' in cropped:
        _, data = cropped.split(',', 1)
        filename = f"gallery_{int(time.time())}.jpg"
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as f:
            f.write(_b64.b64decode(data))
        return filename
    return save_uploaded_image(request.files.get('image'))

@app.route('/admin/gallery/new', methods=['GET', 'POST'])
@login_required
def gallery_new():
    import json as _j
    if request.method == 'POST':
        filename = _save_gallery_image(request)
        if not filename:
            flash('이미지를 선택해주세요.')
            return redirect(request.url)
        labels = request.form.getlist('link_label')
        urls   = request.form.getlist('link_url')
        links  = [{'label': l.strip(), 'url': u.strip()}
                  for l, u in zip(labels, urls) if l.strip() and u.strip()]
        item = GalleryItem(
            title=request.form['title'],
            description=request.form.get('description', ''),
            image_filename=filename,
            links_json=_j.dumps(links, ensure_ascii=False),
            sort_order=int(request.form.get('sort_order', 0)),
        )
        db.session.add(item)
        db.session.commit()
        flash('갤러리 항목이 추가되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('gallery_form.html', item=None)

@app.route('/admin/gallery/<int:gid>/edit', methods=['GET', 'POST'])
@login_required
def gallery_edit(gid):
    import json as _j
    item = GalleryItem.query.get_or_404(gid)
    if request.method == 'POST':
        labels = request.form.getlist('link_label')
        urls   = request.form.getlist('link_url')
        links  = [{'label': l.strip(), 'url': u.strip()}
                  for l, u in zip(labels, urls) if l.strip() and u.strip()]
        item.title = request.form['title']
        item.description = request.form.get('description', '')
        item.links_json = _j.dumps(links, ensure_ascii=False)
        item.sort_order = int(request.form.get('sort_order', 0))
        new_img = _save_gallery_image(request)
        if new_img:
            item.image_filename = new_img
        db.session.commit()
        flash('갤러리 항목이 수정되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('gallery_form.html', item=item)

@app.route('/admin/gallery/<int:gid>/delete', methods=['POST'])
@login_required
def gallery_delete(gid):
    item = GalleryItem.query.get_or_404(gid)
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], item.image_filename)
    if os.path.exists(fpath):
        os.remove(fpath)
    db.session.delete(item)
    db.session.commit()
    flash('갤러리 항목이 삭제되었습니다.')
    return redirect(url_for('admin_dashboard'))


# ── Image AJAX Routes ───────────────────────────────────

@app.route('/admin/project/<int:pid>/images/upload', methods=['POST'])
@login_required
def project_image_upload(pid):
    import base64 as _b64, json as _json
    p = Project.query.get_or_404(pid)
    cropped = request.form.get('cropped_data')
    if cropped and ',' in cropped:
        _, data = cropped.split(',', 1)
        filename = f"proj{pid}_{int(time.time())}.jpg"
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as f:
            f.write(_b64.b64decode(data))
    else:
        filename = save_uploaded_image(request.files.get('image'))
        if not filename:
            return _json.dumps({'error': 'invalid file'}), 400, {'Content-Type': 'application/json'}
    has_any = ProjectImage.query.filter_by(project_id=pid).first() is not None
    img = ProjectImage(project_id=pid, filename=filename, is_main=not has_any)
    db.session.add(img)
    db.session.commit()
    return app.response_class(
        response=_json.dumps({'id': img.id, 'is_main': img.is_main,
                              'url': url_for('static', filename='uploads/' + filename)}),
        mimetype='application/json'
    )


@app.route('/admin/project/images/<int:img_id>/set-main', methods=['POST'])
@login_required
def project_image_set_main(img_id):
    import json as _json
    img = ProjectImage.query.get_or_404(img_id)
    ProjectImage.query.filter_by(project_id=img.project_id).update({'is_main': False})
    img.is_main = True
    db.session.commit()
    return app.response_class(response=_json.dumps({'ok': True}), mimetype='application/json')


@app.route('/admin/project/images/<int:img_id>/delete', methods=['POST'])
@login_required
def project_image_delete(img_id):
    import json as _json
    img = ProjectImage.query.get_or_404(img_id)
    was_main, pid = img.is_main, img.project_id
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], img.filename)
    if os.path.exists(fpath):
        os.remove(fpath)
    db.session.delete(img)
    db.session.commit()
    if was_main:
        nxt = ProjectImage.query.filter_by(project_id=pid).first()
        if nxt:
            nxt.is_main = True
            db.session.commit()
    return app.response_class(response=_json.dumps({'ok': True}), mimetype='application/json')


# ── Project Reorder ─────────────────────────────────────

@app.route('/admin/projects/reorder', methods=['POST'])
@login_required
def projects_reorder():
    import json as _json
    ids = (_json.loads(request.data) or {}).get('ids', [])
    for i, pid in enumerate(ids):
        p = db.session.get(Project, int(pid))
        if p:
            p.order = i
    db.session.commit()
    return app.response_class(response=_json.dumps({'ok': True}), mimetype='application/json')


# ── YouTube API Proxy ────────────────────────────────────

@app.route('/api/youtube')
def youtube_info():
    import json as _json, urllib.request as _req, urllib.error as _err
    video_id = request.args.get('v', '').strip()
    if not video_id:
        return _json.dumps({'error': 'no video id'}), 400, {'Content-Type': 'application/json'}
    api_key = os.environ.get('YOUTUBE_API_KEY', '')
    if not api_key:
        return _json.dumps({'error': 'YOUTUBE_API_KEY not set'}), 503, {'Content-Type': 'application/json'}
    url = (
        'https://www.googleapis.com/youtube/v3/videos'
        f'?part=snippet,statistics&id={video_id}&key={api_key}'
    )
    try:
        with _req.urlopen(url, timeout=6) as resp:
            data = _json.loads(resp.read())
        items = data.get('items', [])
        if not items:
            return _json.dumps({'error': 'not found'}), 404, {'Content-Type': 'application/json'}
        snippet = items[0].get('snippet', {})
        stats   = items[0].get('statistics', {})
        thumb   = (snippet.get('thumbnails', {}).get('high') or
                   snippet.get('thumbnails', {}).get('medium') or {}).get('url', '')
        return app.response_class(
            response=_json.dumps({
                'title':        snippet.get('title', ''),
                'thumbnail':    thumb,
                'viewCount':    stats.get('viewCount', '0'),
                'likeCount':    stats.get('likeCount', '0'),
                'commentCount': stats.get('commentCount', '0'),
            }),
            mimetype='application/json'
        )
    except _err.HTTPError as e:
        return _json.dumps({'error': f'youtube api {e.code}'}), 502, {'Content-Type': 'application/json'}
    except Exception as e:
        return _json.dumps({'error': str(e)}), 500, {'Content-Type': 'application/json'}


# ── Entry ────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=False)
