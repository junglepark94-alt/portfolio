from datetime import datetime, timedelta
from functools import wraps
import json
import os
import re

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from analytics import build_funnel_stats, build_source_stats
from content_sync import _apply_copy_entry, _expand_tiktok_short_url, _find_copy_entry
from models import (CONVERT_KINDS, KST, TRACKABLE_STAGES, Admin, DailyVisit, GalleryItem,
                    Profile, Project, ProjectImage, VisitEvent, db)
from ratelimit import _client_ip, _rate_limited
from schema import init_db  # noqa: F401  (wsgi.py와 `python app.py`가 여기서 가져간다)
from tracking import prune_visit_events, record_event, track_visit
from uploads import (_remove_upload_if_unused, _save_data_uri, _unique_upload_name,
                     _upload_name_from_url, save_uploaded_image, save_uploaded_pdf,
                     uploads_on_persistent_volume)
import images
import youtube

UI_TEXT = {
    'ko': {
        'view_details': '자세히 보기',
        'open_project': '프로젝트 상세 보기',
        'close_project': '프로젝트 상세 닫기',
        'previous_image': '이전 이미지',
        'next_image': '다음 이미지',
        'key_results': '핵심 성과',
        'project_details': '상세 설명',
        'overview': '개요',
        'resources': '관련 자료',
        'videos': '영상',
        'section_nav': '섹션 이동',
        'prev_project': '이전',
        'next_project': '다음',
        'play': '재생',
        'loading': '로딩 중…',
        'playlist': '재생목록',
        'views': '회',
        'open_external': 'YouTube에서 보기',
        'open_tiktok': 'TikTok에서 보기',
        'open_instagram': 'Instagram에서 보기',
    },
    'en': {
        'view_details': 'View details',
        'open_project': 'Open project details',
        'close_project': 'Close project details',
        'previous_image': 'Previous image',
        'next_image': 'Next image',
        'key_results': 'Key results',
        'project_details': 'Project details',
        'overview': 'Overview',
        'resources': 'Resources',
        'videos': 'Videos',
        'section_nav': 'Section navigation',
        'prev_project': 'Prev',
        'next_project': 'Next',
        'play': 'Play',
        'loading': 'Loading…',
        'playlist': 'Playlist',
        'views': 'views',
        'open_external': 'Watch on YouTube',
        'open_tiktok': 'Watch on TikTok',
        'open_instagram': 'Watch on Instagram',
    },
}


def display_period(period, lang='ko'):
    """Return a project period with a locale-appropriate ongoing label."""
    value = period or ''
    if lang == 'en':
        return value.replace('진행 중', 'Present')
    return value.replace('Present', '진행 중')


app = Flask(__name__)
# Railway 프록시가 붙이는 X-Forwarded-For 마지막 값(실제 접속 IP)과 https 여부만 신뢰한다.
# 클라이언트가 직접 넣은 앞쪽 값은 무시되므로 레이트리밋을 IP 위조로 우회할 수 없다.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

_is_production = bool(os.environ.get('PORT'))  # Railway는 PORT를 주입함
app.config['IS_PRODUCTION'] = _is_production

# SECRET_KEY: 프로덕션에서는 반드시 환경변수로 주입해야 함.
# 기본값으로 세션을 서명하면 공격자가 쿠키를 위조해 관리자 인증을 우회할 수 있음.
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if _is_production:
        raise RuntimeError(
            "SECRET_KEY 환경변수가 설정되지 않았습니다. "
            "프로덕션에서는 반드시 무작위 키를 설정하세요 (예: openssl rand -hex 32)."
        )
    _secret_key = 'dev-secret-change-in-prod'  # 로컬 개발 전용
app.config['SECRET_KEY'] = _secret_key
app.config['WTF_CSRF_TIME_LIMIT'] = None  # CSRF 토큰을 세션 수명 동안 유효하게 (관리자 UX)

_db_url = os.environ.get('DATABASE_URL', '')
# Railway/Heroku는 postgres:// 를 제공하지만 SQLAlchemy 1.4+는 postgresql:// 필요
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

