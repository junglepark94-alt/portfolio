from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import os
import time
import re
import json
import base64
import threading
import secrets

KST = timezone(timedelta(hours=9))

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
    },
}


def display_period(period, lang='ko'):
    """Return a project period with a locale-appropriate ongoing label."""
    value = period or ''
    if lang == 'en':
        return value.replace('진행 중', 'Present')
    return value.replace('Present', '진행 중')

def _today_kst():
    return datetime.now(KST).strftime('%Y-%m-%d')

app = Flask(__name__)

_is_production = bool(os.environ.get('PORT'))  # Railway는 PORT를 주입함

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

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

csrf = CSRFProtect(app)


@app.after_request
def _cache_uploaded_images(response):
    # 업로드 파일명은 타임스탬프/영상 id로 고유하므로 오래 캐시해도 안전하다.
    # 관리자 화면을 오갈 때마다 수십 장을 다시 받지 않도록 한다.
    if request.path.startswith('/static/uploads/') and response.status_code == 200:
        response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
    return response


def _looks_like_image(head):
    """매직 바이트로 실제 이미지 여부를 검사 (확장자 위조 방지)."""
    if head[:3] == b'\xff\xd8\xff':                       # JPEG
        return True
    if head[:8] == b'\x89PNG\r\n\x1a\n':                  # PNG
        return True
    if head[:6] in (b'GIF87a', b'GIF89a'):               # GIF
        return True
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':    # WEBP
        return True
    return False


def save_uploaded_image(file, prefix='project'):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return None
    head = file.stream.read(16)
    file.stream.seek(0)
    if not _looks_like_image(head):
        return None
    filename = f"{prefix}_{int(time.time())}.{ext}"
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename


def _save_data_uri(data_uri, filename):
    """data URI(base64 크롭 이미지)를 검증 후 저장. 성공 시 filename, 실패 시 None."""
    if not data_uri or ',' not in data_uri:
        return None
    try:
        raw = base64.b64decode(data_uri.split(',', 1)[1])
    except Exception:
        return None
    if not _looks_like_image(raw[:16]):
        return None
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as f:
        f.write(raw)
    return filename


# ── 간단한 인메모리 레이트리밋 (YouTube 프록시 쿼터 어뷰징 방지) ──
# gunicorn 워커마다 독립적이므로 분산 환경에서는 워커 수만큼 한도가 곱해짐.
# 외부 의존성 없이 캐주얼한 남용을 막는 수준의 방어임.
_RATE_LOCK = threading.Lock()
_RATE_HITS = {}  # client_ip -> [timestamps]


def _client_ip():
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _rate_limited(key, max_hits=30, window=60):
    now = time.time()
    with _RATE_LOCK:
        if len(_RATE_HITS) > 2000:  # 키 무한 증가 방지
            for k in [k for k, v in _RATE_HITS.items() if not v or now - v[-1] > window]:
                _RATE_HITS.pop(k, None)
        hits = [t for t in _RATE_HITS.get(key, []) if now - t < window]
        if len(hits) >= max_hits:
            _RATE_HITS[key] = hits
            return True
        hits.append(now)
        _RATE_HITS[key] = hits
        return False


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
    kpi = db.Column(db.Text, default='')
    my_role = db.Column(db.String(200), default='')
    category = db.Column(db.String(100), default='')
    # English
    links_en_json = db.Column(db.Text, default='[]')
    title_en = db.Column(db.String(120), default='')
    description_en = db.Column(db.Text, default='')
    detail_text_en = db.Column(db.Text, default='')
    kpi_en = db.Column(db.Text, default='')
    my_role_en = db.Column(db.String(200), default='')
    category_en = db.Column(db.String(100), default='')
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
    def links_en(self):
        import json as _json
        try:
            return _json.loads(self.links_en_json or '[]')
        except Exception:
            return []

    @property
    def tech_list(self):
        return [t.strip() for t in (self.tech_stack or '').split(',') if t.strip()]


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
    title_en = db.Column(db.String(200), default='')
    description = db.Column(db.Text, default='')
    image_filename = db.Column(db.String(300), nullable=False)
    links_json = db.Column(db.Text, default='[]')
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def links(self):
        try:
            return json.loads(self.links_json or '[]')
        except Exception:
            return []


