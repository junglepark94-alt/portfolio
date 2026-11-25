"""YouTube Data API 프록시 (API 키를 숨기고 응답을 캐시한다)."""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

from flask import Blueprint, jsonify, request

from ratelimit import _client_ip, _rate_limited

bp = Blueprint('youtube', __name__)

# 조회수·제목은 몇 분 늦어도 괜찮으므로 응답을 잠시 캐시해 API 쿼터(하루 10,000)를 아낀다.
# 방문자가 같은 프로젝트 모달을 열 때마다 YouTube를 다시 부르지 않는다.
_YT_CACHE_TTL = 30 * 60
_YT_CACHE_MAX = 500
_YT_CACHE_LOCK = threading.Lock()
_YT_CACHE = {}  # key -> (expires_at, status, body)


def _json_response(body, status=200):
    return jsonify(body), status


def _yt_cache_get(key):
    now = time.time()
    with _YT_CACHE_LOCK:
        hit = _YT_CACHE.get(key)
        if hit and hit[0] > now:
            return hit[1], hit[2]
        _YT_CACHE.pop(key, None)
    return None


def _yt_cache_put(key, status, body):
    """정상 응답과 '없음(404)'만 캐시한다. 일시적인 오류는 다음 요청에서 다시 시도한다."""
    if status not in (200, 404):
        return
    now = time.time()
    with _YT_CACHE_LOCK:
        if len(_YT_CACHE) >= _YT_CACHE_MAX:
            for k in [k for k, v in _YT_CACHE.items() if v[0] <= now]:
                _YT_CACHE.pop(k, None)
            if len(_YT_CACHE) >= _YT_CACHE_MAX:
                _YT_CACHE.pop(min(_YT_CACHE, key=lambda k: _YT_CACHE[k][0]), None)
        _YT_CACHE[key] = (now + _YT_CACHE_TTL, status, body)


def _yt_get_json(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def _yt_thumbnail(snippet):
    thumbs = snippet.get('thumbnails', {})
    return (thumbs.get('high') or thumbs.get('medium') or {}).get('url', '')


def _yt_proxy(cache_key, fetch):
    """캐시 → 레이트리밋 → API 키 확인 → fetch(api_key) 순으로 처리한다. fetch는 (status, body)를 돌려준다."""
    cached = _yt_cache_get(cache_key)
    if cached:
        return _json_response(cached[1], cached[0])
    if _rate_limited(f"yt:{_client_ip()}"):
        return _json_response({'error': 'rate limited'}, 429)
    api_key = os.environ.get('YOUTUBE_API_KEY', '')
    if not api_key:
        return _json_response({'error': 'YOUTUBE_API_KEY not set'}, 503)
    try:
        status, body = fetch(api_key)
    except urllib.error.HTTPError as e:
        status, body = 502, {'error': f'youtube api {e.code}'}
    except Exception as e:
        print(f"[youtube] {cache_key}: {e!r}")
        status, body = 500, {'error': 'youtube fetch failed'}
    _yt_cache_put(cache_key, status, body)
    return _json_response(body, status)


def _parse_iso_duration(d):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d or '')
    if not m:
        return 0
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


@bp.route('/api/youtube')
def youtube_info():
    video_id = request.args.get('v', '').strip()
    if not video_id:
        return _json_response({'error': 'no video id'}, 400)
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        return _json_response({'error': 'invalid video id'}, 400)

    def fetch(api_key):
        data = _yt_get_json(
            'https://www.googleapis.com/youtube/v3/videos'
            f'?part=snippet,statistics&id={video_id}&key={api_key}', timeout=6)
        items = data.get('items', [])
        if not items:
            return 404, {'error': 'not found'}
        snippet = items[0].get('snippet', {})
        stats = items[0].get('statistics', {})
        return 200, {
            'title':        snippet.get('title', ''),
            'thumbnail':    _yt_thumbnail(snippet),
            'viewCount':    stats.get('viewCount', '0'),
            'likeCount':    stats.get('likeCount', '0'),
            'commentCount': stats.get('commentCount', '0'),
        }

    return _yt_proxy(f'v:{video_id}', fetch)


@bp.route('/api/youtube/playlist')
def youtube_playlist_info():
    playlist_id = request.args.get('list', '').strip()
    if not playlist_id:
        return _json_response({'error': 'no playlist id'}, 400)
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,64}', playlist_id):
        return _json_response({'error': 'invalid playlist id'}, 400)

    def fetch(api_key):
        items_data = _yt_get_json(
            'https://www.googleapis.com/youtube/v3/playlistItems'
            f'?part=contentDetails&maxResults=50&playlistId={playlist_id}&key={api_key}', timeout=8)
        video_ids = [it['contentDetails']['videoId'] for it in items_data.get('items', [])]
        if not video_ids:
            return 404, {'error': 'empty playlist'}
        vdata = _yt_get_json(
            'https://www.googleapis.com/youtube/v3/videos'
            f'?part=snippet,statistics,contentDetails&id={",".join(video_ids)}&key={api_key}', timeout=8)
        videos = []
        for v in vdata.get('items', []):
            dur = _parse_iso_duration(v.get('contentDetails', {}).get('duration', ''))
            views = int(v.get('statistics', {}).get('viewCount', 0) or 0)
            videos.append((dur, views, v))
        if not videos:
            return 404, {'error': 'empty playlist'}
        long_form = [x for x in videos if x[0] > 180]
        pool = long_form or videos
        pool.sort(key=lambda x: x[1], reverse=True)
        best = pool[0][2]
        snippet = best.get('snippet', {})
        stats = best.get('statistics', {})
        return 200, {
            'videoUrl':     f"https://www.youtube.com/watch?v={best['id']}",
            'videoId':      best['id'],
            'title':        snippet.get('title', ''),
            'thumbnail':    _yt_thumbnail(snippet),
            'viewCount':    stats.get('viewCount', '0'),
            'likeCount':    stats.get('likeCount', '0'),
            'commentCount': stats.get('commentCount', '0'),
        }

    return _yt_proxy(f'list:{playlist_id}', fetch)
