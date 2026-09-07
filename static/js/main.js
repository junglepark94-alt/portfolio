// ── Hamburger Menu ───────────────────────────
(function () {
  const hamburger = document.getElementById('navHamburger');
  const mobileMenu = document.getElementById('navMobileMenu');
  if (!hamburger || !mobileMenu) return;

  function openMenu() {
    hamburger.classList.add('open');
    mobileMenu.classList.add('open');
    hamburger.setAttribute('aria-expanded', 'true');
    mobileMenu.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
  function closeMenu() {
    hamburger.classList.remove('open');
    mobileMenu.classList.remove('open');
    hamburger.setAttribute('aria-expanded', 'false');
    mobileMenu.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  hamburger.addEventListener('click', function () {
    hamburger.classList.contains('open') ? closeMenu() : openMenu();
  });
  mobileMenu.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', closeMenu);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeMenu();
  });
})();

// ── Scroll Reveal ────────────────────────────
const revealEls = document.querySelectorAll('.section, .project-card, .timeline-item, .contact-card');
revealEls.forEach(el => el.classList.add('reveal'));

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

revealEls.forEach(el => observer.observe(el));

// ── Project Detail Modal ─────────────────────
const modal = document.getElementById('projectModal');
if (modal) {
  const $ = id => document.getElementById(id);
  const modalBox = modal.querySelector('.modal-box');
  const modalTopbar = modal.querySelector('.modal-topbar');
  const modalMedia = modal.querySelector('.modal-media');
  const modalClose = $('modalClose');
  const pageLang = document.documentElement.lang === 'en' ? 'en' : 'ko';
  let i18n = {};
  try { i18n = JSON.parse($('modalI18n').textContent); } catch (e) {}
  const t = (key, fallback) => i18n[key] || fallback;
  const modalText = {
    loading: t('loading', pageLang === 'en' ? 'Loading…' : '로딩 중…'),
    playlist: t('playlist', pageLang === 'en' ? 'Playlist' : '재생목록'),
    views: t('views', pageLang === 'en' ? 'views' : '회'),
    play: t('play', pageLang === 'en' ? 'Play' : '재생'),
    external: t('open_external', pageLang === 'en' ? 'Watch on YouTube' : 'YouTube에서 보기'),
  };
  let activeProjectCard = null;
  let anchorSections = [];
  let clickedAnchorAt = 0;
  let titleObserver = null;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }
  function visibleCards() {
    return [...document.querySelectorAll('.project-card')].filter(c => c.style.display !== 'none');
  }
  function show(id, on) { $(id).hidden = !on; return on; }

  // 요약: 여러 줄이면 불릿 목록, 한 줄이면 문단
  function renderDesc(raw) {
    const lines = (raw || '').replace(/\r/g, '').split('\n').map(s => s.trim()).filter(Boolean);
    const el = $('modalDesc');
    if (lines.length > 1) {
      el.innerHTML = '<ul>' + lines.map(l => `<li>${esc(l.replace(/^[-•·]\s*/, ''))}</li>`).join('') + '</ul>';
    } else {
      el.innerHTML = lines.length ? `<p>${esc(lines[0].replace(/^[-•·]\s*/, ''))}</p>` : '';
    }
    el.hidden = !lines.length;
  }

  // 핵심 성과: "값 | 설명" 형식은 숫자 타일, 나머지는 불릿
  function renderKpi(raw) {
    const lines = (raw || '').replace(/\r/g, '').split('\n').map(s => s.trim()).filter(Boolean);
    const tiles = [], bullets = [];
    lines.forEach(line => {
      const m = line.match(/^(.+?)\s*[|｜]\s*(.+)$/);
      if (m) tiles.push([m[1], m[2]]); else bullets.push(line);
    });
    $('modalKpiGrid').innerHTML = tiles.map(([v, l]) =>
      `<div class="kpi-tile"><div class="kpi-value">${esc(v)}</div><div class="kpi-label">${esc(l)}</div></div>`
    ).join('');
    $('modalKpiList').innerHTML = bullets.map(b => `<li>${esc(b.replace(/^[-•·]\s*/, ''))}</li>`).join('');
    return lines.length > 0;
  }

  // 상세 설명: "## 소제목", "- 항목", 빈 줄/줄바꿈 → 문단
  function renderDetail(raw) {
    const lines = (raw || '').replace(/\r/g, '').split('\n');
    let html = '';
    let list = [];
    const flush = () => {
      if (list.length) {
        html += '<ul class="detail-list">' + list.map(i => `<li>${esc(i)}</li>`).join('') + '</ul>';
        list = [];
      }
    };
    lines.forEach(line => {
      const s = line.trim();
      if (!s) { flush(); return; }
      if (/^#{1,3}\s*/.test(s)) { flush(); html += `<h5 class="detail-sub">${esc(s.replace(/^#{1,3}\s*/, ''))}</h5>`; return; }
      if (/^[-•·]\s+/.test(s)) { list.push(s.replace(/^[-•·]\s+/, '')); return; }
      flush();
      html += `<p>${esc(s)}</p>`;
    });
    flush();
    $('modalDetail').innerHTML = html;
    return html.length > 0;
  }

  function buildAnchors() {
    const nav = $('modalAnchors');
    nav.innerHTML = '';
    // 본문 섹션(개요→성과→상세→자료) 다음에 미디어 섹션(영상) 순서로 정렬
    const sections = [
      ...modal.querySelectorAll('.modal-body [data-anchor]'),
      ...modal.querySelectorAll('.modal-media [data-anchor]'),
    ].filter(sec => !sec.hidden);
    sections.forEach(sec => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'modal-anchor';
      btn.textContent = sec.dataset.anchorLabel || '';
      btn.dataset.target = sec.id;
      btn.addEventListener('click', () => {
        sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setActiveAnchor(sec.id);
        clickedAnchorAt = Date.now();
      });
      nav.appendChild(btn);
    });
    anchorSections = sections;
    setActiveAnchor(sections[0] && sections[0].id);
  }
  // 스크롤 위치 기준으로 현재 섹션 표시 (상단바 아래 기준선에 가장 가까운 섹션)
  function syncActiveAnchor() {
    if (!anchorSections.length || Date.now() - clickedAnchorAt < 700) return;
    const boxTop = modalBox.getBoundingClientRect().top;
    const line = boxTop + modalTopbar.offsetHeight + 24;
    const twoColumn = !window.matchMedia('(max-width: 900px)').matches;
    const flow = anchorSections.filter(sec => !(twoColumn && sec.closest('.modal-media')));
    if (!flow.length) return;
    let current = flow[0];
    flow.forEach(sec => {
      if (sec.getBoundingClientRect().top <= line) current = sec;
    });
    const last = flow[flow.length - 1];
    if (modalBox.scrollTop + modalBox.clientHeight >= modalBox.scrollHeight - 4) current = last;
    setActiveAnchor(current.id);
  }
  let anchorSyncTimer = null;
  modalBox.addEventListener('scroll', () => {
    if (anchorSyncTimer) return;
    anchorSyncTimer = setTimeout(() => { anchorSyncTimer = null; syncActiveAnchor(); }, 60);
  }, { passive: true });
  function setActiveAnchor(id) {
    const nav = $('modalAnchors');
    nav.querySelectorAll('.modal-anchor').forEach(b => {
      const on = b.dataset.target === id;
      b.classList.toggle('active', on);
      if (on && nav.scrollWidth > nav.clientWidth) {
        const left = b.offsetLeft - (nav.clientWidth - b.offsetWidth) / 2;
        nav.scrollTo({ left: Math.max(0, left), behavior: 'smooth' });
      }
    });
  }

  function updateNav() {
    const cards = visibleCards();
    const idx = cards.indexOf(activeProjectCard);
    $('modalCounter').textContent = idx >= 0 ? `${idx + 1} / ${cards.length}` : '';
    const single = cards.length < 2;
    $('modalPrev').disabled = single;
    $('modalNext').disabled = single;
  }
  function openByOffset(delta) {
    const cards = visibleCards();
    const idx = cards.indexOf(activeProjectCard);
    if (idx < 0 || cards.length < 2) return;
    openModal(cards[(idx + delta + cards.length) % cards.length]);
  }

  function openModal(card) {
    activeProjectCard = card;
    const d = card.dataset;

    $('modalTitle').textContent = d.title || '';
    $('modalTopTitle').textContent = d.title || '';
    $('modalPeriod').textContent = d.period || '';
    $('modalCategory').textContent = d.category || '';
    $('modalEyebrowSep').hidden = !(d.category && d.period);
    renderDesc(d.desc);

    const hasRole = !!(d.myrole && d.myrole.trim());
    $('modalMyRole').textContent = hasRole ? d.myrole : '';
    show('modalMetaRow', hasRole);

    show('secResults', renderKpi(d.kpi));
    show('secDetail', renderDetail(d.detail));

    // 갤러리
    let images = [];
    try { images = JSON.parse(d.images || '[]').map(fn => `/static/uploads/${fn}`); } catch (e) {}
    if (show('modalGalleryWrap', images.length > 0)) initGallery(images, d.title || '');

    // 태그 + 링크 (유튜브는 영상 목록으로 분리)
    const tags = (d.tags || '').split(',').map(s => s.trim()).filter(Boolean);
    $('modalTags').innerHTML = tags.map(tag => `<span class="tag">${esc(tag)}</span>`).join('');
    let links = [];
    try { links = JSON.parse(d.links || '[]'); } catch (e) {}
    const plainLinks = links.filter(lk => lk && lk.url && !extractYtId(lk.url) && !extractPlaylistId(lk.url));
    $('modalLinks').innerHTML = plainLinks.map(lk =>
      `<a href="${esc(lk.url)}" class="link-chip" target="_blank" rel="noopener">${esc(lk.label || lk.url)}<span class="chip-arrow">↗</span></a>`
    ).join('');
    show('secResources', plainLinks.length > 0 || tags.length > 0);

    ytListEl.innerHTML = '';
    links.forEach(lk => {
      if (!lk || !lk.url) return;
      const vid = extractYtId(lk.url);
      const pid = !vid && extractPlaylistId(lk.url);
      if (vid) ytListEl.appendChild(createVideoItem(lk.label, lk.url, 'video', vid));
      else if (pid) ytListEl.appendChild(createVideoItem(lk.label, lk.url, 'playlist', pid));
    });
    show('secVideos', ytListEl.children.length > 0);

    buildAnchors();
    updateNav();

    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    modalBox.scrollTop = 0;
    if (modalMedia) modalMedia.scrollTop = 0;
    modalClose.focus();
  }

  function closeModal() {
    if (!modal.classList.contains('active')) return;
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    ytListEl.innerHTML = '';
    if (activeProjectCard) activeProjectCard.focus();
  }

  // 상단바 제목: 본문 제목이 화면 밖으로 나가면 표시
  titleObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => modalTopbar.classList.toggle('show-title', !entry.isIntersecting));
  }, { root: modalBox, threshold: 0 });
  titleObserver.observe($('modalTitle'));

  // ── 갤러리 ─────────────────────────────────
  let galleryIdx = 0;
  let galleryImgs = [];
  const galleryMainImg = $('modalGalleryImg');
  const thumbsEl = $('modalGalleryThumbs');
  const prevBtn = $('galleryPrev');
  const nextBtn = $('galleryNext');

  function initGallery(imgs, alt) {
    galleryImgs = imgs;
    galleryIdx = 0;
    setGallerySlide(0, alt);
    thumbsEl.innerHTML = '';
    if (imgs.length > 1) {
      imgs.forEach((src, i) => {
        const th = document.createElement('img');
        th.src = src; th.alt = ''; th.className = i === 0 ? 'active' : '';
        th.addEventListener('click', () => { galleryIdx = i; setGallerySlide(i, alt); });
        thumbsEl.appendChild(th);
      });
    }
    prevBtn.style.display = imgs.length > 1 ? '' : 'none';
    nextBtn.style.display = imgs.length > 1 ? '' : 'none';
  }

  function setGallerySlide(i, alt) {
    galleryMainImg.src = galleryImgs[i];
    galleryMainImg.alt = alt || '';
    thumbsEl.querySelectorAll('img').forEach((th, ti) => th.classList.toggle('active', ti === i));
  }

  prevBtn?.addEventListener('click', () => {
    galleryIdx = (galleryIdx - 1 + galleryImgs.length) % galleryImgs.length;
    setGallerySlide(galleryIdx);
  });
  nextBtn?.addEventListener('click', () => {
    galleryIdx = (galleryIdx + 1) % galleryImgs.length;
    setGallerySlide(galleryIdx);
  });

  // ── 영상 목록 (썸네일 클릭 시 인라인 재생) ────
  const ytListEl = $('modalYoutubeList');

  function extractYtId(url) {
    const m = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    return m ? m[1] : null;
  }
  function extractPlaylistId(url) {
    const m = url.match(/[?&]list=([a-zA-Z0-9_-]+)/);
    return m ? m[1] : null;
  }
  function fmtNum(n) {
    n = parseInt(n) || 0;
    if (pageLang === 'en') {
      if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
      if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
      return n.toLocaleString();
    }
    if (n >= 10000) return (n / 10000).toFixed(1) + '만';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return n.toLocaleString();
  }
  function createVideoItem(label, url, kind, id) {
    const item = document.createElement('div');
    item.className = 'video-item';
    const thumb = kind === 'video' ? `https://img.youtube.com/vi/${id}/mqdefault.jpg` : '';
    item.innerHTML =
      `<button type="button" class="video-thumb" aria-label="${esc(modalText.play)}">
         <img src="${thumb}" alt="" loading="lazy" />
         <span class="video-play">▶</span>
       </button>
       <div class="video-info">
         ${label ? `<div class="video-label">${esc(label)}</div>` : ''}
         <div class="video-title">${esc(kind === 'playlist' ? modalText.playlist : modalText.loading)}</div>
         <div class="video-stats"><span class="v-views"></span><span class="v-likes"></span></div>
         <a class="video-ext" href="${esc(url)}" target="_blank" rel="noopener">${esc(modalText.external)} ↗</a>
       </div>`;
    const endpoint = kind === 'video' ? `/api/youtube?v=${id}` : `/api/youtube/playlist?list=${id}`;
    fetch(endpoint)
      .then(r => r.json())
      .then(d => {
        if (d.error) { if (kind === 'video') item.querySelector('.video-title').textContent = ''; return; }
        if (d.thumbnail) item.querySelector('.video-thumb img').src = d.thumbnail;
        if (d.title) item.querySelector('.video-title').textContent = d.title;
        item.querySelector('.v-views').textContent = d.viewCount ? '▶ ' + fmtNum(d.viewCount) + ' ' + modalText.views : '';
        item.querySelector('.v-likes').textContent = d.likeCount ? '♥ ' + fmtNum(d.likeCount) : '';
      })
      .catch(() => {});
    item.querySelector('.video-thumb').addEventListener('click', () => {
      const src = kind === 'video'
        ? `https://www.youtube.com/embed/${id}?autoplay=1&rel=0`
        : `https://www.youtube.com/embed/videoseries?list=${id}&autoplay=1`;
      const wrap = document.createElement('div');
      wrap.className = 'video-embed';
      wrap.innerHTML = `<iframe src="${src}" title="${esc(label || '')}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>`;
      item.querySelector('.video-thumb').remove();
      item.insertBefore(wrap, item.firstChild);
      item.classList.add('playing');
    });
    return item;
  }

  modalClose.addEventListener('click', closeModal);
  $('modalPrev').addEventListener('click', () => openByOffset(-1));
  $('modalNext').addEventListener('click', () => openByOffset(1));
  modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', e => {
    if (!modal.classList.contains('active')) return;
    if (e.key === 'Escape') closeModal();
    if (e.target && /^(input|textarea|select)$/i.test(e.target.tagName)) return;
    if (e.key === 'ArrowLeft') openByOffset(-1);
    if (e.key === 'ArrowRight') openByOffset(1);
  });

  document.querySelectorAll('.project-card').forEach(card => {
    card.style.cursor = 'pointer';
    card.addEventListener('click', e => {
      if (e.target.closest('a')) return;
      openModal(card);
    });
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openModal(card);
      }
    });
  });
}

