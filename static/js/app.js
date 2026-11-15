/* Launchly core: theme, sidebar, API client, shared renderers. No framework, no build step. */
(() => {
  const root = document.documentElement;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  window.$ = $; window.$$ = $$;

  /* ---------- theme ---------- */
  $('#themeToggle')?.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.classList.add('theme-anim');
    root.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch (e) {}
    setTimeout(() => root.classList.remove('theme-anim'), 450);
  });

  /* ---------- sidebar: collapse to icons (desktop) / drawer (mobile) ---------- */
  const mobile = () => matchMedia('(max-width: 900px)').matches;
  $('#sbToggle')?.addEventListener('click', () => {
    if (mobile()) return document.body.classList.remove('sb-open');
    root.classList.toggle('sb-collapsed');
    try { localStorage.setItem('sidebar', root.classList.contains('sb-collapsed') ? 'collapsed' : 'open'); } catch (e) {}
  });
  $('#menuBtn')?.addEventListener('click', () => document.body.classList.add('sb-open'));
  $('#backdrop')?.addEventListener('click', () => document.body.classList.remove('sb-open'));
  $$('.sb-nav a').forEach(a => a.addEventListener('click', () => document.body.classList.remove('sb-open')));
  $$('[data-nav]').forEach(a => a.dataset.nav === document.body.dataset.page && a.classList.add('active'));
  const q0 = new URLSearchParams(location.search).get('q');
  if (q0 && $('#searchForm input')) $('#searchForm input').value = q0;

  /* ---------- helpers ---------- */
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const rupee = n => '₹' + Number(n).toLocaleString('en-IN');
  const initials = n => (n || '?').trim().split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
  const fmtDate = (iso, time) => {
    const d = iso.length === 10 ? new Date(iso + 'T00:00:00') : new Date(iso);
    return d.toLocaleString('en-IN', time ? { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' } : { day: 'numeric', month: 'short' });
  };
  const skel = (n = 3, h = 84) => Array.from({ length: n }, () => `<div class="skeleton" style="height:${h}px"></div>`).join('');

  function toast(msg, kind = '') {
    const t = document.createElement('div');
    t.className = 'toast ' + kind; t.textContent = msg;
    $('#toasts').appendChild(t);
    setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 320); }, 3800);
  }

  /* ---------- API ---------- */
  const csrf = () => $('meta[name=csrf-token]').content;
  async function api(url, { method = 'GET', body, form } = {}) {
    const opt = { method, credentials: 'same-origin', headers: { Accept: 'application/json', 'X-CSRFToken': csrf() } };
    if (body) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
    if (form) opt.body = form;
    const r = await fetch(url, opt);
    let data = null; try { data = await r.json(); } catch (e) {}
    if (!r.ok) {
      if ((r.status === 401 || r.status === 403) && /credentials/i.test(data?.detail || '')) {
        location.href = '/login/?next=' + encodeURIComponent(location.pathname + location.search);
        throw new Error('Please log in');
      }
      const err = new Error(data?.detail || 'Something went wrong. Please try again.');
      err.status = r.status; err.data = data; throw err;
    }
    return data;
  }

  /* ---------- modal ---------- */
  function modal(html) {
    const bg = document.createElement('div');
    bg.className = 'modal-bg';
    bg.innerHTML = `<div class="modal" role="dialog" aria-modal="true">${html}</div>`;
    document.body.appendChild(bg);
    const onKey = e => e.key === 'Escape' && bg.close();
    bg.close = () => { bg.remove(); document.removeEventListener('keydown', onKey); };
    bg.addEventListener('click', e => (e.target === bg || e.target.closest('[data-close]')) && bg.close());
    document.addEventListener('keydown', onKey);
    return bg;
  }

  /* ---------- app card ---------- */
  const premiumBadge = '<span class="badge badge-premium"><svg class="i"><use href="#i-star"/></svg>Premium</span>';
  const logoHtml = p => p.logo ? `<img loading="lazy" src="${esc(p.logo)}" alt="">` : esc(initials(p.name));

  function appCard(p, i = 0) {
    if (p.slot_open) {
      return `<a class="app-card slot-open reveal" style="--i:${i}" href="/advertise/?slot=${esc(p.slot_type)}&category=${esc(p.category)}&position=${p.position}">
        <b>Your app here</b><span class="muted">${esc(p.label)} · from ${rupee(p.price)}/week</span></a>`;
    }
    return `<article class="app-card reveal ${p.is_premium ? 'is-premium' : ''} ${p.sponsored ? 'sponsored' : ''}" style="--i:${i}" data-id="${p.id}">
      <a class="logo" href="/product/${esc(p.slug)}/" style="--c:${esc(p.category.color)}">${logoHtml(p)}</a>
      <div class="body">
        <div class="title-row"><a class="name" href="/product/${esc(p.slug)}/">${esc(p.name)}</a>${p.is_premium ? premiumBadge : ''}${p.sponsored ? '<span class="badge badge-sponsor">Sponsored</span>' : ''}</div>
        <p class="tag">${esc(p.tagline)}</p>
        <span class="chip sm">${esc(p.category.icon)} ${esc(p.category.name)}</span>
      </div>
      <div class="actions">${voteButtons(p)}</div>
    </article>`;
  }
  const voteButtons = p => `
    <button class="vote ${p.upvoted ? 'on' : ''}" data-vote="upvote" aria-label="Upvote"><svg class="i"><use href="#i-up"/></svg><b>${p.upvotes}</b></button>
    <button class="like ${p.liked ? 'on' : ''}" data-vote="like" aria-label="Like"><svg class="i"><use href="#i-heart"/></svg><b>${p.likes}</b></button>`;

  document.addEventListener('click', async e => {
    const btn = e.target.closest('[data-vote]');
    if (!btn) return;
    const host = btn.closest('[data-id]'), kind = btn.dataset.vote;
    try {
      const out = await api(`/api/products/${host.dataset.id}/${kind}/`, { method: 'POST' });
      $$(`[data-id="${host.dataset.id}"] [data-vote="${kind}"]`).forEach(b => {
        b.classList.toggle('on', out.active);
        b.querySelector('b').textContent = out.count;
        b.classList.remove('pop'); void b.offsetWidth; b.classList.add('pop');
      });
    } catch (err) { if (err.message !== 'Please log in') toast(err.message, 'bad'); }
  });

  /* ---------- ad slot board ---------- */
  function renderBoard(el, data) {
    const wk = data.weeks;
    const cell = (c, r, w) => {
      if (!c) return `<td><a class="cell free" data-key="${esc(r.key)}" data-start="${w.from}" href="/advertise/?slot=${r.slot_type}&category=${esc(r.category)}&position=${r.position}&start=${w.from}">Available</a></td>`;
      const mini = c.logo ? `<img src="${esc(c.logo)}" alt="">` : `<span class="mini">${esc(initials(c.name))}</span>`;
      return `<td><span class="cell ${c.pending ? 'held' : 'booked'}" title="${c.pending ? 'Payment in progress' : 'Booked until ' + fmtDate(c.until)}">${mini}<span>${c.pending ? 'Reserved' : esc(c.name)}</span></span></td>`;
    };
    let rows = '', group = '';
    data.rows.forEach(r => {
      if (r.group !== group) { group = r.group; rows += `<tr class="grp"><td colspan="${wk.length + 2}">${esc(r.icon)} ${esc(group)}</td></tr>`; }
      rows += `<tr><td>${esc(r.label)}</td><td class="price">${rupee(r.price)}</td>${r.cells.map((c, i) => cell(c, r, wk[i])).join('')}</tr>`;
    });
    el.innerHTML = `<table class="board"><thead><tr><th>Slot</th><th>Per week</th>${wk.map(w => `<th>${fmtDate(w.from)} – ${fmtDate(w.to)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`;
  }

  /* ---------- Razorpay Checkout ---------- */
  function pay(checkout) {
    return new Promise((resolve, reject) => {
      if (!window.Razorpay) return reject(new Error('Razorpay could not load. Check your connection.'));
      const rz = new Razorpay({
        ...checkout, theme: { color: '#5b5bf0' },
        modal: { ondismiss: () => reject(new Error('Payment cancelled')) },
        handler: async r => { try { resolve(await api('/api/payments/verify/', { method: 'POST', body: r })); } catch (e) { reject(e); } },
      });
      rz.on('payment.failed', r => reject(new Error(r.error?.description || 'Payment failed')));
      rz.open();
    });
  }

  window.L = { api, esc, toast, modal, appCard, voteButtons, renderBoard, pay, rupee, initials, fmtDate, skel, logoHtml, premiumBadge };
})();
