"""간단한 인메모리 레이트리밋 (YouTube 프록시 쿼터·로그인 무차별 대입 방지)."""
import threading
import time

from flask import request

# ── 간단한 인메모리 레이트리밋 (YouTube 프록시 쿼터 어뷰징 방지) ──
# gunicorn 워커마다 독립적이므로 분산 환경에서는 워커 수만큼 한도가 곱해짐.
# 외부 의존성 없이 캐주얼한 남용을 막는 수준의 방어임.
_RATE_LOCK = threading.Lock()
_RATE_HITS = {}  # client_ip -> [timestamps]


def _client_ip():
    # ProxyFix가 프록시가 붙인 값으로 remote_addr를 채운다. X-Forwarded-For를 직접 읽지 않는다.
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