class DailyVisit(db.Model):
    """일별 방문수 집계 (KST 기준, 세션당 하루 1회)"""
    __tablename__ = 'daily_visit'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), unique=True, index=True, nullable=False)  # YYYY-MM-DD
    count = db.Column(db.Integer, default=0)


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


def track_visit():
    """공개 페이지 방문 기록. 같은 세션은 하루 1회만 카운트."""
    try:
        record_event('visit')
        today = _today_kst()
        key = f'v_{today}'
        if session.get(key):
            return
        session[key] = True
        rec = DailyVisit.query.filter_by(date=today).first()
        if rec is None:
            rec = DailyVisit(date=today, count=0)
            db.session.add(rec)
        rec.count = (rec.count or 0) + 1
        db.session.commit()
    except Exception:
        db.session.rollback()


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
    remember_url = db.Column(db.String(300), default='')
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
    # 프로필 이미지 (3.5:4.5)
    profile_image_filename = db.Column(db.String(300), default='')
    # 어학 성적 [{exam, score, date}]
    language_scores_json = db.Column(db.Text, default='[]')
    # English
    name_en = db.Column(db.String(80), default='')
    role_en = db.Column(db.String(120), default='')
    tagline_en = db.Column(db.Text, default='')
    about_text_en = db.Column(db.Text, default='')
    experience_en_json = db.Column(db.Text, default='[]')
    education_en_json = db.Column(db.Text, default='[]')
    awards_en_json = db.Column(db.Text, default='[]')
    skills_en = db.Column(db.String(500), default='')
    tools_en_json = db.Column(db.Text, default='[]')

    @property
    def language_scores(self):
        import json as _j
        try:
            return _j.loads(self.language_scores_json or '[]')
        except Exception:
            return []

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
    def tools_en(self):
        import json as _j
        try:
            return _j.loads(self.tools_en_json or '[]')
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
    def experience_en(self):
        import json as _j
        try:
            return _j.loads(self.experience_en_json or '[]')
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
    def education_en(self):
        import json as _j
        try:
            return _j.loads(self.education_en_json or '[]')
        except Exception:
            return []

    @property
    def awards(self):
        import json as _j
        try:
            return _j.loads(self.awards_json or '[]')
        except Exception:
            return []

    @property
    def awards_en(self):
        import json as _j
        try:
            return _j.loads(self.awards_en_json or '[]')
        except Exception:
            return []



class ContentSync(db.Model):
    """기준 문안(JSON) 동기화가 어느 버전까지 적용됐는지 기록. 이후에는 관리자 수정이 최신이다."""
    __tablename__ = 'content_sync'
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(120), default='')
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)


def _normalize_copy(value):
    """Apply narrowly scoped spelling and metric corrections to public copy."""
    normalized = value or ''
    for old, new in [
        ('사이니', '샤이니'),
        ('버츄얼', '버추얼'),
        ('런칭', '론칭'),
        ('컨셉카', '콘셉트카'),
        ('6782%', '67–82%'),
        ('67~82%', '67–82%'),
        ('Contents Planning', 'Content Strategy & Production'),
        ('Digital Contents', 'Digital Content'),
        ('Assitant', 'Assistant'),
        ('Planning & Operations Planning & Operations', 'Planning & Operations'),
        ('Mountain Village Women', 'City Girls on the Climb'),
        ('Mountain City Women', 'City Girls on the Climb'),
        ('City girls on the climb', 'City Girls on the Climb'),
        ('SHINee Inc. - tvN', 'SHINee Inc. — tvN'),
        ('빙그레X더현대서울', '빙그레×더현대서울'),
        ('Social Eye Awards', 'Social i Awards'),
        ('Social I Award', 'Social i Awards'),
    ]:
        normalized = normalized.replace(old, new)
    # 이전 규칙이 만든 'Grand Prize' 중복 표기 복구
    normalized = normalized.replace('Korea Pop-Up Store Awards Grand Prize – Grand Prize',
                                    'Korea Pop-Up Store Awards – Grand Prize')
    normalized = normalized.replace('Grand Prize at the 2025 Korea Pop-Up Store Awards Grand Prize',
                                    'Grand Prize at the 2025 Korea Pop-Up Store Awards')
    return normalized


