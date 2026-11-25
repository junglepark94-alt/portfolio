"""기준 문안(JSON) 동기화, 표기 정리, 썸네일 교체, TikTok 단축링크 풀기."""
import json
import os
import re
import threading
import urllib.request

from flask import current_app

from images import warm_variants
from models import ContentSync, Profile, Project, ProjectImage, _utcnow, db
from uploads import _fetch_external_image, _fetch_youtube_thumbnail

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

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
        # 복수형을 먼저 바꿔야 단수형 규칙이 'Awards'에 s를 하나 더 붙이지 않는다
        ('Social I Awards', 'Social i Awards'),
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
    """최초 1회 동기화: 히어로 기준 문안 + 프로필/기간 표기 정리 + 프로젝트 기준 문안 적용."""
    _apply_profile_hero_copy()
    normalize_profile_and_periods()
    _apply_project_copy_overrides()
    db.session.commit()


def _load_canonical_application():
    """data/hyundai_application_2026.json. 파일이 없거나 깨졌으면 빈 dict."""
    content_path = os.path.join(DATA_DIR, 'hyundai_application_2026.json')
    try:
        with open(content_path, encoding='utf-8') as content_file:
            return json.load(content_file)
    except (OSError, ValueError):
        return {}


def _apply_profile_hero_copy():
    """히어로 이름·직무·소개 문구를 기준 문안으로 덮어쓴다. 최초 동기화(seed)에서만 호출된다."""
    canonical = _load_canonical_application()
    site_copy = canonical.get('site_copy', {})
    profile = db.session.get(Profile, 1)
    if not profile:
        return
    profile.name_en = canonical.get('identity', {}).get('name_en', 'Jonggeol Park')
    profile.role = site_copy.get('hero_role_ko', profile.role)
    profile.role_en = site_copy.get('hero_role_en', profile.role_en)
    profile.tagline = site_copy.get('hero_tagline_ko', profile.tagline)
    profile.tagline_en = site_copy.get('hero_tagline_en', profile.tagline_en)


def normalize_profile_and_periods():
    """오탈자·기간 표기·영문 용어만 정리한다 (관리자가 쓴 문안의 내용은 바꾸지 않는다)."""
    site_copy = _load_canonical_application().get('site_copy', {})
    profile = db.session.get(Profile, 1)
    if profile:
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


_TIKTOK_SHORT_RE = re.compile(r'https?://(?:vt|vm)\.tiktok\.com/[A-Za-z0-9]+/?|https?://(?:www\.)?tiktok\.com/t/[A-Za-z0-9]+/?')
_TIKTOK_VIDEO_RE = re.compile(r'https://(?:www\.|m\.)?tiktok\.com/(@[\w.-]+)/video/(\d+)')


def _expand_tiktok_short_url(url):
    """vt.tiktok.com 같은 단축 링크를 tiktok.com/@계정/video/ID로 푼다. 실패하면 원래 값을 돌려준다."""
    if not url or not _TIKTOK_SHORT_RE.fullmatch(url.strip()):
        return url
    try:
        req = urllib.request.Request(url.strip(), headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            final = resp.geturl()
    except Exception as exc:
        print(f"[tiktok-expand] {url}: {exc!r}")
        return url
    m = _TIKTOK_VIDEO_RE.match(final)
    return f'https://www.tiktok.com/{m.group(1)}/video/{m.group(2)}' if m else url


def _expand_short_links_json(raw):
    """링크 JSON 목록의 TikTok 단축 링크만 풀어서 돌려준다. 바뀐 게 없으면 입력 그대로."""
    try:
        links = json.loads(raw or '[]')
    except (TypeError, ValueError):
        return raw
    if not isinstance(links, list):
        return raw
    changed = False
    for link in links:
        if isinstance(link, dict) and link.get('url'):
            expanded = _expand_tiktok_short_url(link['url'])
            if expanded != link['url']:
                link['url'] = expanded
                changed = True
    return json.dumps(links, ensure_ascii=False) if changed else raw


def expand_short_video_links():
    """저장된 TikTok 단축 링크를 매 시작 시 정식 주소로 바꾼다. 풀린 뒤에는 대상이 남지 않아 반복 실행해도 안전하다."""
    for project in Project.query.all():
        for attr in ('links_json', 'links_en_json'):
            raw = getattr(project, attr)
            if raw and ('tiktok.com/' in raw):
                setattr(project, attr, _expand_short_links_json(raw))
    db.session.commit()


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
    path = os.path.join(DATA_DIR, 'site_projects.json')
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
    marker.applied_at = _utcnow()
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
    """normalize_public_content()를 CONTENT_SEED_VERSION당 한 번만 실행. 실행했으면 True.

    워커 두 개가 동시에 부팅하며 같은 마커를 넣으려 하면 _set_marker가 실패하고, 먼저 성공한 쪽을 그대로 둔다.
    """
    if _marker_version('seed_version') >= CONTENT_SEED_VERSION:
        return False
    normalize_public_content()
    return _set_marker('seed_version', CONTENT_SEED_VERSION)


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


def run_boot_network_tasks():
    """부팅 후 백그라운드 작업 (썸네일 내려받기, TikTok 단축링크 풀기, 이미지 축소본 미리 만들기). 앱 컨텍스트 안에서 호출."""
    try:
        apply_youtube_thumbnail_swaps()
    except Exception as exc:
        db.session.rollback()
        print(f"[thumbnail-swap] skipped: {exc!r}")
    try:
        expand_short_video_links()
    except Exception as exc:
        db.session.rollback()
        print(f"[tiktok-expand] skipped: {exc!r}")
    try:
        # 썸네일 교체가 끝난 뒤에 해야 새로 받은 썸네일의 축소본까지 만든다
        warm_variants()
    except Exception as exc:
        db.session.rollback()
        print(f"[images] warm-up skipped: {exc!r}")


def start_boot_network_tasks():
    """run_boot_network_tasks()를 백그라운드 스레드에서 실행한다.

    요청 하나에 최대 6~10초씩 걸리므로 부팅 중에 돌리면 헬스체크(30초)를 넘겨 배포가 실패할 수 있다.
    """
    flask_app = current_app._get_current_object()

    def _worker():
        with flask_app.app_context():
            try:
                run_boot_network_tasks()
            finally:
                db.session.remove()

    thread = threading.Thread(target=_worker, name='boot-network-tasks', daemon=True)
    thread.start()
    return thread
