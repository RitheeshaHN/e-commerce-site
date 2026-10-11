/* =========================================================================
   main.js — global UI behaviour
   • mobile navbar toggle
   • toast auto-dismiss
   • navbar search suggestions (fetch → JSON endpoint)
   • helpers shared with cart.js (updateCartBadge, showToast)
   ========================================================================= */

/** Update the navbar cart badge with an animation. */
function updateCartBadge(count) {
  const badge = document.getElementById('cartBadge');
  if (!badge) return;
  badge.textContent = count;
  badge.dataset.count = count;
  badge.classList.remove('bump');
  // Force a reflow so the animation restarts every time.
  void badge.offsetWidth;
  badge.classList.add('bump');
  badge.style.display = count > 0 ? 'grid' : 'none';
}

/**
 * Show a toast message.
 * @param {string} text  message to display
 * @param {string} type  success | error | warning | info
 */
function showToast(text, type = 'info') {
  const wrap = document.getElementById('toasts');
  if (!wrap) return;
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = text;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

document.addEventListener('DOMContentLoaded', () => {
  /* ---------------- Mobile nav toggle ---------------- */
  const navToggle = document.getElementById('navToggle');
  const navLinks = document.getElementById('navLinks');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      const open = navLinks.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', String(open));
    });
  }

  /* ---------------- Toast auto-dismiss ---------------- */
  document.querySelectorAll('[data-toast]').forEach((t) => {
    setTimeout(() => {
      t.style.opacity = '0';
      setTimeout(() => t.remove(), 300);
    }, 3500);
  });

  /* ---------------- Search suggestions ---------------- */
  const input = document.getElementById('navSearchInput');
  const box = document.getElementById('searchSuggest');
  if (input && box) {
    let timer = null;

    const hide = () => { box.hidden = true; box.innerHTML = ''; };

    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) return hide();

      // Debounce: wait 200ms after the last keystroke.
      timer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/search/?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          if (!data.results.length) return hide();
          box.innerHTML = data.results
            .map(
              (r) =>
                `<a href="/products/${r.slug}/">${r.name}` +
                ` <small>${r.brand}</small></a>`
            )
            .join('');
          box.hidden = false;
        } catch (_) {
          hide(); // network problem → search still works via form submit
        }
      }, 200);
    });

    // Close when clicking outside the search box.
    document.addEventListener('click', (e) => {
      if (!box.contains(e.target) && e.target !== input) hide();
    });
  }
});