_PERIOD_DATE = r'\d{4}\.\s*\d{1,2}(?:\.\s*\d{1,2})?'
_PERIOD_END = r'현재|진행 중|Present|Ongoing'


def _normalize_period(value):
    """Unify date ranges to 'YYYY.MM – YYYY.MM' with an en dash and no stray spaces."""
    normalized = value or ''
    normalized = re.sub(r'(\d{4})\.\s+(\d{1,2})', r'\1.\2', normalized)
    normalized = re.sub(r'(\d{4}\.\d{1,2})\.\s+(\d{1,2})', r'\1.\2', normalized)
    normalized = re.sub(
        r'(%s)\s*[-~–—]\s*(%s|%s)' % (_PERIOD_DATE, _PERIOD_DATE, _PERIOD_END),
        r'\1 – \2', normalized,
    )
    return normalized


def _normalize_json_entries(raw):
    """Normalize copy and periods inside a JSON list of dict entries; leave unparsable input as-is."""
    try:
        entries = json.loads(raw or '[]')
    except (TypeError, ValueError):
        return raw
    if not isinstance(entries, list):
        return raw
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key, val in entry.items():
            if isinstance(val, list):
                entry[key] = [_normalize_copy(v) if isinstance(v, str) else v for v in val]
                continue
            if not isinstance(val, str):
                continue
            val = _normalize_copy(val)
            if key == 'period':
                val = _normalize_period(val)
            if key == 'title' and val.strip() in ('2025 Korea Pop-Up Store Awards', 'Korea Pop-Up Store Awards'):
                val = val.strip() + ' Grand Prize'
            entry[key] = val
    return json.dumps(entries, ensure_ascii=False)


def normalize_public_content():
    """최초 1회 동기화: 프로필/기간 표기 정리 + 프로젝트 기준 문안 적용."""
    normalize_profile_and_periods()
    _apply_project_copy_overrides()
    db.session.commit()


def normalize_profile_and_periods():
    """오탈자·기간 표기·영문 용어만 정리한다 (관리자가 쓴 문안의 내용은 바꾸지 않는다)."""
    content_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data',
                                'hyundai_application_2026.json')
    try:
        with open(content_path, encoding='utf-8') as content_file:
            canonical = json.load(content_file)
    except (OSError, ValueError):
        canonical = {}

    profile = db.session.get(Profile, 1)
    site_copy = canonical.get('site_copy', {})
    if profile:
        profile.name_en = canonical.get('identity', {}).get('name_en', 'Jonggeol Park')
        profile.role = site_copy.get('hero_role_ko', profile.role)
        profile.role_en = site_copy.get('hero_role_en', profile.role_en)
        profile.tagline = site_copy.get('hero_tagline_ko', profile.tagline)
        profile.tagline_en = site_copy.get('hero_tagline_en', profile.tagline_en)
        for attr in (
            'about_text', 'about_text_en', 'skills', 'skills_en', 'skills_json',
            'tools_json', 'tools_en_json',
        ):
            setattr(profile, attr, _normalize_copy(getattr(profile, attr)))
        for attr in (
            'experience_json', 'experience_en_json', 'education_json',
            'education_en_json', 'awards_json', 'awards_en_json',
        ):
            setattr(profile, attr, _normalize_json_entries(getattr(profile, attr)))

    category_map = site_copy.get('categories_en', {
        '콘텐츠 기획': 'Content Strategy & Production',
        '디지털 콘텐츠': 'Digital Content',
        '오프라인 캠페인': 'Brand Experience',
        '프로듀싱': 'Entertainment Production',
    })
    legacy_category_map = {
        'Contents Planning': 'Content Strategy & Production',
        'Digital Contents': 'Digital Content',
        'Offline Campaign': 'Brand Experience',
        'Producing': 'Entertainment Production',
    }
    for project in Project.query.all():
        for attr in (
            'title', 'description', 'detail_text', 'kpi', 'my_role', 'category',
            'title_en', 'description_en', 'detail_text_en', 'kpi_en', 'my_role_en',
        ):
            setattr(project, attr, _normalize_copy(getattr(project, attr)))

        project.period = _normalize_period(project.period)

        project.category_en = legacy_category_map.get(
            project.category_en,
            category_map.get(project.category, project.category_en),
        )
        if '샤이니의 빛돌기획' in project.title:
            project.title = 'tvN 예능 ‘샤이니의 빛돌기획’ 제작'
            project.title_en = 'SHINee Inc. — tvN Branded Entertainment'
        if 'Banana Salon' in project.title or 'Banana Salon' in project.title_en:
            project.period = '2026.07 – 진행 중'


