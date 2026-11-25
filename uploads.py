"""업로드 파일 저장·검증·정리와 허용 호스트에서의 이미지 내려받기."""
import base64
import hashlib
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from flask import current_app

from models import GalleryItem, Profile, ProjectImage

def uploads_on_persistent_volume(upload_folder=None):
    """업로드 폴더가 Railway 볼륨 안에 있는지. 볼륨이 붙으면 Railway가 RAILWAY_VOLUME_MOUNT_PATH를 넣는다.

    볼륨 밖이면 컨테이너 파일시스템이라 재배포 때 업로드 파일이 모두 사라진다.
    """
    mount = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '').strip()
    if not mount:
        return False
    folder = os.path.abspath(upload_folder or current_app.config['UPLOAD_FOLDER'])
    mount = os.path.abspath(mount)
    try:
        return os.path.commonpath([folder, mount]) == mount
    except ValueError:  # 다른 드라이브(Windows)
        return False

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


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


def _unique_upload_name(prefix, ext):
    """같은 초에 여러 장을 올려도 겹치지 않는 업로드 파일명.

    업로드 파일은 immutable로 캐시되므로 같은 이름을 다시 쓰면 안 된다.
    """
    return f"{prefix}_{int(time.time())}_{secrets.token_hex(4)}.{ext}"


def _remove_upload_if_unused(filename):
    """어떤 행도 더 이상 가리키지 않을 때만 업로드 파일을 지운다.

    yt_/ext_ 썸네일은 같은 영상·URL을 쓰는 프로젝트끼리 파일 하나를 공유하므로,
    행을 지운 뒤(커밋 후) 호출해야 남은 참조만 센다.
    """
    if not filename:
        return False
    if os.path.basename(filename) != filename:  # 업로드 폴더 밖은 절대 건드리지 않는다
        return False
    in_use = (ProjectImage.query.filter_by(filename=filename).count()
              + GalleryItem.query.filter_by(image_filename=filename).count()
              + Profile.query.filter_by(profile_image_filename=filename).count()
              + Profile.query.filter_by(resume_filename=filename).count()
              + Profile.query.filter(Profile.og_image_url.like(f'%/uploads/{filename}')).count())
    if in_use:
        return False
    fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    try:
        os.remove(fpath)
    except OSError:
        return False
    return True


def _upload_name_from_url(url):
    """'/static/uploads/<파일명>'을 가리키는 URL이면 파일명을, 외부 URL이면 ''를 돌려준다."""
    path = urlparse(url or '').path
    marker = '/static/uploads/'
    if marker not in path:
        return ''
    name = path.rsplit(marker, 1)[1]
    return name if name and os.path.basename(name) == name else ''


def save_uploaded_pdf(file, prefix='resume'):
    """PDF 업로드 저장. 확장자와 매직 바이트(%PDF-)가 모두 맞을 때만 저장하고 파일명을 돌려준다."""
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext != 'pdf':
        return None
    head = file.stream.read(5)
    file.stream.seek(0)
    if head != b'%PDF-':
        return None
    filename = _unique_upload_name(prefix, 'pdf')
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
    return filename


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
    filename = _unique_upload_name(prefix, ext)
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
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
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    with open(os.path.join(current_app.config['UPLOAD_FOLDER'], filename), 'wb') as f:
        f.write(raw)
    return filename


_YT_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')

# 외부 이미지는 이 호스트에서만 받는다 (유튜브 썸네일, tvN 공식 프로그램 이미지)
_ALLOWED_IMAGE_HOSTS = {'img.youtube.com', 'i.ytimg.com', 'poc-cf-image.cjenm.com'}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _is_allowed_image_url(url):
    parts = urlparse(url or '')
    return parts.scheme == 'https' and parts.hostname in _ALLOWED_IMAGE_HOSTS


class _AllowedHostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """리다이렉트도 허용 호스트(https)로 가는 것만 따라간다. 처음 URL만 검사하면 리다이렉트로 우회된다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_allowed_image_url(newurl):
            raise urllib.error.HTTPError(newurl, code, 'redirect to disallowed host', headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_IMAGE_OPENER = urllib.request.build_opener(_AllowedHostRedirectHandler)


def _open_image_url(url, timeout):
    return _IMAGE_OPENER.open(url, timeout=timeout)


def _download_image(url, filename):
    """허용 호스트의 이미지를 uploads에 저장. 성공 시 filename, 실패 시 None."""
    if not _is_allowed_image_url(url):
        return None
    folder = current_app.config['UPLOAD_FOLDER']
    target = os.path.join(folder, filename)
    if os.path.exists(target) and os.path.getsize(target) > 8000:
        return filename
    try:
        with _open_image_url(url, timeout=10) as resp:
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
