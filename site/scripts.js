(() => {
  document.documentElement.classList.add('js');

  const menuToggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#primary-navigation');
  const closeMenu = () => {
    if (!menuToggle || !nav) return;
    menuToggle.setAttribute('aria-expanded', 'false');
    nav.classList.remove('is-open');
  };
  menuToggle?.addEventListener('click', () => {
    const isOpen = menuToggle.getAttribute('aria-expanded') === 'true';
    menuToggle.setAttribute('aria-expanded', String(!isOpen));
    nav.classList.toggle('is-open', !isOpen);
  });
  nav?.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenu));

  const copyStatus = document.querySelector('#copy-status');
  const fallbackCopy = (text) => {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    let copied = false;
    try { copied = document.execCommand('copy'); } catch (error) { copied = false; }
    area.remove();
    return copied;
  };
  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      const text = button.dataset.copy || '';
      let copied = false;
      if (navigator.clipboard && window.isSecureContext) {
        try { await navigator.clipboard.writeText(text); copied = true; } catch (error) { copied = false; }
      }
      if (!copied) copied = fallbackCopy(text);
      const original = button.innerHTML;
      button.classList.toggle('is-copied', copied);
      button.innerHTML = copied ? '<span class="copy-icon">✓</span> Copiado' : '<span class="copy-icon">!</span> Selecciona y copia';
      if (copyStatus) copyStatus.textContent = copied ? 'Comando copiado al portapapeles.' : 'No se pudo copiar automáticamente; selecciona el comando para copiarlo.';
      window.setTimeout(() => { button.innerHTML = original; button.classList.remove('is-copied'); }, 2200);
    });
  });

  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const activateTab = (tab) => {
    tabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-selected', String(active));
      const panel = document.getElementById(item.getAttribute('aria-controls'));
      if (panel) {
        panel.hidden = !active;
        panel.classList.toggle('is-active', active);
      }
    });
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activateTab(tab));
    tab.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      const nextIndex = event.key === 'ArrowRight' ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length;
      tabs[nextIndex].focus();
      activateTab(tabs[nextIndex]);
    });
  });

  const revealItems = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12 });
    revealItems.forEach((item) => revealObserver.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add('is-visible'));
  }

  const lightbox = document.querySelector('#lightbox');
  const lightboxImage = document.querySelector('#lightbox-image');
  const lightboxTitle = document.querySelector('#lightbox-title');
  const lightboxDescription = document.querySelector('#lightbox-description');
  const lightboxKicker = document.querySelector('#lightbox-kicker');
  const lightboxCount = document.querySelector('#lightbox-count');
  const shotCards = [...document.querySelectorAll('[data-shot]')];
  const closeButton = lightbox?.querySelector('[data-lightbox-close].lightbox-close');
  let activeShot = 0;
  let lastFocused = null;
  let tourMode = false;

  const renderShot = (index) => {
    if (!shotCards.length) return;
    activeShot = (index + shotCards.length) % shotCards.length;
    const card = shotCards[activeShot];
    const source = card.dataset.image;
    const image = card.querySelector('img');
    lightboxImage.src = source;
    lightboxImage.alt = image?.alt || '';
    lightboxTitle.textContent = card.dataset.title || '';
    lightboxKicker.textContent = card.dataset.kicker || '';
    lightboxDescription.textContent = image?.alt || 'Vista real de la ejecución local.';
    lightboxCount.textContent = `${String(activeShot + 1).padStart(2, '0')} / ${String(shotCards.length).padStart(2, '0')}`;
  };
  const openLightbox = (index, isTour = false) => {
    if (!lightbox) return;
    tourMode = isTour;
    lastFocused = document.activeElement;
    renderShot(index);
    lightbox.hidden = false;
    document.body.classList.add('lightbox-open');
    closeButton?.focus();
  };
  const closeLightbox = () => {
    if (!lightbox || lightbox.hidden) return;
    lightbox.hidden = true;
    document.body.classList.remove('lightbox-open');
    tourMode = false;
    if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
  };
  document.querySelectorAll('[data-lightbox-index]').forEach((trigger) => {
    trigger.addEventListener('click', () => openLightbox(Number(trigger.dataset.lightboxIndex) || 0));
  });
  document.querySelector('#tour-start')?.addEventListener('click', () => openLightbox(0, true));
  lightbox?.querySelectorAll('[data-lightbox-close]').forEach((element) => element.addEventListener('click', closeLightbox));
  lightbox?.querySelector('.lightbox-prev')?.addEventListener('click', () => renderShot(activeShot - 1));
  lightbox?.querySelector('.lightbox-next')?.addEventListener('click', () => renderShot(activeShot + 1));
  document.addEventListener('keydown', (event) => {
    if (!lightbox || lightbox.hidden) {
      if (event.key === 'Escape') closeMenu();
      return;
    }
    if (event.key === 'Escape') closeLightbox();
    if (event.key === 'ArrowLeft') renderShot(activeShot - 1);
    if (event.key === 'ArrowRight') renderShot(activeShot + 1);
    if (event.key === 'Tab') {
      const focusable = [...lightbox.querySelectorAll('button')].filter((item) => !item.disabled);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  // Keep the tour intent discoverable to assistive technology without adding a second control.
  if (tourMode) lightbox?.setAttribute('data-tour', 'true');
})();
