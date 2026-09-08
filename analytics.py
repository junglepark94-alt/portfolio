"""어드민 퍼널 대시보드 집계.

DB와 Flask에 의존하지 않는 순수 함수만 둔다. app.py가 이벤트 튜플을 넘긴다.
"""

FUNNEL_LABELS = [
    ('visit', '방문'),
    ('projects_view', '프로젝트 섹션 도달'),
    ('project_detail', '프로젝트 상세 열람'),
    ('convert', '전환 (이력서·연락)'),
]

CONVERT_LABELS = {
    'resume': '이력서 다운로드',
    'email': '이메일',
    'linkedin': '링크드인',
    'github': '깃허브',
    'blog': '블로그',
    'remember': '리멤버',
}


def _pct(part, whole):
    return round(part / whole * 100, 1) if whole else 0.0


def build_funnel_stats(events, project_titles, top_n=8):
    """이벤트 튜플에서 퍼널·전환 내역·프로젝트 랭킹을 만든다.

    단계 값은 stage별 단순 카운트가 아니라 '그 단계 이상 도달한 세션 수'다.
    단순 카운트는 projects_view가 유실된 세션 때문에 3단계가 2단계보다
    커지는 역전을 만들 수 있다. 누적 정의는 단조 감소를 보장한다.
    """
    ranks = {stage: i + 1 for i, (stage, _) in enumerate(FUNNEL_LABELS)}
    best = {}
    converts = {}
    projects = {}

    for session_key, stage, project_id, detail in events:
        rank = ranks.get(stage)
        if rank is None:
            continue
        if rank > best.get(session_key, 0):
            best[session_key] = rank
        if stage == 'convert' and detail:
            converts.setdefault(detail, set()).add(session_key)
        if stage == 'project_detail' and project_id:
            projects.setdefault(project_id, set()).add(session_key)

    steps = []
    previous = None
    for i, (stage, label) in enumerate(FUNNEL_LABELS, start=1):
        count = sum(1 for rank in best.values() if rank >= i)
        steps.append({
            'stage': stage,
            'label': label,
            'count': count,
            'width': 0.0,
            'rate': None if previous is None else _pct(count, previous),
        })
        previous = count

    top = steps[0]['count']
    for step in steps:
        step['width'] = _pct(step['count'], top)

    conversions = sorted(
        [{'kind': kind, 'label': CONVERT_LABELS.get(kind, kind), 'count': len(keys)}
         for kind, keys in converts.items()],
        key=lambda row: (-row['count'], row['kind']),
    )

    ranking = sorted(
        [{'project_id': pid,
          'title': project_titles.get(pid) or '삭제됨 (#%d)' % pid,
          'count': len(keys)}
         for pid, keys in projects.items()],
        key=lambda row: (-row['count'], row['project_id']),
    )[:top_n]

    return {
        'steps': steps,
        'overall': _pct(steps[-1]['count'], top),
        'conversions': conversions,
        'ranking': ranking,
        'sessions': len(best),
    }
