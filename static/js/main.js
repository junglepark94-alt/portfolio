// ── Hero Canvas Mesh Gradient ────────────────
(function () {
  const canvas = document.getElementById('heroCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const hero = canvas.parentElement;

  let W, H;
  function resize() {
    W = canvas.width  = hero.offsetWidth;
    H = canvas.height = hero.offsetHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  // 마우스 (0~1 비율)
  let mxT = 0.5, myT = 0.35, mxC = 0.5, myC = 0.35;
  document.addEventListener('mousemove', function (e) {
    const r = hero.getBoundingClientRect();
    mxT = Math.max(0, Math.min(1, (e.clientX - r.left) / W));
    myT = Math.max(0, Math.min(1, (e.clientY - r.top)  / H));
  });

  // 색상 포인트 정의
  // x, y: 기준 위치(비율), ax/ay: 진폭(비율), sp: 속도, ph: 위상
  // r,g,b: 색상, a: 최대 불투명도, rad: 반지름 비율
  var pts = [
    { x:.82, y:.08, ax:.12, ay:.10, sp:.00028, ph:0.0, r:210,g:150,b:80,  a:.32, rad:.58 },
    { x:.65, y:.75, ax:.10, ay:.14, sp:.00035, ph:1.8, r:220,g:170,b:100, a:.22, rad:.48 },
    { x:.08, y:.82, ax:.14, ay:.10, sp:.00022, ph:3.2, r:90, g:130,b:180, a:.22, rad:.55 },
    { x:.18, y:.10, ax:.08, ay:.13, sp:.00030, ph:2.0, r:100,g:145,b:200, a:.16, rad:.44 },
    { x:.45, y:.50, ax:.09, ay:.08, sp:.00042, ph:0.9, r:230,g:185,b:120, a:.14, rad:.40 },
    { x:.30, y:.60, ax:.11, ay:.09, sp:.00018, ph:4.1, r:90, g:130,b:180, a:.12, rad:.38 },
  ];

  function draw(ts) {
    // 마우스 부드럽게 따라오기
    mxC += (mxT - mxC) * 0.04;
    myC += (myT - myC) * 0.04;

    // 베이스
    ctx.fillStyle = '#f4f1ed';
    ctx.fillRect(0, 0, W, H);

    pts.forEach(function (p, i) {
      // 사인파로 위치 계산
      var px = (p.x + Math.sin(ts * p.sp + p.ph)         * p.ax) * W;
      var py = (p.y + Math.cos(ts * p.sp * 0.73 + p.ph)  * p.ay) * H;

      // 마우스 인력 (포인트마다 강도 다르게)
      var mf = (i % 2 === 0) ? 0.10 : 0.06;
      px += (mxC - 0.5) * W * mf;
      py += (myC - 0.35) * H * mf;

      var rad = p.rad * Math.max(W, H);
      var g = ctx.createRadialGradient(px, py, 0, px, py, rad);
      g.addColorStop(0,    'rgba('+p.r+','+p.g+','+p.b+','+p.a+')');
      g.addColorStop(0.45, 'rgba('+p.r+','+p.g+','+p.b+','+(p.a*0.28)+')');
      g.addColorStop(1,    'rgba('+p.r+','+p.g+','+p.b+',0)');

      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    });

    // 마우스 추적 포인트 — 커서 근처 amber 빛
    var mx = mxC * W, my = myC * H;
    var mg = ctx.createRadialGradient(mx, my, 0, mx, my, Math.max(W,H) * 0.28);
    mg.addColorStop(0,   'rgba(200,135,58,0.18)');
    mg.addColorStop(0.5, 'rgba(200,135,58,0.05)');
    mg.addColorStop(1,   'rgba(200,135,58,0)');
    ctx.fillStyle = mg;
    ctx.fillRect(0, 0, W, H);

    requestAnimationFrame(draw);
  }

  requestAnimationFrame(draw);
})();

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
  const modalClose = document.getElementById('modalClose');

  function openModal(card) {
    const d = card.dataset;

    document.getElementById('modalTitle').textContent = d.title || '';
    document.getElementById('modalPeriod').textContent = d.period || '';
    document.getElementById('modalDesc').textContent = d.desc || '';

    const metaRow = document.getElementById('modalMetaRow');
    const myRoleEl = document.getElementById('modalMyRole');
    if (d.myrole && d.myrole.trim()) {
      myRoleEl.textContent = d.myrole;
      metaRow.style.display = '';
    } else {
      metaRow.style.display = 'none';
    }

    const kpiBlock = document.getElementById('modalKpiBlock');
    const kpiEl = document.getElementById('modalKpi');
    const kpiItems = (d.kpi || '').split('\n').filter(function (s) { return s.trim(); });
    if (kpiItems.length) {
      kpiEl.innerHTML = kpiItems.map(function (item) {
        return '<div class="modal-kpi-item">📊 ' + item.trim() + '</div>';
      }).join('');
      kpiBlock.style.display = '';
    } else {
      kpiBlock.style.display = 'none';
    }

    const detailBlock = document.getElementById('modalDetailBlock');
    if (d.detail && d.detail.trim()) {
      document.getElementById('modalDetail').textContent = d.detail;
      detailBlock.style.display = '';
    } else {
      detailBlock.style.display = 'none';
    }

    // 갤러리
    const galleryWrap = document.getElementById('modalGalleryWrap');
    let images = [];
    try { images = JSON.parse(d.images || '[]').map(fn => `/static/uploads/${fn}`); } catch(e) {}
    if (images.length) {
      galleryWrap.style.display = '';
      initGallery(images, d.title || '');
    } else {
      galleryWrap.style.display = 'none';
    }

    const tagsEl = document.getElementById('modalTags');
    tagsEl.innerHTML = (d.tags || '').split(',')
      .filter(t => t.trim())
      .map(t => `<span class="tag">${t.trim()}</span>`)
      .join('');

    const linksEl = document.getElementById('modalLinks');
    let links = [];
    try { links = JSON.parse(d.links || '[]'); } catch (e) {}
    linksEl.innerHTML = links
      .filter(lk => !extractYtId(lk.url) && !extractPlaylistId(lk.url))
      .map(lk => `<a href="${lk.url}" class="pc-link" target="_blank" rel="noopener">${lk.label} →</a>`)
      .join('');

    // YouTube 카드들 (영상 + 재생목록)
    ytListEl.innerHTML = '';
    links.forEach(lk => {
      const vid = extractYtId(lk.url);
      const pid = !vid && extractPlaylistId(lk.url);
      if (vid) ytListEl.appendChild(createYtCard(lk.label, lk.url, vid));
      else if (pid) ytListEl.appendChild(createPlaylistCard(lk.label, lk.url, pid));
    });

    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  // ── 갤러리 ─────────────────────────────────
  let galleryIdx = 0;
  let galleryImgs = [];
  const galleryMainImg = document.getElementById('modalGalleryImg');
  const thumbsEl = document.getElementById('modalGalleryThumbs');
  const prevBtn = document.getElementById('galleryPrev');
  const nextBtn = document.getElementById('galleryNext');

  function initGallery(imgs, alt) {
    galleryImgs = imgs;
    galleryIdx = 0;
    setGallerySlide(0, alt);
    // 썸네일
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
    thumbsEl.querySelectorAll('img').forEach((t, ti) => t.classList.toggle('active', ti === i));
  }

  prevBtn?.addEventListener('click', () => {
    galleryIdx = (galleryIdx - 1 + galleryImgs.length) % galleryImgs.length;
    setGallerySlide(galleryIdx);
  });
  nextBtn?.addEventListener('click', () => {
    galleryIdx = (galleryIdx + 1) % galleryImgs.length;
    setGallerySlide(galleryIdx);
  });

  // ── YouTube 카드 ────────────────────────────
  const ytListEl = document.getElementById('modalYoutubeList');

  function extractYtId(url) {
    const m = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    return m ? m[1] : null;
  }
  function extractPlaylistId(url) {
    const m = url.match(/[?&]list=([a-zA-Z0-9_-]+)/);
    return m ? m[1] : null;
  }
  function createPlaylistCard(label, playlistUrl, playlistId) {
    const item = document.createElement('div');
    item.className = 'yt-item';
    item.innerHTML = (label ? `<div class="yt-item-label">${label}</div>` : '')
      + `<a href="${playlistUrl}" class="yt-card" target="_blank" rel="noopener">
           <div class="yt-thumb-wrap">
             <img src="" alt="" />
             <span class="yt-play">▶</span>
           </div>
           <div class="yt-info">
             <div class="yt-title">로딩 중…</div>
             <div class="yt-stats">
               <span class="yt-views"></span>
               <span class="yt-likes"></span>
               <span class="yt-comments"></span>
             </div>
           </div>
         </a>`;
    fetch(`/api/youtube/playlist?list=${playlistId}`)
      .then(r => r.json())
      .then(d => {
        if (d.error) { item.querySelector('.yt-title').textContent = '재생목록'; return; }
        if (d.thumbnail) item.querySelector('.yt-thumb-wrap img').src = d.thumbnail;
        item.querySelector('.yt-title').textContent = d.title || '';
        item.querySelector('.yt-views').textContent    = d.viewCount    ? '▶ ' + fmtNum(d.viewCount)    + ' 회' : '';
        item.querySelector('.yt-likes').textContent    = d.likeCount    ? '👍 ' + fmtNum(d.likeCount)            : '';
        item.querySelector('.yt-comments').textContent = d.commentCount ? '💬 ' + fmtNum(d.commentCount)       : '';
      })
      .catch(() => { item.querySelector('.yt-title').textContent = ''; });
    return item;
  }
  function fmtNum(n) {
    n = parseInt(n) || 0;
    if (n >= 10000) return (n / 10000).toFixed(1) + '만';
    if (n >= 1000)  return (n / 1000).toFixed(1) + 'k';
    return n.toLocaleString();
  }
  function createYtCard(label, videoUrl, videoId) {
    const item = document.createElement('div');
    item.className = 'yt-item';
    item.innerHTML = (label ? `<div class="yt-item-label">${label}</div>` : '')
      + `<a href="${videoUrl}" class="yt-card" target="_blank" rel="noopener">
           <div class="yt-thumb-wrap">
             <img src="https://img.youtube.com/vi/${videoId}/hqdefault.jpg" alt="" />
             <span class="yt-play">▶</span>
           </div>
           <div class="yt-info">
             <div class="yt-title">로딩 중…</div>
             <div class="yt-stats">
               <span class="yt-views"></span>
               <span class="yt-likes"></span>
               <span class="yt-comments"></span>
             </div>
           </div>
         </a>`;
    fetch(`/api/youtube?v=${videoId}`)
      .then(r => r.json())
      .then(d => {
        if (d.error) { item.querySelector('.yt-title').textContent = ''; return; }
        if (d.thumbnail) item.querySelector('.yt-thumb-wrap img').src = d.thumbnail;
        item.querySelector('.yt-title').textContent = d.title || '';
        item.querySelector('.yt-views').textContent   = d.viewCount    ? '▶ ' + fmtNum(d.viewCount)    + ' 회' : '';
        item.querySelector('.yt-likes').textContent   = d.likeCount    ? '👍 ' + fmtNum(d.likeCount)            : '';
        item.querySelector('.yt-comments').textContent = d.commentCount ? '💬 ' + fmtNum(d.commentCount)       : '';
      })
      .catch(() => { item.querySelector('.yt-title').textContent = ''; });
    return item;
  }

  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  document.querySelectorAll('.project-card').forEach(card => {
    card.style.cursor = 'pointer';
    card.addEventListener('click', e => {
      if (e.target.closest('a')) return;
      openModal(card);
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
      btn.setAttribute('aria-label', `슬라이드 ${i + 1}`);
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

// ── Project Form: EN Links ───────────────────
const linkRowsEn = document.getElementById('linkRowsEn');
const addLinkBtnEn = document.getElementById('addLinkBtnEn');
if (linkRowsEn && addLinkBtnEn) {
  function wireRemoveBtnEn(row) {
    row.querySelector('.link-remove-btn').addEventListener('click', () => {
      if (linkRowsEn.querySelectorAll('.link-row').length > 1) row.remove();
    });
  }
  linkRowsEn.querySelectorAll('.link-row').forEach(wireRemoveBtnEn);
  addLinkBtnEn.addEventListener('click', () => {
    const row = document.createElement('div');
    row.className = 'link-row';
    row.innerHTML = '<input type="text" name="link_label_en" placeholder="Link name (e.g. GitHub, Demo)" />'
      + '<input type="text" name="link_url_en" placeholder="https://..." />'
      + '<button type="button" class="link-remove-btn" aria-label="삭제">×</button>';
    linkRowsEn.appendChild(row);
    wireRemoveBtnEn(row);
    row.querySelector('input').focus();
  });
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

window.addEventListener('scroll', () => {
  let current = '';
  sections.forEach(sec => {
    if (window.scrollY >= sec.offsetTop - 120) current = sec.id;
  });
  navLinks.forEach(a => {
    a.style.color = a.getAttribute('href') === `#${current}` ? 'var(--accent)' : '';
  });
});