_using_sqlite = not _db_url or _db_url.startswith('sqlite')

if _using_sqlite:
    # 명시적인 sqlite URL(예: 테스트의 sqlite:///:memory:)은 그대로 쓰고, 미설정일 때만 로컬 파일을 사용
    if not _db_url:
        _db_url = 'sqlite:///portfolio.db'
    if _is_production:
        print("=" * 60)
        print("WARNING: DATABASE_URL is not set. Using SQLite.")
        print("Data WILL be lost on every redeploy!")
        print("Set DATABASE_URL in Railway environment variables.")
        print("=" * 60)

app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
if not _using_sqlite:
    # Railway Postgres는 유휴 연결을 끊는다. 끊긴 연결로 쿼리하면 TCP 타임아웃까지 멈추므로
    # 사용 전에 ping 하고 주기적으로 재연결한다.
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}
print(f"[DB] engine={'SQLite (ephemeral!)' if _using_sqlite else 'PostgreSQL'}")
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

db.init_app(app)
app.register_blueprint(youtube.bp)
app.register_blueprint(images.bp)

if _is_production and not uploads_on_persistent_volume(app.config['UPLOAD_FOLDER']):
    print("=" * 60)
    print("WARNING: static/uploads is not on a Railway volume.")
    print("Uploaded images and the resume PDF WILL be lost on every redeploy!")
    print(f"Attach a volume mounted at {app.config['UPLOAD_FOLDER']}")
    print("=" * 60)

csrf = CSRFProtect(app)


@app.after_request
def _cache_uploaded_images(response):
    # 업로드 파일명은 타임스탬프/영상 id로 고유하므로 오래 캐시해도 안전하다.
    # 관리자 화면을 오갈 때마다 수십 장을 다시 받지 않도록 한다.
    if request.path.startswith('/static/uploads/') and response.status_code == 200:
        response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
    elif (request.path.startswith('/static/') and request.args.get('v')
          and response.status_code == 200):
        # ?v=<수정시각>이 붙은 CSS·JS는 파일이 바뀌면 주소가 바뀌므로 1년 캐시해도 안전하다
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


_STATIC_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')


@app.url_defaults
def _version_static_urls(endpoint, values):
    """url_for('static', ...)에 파일 수정 시각을 붙인다 (업로드 파일 제외).

    예전에는 CSS·JS가 no-cache라 방문할 때마다 서버에 변경 여부를 물었다(왕복 약 150ms).
    """
    if endpoint != 'static' or 'v' in values:
        return
    filename = values.get('filename') or ''
    if filename.startswith('uploads/'):
        return
    try:
        values['v'] = int(os.stat(os.path.join(_STATIC_ROOT, filename)).st_mtime)
    except OSError:
        pass


# ── Context Processor ────────────────────────────────────

@app.context_processor
def inject_globals():
    try:
        p = db.session.get(Profile, 1)
    except Exception:
        p = None
    return {'profile': p, 'image_url': images.image_url, 'image_srcset': images.image_srcset}


# ── Public Routes ────────────────────────────────────────

def _visible_projects():
    """공개 페이지용 프로젝트 목록. 숨김 처리된 항목(is_hidden=True)은 제외한다."""
    return (Project.query
            .filter(db.or_(Project.is_hidden.is_(None), Project.is_hidden.is_(False)))
            .order_by(Project.order, Project.created_at.desc()).all())


def _flat(text):
    """줄바꿈·연속 공백을 한 칸으로 접는다 (구조화 데이터용)."""
    return re.sub(r'\s+', ' ', text or '').strip()


