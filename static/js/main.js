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

    const detailBlock = document.getElementById('modalDetailBlock');
    if (d.detail && d.detail.trim()) {
      document.getElementById('modalDetail').textContent = d.detail;
      detailBlock.style.display = '';
    } else {
      detailBlock.style.display = 'none';
    }

    const imageWrap = document.getElementById('modalImageWrap');
    if (d.image) {
      document.getElementById('modalImage').src = d.image;
      document.getElementById('modalImage').alt = d.title || '';
      imageWrap.style.display = '';
    } else {
      imageWrap.style.display = 'none';
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

    modal.classList.add('active');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
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
