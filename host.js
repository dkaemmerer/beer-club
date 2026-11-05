/**
 * Beer Club — Host Director Dashboard Logic
 * Real-time SSE listener, round stepper, lineup ordering, and QR generator
 */

(function() {
  'use strict';

  const state = {
    eventId: getQueryParam('event') || 'craft-showdown',
    eventData: null,
    beers: [],
    participants: [],
    participantStatuses: [],
    currentRound: 1,
    analytics: null,
    sse: null,
    lanIp: window.location.hostname,
    toastTimer: null
  };

  function getQueryParam(key) {
    const params = new URLSearchParams(window.location.search);
    return params.get(key);
  }

  const els = {
    hostEventTitle: document.getElementById('host-event-title'),
    hostEventTheme: document.getElementById('host-event-theme'),
    badgeHostStatus: document.getElementById('badge-host-status'),
    btnLoadSampleEvent: document.getElementById('btn-load-sample-event'),
    btnResetBlankEvent: document.getElementById('btn-reset-blank-event'),
    linkParticipantView: document.getElementById('link-participant-view'),
    countBeersTab: document.getElementById('count-beers-tab'),

    // Tabs
    tabButtons: document.querySelectorAll('.tab-btn'),
    tabPanes: document.querySelectorAll('.tab-pane'),

    // Live Tab
    roundStepperStrip: document.getElementById('round-stepper-strip'),
    hostRoundBadge: document.getElementById('host-round-badge'),
    hostBeerImg: document.getElementById('host-beer-img'),
    hostBeerName: document.getElementById('host-beer-name'),
    hostBeerBrewery: document.getElementById('host-beer-brewery'),
    hostBeerMeta: document.getElementById('host-beer-meta'),
    labelRatingsProgress: document.getElementById('label-ratings-progress'),
    barRatingsProgress: document.getElementById('bar-ratings-progress'),
    btnHostPrevRound: document.getElementById('btn-host-prev-round'),
    btnHostNextRound: document.getElementById('btn-host-next-round'),
    btnHostReveal: document.getElementById('btn-host-reveal'),
    pendingWarning: document.getElementById('pending-warning'),
    countRoster: document.getElementById('count-roster'),
    participantRosterList: document.getElementById('participant-roster-list'),

    // QR Tab
    hostQrImg: document.getElementById('host-qr-img'),
    inputJoinUrl: document.getElementById('input-join-url'),
    btnCopyJoinUrl: document.getElementById('btn-copy-join-url'),
    btnShareJoinUrl: document.getElementById('btn-share-join-url'),
    crostiniIpNotice: document.getElementById('crostini-ip-notice'),

    // Lineup & Event Tab
    editEventTitle: document.getElementById('edit-event-title'),
    editEventTheme: document.getElementById('edit-event-theme'),
    editEventDate: document.getElementById('edit-event-date'),
    btnSaveEventDetails: document.getElementById('btn-save-event-details'),
    lineupTableContainer: document.getElementById('lineup-table-container'),
    btnAddBeer: document.getElementById('btn-add-beer'),
    addBeerName: document.getElementById('add-beer-name'),
    addBeerBrewery: document.getElementById('add-beer-brewery'),
    addBeerStyle: document.getElementById('add-beer-style'),
    addBeerAbv: document.getElementById('add-beer-abv'),
    addBeerImg: document.getElementById('add-beer-img'),
    addBeerNotes: document.getElementById('add-beer-notes'),

    // Results Tab
    btnReHideReveal: document.getElementById('btn-re-hide-reveal'),
    hostSuperlativesGrid: document.getElementById('host-superlatives-grid'),
    hostRankedBeersList: document.getElementById('host-ranked-beers-list'),

    // Toast
    toast: document.getElementById('toast-notification')
  };

  function init() {
    setupTabs();
    setupEventListeners();
    fetchLanInfo();
    loadHostState();
    connectSSE();
  }

  function showToast(msg) {
    if (!els.toast) return;
    els.toast.textContent = msg;
    els.toast.classList.add('visible');
    if (state.toastTimer) clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => {
      els.toast.classList.remove('visible');
    }, 2600);
  }

  function setupTabs() {
    els.tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        els.tabButtons.forEach(b => b.classList.remove('active'));
        els.tabPanes.forEach(p => p.style.display = 'none');

        btn.classList.add('active');
        const targetId = btn.dataset.tab;
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.style.display = 'block';

        if (targetId === 'tab-results') {
          renderHostResults();
        }
      });
    });
  }

  function setupEventListeners() {
    els.btnHostNextRound.addEventListener('click', handleNextRound);
    els.btnHostPrevRound.addEventListener('click', handlePrevRound);
    els.btnHostReveal.addEventListener('click', handleReveal);
    els.btnReHideReveal.addEventListener('click', handleReLock);

    if (els.btnLoadSampleEvent) {
      els.btnLoadSampleEvent.addEventListener('click', handleLoadSampleEvent);
    }

    if (els.btnResetBlankEvent) {
      els.btnResetBlankEvent.addEventListener('click', handleResetBlankEvent);
    }

    if (els.editEventDate) {
      els.editEventDate.addEventListener('click', () => {
        if (typeof els.editEventDate.showPicker === 'function') {
          try {
            els.editEventDate.showPicker();
          } catch (_) {
            // Ignore if already open or unsupported
          }
        }
      });
    }

    els.btnCopyJoinUrl.addEventListener('click', () => {
      els.inputJoinUrl.select();
      navigator.clipboard.writeText(els.inputJoinUrl.value);
      showToast('Join link copied to clipboard');
    });

    if (els.btnShareJoinUrl) {
      els.btnShareJoinUrl.addEventListener('click', async () => {
        const shareUrl = els.inputJoinUrl.value.trim() || `${window.location.origin}/join`;
        const eventTitle = (state.eventData && state.eventData.title) ? state.eventData.title : 'Beer Club';
        const shareData = {
          title: `${eventTitle} — Beer Club`,
          text: `Join our "${eventTitle}" blind beer tasting flight!`,
          url: shareUrl
        };
        if (navigator.share) {
          try {
            await navigator.share(shareData);
          } catch (err) {
            if (err && err.name !== 'AbortError') {
              navigator.clipboard.writeText(shareUrl);
              showToast('Join link copied to clipboard');
            }
          }
        } else {
          navigator.clipboard.writeText(shareUrl);
          showToast('Join link copied to clipboard (native share menu requires mobile device)');
        }
      });
    }

    els.inputJoinUrl.addEventListener('input', () => {
      const val = els.inputJoinUrl.value.trim();
      if (val) {
        els.hostQrImg.src = `/api/qrcode?text=${encodeURIComponent(val)}`;
      }
    });

    if (els.btnSaveEventDetails) {
      els.btnSaveEventDetails.addEventListener('click', handleSaveEventDetails);
    }

    els.btnAddBeer.addEventListener('click', handleAddBeer);
  }

  async function handleLoadSampleEvent() {
    if (!confirm('Reset the app to the "Fall Brews" Demo Event (6 beers)? This will reset the lineup, participants, and ratings so you can do a fresh dry run.')) {
      return;
    }
    try {
      const res = await fetch(`/api/events/${state.eventId}/reset_sample`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (res.ok) {
        await loadHostState();
        showToast('Loaded "Fall Brews" Demo Event!');
      }
    } catch (err) {
      console.error('Load sample event failed:', err);
    }
  }

  async function handleResetBlankEvent() {
    if (!confirm('Start a brand-new blank event? This will wipe all current beers, participants, and ratings so you can set up an event from scratch.')) {
      return;
    }
    try {
      const res = await fetch(`/api/events/${state.eventId}/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (res.ok) {
        await loadHostState();
        document.querySelector('[data-tab="tab-lineup"]').click();
        if (els.editEventTitle) els.editEventTitle.focus();
        showToast('Started a blank event — enter your theme and add beers!');
      }
    } catch (err) {
      console.error('Reset event failed:', err);
    }
  }

  async function fetchLanInfo() {
    try {
      const res = await fetch('/api/info');
      const data = await res.json();
      if (data.lan_ip && data.lan_ip !== '127.0.0.1') {
        state.lanIp = data.lan_ip;
      }
      updateQrCode();
    } catch (_) {
      updateQrCode();
    }
  }

  function updateQrCode() {
    const port = window.location.port ? `:${window.location.port}` : '';
    const host = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && state.lanIp !== '127.0.0.1'
      ? state.lanIp
      : window.location.hostname;

    const joinUrl = `${window.location.protocol}//${host}${port}/join`;
    if (document.activeElement !== els.inputJoinUrl) {
      els.inputJoinUrl.value = joinUrl;
      els.hostQrImg.src = `/api/qrcode?text=${encodeURIComponent(joinUrl)}`;
    }
    els.linkParticipantView.href = `/join`;

    if (els.crostiniIpNotice) {
      els.crostiniIpNotice.style.display = host.startsWith('100.115.92.') ? 'block' : 'none';
    }
  }

  async function loadHostState() {
    try {
      const res = await fetch(`/api/events/${state.eventId}/host_state`);
      if (!res.ok) throw new Error('Host state fetch failed');
      const data = await res.json();

      const wasFirstLoad = (state.eventData === null);
      if (data.event && data.event.id) {
        state.eventId = data.event.id;
      }
      state.eventData = data.event;
      state.beers = data.beers;
      state.participants = data.participants;
      state.participantStatuses = data.participant_statuses || [];
      state.currentRound = data.event.current_beer_index;
      state.analytics = data.analytics;

      renderHeader();
      updateQrCode();
      renderRoundStepper();
      renderLiveRound();
      renderRoster();
      renderLineup();
      renderHostResults();

      // If starting from a fresh blank event on first load, jump directly to Flight & Event Setup tab
      if (wasFirstLoad && state.beers.length === 0) {
        document.querySelector('[data-tab="tab-lineup"]').click();
      }
    } catch (err) {
      console.error('Failed to load host state:', err);
    }
  }

  function renderHeader() {
    if (!state.eventData) return;
    els.hostEventTitle.textContent = state.eventData.title;
    els.hostEventTheme.textContent = state.eventData.theme || 'Blind Tasting Flight';
    els.countBeersTab.textContent = state.beers.length;

    // Populate event editor inputs if not currently focused
    if (els.editEventTitle && document.activeElement !== els.editEventTitle) {
      els.editEventTitle.value = state.eventData.title || '';
    }
    if (els.editEventTheme && document.activeElement !== els.editEventTheme) {
      els.editEventTheme.value = state.eventData.theme || '';
    }
    if (els.editEventDate && document.activeElement !== els.editEventDate) {
      els.editEventDate.value = state.eventData.date || '';
    }

    if (state.eventData.status === 'revealed') {
      els.badgeHostStatus.className = 'badge badge-amber';
      els.badgeHostStatus.textContent = 'Flight Revealed';
      els.btnHostReveal.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>
        </svg>
        View Results
      `;
    } else {
      els.badgeHostStatus.className = 'badge badge-emerald';
      els.badgeHostStatus.textContent = 'Blind Tasting Live';
      els.btnHostReveal.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>
        </svg>
        Reveal All Beers
      `;
    }
  }

  function renderRoundStepper() {
    if (!els.roundStepperStrip) return;
    els.roundStepperStrip.innerHTML = '';
    state.beers.forEach(b => {
      const pill = document.createElement('button');
      pill.className = 'round-step-pill' + (b.order_num === state.currentRound ? ' active' : '');
      pill.innerHTML = `
        <div class="round-step-num">Round ${b.order_num}</div>
        <div class="round-step-name">${b.name}</div>
      `;
      pill.addEventListener('click', () => updateRound(b.order_num));
      els.roundStepperStrip.appendChild(pill);
    });
  }

  function renderLiveRound() {
    const total = state.beers.length;
    if (total === 0) {
      els.hostRoundBadge.textContent = 'Setup Mode (0 Beers)';
      els.hostBeerName.textContent = 'No Beers in Flight Yet';
      els.hostBeerBrewery.textContent = 'Open the "Flight & Event" tab to add your beers';
      els.hostBeerMeta.textContent = 'Once you add beers to the lineup, they will appear here for live pouring.';
      els.hostBeerImg.src = 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 fill=%22%23141418%22/><text x=%2250%22 y=%2266%22 text-anchor=%22middle%22 font-size=%2248%22>🍺</text></svg>';
      els.labelRatingsProgress.textContent = '0 / 0 (0%)';
      els.barRatingsProgress.style.width = '0%';
      els.pendingWarning.style.display = 'none';
      els.btnHostPrevRound.disabled = true;
      els.btnHostNextRound.disabled = true;
      els.btnHostReveal.disabled = true;
      return;
    }

    els.btnHostNextRound.disabled = false;
    els.btnHostReveal.disabled = false;
    els.hostRoundBadge.textContent = `Round ${state.currentRound} of ${total}`;

    const currentBeer = state.beers.find(b => b.order_num === state.currentRound) || state.beers[0];
    if (currentBeer) {
      els.hostBeerName.textContent = currentBeer.name;
      els.hostBeerBrewery.textContent = currentBeer.brewery;
      const metaParts = [];
      if (currentBeer.style) metaParts.push(currentBeer.style);
      if (currentBeer.abv) metaParts.push(`${currentBeer.abv}% ABV`);
      if (currentBeer.notes) metaParts.push(currentBeer.notes);
      els.hostBeerMeta.textContent = metaParts.join(' • ');
      els.hostBeerImg.src = currentBeer.image_url || 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 fill=%22%23141418%22/><text x=%2250%22 y=%2266%22 text-anchor=%22middle%22 font-size=%2248%22>🍺</text></svg>';
    }

    const totalParticipants = state.participantStatuses.length;
    const ratedCount = state.participantStatuses.filter(p => p.has_rated).length;
    const pct = totalParticipants > 0 ? Math.round((ratedCount / totalParticipants) * 100) : 0;

    els.labelRatingsProgress.textContent = `${ratedCount} / ${totalParticipants} (${pct}%)`;
    els.barRatingsProgress.style.width = `${pct}%`;

    if (totalParticipants > 0 && ratedCount < totalParticipants) {
      els.pendingWarning.style.display = 'block';
    } else {
      els.pendingWarning.style.display = 'none';
    }

    els.btnHostPrevRound.disabled = (state.currentRound <= 1);
  }

  function renderRoster() {
    els.countRoster.textContent = state.participantStatuses.length;
    els.participantRosterList.innerHTML = '';

    if (state.participantStatuses.length === 0) {
      els.participantRosterList.innerHTML = `
        <div style="text-align: center; padding: 28px 12px; color: var(--text-muted); font-size: 0.85rem;">
          No tasters connected yet.<br>Open the <strong>QR &amp; Invites</strong> tab so guests can scan in.
        </div>
      `;
      return;
    }

    state.participantStatuses.forEach(p => {
      const item = document.createElement('div');
      item.className = 'roster-item';

      const statusBadge = p.has_rated
        ? `<span class="badge badge-emerald">${p.rating.toFixed(2)} ★</span>`
        : `<span class="badge badge-amber">Tasting…</span>`;

      const noteSnippet = (p.has_rated && p.notes && p.notes.trim())
        ? `<div style="font-size: 0.78rem; color: var(--text-secondary); font-style: italic; margin-top: 2px;">"${escapeHtml(p.notes.trim())}"</div>`
        : '';

      item.innerHTML = `
        <div class="roster-name-group" style="align-items: flex-start;">
          <span style="font-size: 1.25rem; line-height: 1.2;">${p.avatar}</span>
          <div>
            <div>${escapeHtml(p.name)}</div>
            ${noteSnippet}
          </div>
        </div>
        <div style="flex-shrink: 0;">${statusBadge}</div>
      `;
      els.participantRosterList.appendChild(item);
    });
  }

  function renderLineup() {
    els.lineupTableContainer.innerHTML = '';
    if (state.beers.length === 0) {
      els.lineupTableContainer.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem;">No beers in this flight yet.</p>';
      return;
    }

    state.beers.forEach((b, idx) => {
      const row = document.createElement('div');
      row.className = 'history-item';
      row.style.cursor = 'default';
      row.innerHTML = `
        <div class="history-item-left">
          <div class="history-round-num">#${b.order_num}</div>
          ${b.image_url ? `<img src="${b.image_url}" style="width: 44px; height: 44px; border-radius: 8px; object-fit: cover; border: 1px solid var(--border-subtle);">` : ''}
          <div style="min-width: 0;">
            <div style="font-weight: 700; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${b.name}</div>
            <div style="font-size: 0.78rem; color: var(--amber-400);">${b.brewery}${b.style ? ' • ' + b.style : ''}${b.abv ? ' • ' + b.abv + '%' : ''}</div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
          <button class="btn btn-secondary btn-icon-only btn-move-up" title="Move Up" ${idx === 0 ? 'disabled' : ''}>↑</button>
          <button class="btn btn-secondary btn-icon-only btn-move-down" title="Move Down" ${idx === state.beers.length - 1 ? 'disabled' : ''}>↓</button>
          <button class="btn btn-secondary btn-icon-only btn-delete-beer" title="Remove Beer" style="color: var(--rose-400);">✕</button>
        </div>
      `;

      row.querySelector('.btn-move-up').addEventListener('click', () => moveBeer(b.id, 'up'));
      row.querySelector('.btn-move-down').addEventListener('click', () => moveBeer(b.id, 'down'));
      row.querySelector('.btn-delete-beer').addEventListener('click', async () => {
        if (confirm(`Remove "${b.name}" from the lineup?`)) {
          await deleteBeer(b.id);
        }
      });

      els.lineupTableContainer.appendChild(row);
    });
  }

  async function handleSaveEventDetails() {
    const title = els.editEventTitle.value.trim();
    const theme = els.editEventTheme.value.trim();
    const date = els.editEventDate.value.trim();
    if (!title) {
      showToast('Event title cannot be empty');
      return;
    }
    try {
      const res = await fetch(`/api/events/${state.eventId}/details`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, theme, date })
      });
      if (res.ok) {
        await loadHostState();
        showToast('Event details updated');
      }
    } catch (err) {
      console.error('Save event details error:', err);
    }
  }

  async function moveBeer(beerId, direction) {
    try {
      const res = await fetch(`/api/beers/${beerId}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction })
      });
      if (res.ok) {
        await loadHostState();
      }
    } catch (err) {
      console.error('Move beer error:', err);
    }
  }

  async function handleNextRound() {
    if (state.currentRound < state.beers.length) {
      await updateRound(state.currentRound + 1);
    } else {
      handleReveal();
    }
  }

  async function handlePrevRound() {
    if (state.currentRound > 1) {
      await updateRound(state.currentRound - 1);
    }
  }

  async function updateRound(roundNum) {
    try {
      const res = await fetch(`/api/events/${state.eventId}/round`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_beer_index: roundNum })
      });
      if (res.ok) {
        state.currentRound = roundNum;
        await loadHostState();
        showToast(`Switched room to Round #${roundNum}`);
      }
    } catch (err) {
      console.error('Update round failed:', err);
    }
  }

  async function handleReveal() {
    if (state.eventData && state.eventData.status === 'revealed') {
      document.querySelector('[data-tab="tab-results"]').click();
      return;
    }
    if (confirm('Unmask all beers and broadcast final results to every participant?')) {
      try {
        const res = await fetch(`/api/events/${state.eventId}/reveal`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        if (res.ok) {
          await loadHostState();
          document.querySelector('[data-tab="tab-results"]').click();
          showToast('All beers revealed to the room!');
        }
      } catch (err) {
        console.error('Reveal failed:', err);
      }
    }
  }

  async function handleReLock() {
    await fetch(`/api/events/${state.eventId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'active' })
    });
    await loadHostState();
    document.querySelector('[data-tab="tab-live"]').click();
    showToast('Returned to blind tasting mode');
  }

  async function handleAddBeer() {
    const name = els.addBeerName.value.trim();
    const brewery = els.addBeerBrewery.value.trim();
    if (!name || !brewery) {
      showToast('Beer Name and Brewery are required');
      return;
    }

    try {
      const res = await fetch(`/api/events/${state.eventId}/beers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          brewery: brewery,
          style: els.addBeerStyle.value.trim(),
          abv: parseFloat(els.addBeerAbv.value) || 0.0,
          image_url: els.addBeerImg.value.trim(),
          notes: els.addBeerNotes.value.trim()
        })
      });

      if (res.ok) {
        els.addBeerName.value = '';
        els.addBeerBrewery.value = '';
        els.addBeerStyle.value = '';
        els.addBeerAbv.value = '';
        els.addBeerImg.value = '';
        els.addBeerNotes.value = '';
        await loadHostState();
        showToast(`Added "${name}" to flight`);
      }
    } catch (err) {
      console.error('Add beer failed:', err);
    }
  }

  async function deleteBeer(beerId) {
    try {
      const res = await fetch(`/api/beers/${beerId}`, { method: 'DELETE' });
      if (res.ok) {
        await loadHostState();
        showToast('Removed beer from flight');
      }
    } catch (err) {
      console.error('Delete beer failed:', err);
    }
  }

  function renderHostResults() {
    if (!state.analytics) return;
    const a = state.analytics;

    els.hostSuperlativesGrid.innerHTML = '';
    const superList = Object.values(a.superlatives || {});
    superList.forEach(s => {
      const card = document.createElement('div');
      card.className = 'superlative-card';
      card.innerHTML = `
        <div class="superlative-header">
          <div class="superlative-title">${s.title}</div>
          <div class="superlative-badge">${s.value}</div>
        </div>
        <div class="superlative-name">${s.name}</div>
        <div class="superlative-desc">${s.subtitle}</div>
      `;
      els.hostSuperlativesGrid.appendChild(card);
    });

    els.hostRankedBeersList.innerHTML = '';
    const ranked = a.ranked_beers || [];
    if (ranked.length === 0) {
      els.hostRankedBeersList.innerHTML = `
        <div class="card" style="text-align: center; color: var(--text-muted);">
          No ratings submitted yet. Scores and histograms will populate here as participants rate each round.
        </div>
      `;
      return;
    }

    ranked.forEach(item => {
      const card = document.createElement('div');
      card.className = 'beer-reveal-card';

      const notesList = item.notes_list || [];
      let notesHtml = '';
      if (notesList.length > 0) {
        notesHtml = `
          <div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border-subtle);">
            <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px;">Participant Blind Tasting Notes (${notesList.length})</div>
            ${notesList.map(n => `
              <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; padding: 8px 12px; background: rgba(255, 255, 255, 0.03); border-radius: var(--radius-sm); margin-bottom: 6px;">
                <div style="font-size: 0.85rem; color: var(--text-secondary);">
                  <strong style="color: var(--text-primary);">${escapeHtml(n.avatar)} ${escapeHtml(n.name)}:</strong> "${escapeHtml(n.notes)}"
                </div>
                <span class="badge badge-subtle" style="flex-shrink: 0; font-family: var(--font-mono);">${n.rating.toFixed(2)} ★</span>
              </div>
            `).join('')}
          </div>
        `;
      }

      card.innerHTML = `
        <div class="beer-reveal-header">
          <div class="beer-rank-badge ${item.rank === 1 ? 'top-rank' : ''}">#${item.rank}</div>
          ${item.image_url ? `<img src="${item.image_url}" class="beer-image" alt="${item.name}">` : ''}
          <div class="beer-meta">
            <div class="beer-title">${item.name}</div>
            <div class="beer-brewery">${item.brewery}</div>
            <div class="beer-subdetails">Poured as Beer #${item.order_num} • ${item.count} ${item.count === 1 ? 'rating' : 'ratings'}</div>
          </div>
        </div>

        <div class="score-comparison-row">
          <div class="score-col">
            <div class="score-col-label">Club Average</div>
            <div class="score-col-val">${item.average.toFixed(2)} ★</div>
          </div>
          <div class="score-col">
            <div class="score-col-label">Spread (Std Dev)</div>
            <div class="score-col-val" style="color: var(--text-secondary);">±${item.std_dev.toFixed(2)}</div>
          </div>
          <div class="score-col">
            <div class="score-col-label">Min – Max</div>
            <div class="score-col-val" style="color: var(--text-primary); font-size: 1rem;">${item.min !== null ? item.min.toFixed(2) : '—'} – ${item.max !== null ? item.max.toFixed(2) : '—'}</div>
          </div>
        </div>

        <div class="histogram-container">
          <div class="histogram-header">
            <span>Club Rating Distribution (1.00 – 5.00)</span>
          </div>
          ${renderHistogramSVG(item.histogram)}
        </div>
        ${notesHtml}
      `;
      els.hostRankedBeersList.appendChild(card);
    });
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderHistogramSVG(histData) {
    if (!histData) return '';
    const keys = Object.keys(histData).sort((a, b) => parseFloat(a) - parseFloat(b));
    const counts = keys.map(k => histData[k]);
    const maxCount = Math.max(...counts, 1);

    const svgWidth = 620;
    const svgHeight = 118;
    const paddingX = 16;
    const paddingBottom = 22;
    const paddingTop = 20;
    const usableHeight = svgHeight - paddingBottom - paddingTop;
    const stepWidth = (svgWidth - paddingX * 2) / keys.length;
    const barWidth = Math.max(10, Math.floor(stepWidth - 6));

    let barsSvg = '';
    keys.forEach((key, idx) => {
      const valNum = parseFloat(key);
      const count = histData[key];
      const x = Math.round(paddingX + idx * stepWidth + (stepWidth - barWidth) / 2);
      const barHeight = count > 0 ? Math.max(8, Math.round((count / maxCount) * usableHeight)) : 3;
      const y = svgHeight - paddingBottom - barHeight;
      const isMajor = Number.isInteger(valNum);

      barsSvg += `
        <rect class="hist-track" x="${x}" y="${paddingTop}" width="${barWidth}" height="${usableHeight}" rx="3" />
        <rect class="hist-bar" x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="3" />
        ${count > 0 ? `<text class="hist-val" x="${x + barWidth / 2}" y="${y - 5}">${count}</text>` : ''}
        ${isMajor ? `<text class="hist-label" x="${x + barWidth / 2}" y="${svgHeight - 5}">${valNum.toFixed(1)}</text>` : ''}
      `;
    });

    return `
      <svg class="histogram-svg" viewBox="0 0 ${svgWidth} ${svgHeight}">
        ${barsSvg}
      </svg>
    `;
  }

  function connectSSE() {
    if (state.sse) state.sse.close();
    state.sse = new EventSource(`/api/events/${state.eventId}/stream`);

    state.sse.addEventListener('participant_joined', () => loadHostState());
    state.sse.addEventListener('rating_update', () => loadHostState());
    state.sse.addEventListener('round_change', (e) => {
      const data = JSON.parse(e.data);
      state.currentRound = data.current_round;
      loadHostState();
    });
    state.sse.addEventListener('reveal', () => loadHostState());
    state.sse.addEventListener('status_change', () => loadHostState());
    state.sse.addEventListener('lineup_change', () => loadHostState());
    state.sse.addEventListener('event_reset', () => loadHostState());

    state.sse.onerror = () => {
      setTimeout(connectSSE, 3000);
    };
  }

  document.addEventListener('DOMContentLoaded', init);
})();