def build_structured_data(profile, projects, lang, page_url):
    """페이지에 보이는 프로필·프로젝트 내용을 schema.org JSON-LD로 옮긴다.

    화면에 이미 공개된 문안만 담는다 — 검색엔진·AI 리더가 모달(JS) 안의
    프로젝트 설명과 성과까지 정확히 읽도록 하기 위한 것이다.
    """
    if not profile:
        return None
    en = lang == 'en'

    def pick(ko, en_value):
        return (en_value or ko) if en else ko

    experience = pick(profile.experience, profile.experience_en)
    education = pick(profile.education, profile.education_en)
    awards = pick(profile.awards, profile.awards_en)
    tools = pick(profile.tools, profile.tools_en)
    skills = ([s.strip() for s in profile.skills_en.split(',') if s.strip()]
              if en and profile.skills_en else profile.skill_list)

    person = {
        '@type': 'Person',
        'name': pick(profile.name, profile.name_en),
        'jobTitle': pick(profile.role, profile.role_en),
        'description': _flat(pick(profile.tagline, profile.tagline_en)),
        'url': page_url,
    }
    if en and profile.name_en and profile.name_en != profile.name:
        person['alternateName'] = profile.name
    if profile.email:
        person['email'] = f'mailto:{profile.email}'
    same_as = [u for u in (profile.linkedin_url, profile.remember_url,
                           profile.github_url, profile.blog_url) if u]
    if same_as:
        person['sameAs'] = same_as
    knows = skills + [t.get('name') for t in tools if isinstance(t, dict) and t.get('name')]
    if knows:
        person['knowsAbout'] = knows
    schools = [e.get('school') for e in education if isinstance(e, dict) and e.get('school')]
    if schools:
        person['alumniOf'] = [{'@type': 'EducationalOrganization', 'name': s} for s in schools]
    award_names = [' · '.join(filter(None, [a.get('year'), a.get('title'), a.get('org')]))
                   for a in awards if isinstance(a, dict) and a.get('title')]
    if award_names:
        person['award'] = award_names
    occupations = []
    for ex in experience:
        if not isinstance(ex, dict) or not ex.get('role'):
            continue
        desc = ' · '.join(filter(None, [ex.get('company'), ex.get('period')]))
        bullets = ' / '.join(_flat(b) for b in ex.get('bullets') or [] if b)
        occupations.append({'@type': 'Occupation', 'name': ex['role'],
                            'description': f'{desc} — {bullets}' if bullets else desc})
    if occupations:
        person['hasOccupation'] = occupations

    works = []
    for p in projects:
        title = pick(p.title, p.title_en)
        parts = [_flat(pick(p.description, p.description_en)), _flat(pick(p.kpi, p.kpi_en))]
        work = {'@type': 'CreativeWork', 'name': title,
                'description': ' '.join(x for x in parts if x)}
        role = pick(p.my_role, p.my_role_en)
        if role:
            work['creator'] = {'@type': 'Role', 'roleName': role,
                               'creator': {'@type': 'Person', 'name': person['name']}}
        category = pick(p.category, p.category_en)
        if category:
            work['genre'] = category
        if p.period:
            work['temporalCoverage'] = display_period(p.period, lang)
        if p.tech_list:
            work['keywords'] = ', '.join(p.tech_list)
        works.append(work)

    data = {'@context': 'https://schema.org', '@type': 'ProfilePage',
            'inLanguage': lang, 'url': page_url, 'mainEntity': person}
    if works:
        data['hasPart'] = works
    return data


def _render_index(lang):
    track_visit()
    projects = _visible_projects()
    gallery_items = GalleryItem.query.order_by(GalleryItem.sort_order, GalleryItem.created_at).all()
    profile = db.session.get(Profile, 1)
    return render_template(
        'index.html', projects=projects, gallery_items=gallery_items,
        profile=profile, lang=lang, ui=UI_TEXT[lang], display_period=display_period,
        structured_data=build_structured_data(profile, projects, lang, request.base_url),
    )

@app.route('/')
def index():
    return _render_index('ko')

@app.route('/en')
def index_en():
    return _render_index('en')


# ── Admin Auth ───────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # 무차별 대입 방지: IP당 5분에 10회까지만 시도할 수 있다
        if _rate_limited(f'login:{_client_ip()}', max_hits=10, window=300):
            flash('로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.')
            return render_template('login.html'), 429
        admin = Admin.query.filter_by(username=request.form.get('username', '')).first()
        if admin and admin.check_password(request.form.get('password', '')):
            session.clear()  # 로그인 전 세션 값을 이어받지 않는다 (세션 고정 방지)
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')