// ── Cover Flow ────────────────────────────────
(function () {
  const stage = document.getElementById('coverflowStage');
    if (!stage) return;

    const cards = Array.from(stage.querySelectorAll('.gallery-card'));
    const dotsWrap = document.getElementById('coverflowDots');
    const prevBtn = document.getElementById('cfPrev');
    const nextBtn = document.getElementById('cfNext');
    if (!cards.length) return;

    let activeIdx = 0;

    // Build dots
    const dots = cards.map((_, i) => {
      const btn = document.createElement('button');
      btn.className = 'cf-dot';
      const slideLabel = document.documentElement.lang === 'en' ? 'Slide' : '슬라이드';
      btn.setAttribute('aria-label', `${slideLabel} ${i + 1}`);
      btn.addEventListener('click', () => goTo(i));
      dotsWrap.appendChild(btn);
      return btn;
    });

    const SCALE   = [1,    0.78, 0.62, 0.50];
    const OPACITY = [1,    0.62, 0.36, 0.0 ];
    const TX      = [0,    250,  360,  450 ];
    const RY      = [0,    46,   56,   62  ];
    const ZI      = [10,   8,    6,    4   ];

    const titleDisplay = document.getElementById('cfTitleDisplay');

    function update() {
      cards.forEach((card, i) => {
        let off = i - activeIdx;
        // wrap offset for looping display
        if (off > cards.length / 2) off -= cards.length;
        if (off < -cards.length / 2) off += cards.length;
        const abs = Math.abs(off);
        const sign = off < 0 ? -1 : 1;

        if (abs >= SCALE.length) {
          card.style.opacity = '0';
          card.style.zIndex  = '1';
          card.style.pointerEvents = 'none';
          card.style.transform = `translateX(${sign * 520}px) scale(0.45) rotateY(${-sign * 65}deg)`;
          card.classList.remove('cf-active');
          return;
        }

        card.style.opacity = OPACITY[abs];
        card.style.zIndex  = ZI[abs];
        card.style.pointerEvents = 'auto';

        const tx = abs === 0 ? 0 : sign * TX[abs];
        const ry = abs === 0 ? 0 : -sign * RY[abs];
        card.style.transform = `translateX(${tx}px) scale(${SCALE[abs]}) rotateY(${ry}deg)`;
        card.classList.toggle('cf-active', abs === 0);
      });

      dots.forEach((d, i) => d.classList.toggle('active', i === activeIdx));
      if (prevBtn) prevBtn.disabled = false;
      if (nextBtn) nextBtn.disabled = false;
      if (titleDisplay) titleDisplay.textContent = cards[activeIdx].dataset.title || '';
    }

    function goTo(idx) {
      activeIdx = ((idx % cards.length) + cards.length) % cards.length;
      update();
    }

    // Card clicks — side: navigate, center: show title (already shown)
    cards.forEach((card, i) => {
      card.addEventListener('click', () => {
        if (i !== activeIdx) goTo(i);
      });
    });

    // Arrow buttons
    if (prevBtn) prevBtn.addEventListener('click', () => goTo(activeIdx - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => goTo(activeIdx + 1));

    // Keyboard (only when gallery is in view)
    document.addEventListener('keydown', e => {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      const sec = document.getElementById('gallery');
      if (!sec) return;
      const r = sec.getBoundingClientRect();
      if (r.top < window.innerHeight && r.bottom > 0) {
        e.preventDefault();
        goTo(activeIdx + (e.key === 'ArrowRight' ? 1 : -1));
      }
    });

    // Touch swipe
    let tx0 = 0;
    stage.addEventListener('touchstart', e => { tx0 = e.touches[0].clientX; }, { passive: true });
    stage.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].clientX - tx0;
      if (Math.abs(dx) > 40) goTo(activeIdx + (dx < 0 ? 1 : -1));
    }, { passive: true });

    // Mouse drag
    let mx0 = 0, dragging = false;
    stage.addEventListener('mousedown', e => { mx0 = e.clientX; dragging = true; });
    window.addEventListener('mouseup', e => {
      if (!dragging) return;
      dragging = false;
      const dx = e.clientX - mx0;
      if (Math.abs(dx) > 40) goTo(activeIdx + (dx < 0 ? 1 : -1));
    });

    update();
  })();

