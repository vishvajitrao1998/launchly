/* Page controllers. Every page is a static template; these fill it from /api/. */
(() => {
  const { api, esc, toast, modal, appCard, voteButtons, renderBoard, pay, rupee, fmtDate, skel, logoHtml, premiumBadge } = window.L;
  const $ = window.$, $$ = window.$$;
  const pages = {};
  const localDate = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD

  /* ======================= HOME ======================= */
  pages.home = async () => {
    const q = new URLSearchParams(location.search).get('q');
    $('#heroAd').innerHTML = skel(1, 260);
    $('#spotlight').innerHTML = skel(3, 90);
    $('#feed').innerHTML = skel(4, 90);
    api('/api/ads/board/').then(d => renderBoard($('#board'), d));

    const [cats, feed] = await Promise.all([api('/api/categories/'), api('/api/feed/')]);

    // hero ad (paid)
    const h = feed.hero;
    $('#heroAd').innerHTML = h.slot_open
      ? `<div class="hero-banner open reveal"><div><div class="tagline">📣 Reserved for advertisers</div><h3>Your product, front and centre</h3><p>The hero banner is the first thing every visitor sees. Book it from ${rupee(h.price)}/week.</p></div><a class="btn" href="/advertise/?slot=hero">Book the hero slot</a></div>`
      : `<div class="hero-banner reveal"><div><div class="tagline"><svg class="i" style="width:14px;height:14px"><use href="#i-star"/></svg>Sponsored</div>
          <div class="logo" style="margin-top:14px">${logoHtml(h)}</div><h3>${esc(h.name)}</h3><p>${esc(h.tagline)}</p></div>
          <a class="btn" href="/product/${esc(h.slug)}/">Take a look</a></div>`;

    // sponsored spotlight (3 paid tiles)
    $('#spotlight').innerHTML = feed.spotlight.map((p, i) => appCard(p, i)).join('');

    // categories + feed
    let active = '';
    $('#cats').innerHTML = `<button class="chip on" data-cat="">✨ All</button>` + cats.map(c =>
      `<button class="chip" data-cat="${esc(c.slug)}" style="--c:${esc(c.color)}">${esc(c.icon)} ${esc(c.name)} <small>${c.count}</small></button>`).join('');
    const drawFeed = () => {
      const list = feed.sections.filter(s => !active || s.category.slug === active);
      $('#feed').innerHTML = list.length ? list.map(s => `
        <section class="cat-section"><div class="cat-title" style="--c:${esc(s.category.color)}"><span class="cat-ico">${esc(s.category.icon)}</span><h2>${esc(s.category.name)}</h2></div>
        <div class="app-grid">${s.items.map((p, i) => appCard(p, i)).join('')}</div></section>`).join('')
        : '<div class="empty">No launches in this category yet. Be the first!</div>';
    };
    $('#cats').addEventListener('click', e => {
      const b = e.target.closest('[data-cat]'); if (!b) return;
      active = b.dataset.cat;
      $$('#cats .chip').forEach(c => c.classList.toggle('on', c === b));
      drawFeed();
    });
    drawFeed();

    if (feed.latest.length) {
      $('#latestWrap').hidden = false;
      $('#latest').innerHTML = feed.latest.map((p, i) => appCard(p, i)).join('');
    }

    // search results replace the feed
    if (q) {
      const res = await api('/api/products/?q=' + encodeURIComponent(q));
      $('#feed').hidden = true; $('#latestWrap').hidden = true;
      const box = $('#searchResults'); box.hidden = false;
      box.innerHTML = `<section class="block"><div class="block-head"><h2>Results for “${esc(q)}”</h2></div><div class="app-grid">${res.length ? res.map((p, i) => appCard(p, i)).join('') : '<div class="empty">Nothing found.</div>'}</div></section>`;
      box.scrollIntoView({ behavior: 'smooth' });
    }
  };

  /* ======================= PRICING ======================= */
  pages.pricing = async () => {
    $('#plans').innerHTML = skel(3, 380);
    const [data, me] = await Promise.all([api('/api/pricing/'), api('/api/me/')]);
    if (me.authenticated && me.credits) { const n = $('#creditNote'); n.hidden = false; n.textContent = `You have ${me.credits} Premium launch credit${me.credits > 1 ? 's' : ''} left`; }

    $('#plans').innerHTML = data.plans.map((p, i) => `
      <article class="card plan reveal ${p.highlighted ? 'hl' : ''}" style="--i:${i}">
        ${p.highlighted ? '<span class="badge badge-premium pill">Most popular</span>' : ''}
        <div><h3>${esc(p.name)}</h3><p class="muted">${esc(p.tagline)}</p></div>
        <div class="price-big">${p.price ? rupee(p.price) : 'Free'}<small>${p.price ? ' / month' : ''}</small></div>
        <ul>${p.features.map(f => `<li><svg class="i"><use href="#i-check"/></svg><span>${esc(f)}</span></li>`).join('')}</ul>
        <button class="btn ${p.highlighted ? 'btn-primary' : ''} btn-lg" data-plan="${esc(p.slug)}" data-price="${p.price}">${p.price ? 'Choose ' + esc(p.name) : 'Start free'}</button>
      </article>`).join('');

    $('#adPrices').innerHTML = data.ads.map((a, i) => `
      <article class="card ad-card reveal" style="--i:${i}"><h3>${esc(a.name)}</h3><p class="muted">${esc(a.description)}</p>
        <div class="price-big" style="font-size:1.8rem">${rupee(a.price)}<small> / week</small></div>
        <a class="btn btn-ghost" href="/advertise/?slot=${esc(a.slot_type)}">Book this slot</a></article>`).join('');

    $('#plans').addEventListener('click', async e => {
      const b = e.target.closest('[data-plan]'); if (!b) return;
      if (!+b.dataset.price) return (location.href = '/submit/');
      if (!me.authenticated) return (location.href = '/login/?next=/pricing/');
      b.disabled = true;
      try {
        const { checkout } = await api('/api/payments/plan/', { method: 'POST', body: { plan: b.dataset.plan } });
        await pay(checkout);
        toast('Payment successful. Your Premium credits are ready 🎉');
        setTimeout(() => location.reload(), 900);
      } catch (err) { toast(err.message, 'bad'); }
      b.disabled = false;
    });
  };

  /* ======================= ADVERTISE ======================= */
  pages.advertise = async () => {
    const [board, me] = await Promise.all([api('/api/ads/board/'), api('/api/me/')]);
    renderBoard($('#board'), board);
    const body = $('#bookBody');
    if (!me.authenticated) {
      body.innerHTML = '<p class="muted" style="margin-bottom:14px">Log in to book a slot.</p><a class="btn btn-primary" href="/login/?next=/advertise/">Log in</a>';
      return;
    }
    const prods = (await api('/api/me/products/')).filter(p => p.status === 'approved');
    if (!prods.length) {
      body.innerHTML = '<p class="muted" style="margin-bottom:14px">You need an approved product before you can advertise it.</p><a class="btn btn-primary" href="/submit/">Launch a product</a>';
      return;
    }
    let opts = '', g = '';
    board.rows.forEach(r => {
      if (r.group !== g) { if (g) opts += '</optgroup>'; g = r.group; opts += `<optgroup label="${esc(g)}">`; }
      opts += `<option value="${esc(r.key)}">${esc(r.label)} · ${rupee(r.price)}/wk</option>`;
    });
    opts += '</optgroup>';
    body.innerHTML = `
      <div style="display:grid;gap:16px">
        <label class="field"><span>Slot</span><select id="bSlot">${opts}</select></label>
        <label class="field"><span>Product</span><select id="bProd">${prods.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></label>
        <div class="grid-2">
          <label class="field"><span>Start date</span><input type="date" id="bStart" min="${localDate()}" value="${localDate()}"></label>
          <label class="field"><span>Weeks</span><select id="bWeeks">${Array.from({ length: 12 }, (_, i) => `<option>${i + 1}</option>`).join('')}</select></label>
        </div>
        <div class="total"><span class="muted">Total</span><b id="bTotal"></b></div>
        <em class="err" id="bErr"></em>
        <button class="btn btn-primary btn-lg" id="bPay">Pay with Razorpay</button>
      </div>`;
    const priceOf = () => board.rows.find(r => r.key === $('#bSlot').value).price;
    const total = () => ($('#bTotal').textContent = rupee(priceOf() * +$('#bWeeks').value));
    const select = (key, start) => {
      if (key && [...$('#bSlot').options].some(o => o.value === key)) $('#bSlot').value = key;
      if (start) $('#bStart').value = start;
      total();
    };
    const p = new URLSearchParams(location.search);
    if (p.get('slot')) select(`${p.get('slot')}:${p.get('category') || '-'}:${p.get('position') || 1}`, p.get('start'));
    total();
    $('#bSlot').onchange = $('#bWeeks').onchange = total;

    // clicking a free cell fills the form instead of navigating
    $('#board').addEventListener('click', e => {
      const a = e.target.closest('.cell.free'); if (!a) return;
      e.preventDefault(); select(a.dataset.key, a.dataset.start);
      const card = $('#bookCard'); card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      card.classList.remove('flash'); void card.offsetWidth; card.classList.add('flash');
    });

    $('#bPay').onclick = async () => {
      const [slot_type, cat, position] = $('#bSlot').value.split(':');
      const err = $('#bErr'); err.classList.remove('show');
      const btn = $('#bPay'); btn.disabled = true;
      try {
        const { checkout } = await api('/api/payments/ad/', { method: 'POST', body: {
          slot_type, category: cat === '-' ? '' : cat, position, product: $('#bProd').value,
          start_date: $('#bStart').value, weeks: $('#bWeeks').value } });
        await pay(checkout);
        toast('Slot booked! Your ad is scheduled 🎉');
        renderBoard($('#board'), await api('/api/ads/board/'));
      } catch (e) { err.textContent = e.message; err.classList.add('show'); }
      btn.disabled = false;
    };
  };

  /* ======================= SUBMIT / EDIT ======================= */
  function showErrors(form, err) {
    $$('.err', form).forEach(x => x.classList.remove('show'));
    $$('.field.invalid', form).forEach(x => x.classList.remove('invalid'));
    let shown = false;
    for (const [k, v] of Object.entries(err.data || {})) {
      if (k === 'detail') continue;
      const f = form.querySelector(`[name="${k}"]`)?.closest('.field');
      if (!f) continue;
      f.classList.add('invalid');
      const el = f.querySelector('.err'); el.textContent = [].concat(v).join(' '); el.classList.add('show'); shown = true;
    }
    if (!shown) { const el = $('#formErr'); el.textContent = err.message; el.classList.add('show'); }
  }

  pages.submit = async () => {
    const form = $('#submitForm'), editId = form.dataset.edit;
    const [cats, me] = await Promise.all([api('/api/categories/'), api('/api/me/')]);
    form.category.innerHTML = '<option value="">Select a category…</option>' + cats.map(c => `<option value="${esc(c.slug)}">${esc(c.icon)} ${esc(c.name)}</option>`).join('');

    const count = () => ($('#tagCount').textContent = `${form.tagline.value.length}/140`);
    form.tagline.addEventListener('input', count);
    const minDt = new Date(Date.now() + 3600e3 + 60e3);
    form.scheduled_for.min = new Date(minDt - minDt.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
    $$('[name=launch_mode]', form).forEach(r => r.addEventListener('change', () => ($('#scheduleBox').hidden = form.launch_mode.value !== 'schedule')));
    form.logo.addEventListener('change', () => {
      const f = form.logo.files[0], img = $('#logoPrev');
      if (f) { img.src = URL.createObjectURL(f); img.hidden = false; } else img.hidden = true;
    });

    if (me.credits > 0) $('#premiumNote').textContent = `You have ${me.credits} Premium credit${me.credits > 1 ? 's' : ''}. Uses one on submit.`;
    else { $('#premiumNote').innerHTML = 'No credits yet. <a class="link" href="/pricing/">Get a plan</a> to unlock Premium launches.'; form.premium.disabled = true; }

    if (editId) {
      $('#submitTitle').textContent = 'Update your launch';
      $('#submitBtn').textContent = 'Resubmit for review';
      $('#premiumOpt').hidden = true;
      const p = await api(`/api/me/products/${editId}/`);
      ['name', 'tagline', 'description', 'website_url'].forEach(k => (form.elements[k].value = p[k]));
      form.category.value = p.category.slug; count();
      if (p.scheduled_for) {
        form.launch_mode.value = 'schedule'; $('#scheduleBox').hidden = false;
        const d = new Date(p.scheduled_for); form.scheduled_for.value = new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
      }
      if (p.admin_note) { const n = $('#adminNote'); n.hidden = false; n.innerHTML = `<b>Message from our team:</b><br>${esc(p.admin_note)}`; }
    }

    form.addEventListener('submit', async e => {
      e.preventDefault();
      const fd = new FormData(form);
      if (!form.logo.files[0]) fd.delete('logo');
      if (form.launch_mode.value === 'schedule' && form.scheduled_for.value) fd.set('scheduled_for', new Date(form.scheduled_for.value).toISOString());
      else fd.delete('scheduled_for');
      fd.set('premium', form.premium.checked ? 'true' : 'false');
      const btn = $('#submitBtn'); btn.disabled = true;
      try {
        await api(editId ? `/api/me/products/${editId}/` : '/api/me/products/', { method: editId ? 'PATCH' : 'POST', form: fd });
        toast('Submitted! We will review it shortly 🚀');
        setTimeout(() => (location.href = '/dashboard/'), 800);
      } catch (err) { showErrors(form, err); btn.disabled = false; }
    });
  };

  /* ======================= DASHBOARD ======================= */
  const stLabel = { pending: 'In review', needs_info: 'Needs info', approved: 'Live', rejected: 'Rejected', scheduled: 'Scheduled', active: 'Active', cancelled: 'Cancelled' };
  const stBadge = k => `<span class="badge badge-status st-${k}">${stLabel[k] || k}</span>`;

  pages.dashboard = async () => {
    $('#myProducts').innerHTML = skel(3, 100);
    const [prods, ads, me] = await Promise.all([api('/api/me/products/'), api('/api/me/ads/'), api('/api/me/')]);
    $('#dashSub').textContent = `Premium credits: ${me.credits}`;
    $('#myProducts').innerHTML = prods.length ? prods.map((p, i) => {
      const st = p.status === 'approved' && !p.is_live ? 'scheduled' : p.status === 'approved' ? 'approved' : p.status;
      const when = st === 'scheduled' ? `Goes live ${fmtDate(p.launch_at, true)}` : p.scheduled_for && p.status !== 'approved' ? `Requested for ${fmtDate(p.scheduled_for, true)}` : '';
      return `<article class="row-card" style="--i:${i}">
        <div class="logo" style="--c:${esc(p.category.color)}">${logoHtml(p)}</div>
        <div class="grow">
          <div class="title-row"><b>${esc(p.name)}</b>${stBadge(st)}${p.is_premium ? premiumBadge : ''}</div>
          <div class="meta-line"><span>${esc(p.category.icon)} ${esc(p.category.name)}</span>${when ? `<span><svg class="i" style="width:14px;height:14px"><use href="#i-clock"/></svg> ${when}</span>` : ''}<span>▲ ${p.upvotes}</span><span>♥ ${p.likes}</span></div>
          ${p.admin_note ? `<div class="note"><b>Message from our team:</b> ${esc(p.admin_note)}</div>` : ''}
          <div class="row-actions">
            ${p.is_live ? `<a class="btn btn-sm" href="/product/${esc(p.slug)}/">View</a><a class="btn btn-sm btn-ghost" href="/advertise/">Advertise</a>` : ''}
            ${['pending', 'needs_info'].includes(p.status) ? `<a class="btn btn-sm ${p.status === 'needs_info' ? 'btn-primary' : ''}" href="/submit/?edit=${p.id}">${p.status === 'needs_info' ? 'Fix & resubmit' : 'Edit'}</a>` : ''}
          </div>
        </div></article>`;
    }).join('') : '<div class="empty">No launches yet. <a class="link" href="/submit/">Launch your first product</a></div>';
    $('#myAds').innerHTML = ads.length ? ads.map((a, i) => `<article class="row-card" style="--i:${i}"><div class="grow"><div class="title-row"><b>${esc(a.product)}</b>${stBadge(a.status)}</div>
      <div class="meta-line"><span>${esc(a.group)} · ${esc(a.label)}</span><span>${fmtDate(a.starts_on)} – ${fmtDate(a.ends_on)}</span></div></div></article>`).join('')
      : '<div class="empty">No ad bookings yet.</div>';
  };

  /* ======================= REVIEW (staff) ======================= */
  pages.review = async () => {
    let status = 'pending';
    const names = { pending: 'Pending', needs_info: 'Needs info', approved: 'Approved', rejected: 'Rejected' };
    const templates = {
      request_info: name => `Thanks for submitting ${name}! Before we can approve it, we need:\n\n- `,
      reject: () => 'Reason: ',
      email: () => '',
    };
    const copy = { request_info: ['Request more info', 'Send request'], reject: ['Reject launch', 'Reject & email'], email: ['Email the maker', 'Send email'] };

    async function load() {
      $('#queue').innerHTML = skel(3, 110);
      const d = await api(`/api/admin/queue/?status=${status}`);
      $('#tabs').innerHTML = Object.entries(names).map(([k, v]) => `<button class="tab ${k === status ? 'on' : ''}" data-tab="${k}">${v}<b>${d.counts[k] || 0}</b></button>`).join('');
      $('#queue').innerHTML = d.items.length ? d.items.map((p, i) => `
        <article class="row-card" style="--i:${i}" data-id="${p.id}" data-name="${esc(p.name)}">
          <div class="logo" style="--c:${esc(p.category.color)}">${logoHtml(p)}</div>
          <div class="grow">
            <div class="title-row"><b>${esc(p.name)}</b>${p.is_premium ? premiumBadge : ''}<a class="link" href="${esc(p.website_url)}" target="_blank" rel="noopener">${esc(p.website_url)}</a></div>
            <div class="meta-line"><span>${esc(p.category.icon)} ${esc(p.category.name)}</span><span>by ${esc(p.owner.username)} (${esc(p.owner.email || 'no email')})</span>${p.scheduled_for ? `<span><svg class="i" style="width:14px;height:14px"><use href="#i-clock"/></svg> Wants ${fmtDate(p.scheduled_for, true)}</span>` : ''}</div>
            <p class="desc"><b>${esc(p.tagline)}</b><br>${esc(p.description)}</p>
            ${p.admin_note ? `<div class="note">Last note: ${esc(p.admin_note)}</div>` : ''}
            <div class="row-actions">
              ${status !== 'approved' ? '<button class="btn btn-sm btn-ok" data-review="approve">Approve</button>' : ''}
              <button class="btn btn-sm" data-review="request_info">Request info</button>
              ${status !== 'rejected' ? '<button class="btn btn-sm btn-bad" data-review="reject">Reject</button>' : ''}
              <button class="btn btn-sm btn-ghost" data-review="email">Email maker</button>
            </div>
          </div></article>`).join('') : '<div class="empty">Nothing here 🎉</div>';
    }

    $('#tabs').addEventListener('click', e => { const t = e.target.closest('[data-tab]'); if (t) { status = t.dataset.tab; load(); } });
    $('#queue').addEventListener('click', e => {
      const b = e.target.closest('[data-review]'); if (!b) return;
      const card = b.closest('.row-card'), id = card.dataset.id, action = b.dataset.review;
      const send = async message => {
        await api(`/api/admin/products/${id}/review/`, { method: 'POST', body: { action, message } });
        toast(action === 'approve' ? 'Approved. The maker was emailed.' : 'Done. The maker was emailed.');
        if (action === 'email') return;
        card.classList.add('leave'); setTimeout(load, 450);
      };
      if (action === 'approve') return send('').catch(err => toast(err.message, 'bad'));
      const [title, cta] = copy[action];
      const m = modal(`<h3>${title}</h3><p class="muted">${esc(card.dataset.name)}: the message is emailed to the maker and shown on their dashboard.</p>
        <textarea rows="6" id="mMsg" placeholder="Write your message…">${esc(templates[action](card.dataset.name))}</textarea><em class="err" id="mErr"></em>
        <div class="row-actions"><button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="mSend">${cta}</button></div>`);
      $('#mMsg', m).focus();
      $('#mSend', m).onclick = async () => {
        try { await send($('#mMsg', m).value); m.close(); }
        catch (err) { const el = $('#mErr', m); el.textContent = err.message; el.classList.add('show'); }
      };
    });
    load();
  };

  /* ======================= PRODUCT DETAIL ======================= */
  pages.product = async () => {
    const el = $('#productView');
    let p;
    try { p = await api(`/api/products/${el.dataset.slug}/`); }
    catch (e) { el.innerHTML = '<div class="empty">This product could not be found.</div>'; return; }
    document.title = `${p.name} · Launchly`;
    el.innerHTML = `
      ${p.is_live ? '' : '<div class="callout warn">Preview only. This product is not public yet.</div>'}
      <article class="card pd reveal" data-id="${p.id}">
        <div class="pd-top" style="--c:${esc(p.category.color)}">
          <div class="logo">${logoHtml(p)}</div>
          <div><div class="title-row"><h1 style="font-size:2rem">${esc(p.name)}</h1>${p.is_premium ? premiumBadge : ''}</div><p class="muted">${esc(p.tagline)}</p></div>
          <div class="pd-actions"><a class="btn" href="${esc(p.website_url)}" target="_blank" rel="noopener">Visit website</a>${p.is_live ? voteButtons(p) : ''}</div>
        </div>
        <div class="meta-line"><span class="chip sm">${esc(p.category.icon)} ${esc(p.category.name)}</span>${p.launch_at ? `<span>Launched ${fmtDate(p.launch_at, true)}</span>` : ''}<span>by @${esc(p.maker)}</span></div>
        <div class="pd-desc">${esc(p.description)}</div>
      </article>`;
  };

  const run = pages[document.body.dataset.page];
  if (run) run().catch(e => e.message !== 'Please log in' && toast(e.message, 'bad'));
})();
