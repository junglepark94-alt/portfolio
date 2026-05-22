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
    if (d.kpi && d.kpi.trim()) {
      kpiEl.textContent = d.kpi;
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
    linksEl.innerHTML = links.map(lk =>
      `<a href="${lk.url}" class="pc-link" target="_blank" rel="noopener">${lk.label} →</a>`
    ).join('');

    // YouTube 카드
    ytWrap.style.display = 'none';
    const ytLink_ = links.find(lk => extractYtId(lk.url));
    if (ytLink_) loadYoutube(ytLink_.url, extractYtId(ytLink_.url));

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
  const ytWrap   = document.getElementById('modalYoutube');
  const ytLink   = document.getElementById('modalYoutubeLink');
  const ytThumb  = document.getElementById('modalYoutubeThumb');
  const ytTitle  = document.getElementById('modalYoutubeTitle');
  const ytViews  = document.getElementById('modalYoutubeViews');
  const ytLikes  = document.getElementById('modalYoutubeLikes');
  const ytCmnts  = document.getElementById('modalYoutubeComments');

  function extractYtId(url) {
    const m = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    return m ? m[1] : null;
  }
  function fmtNum(n) {
    n = parseInt(n) || 0;
    if (n >= 10000) return (n / 10000).toFixed(1) + '만';
    if (n >= 1000)  return (n / 1000).toFixed(1) + 'k';
    return n.toLocaleString();
  }
  function loadYoutube(videoUrl, videoId) {
    ytWrap.style.display = 'none';
    ytLink.href = videoUrl;
    ytThumb.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
    ytTitle.textContent = '로딩 중…';
    ytViews.textContent = ytLikes.textContent = ytCmnts.textContent = '';
    ytWrap.style.display = '';
    fetch(`/api/youtube?v=${videoId}`)
      .then(r => r.json())
      .then(d => {
        if (d.error) return;
        if (d.thumbnail) ytThumb.src = d.thumbnail;
        ytTitle.textContent  = d.title || '';
        ytViews.textContent  = d.viewCount  ? '▶ ' + fmtNum(d.viewCount)  + ' 회' : '';
        ytLikes.textContent  = d.likeCount  ? '👍 ' + fmtNum(d.likeCount)         : '';
        ytCmnts.textContent  = d.commentCount ? '💬 ' + fmtNum(d.commentCount)    : '';
      })
      .catch(() => { ytTitle.textContent = ''; });
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

// ── Gallery Modal ────────────────────────────
const galleryModal = document.getElementById('galleryModal');
if (galleryModal) {
  const gClose = document.getElementById('galleryModalClose');

  function openGalleryModal(card) {
    const d = card.dataset;
    document.getElementById('galleryModalImg').src = d.image || '';
    document.getElementById('galleryModalImg').alt = d.title || '';
    document.getElementById('galleryModalTitle').textContent = d.title || '';
    document.getElementById('galleryModalDesc').textContent = d.desc || '';
    document.getElementById('galleryModalImgWrap').style.display = d.image ? '' : 'none';

    const linksEl = document.getElementById('galleryModalLinks');
    let links = [];
    try { links = JSON.parse(d.links || '[]'); } catch(e) {}
    linksEl.innerHTML = links.map(lk =>
      `<a href="${lk.url}" class="pc-link" target="_blank" rel="noopener">${lk.label} →</a>`
    ).join('');

    galleryModal.classList.add('active');
    galleryModal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closeGalleryModal() {
    galleryModal.classList.remove('active');
    galleryModal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  gClose.addEventListener('click', closeGalleryModal);
  galleryModal.addEventListener('click', e => { if (e.target === galleryModal) closeGalleryModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeGalleryModal(); });

  document.querySelectorAll('.gallery-card').forEach(card => {
    card.addEventListener('click', () => openGalleryModal(card));
  });
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
      <input type="text" name="link_label" placeholder="링크 이름 (예: GitHub, 발표자료)" />
      <input type="url"  name="link_url"   placeholder="https://..." />
      <button type="button" class="link-remove-btn" aria-label="삭제">×</button>`;
    linkRows.appendChild(row);
    wireRemoveBtn(row);
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