def _relabel_links(raw, label_map):
    """Rename link labels in a links JSON list; leave unparsable input untouched."""
    if not label_map:
        return raw
    try:
        links = json.loads(raw or '[]')
    except (TypeError, ValueError):
        return raw
    if not isinstance(links, list):
        return raw
    for link in links:
        if isinstance(link, dict) and link.get('label') in label_map:
            link['label'] = label_map[link['label']]
    return json.dumps(links, ensure_ascii=False)


_COPY_FIELDS = ('description', 'kpi', 'detail_text', 'description_en', 'kpi_en', 'detail_text_en')


def _load_copy_entries():
    """data/site_projects.json의 프로젝트 기준 문안 목록. 파일이 없거나 깨졌으면 빈 목록."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'site_projects.json')
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh).get('projects', [])
    except (OSError, ValueError):
        return []


def _find_copy_entry(title):
    title = title or ''
    return next((o for o in _load_copy_entries() if o.get('match') and o['match'] in title), None)


def _apply_copy_entry(project, entry):
    """기준 문안 한 건을 프로젝트에 적용 (요약·성과·상세·링크 라벨·썸네일 교체)."""
    for field in _COPY_FIELDS:
        if entry.get(field) is not None:
            setattr(project, field, entry[field])
    project.links_json = _relabel_links(project.links_json, entry.get('link_labels'))
    project.links_en_json = _relabel_links(project.links_en_json, entry.get('link_labels_en'))
    _swap_in_youtube_thumbnails(project, entry.get('youtube_thumbnails'))
    _swap_in_official_images(project, entry.get('image_replacements'))


def _apply_project_copy_overrides():
    """모든 프로젝트에 기준 문안을 적용. 최초 동기화와 관리자의 '불러오기' 버튼에서만 호출된다."""
    entries = _load_copy_entries()
    for project in Project.query.all():
        title = project.title or ''
        entry = next((o for o in entries if o.get('match') and o['match'] in title), None)
        if entry:
            _apply_copy_entry(project, entry)


def apply_youtube_thumbnail_swaps():
    """잘린 스크린샷 → 원본 썸네일/공식 이미지 교체.

    매 시작 시 실행해도 안전하다: 지정된 파일명만 찾아 바꾸고, 교체 후에는 대상이 남지 않는다.
    """
    entries = [e for e in _load_copy_entries()
               if e.get('youtube_thumbnails') or e.get('image_replacements')]
    if not entries:
        return
    for project in Project.query.all():
        title = project.title or ''
        entry = next((o for o in entries if o.get('match') and o['match'] in title), None)
        if not entry:
            continue
        _swap_in_youtube_thumbnails(project, entry.get('youtube_thumbnails'))
        _swap_in_official_images(project, entry.get('image_replacements'))
    db.session.commit()


# 기준 문안 동기화는 이 버전당 한 번만 실행된다. 그 뒤로는 관리자 화면에서 저장한 내용이 항상 최신이다.
# 값을 올리면 다음 시작 때 한 번 더 덮어쓰므로, 관리자 수정 내용을 잃어도 되는 경우에만 올린다.
CONTENT_SEED_VERSION = 1


# 오탈자/기간 표기 정리는 이 버전당 한 번 더 실행된다. 문안 내용은 건드리지 않으므로 관리자 수정과 충돌하지 않는다.
PROFILE_FIX_VERSION = 2


def _marker_version(key):
    marker = db.session.get(ContentSync, key)
    return int(marker.value) if marker and (marker.value or '').isdigit() else 0


def _set_marker(key, version):
    marker = db.session.get(ContentSync, key)
    if marker is None:
        marker = ContentSync(key=key)
        db.session.add(marker)
    marker.value = str(version)
    marker.applied_at = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return False
    return True


def apply_profile_fixes_once():
    """normalize_profile_and_periods()를 PROFILE_FIX_VERSION당 한 번 실행."""
    if _marker_version('profile_fix_version') >= PROFILE_FIX_VERSION:
        return False
    normalize_profile_and_periods()
    db.session.commit()
    return _set_marker('profile_fix_version', PROFILE_FIX_VERSION)


def sync_canonical_content_once():
    """normalize_public_content()를 CONTENT_SEED_VERSION당 한 번만 실행. 실행했으면 True."""
    marker = db.session.get(ContentSync, 'seed_version')
    applied = int(marker.value) if marker and (marker.value or '').isdigit() else 0
    if applied >= CONTENT_SEED_VERSION:
        return False
    normalize_public_content()
    if marker is None:
        marker = ContentSync(key='seed_version')
        db.session.add(marker)
    marker.value = str(CONTENT_SEED_VERSION)
    marker.applied_at = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        # 워커 두 개가 동시에 부팅하며 같은 마커를 넣으려 한 경우: 먼저 성공한 쪽을 그대로 둔다
        db.session.rollback()
        return False
    return True


_YT_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')

# 외부 이미지는 이 호스트에서만 받는다 (유튜브 썸네일, tvN 공식 프로그램 이미지)
_ALLOWED_IMAGE_HOSTS = {'img.youtube.com', 'i.ytimg.com', 'poc-cf-image.cjenm.com'}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _download_image(url, filename):
    """허용 호스트의 이미지를 uploads에 저장. 성공 시 filename, 실패 시 None."""
    import urllib.parse as _parse
    import urllib.request as _req
    parts = _parse.urlparse(url)
    if parts.scheme != 'https' or parts.hostname not in _ALLOWED_IMAGE_HOSTS:
        return None
    folder = app.config['UPLOAD_FOLDER']
    target = os.path.join(folder, filename)
    if os.path.exists(target) and os.path.getsize(target) > 8000:
        return filename
    try:
        with _req.urlopen(url, timeout=10) as resp:
            if getattr(resp, 'status', 200) != 200:
                return None
            raw = resp.read(_MAX_IMAGE_BYTES)
    except Exception:
        return None
    if len(raw) < 8000 or not _looks_like_image(raw[:16]):
        return None
    os.makedirs(folder, exist_ok=True)
    with open(target, 'wb') as fh:
        fh.write(raw)
    return filename


def _fetch_external_image(url):
    """공식 이미지 URL을 내려받아 안정적인 파일명으로 저장한다."""
    import hashlib
    if not url:
        return None
    return _download_image(url, 'ext_' + hashlib.sha1(url.encode()).hexdigest()[:12] + '.jpg')


def _fetch_youtube_thumbnail(video_id):
    """Download a video's original 1280x720 thumbnail into uploads. Returns filename or None."""
    if not _YT_ID_RE.match(video_id or ''):
        return None
    filename = f'yt_{video_id}.jpg'
    for quality in ('maxresdefault', 'hqdefault'):
        # maxresdefault가 없으면 유튜브가 120x90 회색 자리표시자를 주므로 크기 검사로 걸러진다
        got = _download_image(f'https://img.youtube.com/vi/{video_id}/{quality}.jpg', filename)
        if got:
            return got
    return None