// ── Sortable rows (drag-handle based) ───────
function makeSortable(container, itemSelector) {
  let src = null;

  container.addEventListener('mousedown', function (e) {
    if (e.target.closest('.drag-handle')) {
      const row = e.target.closest(itemSelector);
      if (row) row.draggable = true;
    }
  });

  container.addEventListener('dragstart', function (e) {
    src = e.target.closest(itemSelector);
    if (!src) return;
    e.dataTransfer.effectAllowed = 'move';
    setTimeout(function () { src.classList.add('dragging'); }, 0);
  });

  container.addEventListener('dragover', function (e) {
    e.preventDefault();
    const over = e.target.closest(itemSelector);
    if (!over || over === src) return;
    const mid = over.getBoundingClientRect().top + over.offsetHeight / 2;
    if (e.clientY < mid) {
      container.insertBefore(src, over);
    } else {
      container.insertBefore(src, over.nextSibling);
    }
  });

  container.addEventListener('dragend', function () {
    if (src) { src.classList.remove('dragging'); src.draggable = false; src = null; }
    container.querySelectorAll(itemSelector).forEach(function (r) { r.draggable = false; });
  });
}

// ── Project Form: KPI Rows ───────────────────
const kpiRows = document.getElementById('kpiRows');
const addKpiBtn = document.getElementById('addKpiBtn');
if (kpiRows && addKpiBtn) {
  function wireKpiRemove(row) {
    row.querySelector('.kpi-remove-btn').addEventListener('click', function () {
      if (kpiRows.querySelectorAll('.kpi-row').length > 1) row.remove();
    });
  }
  kpiRows.querySelectorAll('.kpi-row').forEach(wireKpiRemove);
  addKpiBtn.addEventListener('click', function () {
    const row = document.createElement('div');
    row.className = 'kpi-row';
    row.innerHTML = '<span class="drag-handle" title="드래그하여 순서 변경">⠿</span>'
      + '<input type="text" name="kpi_item" placeholder="예: 작업 시간 70% 단축" />'
      + '<button type="button" class="kpi-remove-btn" aria-label="삭제">×</button>';
    kpiRows.appendChild(row);
    wireKpiRemove(row);
    row.querySelector('input').focus();
  });
  makeSortable(kpiRows, '.kpi-row');
}

