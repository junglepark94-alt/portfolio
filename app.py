from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ── Models ──────────────────────────────────────────────

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tech_stack = db.Column(db.String(250))   # comma-separated
    github_url = db.Column(db.String(300))
    demo_url = db.Column(db.String(300))
    period = db.Column(db.String(80))        # e.g. "2024.03 – 2024.06"
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def tech_list(self):
        return [t.strip() for t in self.tech_stack.split(',') if t.strip()]


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

    @property
    def skill_list(self):
        return [s.strip() for s in self.skills.split(',') if s.strip()]

    @property
    def experience(self):
        import json
        try:
            return json.loads(self.experience_json or '[]')
        except Exception:
            return []


# ── DB Init ─────────────────────────────────────────────

def init_db():
    db.create_all()
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


# ── Public Routes ────────────────────────────────────────

@app.route('/')
def index():
    projects = Project.query.order_by(Project.order, Project.created_at.desc()).all()
    profile = db.session.get(Profile, 1)
    return render_template('index.html', projects=projects, profile=profile)


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
    return render_template('admin.html', projects=projects, profile=profile)


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
        profile.skills = request.form.get('skills', '')
        profile.email = request.form.get('email', '')
        profile.linkedin_url = request.form.get('linkedin_url', '')
        profile.github_url = request.form.get('github_url', '')
        profile.blog_url = request.form.get('blog_url', '')

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
        p = Project(
            title=request.form['title'],
            description=request.form['description'],
            tech_stack=request.form['tech_stack'],
            github_url=request.form.get('github_url', ''),
            demo_url=request.form.get('demo_url', ''),
            period=request.form.get('period', ''),
            order=int(request.form.get('order', 0)),
        )
        db.session.add(p)
        db.session.commit()
        flash('프로젝트가 추가되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('project_form.html', project=None)


@app.route('/admin/project/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
def project_edit(pid):
    p = Project.query.get_or_404(pid)
    if request.method == 'POST':
        p.title = request.form['title']
        p.description = request.form['description']
        p.tech_stack = request.form['tech_stack']
        p.github_url = request.form.get('github_url', '')
        p.demo_url = request.form.get('demo_url', '')
        p.period = request.form.get('period', '')
        p.order = int(request.form.get('order', 0))
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


# ── Entry ────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=False)