def _swap_in_official_images(project, mapping):
    """잘린 캡처를 공식 이미지(프로그램 키아트 등)로 교체."""
    if not mapping:
        return
    images = {img.filename: img for img in ProjectImage.query.filter_by(project_id=project.id)}
    for old_name, url in mapping.items():
        target = images.get(old_name)
        if target is None:
            continue
        new_name = _fetch_external_image(url)
        if new_name and new_name != target.filename:
            target.filename = new_name


def _swap_in_youtube_thumbnails(project, mapping):
    """Replace cropped screenshots with the original YouTube thumbnails they came from."""
    if not mapping:
        return
    images = {img.filename: img for img in ProjectImage.query.filter_by(project_id=project.id)}
    for old_name, video_id in mapping.items():
        target = images.get(old_name)
        if target is None:
            continue  # 이미 교체됐거나 다른 환경
        new_name = _fetch_youtube_thumbnail(video_id)
        if new_name and new_name != target.filename:
            target.filename = new_name


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
            "ALTER TABLE project ALTER COLUMN kpi TYPE TEXT",  # PostgreSQL only; SQLite ignores
            "ALTER TABLE project ADD COLUMN my_role VARCHAR(200) DEFAULT ''",
            "ALTER TABLE project ADD COLUMN category VARCHAR(100) DEFAULT ''",
            "ALTER TABLE profile ADD COLUMN profile_image_filename VARCHAR(300) DEFAULT ''",
            "ALTER TABLE profile ADD COLUMN language_scores_json TEXT DEFAULT '[]'",
            "ALTER TABLE profile ADD COLUMN remember_url VARCHAR(300) DEFAULT ''",
            # English columns
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
        _admin_pw = os.environ.get('ADMIN_PASSWORD')
        if not _admin_pw:
            if _is_production:
                import secrets
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
    try:
        apply_youtube_thumbnail_swaps()
    except Exception as exc:
        db.session.rollback()
        print(f"[thumbnail-swap] skipped: {exc!r}")