// ── Project Form: Dynamic Links ──────────────
const linkRows = document.getElementById('linkRows');
const addLinkBtn = document.getElementById('addLinkBtn');
if (linkRows && addLinkBtn) {
  function wireRemoveBtn(row) {
    row.querySelector('.link-remove-btn').addEventListener('click', () => {
      if (linkRows.querySelectorAll('.link-row').length > 1) {
        row.remove();
      }
    });
  }
  linkRows.querySelectorAll('.link-row').forEach(wireRemoveBtn);
  addLinkBtn.addEventListener('click', () => {
    const row = document.createElement('div');
    row.className = 'link-row';
    row.innerHTML = `
      <span class="drag-handle" title="드래그하여 순서 변경">⠿</span>
      <input type="text" name="link_label" placeholder="링크 이름 (예: GitHub, 발표자료)" />
      <input type="url"  name="link_url"   placeholder="https://..." />
      <button type="button" class="link-remove-btn" aria-label="삭제">×</button>`;
    linkRows.appendChild(row);
    wireRemoveBtn(row);
    row.querySelector('input').focus();
  });
  makeSortable(linkRows, '.link-row');
}

// ── Project Category Filter ──────────────────
const filterBar = document.getElementById('projectFilterBar');
if (filterBar) {
  const projectCards = document.querySelectorAll('.project-card');
  const cats = [...new Set(
    [...projectCards].map(c => c.dataset.category).filter(c => c && c.trim())
  )];
  if (cats.length > 0) {
    filterBar.classList.add('visible');
    cats.forEach(cat => {
      const btn = document.createElement('button');
      btn.className = 'filter-btn';
      btn.dataset.cat = cat;
      btn.textContent = cat;
      filterBar.appendChild(btn);
    });
  }
  filterBar.addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    filterBar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const cat = btn.dataset.cat;
    projectCards.forEach(card => {
      card.style.display = (!cat || card.dataset.category === cat) ? '' : 'none';
    });
  });
}

