/* =========================================================================
   cart.js — AJAX cart operations (no page reloads)

   Works for both guests (session cart) and logged-in users (DB cart):
   the server decides where to store things, the endpoints are the same.

   Endpoints (all POST + CSRF):
     /cart/update/<item_id>/   {quantity}
     /cart/remove/<item_id>/
   ========================================================================= */

/** Read the CSRF token from the form Django rendered on this page. */
function getCsrfToken() {
  const el = document.querySelector('[name=csrfmiddlewaretoken]');
  if (el) return el.value;
  // Fallback: read the cookie set by Django's CSRF middleware.
  const match = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[2]) : '';
}

/** POST JSON to a cart endpoint and return the parsed response. */
async function cartPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCsrfToken(),
      'X-Requested-With': 'XMLHttpRequest',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

/** Refresh the summary numbers in the sidebar without reloading. */
function refreshSummary(totals) {
  if (!totals) return;
  const set = (key, value) => {
    const el = document.querySelector(`[data-summary="${key}"]`);
    if (el) el.textContent = value;
  };
  set('subtotal', Number(totals.subtotal).toFixed(2));
  set('total', Number(totals.total).toFixed(2));

  const shipEl = document.querySelector('[data-summary="shipping"]');
  if (shipEl) shipEl.textContent = Number(totals.shipping).toFixed(2);
}

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('cartItems');
  if (!container) return; // Not on the cart page.

  /** Wire up one cart line (also called for lines re-rendered later). */
  function bindLine(line) {
    const itemId = line.dataset.itemId;
    const qtyInput = line.querySelector('.qty-input');

    // ---------- Quantity stepper buttons ----------
    line.querySelectorAll('.qty-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const delta = btn.dataset.action === 'inc' ? 1 : -1;
        const current = parseInt(qtyInput.value, 10) || 1;
        const next = Math.max(0, Math.min(10, current + delta));
        if (next === current) return;
        qtyInput.value = next;
        await sendUpdate(line, itemId, next);
      });
    });

    // ---------- Direct input (on blur / Enter) ----------
    qtyInput.addEventListener('change', async () => {
      let v = parseInt(qtyInput.value, 10);
      if (isNaN(v) || v < 0) v = 1;
      v = Math.min(10, v);
      qtyInput.value = v;
      await sendUpdate(line, itemId, v);
    });

    // ---------- Remove button ----------
    const removeBtn = line.querySelector('[data-action="remove"]');
    if (removeBtn) {
      removeBtn.addEventListener('click', async () => {
        const data = await cartPost(`/cart/remove/${itemId}/`);
        if (data.ok) {
          line.classList.add('removing');
          setTimeout(() => {
            line.remove();
            updateCartBadge(data.count);
            refreshSummary(data.totals);
            showToast('🗑️ ' + data.message, 'info');
            // Everything gone? Reload so the empty state appears.
            if (data.count === 0) location.reload();
          }, 180);
        } else {
          showToast(data.message, 'error');
        }
      });
    }
  }

  /** Push a new quantity to the server and update the UI. */
  async function sendUpdate(line, itemId, quantity) {
    try {
      const data = await cartPost(`/cart/update/${itemId}/`, { quantity });

      if (!data.ok) {
        showToast('⚠️ ' + data.message, 'warning');
        return;
      }

      if (data.count === 0) {
        // Cart became empty → show the empty state.
        location.reload();
        return;
      }

      updateCartBadge(data.count);
      refreshSummary(data.totals);

      // Update this line's total (the server sends it back).
      const linePrice = line.querySelector('[data-line-price]');
      if (linePrice && data.line_total != null) {
        linePrice.textContent = Number(data.line_total).toFixed(0);
      }

      // Quantity was clamped to stock — reflect the real value.
      if (quantity > 0 && parseInt(line.querySelector('.qty-input').value, 10) !== quantity) {
        line.querySelector('.qty-input').value = quantity;
      }

      // Removing via quantity 0: fade the row out.
      if (quantity === 0) {
        line.classList.add('removing');
        setTimeout(() => line.remove(), 180);
      }

      showToast('✅ ' + data.message, 'success');
    } catch (_) {
      showToast('Could not reach the server. Please retry.', 'error');
    }
  }

  container.querySelectorAll('.cart-line').forEach(bindLine);
});