# ── Context Processor ────────────────────────────────────

@app.context_processor
def inject_globals():
    try:
        p = db.session.get(Profile, 1)
    except Exception:
        p = None
    return {'profile': p}


# ── Public Routes ────────────────────────────────────────

def _render_index(lang):
    track_visit()
    projects = Project.query.order_by(Project.order, Project.created_at.desc()).all()
    gallery_items = GalleryItem.query.order_by(GalleryItem.sort_order, GalleryItem.created_at).all()
    profile = db.session.get(Profile, 1)
    return render_template(
        'index.html', projects=projects, gallery_items=gallery_items,
        profile=profile, lang=lang, ui=UI_TEXT[lang], display_period=display_period,
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
    return render_template('admin.html', projects=projects, profile=profile,
                           gallery_items=gallery_items, db_info=db_info,
                           visit_stats=visit_stats)


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
            fn = _save_data_uri(prof_img_cropped, f"profile_{int(time.time())}.jpg")
            if fn:
                profile.profile_image_filename = fn
        elif prof_img_file and prof_img_file.filename:
            fn = save_uploaded_image(prof_img_file, 'profile')
            if fn:
                profile.profile_image_filename = fn

        og_cropped = request.form.get('og_cropped_data', '')
        og_file = request.files.get('og_image_file')
        if og_cropped and ',' in og_cropped:
            fn = _save_data_uri(og_cropped, f"og_{int(time.time())}.jpg")
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
        # EN experience
        en_companies = request.form.getlist('en_exp_company')
        en_periods   = request.form.getlist('en_exp_period')
        en_roles     = request.form.getlist('en_exp_role')
        en_bullets   = request.form.getlist('en_exp_bullets')
        experience_en = []
        for i, c in enumerate(en_companies):
            if c.strip():
                experience_en.append({'company': c.strip(),
                    'period': en_periods[i].strip() if i < len(en_periods) else '',
                    'role': en_roles[i].strip() if i < len(en_roles) else '',
                    'bullets': [b.strip() for b in en_bullets[i].split('\n') if b.strip()] if i < len(en_bullets) else []})
        profile.experience_en_json = json.dumps(experience_en, ensure_ascii=False)
        # EN education
        en_edu_schools  = request.form.getlist('en_edu_school')
        en_edu_majors   = request.form.getlist('en_edu_major')
        en_edu_degrees  = request.form.getlist('en_edu_degree')
        en_edu_periods  = request.form.getlist('en_edu_period')
        education_en = [{'school': s.strip(),
            'major': en_edu_majors[i].strip() if i < len(en_edu_majors) else '',
            'degree': en_edu_degrees[i].strip() if i < len(en_edu_degrees) else '',
            'period': en_edu_periods[i].strip() if i < len(en_edu_periods) else ''}
            for i, s in enumerate(en_edu_schools) if s.strip()]
        profile.education_en_json = json.dumps(education_en, ensure_ascii=False)
        # EN awards
        en_award_titles = request.form.getlist('en_award_title')
        en_award_orgs   = request.form.getlist('en_award_org')
        en_award_years  = request.form.getlist('en_award_year')
        awards_en = [{'title': t.strip(),
            'org': en_award_orgs[i].strip() if i < len(en_award_orgs) else '',
            'year': en_award_years[i].strip() if i < len(en_award_years) else ''}
            for i, t in enumerate(en_award_titles) if t.strip()]
        profile.awards_en_json = json.dumps(awards_en, ensure_ascii=False)
        # EN tools
        en_tool_names  = request.form.getlist('en_tool_name')
        en_tool_levels = request.form.getlist('en_tool_level')
        tools_en = [{'name': n.strip(), 'level': l}
            for n, l in zip(en_tool_names, en_tool_levels) if n.strip()]
        profile.tools_en_json = json.dumps(tools_en, ensure_ascii=False)

        # 이력서 PDF 업로드
        resume_file = request.files.get('resume_file')
        if resume_file and resume_file.filename:
            ext = resume_file.filename.rsplit('.', 1)[-1].lower() if '.' in resume_file.filename else ''
            if ext == 'pdf':
                filename = f"resume_{int(time.time())}.pdf"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                resume_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                profile.resume_filename = filename

        # 어학 성적
        lang_exams  = request.form.getlist('lang_exam')
        lang_scores = request.form.getlist('lang_score')
        lang_dates  = request.form.getlist('lang_date')
        language_scores = [
            {'exam': e.strip(), 'score': lang_scores[i].strip() if i < len(lang_scores) else '',
             'date': lang_dates[i].strip() if i < len(lang_dates) else ''}
            for i, e in enumerate(lang_exams) if e.strip()
        ]
        profile.language_scores_json = json.dumps(language_scores, ensure_ascii=False)

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
            order=int(request.form.get('order', 0)),
            detail_text=request.form.get('detail_text', ''),
            image_filename=img or '',
            links_json=_json.dumps(links, ensure_ascii=False),
            links_en_json=_json.dumps(links_en, ensure_ascii=False),
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
        en_labels = request.form.getlist('link_label_en')
        p.links_en_json = _json.dumps(
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


@app.route('/admin/project/<int:pid>/delete', methods=['POST'])
@login_required
def project_delete(pid):
    p = Project.query.get_or_404(pid)
    # 연결된 이미지 파일도 디스크에서 제거 (cascade는 DB 행만 삭제함)
    for img in p.images:
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], img.filename)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except OSError:
                pass
    db.session.delete(p)
    db.session.commit()
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
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], profile.profile_image_filename)
        if os.path.exists(fpath):
            os.remove(fpath)
        profile.profile_image_filename = ''
        db.session.commit()
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
    fn = _save_data_uri(cropped, f"gallery_{int(time.time())}.jpg")
    if fn:
        return fn
    return save_uploaded_image(request.files.get('image'), 'gallery')

