"""DB 모델과 여러 모듈이 같이 쓰는 날짜·JSON 헬퍼."""
import json
from datetime import datetime, timedelta, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

KST = timezone(timedelta(hours=9))

def _today_kst():
    return datetime.now(KST).strftime('%Y-%m-%d')


def _utcnow():
    """기존 컬럼과 같은 naive UTC 시각 (datetime.utcnow()는 deprecated)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_list(raw):
    """JSON 문자열 컬럼을 목록으로 읽는다. 비었거나 깨졌으면 빈 목록."""
    try:
        return json.loads(raw or '[]')
    except (TypeError, ValueError):
        return []


db = SQLAlchemy()

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
    created_at = db.Column(db.DateTime, default=_utcnow)
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
    is_hidden = db.Column(db.Boolean, default=False)  # True면 공개 페이지에서 제외 (관리자에서만 보임)
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
        return _json_list(self.links_json)

    @property
    def links_en(self):
        return _json_list(self.links_en_json)

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
    created_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def links(self):
        return _json_list(self.links_json)


class DailyVisit(db.Model):
    """일별 방문수 집계 (KST 기준, 세션당 하루 1회)"""
    __tablename__ = 'daily_visit'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), unique=True, index=True, nullable=False)  # YYYY-MM-DD
    count = db.Column(db.Integer, default=0)


FUNNEL_STAGES = ('visit', 'projects_view', 'project_detail', 'convert')
TRACKABLE_STAGES = ('projects_view', 'project_detail', 'convert')
CONVERT_KINDS = ('resume', 'email', 'phone', 'linkedin', 'github', 'blog', 'remember')
VISIT_EVENT_RETENTION_DAYS = 180


class VisitEvent(db.Model):
    """퍼널 단계별 익명 이벤트. 세션당 하루 1회 (stage, project_id, detail) 조합 1회."""
    __tablename__ = 'visit_event'
    id = db.Column(db.Integer, primary_key=True)
    session_key = db.Column(db.String(16), index=True, nullable=False)
    stage = db.Column(db.String(24), index=True, nullable=False)
    project_id = db.Column(db.Integer, default=0, nullable=False)
    detail = db.Column(db.String(32), default='', nullable=False)
    date = db.Column(db.String(10), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    # 유입 경로. visit 이벤트에만 채운다: ?src= 파라미터 > Referer 호스트 > '' (직접 유입)
    source = db.Column(db.String(40), default='', nullable=False)
    __table_args__ = (
        db.UniqueConstraint('session_key', 'stage', 'project_id', 'detail', 'date',
                            name='uq_visit_event_session_stage'),
    )


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
    phone = db.Column(db.String(40), default='')
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
        return _json_list(self.language_scores_json)

    @property
    def skill_list(self):
        return [s.strip() for s in (self.skills or '').split(',') if s.strip()]

    @property
    def skills_with_level(self):
        return _json_list(self.skills_json)

    @property
    def tools(self):
        return _json_list(self.tools_json)

    @property
    def tools_en(self):
        return _json_list(self.tools_en_json)

    @property
    def experience(self):
        return _json_list(self.experience_json)

    @property
    def experience_en(self):
        return _json_list(self.experience_en_json)

    @property
    def education(self):
        return _json_list(self.education_json)

    @property
    def education_en(self):
        return _json_list(self.education_en_json)

    @property
    def awards(self):
        return _json_list(self.awards_json)

    @property
    def awards_en(self):
        return _json_list(self.awards_en_json)



class ContentSync(db.Model):
    """기준 문안(JSON) 동기화가 어느 버전까지 적용됐는지 기록. 이후에는 관리자 수정이 최신이다."""
    __tablename__ = 'content_sync'
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(120), default='')
    applied_at = db.Column(db.DateTime, default=_utcnow)
