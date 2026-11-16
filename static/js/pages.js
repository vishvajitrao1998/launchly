/* Page controllers. Every page is a static template; these fill it from /api/. */
(() => {
  
  const { api, esc, toast, modal, appCard, voteButtons, renderBoard, pay, money, rupee, fmtDate, skel, logoHtml, premiumBadge, pager } = window.L;
  const $ = window.$, $$ = window.$$;
  const pages = {};
  const localDate = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD

    /* ---------- shared: rank rows + right rail ---------- */
  
  const rankItem = (p, rank, i = 0) => appCard(p, i, rank);

  const sideAd = p => p.slot_open
    ? `<a class="side-ad open" href="/advertise/?slot=sidebar&position=${p.position}"><span class="badge badge-sponsor">Ad slot</span><b>Your Product Here</b><span>${esc(p.label)} · from ${money(p.price)}/week</span></a>`
    : `<a class="side-ad" href="/product/${esc(p.slug)}/"><span class="badge badge-sponsor">Sponsored</span>
        <div class="side-row"><div class="logo" style="--c:${esc(p.category.color)}">${logoHtml(p)}</div><div><b>${esc(p.name)}</b><p>${esc(p.tagline)}</p></div></div></a>`;

  async function fillRail() {
    try {
      const { ads } = await api('/api/rail/');
      ads.forEach((p, i) => { const el = $('#railAd' + (i + 1)); if (el) el.innerHTML = sideAd(p); });
    } catch (e) { /* the rail is optional */ }
  }

  /* ======================= HOME ======================= */
    pages.home = async () => {
    const q = new URLSearchParams(location.search).get('q');
    $('#heroAd').innerHTML = skel(1, 260);
    $('#spotlight').innerHTML = skel(3, 90);
    $('#feed').innerHTML = skel(4, 90);
    fillRail();

    const [cats, feed] = await Promise.all([api('/api/categories/'), api('/api/feed/')]);

    // hero ad (paid)
    const h = feed.hero;
    $('#heroAd').innerHTML = h.slot_open
      ? `<div class="hero-banner open reveal"><div><div class="tagline">📣 Reserved for advertisers</div><h3>Your product, front and centre</h3><p>The hero banner is the first thing every visitor sees. Book it from ${money(h.price)}/week.</p></div><a class="btn" href="/advertise/?slot=hero">Book the hero slot</a></div>`
      : `<div class="hero-banner reveal"><div><div class="tagline"><svg class="i" style="width:14px;height:14px"><use href="#i-star"/></svg>Sponsored</div>
          <div class="logo" style="margin-top:14px">${logoHtml(h)}</div><h3>${esc(h.name)}</h3><p>${esc(h.tagline)}</p></div>
          <a class="btn" href="/product/${esc(h.slug)}/">Take a look</a></div>`;

    // sponsored spotlight (3 paid tiles)
    $('#spotlight').innerHTML = feed.spotlight.map((p, i) => appCard(p, i)).join('');

    // top products: today / yesterday / last week / last month
        $('#topSections').innerHTML = feed.top.map(t => `
      <section class="block">
        <div class="block-head"><h2>${esc(t.title)}</h2><a class="link" href="/top/?kind=${t.kind}&offset=${t.offset}">See all</a></div>
        ${t.items.length
          ? `<div class="rank-list two-col">${t.items.map((p, i) => rankItem(p, i + 1, i)).join('')}</div>`
          : '<div class="empty sm">No launches in this period yet. <a class="link" href="/launch-product/">Launch Yours</a></div>'}
      </section>`).join('');

    // categories + feed (with load more when one category is selected)
    let active = '', page = 1, seen = new Set();
    $('#cats').innerHTML = `<button class="chip on" data-cat="">✨ All</button>` + cats.map(c =>
      `<button class="chip" data-cat="${esc(c.slug)}" style="--c:${esc(c.color)}">${esc(c.icon)} ${esc(c.name)} <small>${c.count}</small></button>`).join('');

    const drawFeed = () => {
      const list = feed.sections.filter(s => !active || s.category.slug === active);
      const total = cats.find(c => c.slug === active)?.count || 0;
      $('#feed').innerHTML = (list.length ? list.map(s => `
        <section class="cat-section"><div class="cat-title" style="--c:${esc(s.category.color)}"><span class="cat-ico">${esc(s.category.icon)}</span><h2>${esc(s.category.name)}</h2><a class="link" href="/category/${esc(s.category.slug)}/">See all</a></div>
        <div class="app-grid">${s.items.map((p, i) => appCard(p, i)).join('')}</div></section>`).join('')
        : '<div class="empty">No launches in this category yet. Be the first!</div>')
        + (active && total > 10 ? '<div class="more"><button class="btn btn-ghost" id="moreBtn">Load more</button></div>' : '');
      if (active && total > 10) {
        page = 1; seen = new Set(list.flatMap(s => s.items.filter(p => p.id).map(p => p.id)));
        $('#moreBtn').onclick = async () => {
          const b = $('#moreBtn'); b.disabled = true;
          const r = await api(`/api/products/?category=${encodeURIComponent(active)}&page_size=10&page=${++page}`);
          const fresh = r.results.filter(p => !seen.has(p.id)); fresh.forEach(p => seen.add(p.id));
          $('#feed .app-grid').insertAdjacentHTML('beforeend', fresh.map((p, i) => appCard(p, i)).join(''));
          b.disabled = false; if (page >= r.pages) b.hidden = true;
        };
      }
    };
    $('#cats').addEventListener('click', e => {
      const b = e.target.closest('[data-cat]'); if (!b) return;
      active = b.dataset.cat;
      $$('#cats .chip').forEach(c => c.classList.toggle('on', c === b));
      drawFeed();
    });
    drawFeed();

    // search results replace the feed
    if (q) {
      $('#feed').hidden = true; $('#topSections').hidden = true;
      const box = $('#searchResults'); box.hidden = false;
      box.innerHTML = `<section class="block"><div class="block-head"><h2>Results for “${esc(q)}”</h2></div><div id="resGrid" class="app-grid"></div><div id="resPager"></div></section>`;
      const load = async n => {
        const r = await api(`/api/products/?q=${encodeURIComponent(q)}&page=${n}`);
        $('#resGrid').innerHTML = r.results.length ? r.results.map((p, i) => appCard(p, i)).join('') : '<div class="empty">Nothing found.</div>';
        pager($('#resPager'), r, load);
        box.scrollIntoView({ behavior: 'smooth' });
      };
      load(1);
    }
  };

    /* ======================= LEADERBOARD ======================= */
  pages.top = async () => {
    const qs = new URLSearchParams(location.search);
    let kind = ['day', 'week', 'month'].includes(qs.get('kind')) ? qs.get('kind') : 'day';
    let offset = Math.max(0, parseInt(qs.get('offset')) || 0), page = 1;
    fillRail();

    async function load() {
      $('#topList').innerHTML = skel(6, 84);
      const d = await api(`/api/top/?kind=${kind}&offset=${offset}&page=${page}`);
      kind = d.kind; offset = d.offset;
      history.replaceState(null, '', `/top/?kind=${kind}&offset=${offset}`);
      $$('#kindTabs .tab').forEach(t => t.classList.toggle('on', t.dataset.kind === kind));
      $('#rangeLabel b').textContent = d.label;
      $('#rangeLabel span').textContent = d.sub;
      $('#prevRange').disabled = !d.has_prev;
      $('#nextRange').disabled = !d.has_next;
      $('#topList').innerHTML = d.results.length
        ? d.results.map((p, i) => rankItem(p, d.start + i, i)).join('')
        : '<div class="empty">No launches in this period yet.</div>';
      pager($('#topPager'), d, n => { page = n; load(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
    }

    $('#kindTabs').addEventListener('click', e => {
      const t = e.target.closest('[data-kind]'); if (!t) return;
      kind = t.dataset.kind; offset = 0; page = 1; load();
    });
    $('#prevRange').onclick = () => { offset++; page = 1; load(); };
    $('#nextRange').onclick = () => { offset = Math.max(0, offset - 1); page = 1; load(); };
    load();
  };


    /* ======================= CATEGORY / ALL PRODUCTS ======================= */
  pages.category = async () => {
    const slug = $('#catView').dataset.slug;
    let sort = new URLSearchParams(location.search).get('sort') === 'new' ? 'new' : 'top', page = 1;
    fillRail();

    const cats = await api('/api/categories/');
    const current = cats.find(c => c.slug === slug);
    if (slug && !current) { $('#catList').innerHTML = '<div class="empty">Category not found.</div>'; return; }
    $('#catTitle').textContent = current ? `${current.icon} ${current.name}` : 'All Products';
    document.title = `${current ? current.name : 'All products'} · Launchly`;
    $('#catChips').innerHTML = `<a class="chip ${slug ? '' : 'on'}" href="/products/">✨ All</a>` + cats.map(c =>
      `<a class="chip ${c.slug === slug ? 'on' : ''}" href="/category/${esc(c.slug)}/" style="--c:${esc(c.color)}">${esc(c.icon)} ${esc(c.name)} <small>${c.count}</small></a>`).join('');

    async function load() {
      $('#catList').innerHTML = skel(6, 84);
      const d = await api(`/api/products/?category=${encodeURIComponent(slug)}&sort=${sort}&page=${page}&page=${page}`);
      history.replaceState(null, '', `${location.pathname}?sort=${sort}`);
      $$('#sortTabs .tab').forEach(t => t.classList.toggle('on', t.dataset.sort === sort));
      $('#catSub').textContent = `${d.total} product${d.total === 1 ? '' : 's'}`;
      $('#catList').innerHTML = d.results.length
        ? d.results.map((p, i) => sort === 'top' ? rankItem(p, d.start + i, i) : appCard(p, i)).join('')
        : '<div class="empty">No products here yet. <a class="link" href="/launch-product/">Launch the first one</a></div>';
      pager($('#catPager'), d, n => { page = n; load(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
    }
    $('#sortTabs').addEventListener('click', e => {
      const t = e.target.closest('[data-sort]'); if (!t) return;
      sort = t.dataset.sort; page = 1; load();
    });
    load();
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
      if (!+b.dataset.price) return (location.href = '/launch-product/');
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
    renderBoard($('#board'), board, { home: true });
    const body = $('#bookBody');
    if (!me.authenticated) {
      body.innerHTML = '<p class="muted" style="margin-bottom:14px">Log in to book a slot.</p><a class="btn btn-primary" href="/login/?next=/advertise/">Log in</a>';
      return;
    }
    const prods = (await api('/api/me/products/?status=approved&page_size=50')).results;
    if (!prods.length) {
      body.innerHTML = '<p class="muted" style="margin-bottom:14px">You need an approved product before you can advertise it.</p><a class="btn btn-primary" href="/launch-product/">Launch a product</a>';
      return;
    }
    const opt = r => `<option value="${esc(r.key)}">${esc(r.category ? r.group + ' · ' + r.label : r.label)} · ${money(r.price)}/wk</option>`;
    const opts = `<optgroup label="Category slots">${board.rows.filter(r => r.category).map(opt).join('')}</optgroup>`
           + `<optgroup label="Home page">${board.rows.filter(r => !r.category).map(opt).join('')}</optgroup>`;
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
        renderBoard($('#board'), await api('/api/ads/board/'), {home:true});
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
    if (!shown) { const el = $('.form-err', form) || $('#formErr'); el.textContent = err.message; el.classList.add('show'); }
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

    const MAX = 3; let kept = [], added = [], removed = [];
    const drawShots = () => {
      $('#shotCount').textContent = `${kept.length + added.length}/${MAX}`;
      $('#shots').innerHTML =
        kept.map(s => `<div class="shot"><img src="${esc(s.url)}" alt=""><button type="button" data-rm-kept="${s.id}" aria-label="Remove">×</button></div>`).join('') +
        added.map((f, i) => `<div class="shot"><img src="${URL.createObjectURL(f)}" alt=""><button type="button" data-rm-new="${i}" aria-label="Remove">×</button></div>`).join('');
      $('#addShot').hidden = kept.length + added.length >= MAX;
    };
    $('#addShot').onclick = () => form.screenshots.click();
    form.screenshots.addEventListener('change', () => {
      for (const f of form.screenshots.files) {
        if (kept.length + added.length >= MAX) { toast('Maximum 3 screenshots', 'bad'); break; }
        if (f.size > 3 * 1024 * 1024) { toast(`${f.name} is over 3 MB`, 'bad'); continue; }
        added.push(f);
      }
      form.screenshots.value = ''; drawShots();
    });
    $('#shots').addEventListener('click', e => {
      const k = e.target.closest('[data-rm-kept]'), n = e.target.closest('[data-rm-new]');
      if (k) { removed.push(+k.dataset.rmKept); kept = kept.filter(s => s.id !== +k.dataset.rmKept); }
      if (n) added.splice(+n.dataset.rmNew, 1);
      drawShots();
    });
    drawShots();

        // rich-text description with a hard character limit
    const MAXC = 2000;
    const quill = new Quill('#editor', {
      theme: 'snow',
      placeholder: 'What does it do, who is it for, why is it different?',
      formats: ['bold', 'italic', 'underline', 'strike', 'list', 'link'],
      modules: { toolbar: [['bold', 'italic', 'underline', 'strike'], [{ list: 'ordered' }, { list: 'bullet' }], ['link'], ['clean']] },
    });
    const descCount = () => {
      const n = quill.getLength() - 1, el = $('#descCount');
      el.textContent = `${n}/${MAXC}`;
      el.style.color = n >= MAXC ? 'var(--bad)' : n > MAXC * 0.9 ? 'var(--warn)' : '';
    };
    quill.on('text-change', () => {
      if (quill.getLength() - 1 > MAXC) quill.deleteText(MAXC, quill.getLength());   // also trims pasted text
      descCount();
    });
    descCount();

    if (editId) {
      $('#submitTitle').textContent = 'Update Your Launch';
      $('#submitBtn').textContent = 'Resubmit for Review';
      $('#premiumOpt').hidden = true;
      const p = await api(`/api/me/products/${editId}/`);
      kept = p.screenshots; drawShots();
      ['name', 'tagline', 'website_url'].forEach(k => (form.elements[k].value = p[k]));
      if (/<[a-z][^>]*>/i.test(p.description)) quill.clipboard.dangerouslyPasteHTML(p.description);
      else quill.setText(p.description);   // older plain-text descriptions
      descCount();
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
      fd.set('description', quill.getText().trim() ? quill.root.innerHTML : '');
      if (!form.logo.files[0]) fd.delete('logo');
      fd.delete('screenshots'); added.forEach(f => fd.append('screenshots', f)); removed.forEach(id => fd.append('remove_screenshots', id));
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
    const [ads, me] = await Promise.all([api('/api/me/ads/'), api('/api/me/')]);
    $('#dashSub').textContent = `Premium credits: ${me.credits}`;

    const drawProducts = async n => {
      const d = await api(`/api/me/products/?page=${n}`);
      $('#myProducts').innerHTML = d.results.length ? d.results.map((p, i) => {
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
              ${['pending', 'needs_info'].includes(p.status) ? `<a class="btn btn-sm ${p.status === 'needs_info' ? 'btn-primary' : ''}" href="/launch-product/?edit=${p.id}">${p.status === 'needs_info' ? 'Fix & resubmit' : 'Edit'}</a>` : ''}
            </div>
          </div></article>`;
      }).join('') : '<div class="empty">No launches yet. <a class="link" href="/launch-product/">Launch your first product</a></div>';
      pager($('#prodPager'), d, drawProducts);
    };
    await drawProducts(1);

    $('#myAds').innerHTML = ads.length ? ads.map((a, i) => `<article class="row-card" style="--i:${i}"><div class="grow"><div class="title-row"><b>${esc(a.product)}</b>${stBadge(a.status)}</div>
      <div class="meta-line"><span>${esc(a.group)} · ${esc(a.label)}</span><span>${fmtDate(a.starts_on)} – ${fmtDate(a.ends_on)}</span></div></div></article>`).join('')
      : '<div class="empty">No ad bookings yet.</div>';
  };

  /* ======================= REVIEW (staff) ======================= */
  pages.review = async () => {
    let status = 'pending',page = 1;
    const names = { pending: 'Pending', needs_info: 'Needs info', approved: 'Approved', rejected: 'Rejected' };
    const templates = {
      request_info: name => `Thanks for submitting ${name}! Before we can approve it, we need:\n\n- `,
      reject: () => 'Reason: ',
      email: () => '',
    };
    const copy = { request_info: ['Request more info', 'Send request'], reject: ['Reject launch', 'Reject & email'], email: ['Email the maker', 'Send email'] };

    async function load() {
      $('#queue').innerHTML = skel(3, 110);
      const d = await api(`/api/admin/queue/?status=${status}&page=${page}`);
      $('#tabs').innerHTML = Object.entries(names).map(([k, v]) => `<button class="tab ${k === status ? 'on' : ''}" data-tab="${k}">${v}<b>${d.counts[k] || 0}</b></button>`).join('');
      $('#queue').innerHTML = d.results.length ? d.results.map((p, i) => `
        <article class="row-card" style="--i:${i}" data-id="${p.id}" data-name="${esc(p.name)}">
          <div class="logo" style="--c:${esc(p.category.color)}">${logoHtml(p)}</div>
          <div class="grow">
            <div class="title-row"><b><a class="name" href="/product/${esc(p.slug)}/" target="_blank" rel="noopener">${esc(p.name)}</a></b>${p.is_premium ? premiumBadge : ''}<a class="link" href="${esc(p.website_url)}" target="_blank" rel="noopener">${esc(p.website_url)}</a></div>
            <div class="meta-line"><span>${esc(p.category.icon)} ${esc(p.category.name)}</span><span>by ${esc(p.owner.username)} (${esc(p.owner.email || 'no email')})</span>${p.scheduled_for ? `<span><svg class="i" style="width:14px;height:14px"><use href="#i-clock"/></svg> Wants ${fmtDate(p.scheduled_for, true)}</span>` : ''}</div>
            <p class="desc"><b>${esc(p.tagline)}</b><br>${esc(p.description_text)}</p>
            ${p.admin_note ? `<div class="note">Last note: ${esc(p.admin_note)}</div>` : ''}
            <div class="row-actions">
              ${status !== 'approved' ? '<button class="btn btn-sm btn-ok" data-review="approve">Approve</button>' : ''}
              <button class="btn btn-sm" data-review="request_info">Request info</button>
              ${status !== 'rejected' ? '<button class="btn btn-sm btn-bad" data-review="reject">Reject</button>' : ''}
              <button class="btn btn-sm btn-ghost" data-review="email">Email maker</button>
              <a class="btn btn-sm btn-ghost" href="/product/${esc(p.slug)}/" target="_blank" rel="noopener">View details</a>
            </div>
          </div></article>`).join('') : '<div class="empty">Nothing here 🎉</div>';
          pager($('#qPager'), d, n => { page = n; load(); });
    }

    $('#tabs').addEventListener('click', e => { const t = e.target.closest('[data-tab]'); if (t) { status = t.dataset.tab; page = 1; load(); } });
    $('#queue').addEventListener('click', e => {
      const d = e.target.closest('.desc'); if (d) { d.classList.toggle('open'); return; }
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
      ${p.is_live ? '' : `<div class="callout warn">Preview only. This product is not public yet (status: <b>${esc(p.status)}</b>).
      ${document.body.dataset.staff === '1' ? '<a class="link" href="/review/">← Back to review queue</a>' : ''}</div>`}
      <article class="card pd reveal" data-id="${p.id}">
        <div class="pd-top" style="--c:${esc(p.category.color)}">
          <div class="logo">${logoHtml(p)}</div>
          <div><div class="title-row"><h1 style="font-size:2rem">${esc(p.name)}</h1>${p.is_premium ? premiumBadge : ''}</div><p class="muted">${esc(p.tagline)}</p></div>
          <div class="pd-actions"><a class="btn" href="${esc(p.website_url)}" target="_blank" rel="noopener">Visit</a>${p.is_live ? voteButtons(p) : ''}</div>
        </div>
        <div class="meta-line"><span class="chip sm">${esc(p.category.icon)} ${esc(p.category.name)}</span>${p.launch_at ? `<span>Launched ${fmtDate(p.launch_at, true)}</span>` : ''}<span>by ${esc(p.maker)}</span></div>
        <div class="pd-desc">${p.description}</div>
        ${p.screenshots.length ? `<div class="gallery">${p.screenshots.map(u => `<button class="gal" data-shot="${esc(u)}"><img loading="lazy" src="${esc(u)}" alt="${esc(p.name)} screenshot"></button>`).join('')}</div>` : ''}
      </article>`;
      el.addEventListener('click', e => { const g = e.target.closest('[data-shot]'); if (g) modal(`<img class="lightbox" src="${esc(g.dataset.shot)}" alt=""><div class="row-actions"><button class="btn" data-close>Close</button></div>`); });
      $$('.pd-desc a').forEach(a => { a.target = '_blank'; });
  };

    /* ======================= SETTINGS ======================= */
  pages.settings = async () => {
    const pf = $('#profileForm'), pw = $('#passwordForm');
    const p = await api('/api/me/profile/');
    ['username', 'email', 'first_name', 'last_name', 'display_name'].forEach(k => (pf.elements[k].value = p[k] || ''));

    pf.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = $('button[type=submit]', pf); btn.disabled = true;
      try {
        const out = await api('/api/me/profile/', { method: 'PATCH', body: {
          first_name: pf.elements.first_name.value, last_name: pf.elements.last_name.value, display_name: pf.elements.display_name.value } });
        showErrors(pf, { data: {}, message: '' }); $('.form-err', pf).classList.remove('show');
        const name = out.display_name || out.username;
        $$('.me .me-name').forEach(el => (el.textContent = name));
        $$('.me .avatar').forEach(el => (el.textContent = name.charAt(0).toUpperCase()));
        toast('Profile Updated');
        $$('.greet-name').forEach(el => (el.textContent = name));
      } catch (err) { showErrors(pf, err); }
      btn.disabled = false;
    });

    pw.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = $('button[type=submit]', pw); btn.disabled = true;
      try {
        await api('/api/me/password/', { method: 'POST', body: {
          current_password: pw.elements.current_password.value, new_password: pw.elements.new_password.value,
          confirm_password: pw.elements.confirm_password.value } });
        pw.reset(); showErrors(pw, { data: {}, message: '' }); $('.form-err', pw).classList.remove('show');
        toast('Password Updated');
        
      } catch (err) { showErrors(pw, err); }
      btn.disabled = false;
    });
  };

  const run = pages[document.body.dataset.page];
if (run) run().catch(e => e.message !== 'Please log in' && toast(e.message, 'bad')).finally(() => window.L.enhanceSelects());
})();
