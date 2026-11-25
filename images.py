"""업로드 이미지의 화면 크기용 축소본(WebP).

원본은 그대로 두고, 요청한 폭에 맞춘 WebP를 처음 한 번 만들어 업로드 폴더(볼륨) 안에 캐시한다.
카드 썸네일에 3MB짜리 원본을 그대로 내려보내지 않기 위한 것이다.
"""
import os
import threading

from flask import Blueprint, abort, current_app, send_from_directory, url_for
from PIL import Image, ImageOps

from models import GalleryItem, Profile, ProjectImage

# 카드·프로필(480), 고해상도 화면의 카드(960), 상세 모달의 큰 이미지(1600)
VARIANT_WIDTHS = (480, 960, 1600)
# 인코딩 설정을 바꾸면 이 값을 올린다. 예전 축소본은 다른 폴더에 남아 다시 쓰이지 않는다.
VARIANT_VERSION = 'v1'
WEBP_QUALITY = 80
_RESIZABLE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}  # GIF는 움직임을 잃지 않게 원본을 쓴다
_ONE_YEAR = 365 * 24 * 3600

bp = Blueprint('media', __name__)


def _ext(filename):
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def _variant_dir(width):
    return os.path.join(current_app.config['UPLOAD_FOLDER'], '_resized', VARIANT_VERSION, str(width))


def _variant_name(filename):
    return filename.rsplit('.', 1)[0] + '.webp'


def ensure_variant(filename, width):
    """축소본 파일 경로를 돌려준다. 없으면 만든다. 만들 수 없으면 None (호출하는 쪽이 원본을 쓴다)."""
    if width not in VARIANT_WIDTHS or os.path.basename(filename) != filename:
        return None
    if _ext(filename) not in _RESIZABLE_EXTENSIONS:
        return None
    source = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    folder = _variant_dir(width)
    target = os.path.join(folder, _variant_name(filename))
    if os.path.exists(target):
        return target
    if not os.path.isfile(source):
        return None
    try:
        with Image.open(source) as img:
            img = ImageOps.exif_transpose(img)  # 휴대폰 사진의 회전 정보 반영
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA' if 'A' in img.getbands() or 'transparency' in img.info else 'RGB')
            if img.width > width:  # 작은 이미지는 키우지 않고 WebP로만 바꾼다
                img.thumbnail((width, width * 4), Image.Resampling.LANCZOS)
            os.makedirs(folder, exist_ok=True)
            # 동시에 같은 축소본을 만드는 요청이 있어도 반쯤 쓴 파일을 내보내지 않도록 임시 파일 후 교체
            tmp = f'{target}.{threading.get_ident()}.tmp'
            img.save(tmp, 'WEBP', quality=WEBP_QUALITY, method=4)
        os.replace(tmp, target)
    except Exception as exc:  # 손상된 파일·너무 큰 이미지 등: 원본으로 대신한다
        print(f"[images] {filename}@{width}: {exc!r}")
        return None
    return target


def image_url(filename, width):
    """템플릿용: 업로드 이미지의 축소본 URL. 축소할 수 없는 형식이면 원본 URL."""
    if not filename:
        return ''
    if width in VARIANT_WIDTHS and _ext(filename) in _RESIZABLE_EXTENSIONS:
        return url_for('media.resized', width=width, filename=filename)
    return url_for('static', filename='uploads/' + filename)


def image_srcset(filename, widths=(480, 960)):
    if _ext(filename or '') not in _RESIZABLE_EXTENSIONS:
        return ''
    return ', '.join(f'{image_url(filename, w)} {w}w' for w in widths)


@bp.route('/media/<int:width>/<filename>')
def resized(width, filename):
    if width not in VARIANT_WIDTHS:
        abort(404)
    path = ensure_variant(filename, width)
    if path is None:
        # 축소할 수 없으면 원본을 그대로 보낸다 (없으면 404)
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, max_age=_ONE_YEAR)
    # 서버의 mimetypes 설정에 webp가 없을 수 있어(예: Windows) 형식을 직접 지정한다
    response = send_from_directory(os.path.dirname(path), os.path.basename(path),
                                   mimetype='image/webp', max_age=_ONE_YEAR)
    # 업로드 파일명은 고유하고, 같은 이름의 축소본은 내용이 바뀌지 않는다
    response.headers['Cache-Control'] = f'public, max-age={_ONE_YEAR}, immutable'
    return response


def referenced_upload_images():
    """공개 페이지에서 쓰는 업로드 이미지 파일명 목록."""
    names = {img.filename for img in ProjectImage.query.all()}
    names |= {g.image_filename for g in GalleryItem.query.all()}
    names |= {p.profile_image_filename for p in Profile.query.all()}
    return sorted(n for n in names if n)


def warm_variants():
    """아직 없는 축소본을 미리 만든다. 첫 방문자가 생성 시간을 기다리지 않게 하려는 것. 앱 컨텍스트 안에서 호출."""
    made = 0
    for filename in referenced_upload_images():
        for width in VARIANT_WIDTHS:
            target = os.path.join(_variant_dir(width), _variant_name(filename))
            if not os.path.exists(target) and ensure_variant(filename, width):
                made += 1
    if made:
        print(f"[images] warmed {made} resized variants")
    return made


def remove_variants(filename):
    """원본을 지울 때 그 축소본들도 함께 지운다."""
    if not filename or os.path.basename(filename) != filename:
        return
    root = os.path.join(current_app.config['UPLOAD_FOLDER'], '_resized')
    if not os.path.isdir(root):
        return
    name = _variant_name(filename)
    for version in os.listdir(root):
        for width in os.listdir(os.path.join(root, version)):
            try:
                os.remove(os.path.join(root, version, width, name))
            except OSError:
                pass