@app.route('/admin/logout', methods=['POST'])
def logout():
    # POST + CSRF 토큰으로만 받는다. GET이면 다른 사이트의 <img src>만으로 강제 로그아웃시킬 수 있다.
    session.pop('logged_in', None)
    return redirect(url_for('index'))


def _form_int(name, default=0):
    """숫자 입력칸 값. 비었거나 숫자가 아니면 default."""
    try:
        return int(request.form.get(name) or default)
    except (TypeError, ValueError):
        return default


def login_required(f):
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
        'uploads_warning': _is_production and not uploads_on_persistent_volume(),
        'upload_folder': app.config['UPLOAD_FOLDER'],
    }

    # 방문 통계: 최근 30일 (KST 기준)
    today = datetime.now(KST).date()
    rows = {r.date: r.count for r in DailyVisit.query.all()}
    days = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        ds = d.strftime('%Y-%m-%d')
        days.append({'date': ds, 'label': d.strftime('%m/%d'), 'count': rows.get(ds, 0)})
    visit_stats = {
        'days': days,
        'max': max((d['count'] for d in days), default=0),
        'today': rows.get(today.strftime('%Y-%m-%d'), 0),
        'last7': sum(d['count'] for d in days[-7:]),
        'last30': sum(d['count'] for d in days),
        'total': sum(rows.values()),
    }

    # 퍼널 통계: 30일 치를 한 번만 조회하고 7일/30일로 나눠 집계한다 (7일은 30일의 부분집합)
    prune_visit_events()
    titles = {p.id: p.title for p in projects}
    since_30 = (today - timedelta(days=29)).strftime('%Y-%m-%d')
    since_7 = (today - timedelta(days=6)).strftime('%Y-%m-%d')
    event_rows = db.session.query(
        VisitEvent.session_key, VisitEvent.stage,
        VisitEvent.project_id, VisitEvent.detail, VisitEvent.date, VisitEvent.source,
    ).filter(VisitEvent.date >= since_30).all()
    events_30 = [row[:4] for row in event_rows]
    events_7 = [row[:4] for row in event_rows if row[4] >= since_7]
    funnel = {
        '7': build_funnel_stats(events_7, titles),
        '30': build_funnel_stats(events_30, titles),
    }
    funnel['7']['sources'] = build_source_stats(
        [row[:4] + (row[5],) for row in event_rows if row[4] >= since_7])
    funnel['30']['sources'] = build_source_stats(
        [row[:4] + (row[5],) for row in event_rows])
    funnel_meta = {'since': db.session.query(db.func.min(VisitEvent.date)).scalar() or '-'}

    return render_template('admin.html', projects=projects, profile=profile,
                           gallery_items=gallery_items, db_info=db_info,
                           visit_stats=visit_stats, funnel=funnel,
                           funnel_meta=funnel_meta)


# 프로필 폼의 반복 행: 입력칸 이름은 '<접두사>_<필드>'이고, 첫 필드가 비어 있는 행은 버린다.
EXPERIENCE_FIELDS = ('company', 'period', 'role', 'bullets')
EDUCATION_FIELDS = ('school', 'major', 'degree', 'period')
AWARD_FIELDS = ('title', 'org', 'year')
TOOL_FIELDS = ('name', 'level')
LANGUAGE_SCORE_FIELDS = ('exam', 'score', 'date')


def _form_rows(prefix, fields):
    """같은 이름으로 여러 번 오는 입력칸들을 행(dict) 목록으로 묶는다.

    뒤쪽 필드 값이 모자란 행은 ''로 채운다. 'bullets'는 줄마다 항목 하나인 목록으로 바꾼다.
    """
    columns = {f: request.form.getlist(f'{prefix}_{f}') for f in fields}
    rows = []
    for i, key in enumerate(columns[fields[0]]):
        if not key.strip():
            continue
        row = {}
        for f in fields:
            value = columns[f][i] if i < len(columns[f]) else ''
            if f == 'bullets':
                row[f] = [line.strip() for line in value.split('\n') if line.strip()]
            else:
                row[f] = value.strip()
        rows.append(row)
    return rows