@app.route('/admin/gallery/new', methods=['GET', 'POST'])
@login_required
def gallery_new():
    import json as _j
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
        item.title = request.form['title']
        item.title_en = request.form.get('title_en', '')
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
    p = Project.query.get_or_404(pid)
    cropped = request.form.get('cropped_data')
    filename = _save_data_uri(cropped, f"proj{pid}_{int(time.time())}.jpg")
    if not filename:
        filename = save_uploaded_image(request.files.get('image'), f"proj{pid}")
    if not filename:
        return json.dumps({'error': 'invalid file'}), 400, {'Content-Type': 'application/json'}
    has_any = ProjectImage.query.filter_by(project_id=pid).first() is not None
    img = ProjectImage(project_id=pid, filename=filename, is_main=not has_any)
    db.session.add(img)
    db.session.commit()
    return app.response_class(
        response=json.dumps({'id': img.id, 'is_main': img.is_main,
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


# ── Reorder ─────────────────────────────────────────────

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


@app.route('/admin/gallery/reorder', methods=['POST'])
@login_required
def gallery_reorder():
    import json as _json
    ids = (_json.loads(request.data) or {}).get('ids', [])
    for i, gid in enumerate(ids):
        g = db.session.get(GalleryItem, int(gid))
        if g:
            g.sort_order = i
    db.session.commit()
    return app.response_class(response=_json.dumps({'ok': True}), mimetype='application/json')


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


# ── YouTube API Proxy ────────────────────────────────────

@app.route('/api/youtube')
def youtube_info():
    import json as _json, urllib.request as _req, urllib.error as _err
    if _rate_limited(f"yt:{_client_ip()}"):
        return _json.dumps({'error': 'rate limited'}), 429, {'Content-Type': 'application/json'}
    video_id = request.args.get('v', '').strip()
    if not video_id:
        return _json.dumps({'error': 'no video id'}), 400, {'Content-Type': 'application/json'}
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        return _json.dumps({'error': 'invalid video id'}), 400, {'Content-Type': 'application/json'}
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


# ── YouTube Playlist API Proxy ───────────────────────────

@app.route('/api/youtube/playlist')
def youtube_playlist_info():
    import json as _json, urllib.request as _req, urllib.error as _err, re as _re
    if _rate_limited(f"yt:{_client_ip()}"):
        return _json.dumps({'error': 'rate limited'}), 429, {'Content-Type': 'application/json'}
    playlist_id = request.args.get('list', '').strip()
    if not playlist_id:
        return _json.dumps({'error': 'no playlist id'}), 400, {'Content-Type': 'application/json'}
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,64}', playlist_id):
        return _json.dumps({'error': 'invalid playlist id'}), 400, {'Content-Type': 'application/json'}
    api_key = os.environ.get('YOUTUBE_API_KEY', '')
    if not api_key:
        return _json.dumps({'error': 'YOUTUBE_API_KEY not set'}), 503, {'Content-Type': 'application/json'}

    def fetch(url):
        with _req.urlopen(url, timeout=8) as r:
            return _json.loads(r.read())

    def parse_duration(d):
        m = _re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d or '')
        if not m: return 0
        h, mn, s = (int(x or 0) for x in m.groups())
        return h * 3600 + mn * 60 + s

    try:
        items_data = fetch(
            'https://www.googleapis.com/youtube/v3/playlistItems'
            f'?part=contentDetails&maxResults=50&playlistId={playlist_id}&key={api_key}'
        )
        video_ids = [it['contentDetails']['videoId'] for it in items_data.get('items', [])]
        if not video_ids:
            return _json.dumps({'error': 'empty playlist'}), 404, {'Content-Type': 'application/json'}

        vdata = fetch(
            'https://www.googleapis.com/youtube/v3/videos'
            f'?part=snippet,statistics,contentDetails&id={",".join(video_ids)}&key={api_key}'
        )
        videos = []
        for v in vdata.get('items', []):
            dur = parse_duration(v.get('contentDetails', {}).get('duration', ''))
            views = int(v.get('statistics', {}).get('viewCount', 0) or 0)
            videos.append((dur, views, v))

        long_form = [(dur, views, v) for dur, views, v in videos if dur > 180]
        pool = long_form if long_form else videos
        pool.sort(key=lambda x: x[1], reverse=True)
        best = pool[0][2]

        snippet = best.get('snippet', {})
        stats   = best.get('statistics', {})
        thumb   = (snippet.get('thumbnails', {}).get('high') or
                   snippet.get('thumbnails', {}).get('medium') or {}).get('url', '')
        return app.response_class(
            response=_json.dumps({
                'videoUrl':    f"https://www.youtube.com/watch?v={best['id']}",
                'videoId':     best['id'],
                'title':       snippet.get('title', ''),
                'thumbnail':   thumb,
                'viewCount':   stats.get('viewCount', '0'),
                'likeCount':   stats.get('likeCount', '0'),
                'commentCount':stats.get('commentCount', '0'),
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