// ── Form Language Switcher ───────────────────
(function () {
  document.querySelectorAll('.form-lang-switcher .flang-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const switcher = this.closest('.form-lang-switcher');
      switcher.querySelectorAll('.flang-btn').forEach(function (b) { b.classList.toggle('active', b === btn); });
      const form = this.closest('form') || document.querySelector('form');
      form.dataset.lang = this.dataset.lang;
    });
  });
})();

// ── EN KPI rows (project form) ───────────────
const kpiRowsEn = document.getElementById('kpiRowsEn');
const addKpiBtnEn = document.getElementById('addKpiBtnEn');
if (kpiRowsEn && addKpiBtnEn) {
  function wireKpiEnRemove(row) {
    row.querySelector('.kpi-remove-btn').addEventListener('click', function () {
      if (kpiRowsEn.querySelectorAll('.kpi-row').length > 1) row.remove();
    });
  }
  kpiRowsEn.querySelectorAll('.kpi-row').forEach(wireKpiEnRemove);
  addKpiBtnEn.addEventListener('click', function () {
    const row = document.createElement('div');
    row.className = 'kpi-row';
    row.innerHTML = '<input type="text" name="kpi_item_en" placeholder="e.g. 70% reduction in processing time" />'
      + '<button type="button" class="kpi-remove-btn" aria-label="삭제">×</button>';
    kpiRowsEn.appendChild(row);
    wireKpiEnRemove(row);
    row.querySelector('input').focus();
  });
}

// ── Active Nav Highlight ─────────────────────
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-links a');

let navTick = false;
window.addEventListener('scroll', () => {
  if (navTick) return;
  navTick = true;
  requestAnimationFrame(() => {
    let current = '';
    sections.forEach(sec => {
      if (window.scrollY >= sec.offsetTop - 120) current = sec.id;
    });
    navLinks.forEach(a => {
      a.style.color = a.getAttribute('href') === `#${current}` ? 'var(--accent)' : '';
    });
    navTick = false;
  });
}, { passive: true });