def _form_rows_json(prefix, fields):
    return json.dumps(_form_rows(prefix, fields), ensure_ascii=False)


@app.route('/admin/profile', methods=['GET', 'POST'])
@login_required
def profile_edit():
    profile = db.session.get(Profile, 1)
    if request.method == 'POST':
        # 저장 후 더 이상 쓰이지 않는 이전 업로드 파일을 지우기 위해 기억해 둔다
        old_files = {profile.profile_image_filename, profile.resume_filename,
                     _upload_name_from_url(profile.og_image_url)}
        profile.name = request.form.get('name', '')
        profile.role = request.form.get('role', '')
        profile.tagline = request.form.get('tagline', '')
        profile.about_text = request.form.get('about_text', '')
        profile.email = request.form.get('email', '')
        profile.phone = request.form.get('phone', '').strip()[:40]
        def fix_url(u):
            u = u.strip()
            if u and not u.startswith(('http://', 'https://')):
                u = 'https://' + u
            return u

        profile.linkedin_url = fix_url(request.form.get('linkedin_url', ''))
        profile.github_url = fix_url(request.form.get('github_url', ''))
        profile.remember_url = fix_url(request.form.get('remember_url', ''))
        profile.blog_url = fix_url(request.form.get('blog_url', ''))
        # 프로필 이미지 업로드 (크롭 base64 우선, 없으면 일반 파일)
        prof_img_cropped = request.form.get('profile_image_cropped_data', '')
        prof_img_file = request.files.get('profile_image_file')
        if prof_img_cropped and ',' in prof_img_cropped:
            fn = _save_data_uri(prof_img_cropped, _unique_upload_name('profile', 'jpg'))
            if fn:
                profile.profile_image_filename = fn
        elif prof_img_file and prof_img_file.filename:
            fn = save_uploaded_image(prof_img_file, 'profile')
            if fn:
                profile.profile_image_filename = fn

        og_cropped = request.form.get('og_cropped_data', '')
        og_file = request.files.get('og_image_file')
        if og_cropped and ',' in og_cropped:
            fn = _save_data_uri(og_cropped, _unique_upload_name('og', 'jpg'))
            if fn:
                profile.og_image_url = url_for('static', filename='uploads/' + fn, _external=True)
        elif og_file and og_file.filename:
            fn = save_uploaded_image(og_file, 'og')
            if fn:
                profile.og_image_url = url_for('static', filename='uploads/' + fn, _external=True)
        else:
            profile.og_image_url = request.form.get('og_image_url', '')
        profile.open_to_work = bool(request.form.get('open_to_work'))

        # English fields
        profile.name_en = request.form.get('name_en', '')
        profile.role_en = request.form.get('role_en', '')
        profile.tagline_en = request.form.get('tagline_en', '')
        profile.about_text_en = request.form.get('about_text_en', '')
        profile.skills_en = request.form.get('skills_en', '')
        profile.experience_en_json = _form_rows_json('en_exp', EXPERIENCE_FIELDS)
        profile.education_en_json = _form_rows_json('en_edu', EDUCATION_FIELDS)
        profile.awards_en_json = _form_rows_json('en_award', AWARD_FIELDS)
        profile.tools_en_json = _form_rows_json('en_tool', TOOL_FIELDS)

        # 이력서 PDF 업로드
        resume_file = request.files.get('resume_file')
        resume_rejected = False
        if resume_file and resume_file.filename:
            filename = save_uploaded_pdf(resume_file)
            if filename:
                profile.resume_filename = filename
            else:
                resume_rejected = True

        profile.skills = request.form.get('skills', '')  # 핵심 역량 (쉼표로 구분한 단순 목록)
        profile.language_scores_json = _form_rows_json('lang', LANGUAGE_SCORE_FIELDS)
        profile.tools_json = _form_rows_json('tool', TOOL_FIELDS)
        profile.education_json = _form_rows_json('edu', EDUCATION_FIELDS)
        profile.awards_json = _form_rows_json('award', AWARD_FIELDS)
        profile.experience_json = _form_rows_json('exp', EXPERIENCE_FIELDS)

        db.session.commit()
        for filename in old_files:
            _remove_upload_if_unused(filename)
        if resume_rejected:
            flash('이력서는 PDF 파일만 올릴 수 있습니다. 이력서를 뺀 나머지 내용만 저장했습니다.')
        flash('프로필이 저장되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('profile_form.html', profile=profile)


@app.route('/admin/project/new', methods=['GET', 'POST'])
@login_required
def project_new():
    if request.method == 'POST':
        labels = request.form.getlist('link_label')
        urls   = request.form.getlist('link_url')
        links  = [{'label': l.strip(), 'url': _expand_tiktok_short_url(u.strip())}
                  for l, u in zip(labels, urls) if l.strip() and u.strip()]
        en_labels = request.form.getlist('link_label_en')
        links_en  = [{'label': en_labels[i].strip() if i < len(en_labels) else '', 'url': lk['url']}
                     for i, lk in enumerate(links)]
        kpi_items = request.form.getlist('kpi_item')
        kpi = '\n'.join(i.strip() for i in kpi_items if i.strip())
        img = save_uploaded_image(request.files.get('image'))
        en_kpi_items = request.form.getlist('kpi_item_en')
        p = Project(
            title=request.form['title'],
            description=request.form['description'],
            tech_stack=request.form['tech_stack'],
            github_url='',
            demo_url='',
            period=request.form.get('period', ''),
            order=_form_int('order'),
            detail_text=request.form.get('detail_text', ''),
            image_filename=img or '',
            links_json=json.dumps(links, ensure_ascii=False),
            links_en_json=json.dumps(links_en, ensure_ascii=False),
            kpi=kpi,
            my_role=request.form.get('my_role', ''),
            category=request.form.get('category', ''),
            title_en=request.form.get('title_en', ''),
            description_en=request.form.get('description_en', ''),
            detail_text_en=request.form.get('detail_text_en', ''),
            kpi_en='\n'.join(i.strip() for i in en_kpi_items if i.strip()),
            my_role_en=request.form.get('my_role_en', ''),
            category_en=request.form.get('category_en', ''),
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
        labels = request.form.getlist('link_label')
        urls   = request.form.getlist('link_url')
        links  = [{'label': l.strip(), 'url': _expand_tiktok_short_url(u.strip())}
                  for l, u in zip(labels, urls) if l.strip() and u.strip()]
        p.title = request.form['title']
        p.description = request.form['description']
        p.tech_stack = request.form['tech_stack']
        p.period = request.form.get('period', '')
        p.order = _form_int('order')
        p.detail_text = request.form.get('detail_text', '')
        p.links_json = json.dumps(links, ensure_ascii=False)
        en_labels = request.form.getlist('link_label_en')
        p.links_en_json = json.dumps(
            [{'label': en_labels[i].strip() if i < len(en_labels) else '', 'url': lk['url']}
             for i, lk in enumerate(links)],
            ensure_ascii=False)
        kpi_items = request.form.getlist('kpi_item')
        p.kpi = '\n'.join(i.strip() for i in kpi_items if i.strip())
        p.my_role = request.form.get('my_role', '')
        p.category = request.form.get('category', '')
        p.title_en = request.form.get('title_en', '')
        p.description_en = request.form.get('description_en', '')
        p.detail_text_en = request.form.get('detail_text_en', '')
        en_kpi_items = request.form.getlist('kpi_item_en')
        p.kpi_en = '\n'.join(i.strip() for i in en_kpi_items if i.strip())
        p.my_role_en = request.form.get('my_role_en', '')
        p.category_en = request.form.get('category_en', '')
        db.session.commit()
        flash('프로젝트가 수정되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('project_form.html', project=p)


@app.route('/admin/project/<int:pid>/import-copy', methods=['POST'])
@login_required
def project_import_copy(pid):
    """관리자가 원할 때만 data/site_projects.json의 기준 문안으로 되돌린다."""
    p = Project.query.get_or_404(pid)
    entry = _find_copy_entry(p.title)
    if not entry:
        flash('이 프로젝트 제목과 맞는 기준 문안이 data/site_projects.json에 없습니다.')
    else:
        _apply_copy_entry(p, entry)
        db.session.commit()
        flash('기준 문안을 불러와 저장했습니다. 필요한 부분을 고친 뒤 다시 저장하세요.')
    return redirect(url_for('project_edit', pid=pid))


@app.route('/admin/project/<int:pid>/toggle-hidden', methods=['POST'])
@login_required
def project_toggle_hidden(pid):
    """프로젝트를 공개 페이지에서 숨기거나 다시 공개한다. 데이터는 그대로 남는다."""
    p = Project.query.get_or_404(pid)
    p.is_hidden = not bool(p.is_hidden)
    db.session.commit()
    flash('프로젝트를 숨겼습니다.' if p.is_hidden else '프로젝트를 다시 공개했습니다.')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/project/<int:pid>/delete', methods=['POST'])
@login_required
def project_delete(pid):
    p = Project.query.get_or_404(pid)
    filenames = {img.filename for img in p.images}
    db.session.delete(p)
    db.session.commit()
    # cascade는 DB 행만 지우므로 파일은 따로 지운다. 다른 프로젝트가 같이 쓰는 썸네일은 남긴다.
    for filename in filenames:
        _remove_upload_if_unused(filename)
    flash('프로젝트가 삭제되었습니다.')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/profile/resume/delete', methods=['POST'])
@login_required
def profile_resume_delete():
    profile = db.session.get(Profile, 1)
    if profile and profile.resume_filename:
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], profile.resume_filename)
        if os.path.exists(fpath):
            os.remove(fpath)
        profile.resume_filename = ''
        db.session.commit()
        flash('이력서가 삭제되었습니다.')
    return redirect(url_for('profile_edit'))


@app.route('/admin/profile/image/delete', methods=['POST'])
@login_required
def profile_image_delete():
    profile = db.session.get(Profile, 1)
    if profile and profile.profile_image_filename:
        filename = profile.profile_image_filename
        profile.profile_image_filename = ''
        db.session.commit()
        _remove_upload_if_unused(filename)
        flash('프로필 이미지가 삭제되었습니다.')
    return redirect(url_for('profile_edit'))


@app.route('/resume')
def serve_resume():
    profile = db.session.get(Profile, 1)
    if not profile or not profile.resume_filename:
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], profile.resume_filename,
                               as_attachment=True, download_name='resume.pdf')


# ── Gallery CRUD ────────────────────────────────────────

def _save_gallery_image(request):
    cropped = request.form.get('cropped_data')
    fn = _save_data_uri(cropped, _unique_upload_name('gallery', 'jpg'))
    if fn:
        return fn
    return save_uploaded_image(request.files.get('image'), 'gallery')

@app.route('/admin/gallery/new', methods=['GET', 'POST'])
@login_required
def gallery_new():
    if request.method == 'POST':
        filename = _save_gallery_image(request)
        if not filename:
            flash('이미지를 선택해주세요.')
            return redirect(request.url)
        item = GalleryItem(
            title=request.form['title'],
            title_en=request.form.get('title_en', ''),
            description='',
            image_filename=filename,
            links_json='[]',
            sort_order=_form_int('sort_order'),
        )
        db.session.add(item)
        db.session.commit()
        flash('갤러리 항목이 추가되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('gallery_form.html', item=None)

@app.route('/admin/gallery/<int:gid>/edit', methods=['GET', 'POST'])
@login_required
def gallery_edit(gid):
    item = GalleryItem.query.get_or_404(gid)
    if request.method == 'POST':
        item.title = request.form['title']
        item.title_en = request.form.get('title_en', '')
        item.sort_order = _form_int('sort_order')
        old_img = item.image_filename
        new_img = _save_gallery_image(request)
        if new_img:
            item.image_filename = new_img
        db.session.commit()
        if new_img:
            _remove_upload_if_unused(old_img)
        flash('갤러리 항목이 수정되었습니다.')
        return redirect(url_for('admin_dashboard'))
    return render_template('gallery_form.html', item=item)

@app.route('/admin/gallery/<int:gid>/delete', methods=['POST'])
@login_required
def gallery_delete(gid):
    item = GalleryItem.query.get_or_404(gid)
    filename = item.image_filename
    db.session.delete(item)
    db.session.commit()
    _remove_upload_if_unused(filename)
    flash('갤러리 항목이 삭제되었습니다.')
    return redirect(url_for('admin_dashboard'))


# ── Image AJAX Routes ───────────────────────────────────

@app.route('/admin/project/<int:pid>/images/upload', methods=['POST'])
@login_required
def project_image_upload(pid):
    p = Project.query.get_or_404(pid)
    cropped = request.form.get('cropped_data')
    filename = _save_data_uri(cropped, _unique_upload_name(f'proj{pid}', 'jpg'))
    if not filename:
        filename = save_uploaded_image(request.files.get('image'), f"proj{pid}")
    if not filename:
        return jsonify({'error': 'invalid file'}), 400
    has_any = ProjectImage.query.filter_by(project_id=pid).first() is not None
    img = ProjectImage(project_id=pid, filename=filename, is_main=not has_any)
    db.session.add(img)
    db.session.commit()
    return jsonify({'id': img.id, 'is_main': img.is_main,
                    'url': url_for('static', filename='uploads/' + filename)})


@app.route('/admin/project/images/<int:img_id>/set-main', methods=['POST'])
@login_required
def project_image_set_main(img_id):
    img = ProjectImage.query.get_or_404(img_id)
    ProjectImage.query.filter_by(project_id=img.project_id).update({'is_main': False})
    img.is_main = True
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/admin/project/images/<int:img_id>/delete', methods=['POST'])
@login_required
def project_image_delete(img_id):
    img = ProjectImage.query.get_or_404(img_id)
    was_main, pid, filename = img.is_main, img.project_id, img.filename
    db.session.delete(img)
    db.session.commit()
    _remove_upload_if_unused(filename)
    if was_main:
        nxt = ProjectImage.query.filter_by(project_id=pid).first()
        if nxt:
            nxt.is_main = True
            db.session.commit()
    return jsonify({'ok': True})


# ── Reorder ─────────────────────────────────────────────

def _reorder_ids():
    """재정렬 요청의 ids 목록을 정수 목록으로. 형식이 틀리면 None (전부 거부하고 아무것도 바꾸지 않는다)."""
    data = request.get_json(silent=True)
    ids = data.get('ids') if isinstance(data, dict) else None
    if not isinstance(ids, list):
        return None
    parsed = []
    for value in ids:
        if isinstance(value, bool):
            return None
        try:
            parsed.append(int(value))
        except (TypeError, ValueError):
            return None
    return parsed

@app.route('/admin/projects/reorder', methods=['POST'])
@login_required
def projects_reorder():
    ids = _reorder_ids()
    if ids is None:
        return jsonify({'error': 'ids must be a list of integers'}), 400
    for i, pid in enumerate(ids):
        p = db.session.get(Project, pid)
        if p:
            p.order = i
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/admin/gallery/reorder', methods=['POST'])
@login_required
def gallery_reorder():
    ids = _reorder_ids()
    if ids is None:
        return jsonify({'error': 'ids must be a list of integers'}), 400
    for i, gid in enumerate(ids):
        g = db.session.get(GalleryItem, gid)
        if g:
            g.sort_order = i
    db.session.commit()
    return jsonify({'ok': True})


# ── Public Funnel Tracking ────────────────────────────────────

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


# ── Entry ────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=False)
