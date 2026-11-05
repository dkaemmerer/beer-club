/**
 * Beer Club — Participant Application Logic
 * Mobile-first reactive state management with Server-Sent Events (SSE)
 * Features a bespoke tactile 0.25-increment slider, live SVG pint animation,
 * and a post-submission live Tasting Room Status screen.
 */

(function() {
  'use strict';

  const AVATARS = ['🍺', '🍻', '🥨', '🌾', '👑', '🦁', '🕶️', '🍕', '🌭', '🎯', '🔥', '🏆'];

  const state = {
    eventId: getQueryParam('event') || 'craft-showdown',
    participantId: localStorage.getItem('bc_participant_id') || null,
    participantName: localStorage.getItem('bc_participant_name') || '',
    participantAvatar: localStorage.getItem('bc_participant_avatar') || '🍺',
    currentHostRound: 1,
    viewingBeerIndex: 1,
    eventData: null,
    beers: [],
    myRatings: {},
    roundStatuses: {},
    isRevealed: false,
    isEditingRating: false,
    selectedRating: 3.75,
    sse: null,
    toastTimer: null
  };

  function getQueryParam(key) {
    const params = new URLSearchParams(window.location.search);
    return params.get(key);
  }

  // DOM Elements
  const els = {
    eventTitleDisplay: document.getElementById('event-title-display'),
    eventThemeDisplay: document.getElementById('event-theme-display'),
    btnOpenDrawer: document.getElementById('btn-open-drawer'),
    drawerRoundLabel: document.getElementById('drawer-round-label'),
    participantBadge: document.getElementById('participant-badge'),
    
    // Views
    viewJoin: document.getElementById('view-join'),
    viewTasting: document.getElementById('view-tasting'),
    viewWaiting: document.getElementById('view-waiting'),
    viewReveal: document.getElementById('view-reveal'),
    
    // Join
    inputName: document.getElementById('input-participant-name'),
    avatarGrid: document.getElementById('avatar-grid'),
    btnJoin: document.getElementById('btn-join-event'),

    // Tasting & Slider
    badgeRoundIndicator: document.getElementById('badge-round-indicator'),
    labelViewingMode: document.getElementById('label-viewing-mode'),
    blindBeerTitle: document.getElementById('blind-beer-title'),
    ratingValDisplay: document.getElementById('rating-val-display'),
    ratingVerdictPill: document.getElementById('rating-verdict-pill'),
    pintLiquidRect: document.getElementById('pint-liquid-rect'),
    pintFoamRect: document.getElementById('pint-foam-rect'),
    ratingSlider: document.getElementById('rating-slider'),
    sliderScale: document.getElementById('slider-scale'),
    inputNotes: document.getElementById('input-notes'),
    btnSubmitRating: document.getElementById('btn-submit-rating'),
    bannerCatchupMode: document.getElementById('banner-catchup-mode'),
    btnReturnActiveRound: document.getElementById('btn-return-active-round'),

    // Post-Submission Waiting View
    waitingRoundBadge: document.getElementById('waiting-round-badge'),
    waitingBeerTitle: document.getElementById('waiting-beer-title'),
    waitingMyScore: document.getElementById('waiting-my-score'),
    waitingMyNotes: document.getElementById('waiting-my-notes'),
    btnEditCurrentRating: document.getElementById('btn-edit-current-rating'),
    btnWaitingReturnLive: document.getElementById('btn-waiting-return-live'),
    waitingProgressLabel: document.getElementById('waiting-progress-label'),
    waitingProgressBar: document.getElementById('waiting-progress-bar'),
    waitingRosterList: document.getElementById('waiting-roster-list'),

    // Drawer
    drawerBackdrop: document.getElementById('drawer-backdrop'),
    drawerAllRounds: document.getElementById('drawer-all-rounds'),
    btnCloseDrawer: document.getElementById('btn-close-drawer'),
    drawerBeersList: document.getElementById('drawer-beers-list'),

    // Reveal
    personalScorecard: document.getElementById('personal-scorecard'),
    myAvgBadge: document.getElementById('my-avg-badge'),
    myTopBeerName: document.getElementById('my-top-beer-name'),
    myTopBeerScore: document.getElementById('my-top-beer-score'),
    myLowBeerName: document.getElementById('my-low-beer-name'),
    myLowBeerScore: document.getElementById('my-low-beer-score'),
    superlativesGrid: document.getElementById('superlatives-grid'),
    revealBeersList: document.getElementById('reveal-beers-list'),

    // Toast
    toast: document.getElementById('toast-notification')
  };

  function init() {
    setupAvatarGrid();
    setupSliderTicks();
    setupEventListeners();

    if (state.participantId && state.participantName) {
      updateParticipantBadge();
      loadStateAndConnect();
    } else {
      showJoinView();
      fetchBasicEventMeta();
    }
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

  function setupAvatarGrid() {
    els.avatarGrid.innerHTML = '';
    AVATARS.forEach(emoji => {
      const div = document.createElement('div');
      div.className = 'avatar-option' + (emoji === state.participantAvatar ? ' selected' : '');
      div.textContent = emoji;
      div.addEventListener('click', () => {
        document.querySelectorAll('.avatar-option').forEach(el => el.classList.remove('selected'));
        div.classList.add('selected');
        state.participantAvatar = emoji;
      });
      els.avatarGrid.appendChild(div);
    });
  }

  function setupSliderTicks() {
    if (!els.sliderScale) return;
    els.sliderScale.innerHTML = '';
    for (let i = 0; i <= 16; i++) {
      const val = 1.0 + i * 0.25;
      const isMajor = Number.isInteger(val);
      const tick = document.createElement('div');
      tick.className = 'scale-tick' + (isMajor ? ' major' : '');
      tick.dataset.val = val.toFixed(2);
      tick.innerHTML = `
        <div class="scale-tick-line"></div>
        ${isMajor ? `<span class="scale-tick-label">${val.toFixed(0)}</span>` : ''}
      `;
      els.sliderScale.appendChild(tick);
    }
  }

  function setupEventListeners() {
    els.btnJoin.addEventListener('click', handleJoin);
    els.inputName.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleJoin();
    });

    // Tactile Slider
    els.ratingSlider.addEventListener('input', (e) => {
      setRating(parseFloat(e.target.value));
    });

    // Submit Rating
    els.btnSubmitRating.addEventListener('click', submitCurrentRating);

    // Waiting Screen Controls
    els.btnEditCurrentRating.addEventListener('click', () => {
      state.isEditingRating = true;
      renderCurrentBeerScreen();
    });

    els.btnWaitingReturnLive.addEventListener('click', () => {
      state.viewingBeerIndex = state.currentHostRound;
      state.isEditingRating = false;
      renderCurrentBeerScreen();
    });

    // Drawer Controls
    els.btnOpenDrawer.addEventListener('click', openDrawer);
    els.btnCloseDrawer.addEventListener('click', closeDrawer);
    els.drawerBackdrop.addEventListener('click', closeDrawer);

    // Return to live round
    els.btnReturnActiveRound.addEventListener('click', () => {
      state.viewingBeerIndex = state.currentHostRound;
      state.isEditingRating = false;
      renderCurrentBeerScreen();
    });
  }

  function getVerdictLabel(score) {
    if (score >= 4.75) return 'World-Class Grail';
    if (score >= 4.25) return 'Standout Pour';
    if (score >= 3.75) return 'Really Enjoyable';
    if (score >= 3.25) return 'Solid Craft Pour';
    if (score >= 2.75) return 'Decent & Drinkable';
    if (score >= 2.00) return 'Underwhelming';
    return 'Drain Pour';
  }

  function setRating(val) {
    state.selectedRating = Math.max(1.0, Math.min(5.0, Math.round(val * 4) / 4));
    const formatted = state.selectedRating.toFixed(2);
    els.ratingValDisplay.textContent = formatted;
    els.ratingSlider.value = state.selectedRating;

    const pct = ((state.selectedRating - 1.0) / 4.0) * 100;
    els.ratingSlider.style.setProperty('--slider-pct', `${pct}%`);

    if (els.ratingVerdictPill) {
      els.ratingVerdictPill.textContent = getVerdictLabel(state.selectedRating);
    }

    if (els.pintLiquidRect && els.pintFoamRect) {
      const fillRatio = (state.selectedRating - 1.0) / 4.0;
      const minHeight = 12;
      const maxHeight = 54;
      const liquidHeight = minHeight + fillRatio * (maxHeight - minHeight);
      const liquidY = 74 - liquidHeight;
      els.pintLiquidRect.setAttribute('y', liquidY.toFixed(1));
      els.pintLiquidRect.setAttribute('height', liquidHeight.toFixed(1));
      els.pintFoamRect.setAttribute('y', (liquidY - 5).toFixed(1));
    }

    if (els.sliderScale) {
      els.sliderScale.querySelectorAll('.scale-tick.major').forEach(tick => {
        const tickVal = parseFloat(tick.dataset.val);
        if (Math.abs(tickVal - state.selectedRating) < 0.35) {
          tick.classList.add('active');
        } else {
          tick.classList.remove('active');
        }
      });
    }
  }

  async function fetchBasicEventMeta() {
    try {
      const res = await fetch(`/api/events/${encodeURIComponent(state.eventId)}/state`);
      if (res.ok) {
        const data = await res.json();
        if (data.event) {
          state.eventId = data.event.id || state.eventId;
          els.eventTitleDisplay.textContent = data.event.title;
          els.eventThemeDisplay.textContent = data.event.theme || 'Blind Tasting';
        }
      }
    } catch (_) {}
  }

  function showJoinView() {
    els.viewJoin.style.display = 'block';
    els.viewTasting.style.display = 'none';
    els.viewWaiting.style.display = 'none';
    els.viewReveal.style.display = 'none';
    els.btnOpenDrawer.style.display = 'none';
    els.participantBadge.style.display = 'none';
  }

  function updateParticipantBadge() {
    els.participantBadge.style.display = 'inline-flex';
    els.participantBadge.textContent = `${state.participantAvatar} ${state.participantName}`;
    els.btnOpenDrawer.style.display = state.isRevealed ? 'none' : 'inline-flex';
  }

  async function handleJoin() {
    const name = els.inputName.value.trim();
    if (!name) {
      showToast('Please enter your display name to join');
      els.inputName.focus();
      return;
    }

    els.btnJoin.disabled = true;
    try {
      const res = await fetch(`/api/events/${state.eventId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          avatar: state.participantAvatar,
          participant_id: state.participantId
        })
      });

      const data = await res.json();
      if (data.participant) {
        state.participantId = data.participant.id;
        state.participantName = data.participant.name;
        state.participantAvatar = data.participant.avatar;

        localStorage.setItem('bc_participant_id', state.participantId);
        localStorage.setItem('bc_participant_name', state.participantName);
        localStorage.setItem('bc_participant_avatar', state.participantAvatar);

        updateParticipantBadge();
        loadStateAndConnect();
      }
    } catch (err) {
      console.error('Join error:', err);
      showToast('Could not connect to tasting server');
    } finally {
      els.btnJoin.disabled = false;
    }
  }

  async function loadStateAndConnect() {
    await fetchState();
    connectSSE();
  }

  async function fetchState() {
    try {
      const url = `/api/events/${encodeURIComponent(state.eventId)}/state?participant_id=${encodeURIComponent(state.participantId || '')}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Event not found');
      const data = await res.json();

      if (data.event && data.event.id) {
        state.eventId = data.event.id;
      }
      state.eventData = data.event;
      state.beers = data.beers;
      state.isRevealed = data.is_revealed;
      state.currentHostRound = data.current_round;
      state.myRatings = data.my_ratings || {};
      state.roundStatuses = data.round_statuses || {};

      if (state.participantId && data.participant_registered === false) {
        state.participantId = null;
        localStorage.removeItem('bc_participant_id');
        updateHeader();
        showJoinView();
        return;
      }

      if (!state.viewingBeerIndex || state.viewingBeerIndex > state.beers.length) {
        state.viewingBeerIndex = state.currentHostRound;
      }

      updateHeader();

      if (state.isRevealed) {
        renderRevealView(data.analytics);
      } else {
        renderCurrentBeerScreen();
      }
      renderDrawerList();
    } catch (err) {
      console.error('Fetch state error:', err);
    }
  }

  function updateHeader() {
    if (state.eventData) {
      els.eventTitleDisplay.textContent = state.eventData.title;
      els.eventThemeDisplay.textContent = state.eventData.theme || 'Blind Tasting';
    }
    const ratedCount = Object.keys(state.myRatings).length;
    els.drawerRoundLabel.textContent = `${ratedCount}/${state.beers.length}`;
    if (state.participantId) {
      els.btnOpenDrawer.style.display = state.isRevealed ? 'none' : 'inline-flex';
    } else {
      els.btnOpenDrawer.style.display = 'none';
    }
    if (state.isRevealed) {
      closeDrawer();
    }
  }

  function renderCurrentBeerScreen() {
    if (state.beers.length === 0) {
      renderSliderView();
      return;
    }
    const currentBeer = state.beers.find(b => b.order_num === state.viewingBeerIndex) || state.beers[0];
    if (!currentBeer) return;

    const existing = state.myRatings[currentBeer.id];
    // If participant has already rated this round and isn't explicitly editing, show the Waiting & Room Status view!
    if (existing && !state.isEditingRating) {
      renderWaitingView(currentBeer, existing);
    } else {
      renderSliderView(currentBeer, existing);
    }
  }

  function renderSliderView(currentBeer, existing) {
    els.viewJoin.style.display = 'none';
    els.viewWaiting.style.display = 'none';
    els.viewReveal.style.display = 'none';
    els.viewTasting.style.display = 'block';

    if (state.beers.length === 0 || !currentBeer) {
      els.badgeRoundIndicator.textContent = 'Setting Up Flight';
      els.blindBeerTitle.textContent = 'Waiting for Host…';
      els.btnSubmitRating.disabled = true;
      els.btnSubmitRating.textContent = 'Waiting for First Pour';
      els.bannerCatchupMode.style.display = 'none';
      return;
    }

    els.btnSubmitRating.disabled = false;
    const isCatchup = (state.viewingBeerIndex !== state.currentHostRound);
    els.bannerCatchupMode.style.display = isCatchup ? 'block' : 'none';
    els.labelViewingMode.innerHTML = isCatchup
      ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Reviewing Round #${currentBeer.order_num}`
      : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Identity Hidden`;

    els.badgeRoundIndicator.textContent = `Round ${currentBeer.order_num} of ${state.beers.length}`;
    els.blindBeerTitle.textContent = currentBeer.name;

    if (existing) {
      setRating(existing.rating);
      els.inputNotes.value = existing.notes || '';
      els.btnSubmitRating.textContent = 'Save Updated Rating';
    } else {
      setRating(3.75);
      els.inputNotes.value = '';
      els.btnSubmitRating.textContent = 'Submit Rating';
    }
  }

  function renderWaitingView(currentBeer, myRatingObj) {
    els.viewJoin.style.display = 'none';
    els.viewTasting.style.display = 'none';
    els.viewReveal.style.display = 'none';
    els.viewWaiting.style.display = 'block';

    els.waitingRoundBadge.textContent = `Round ${currentBeer.order_num} of ${state.beers.length} Submitted`;
    els.waitingBeerTitle.textContent = currentBeer.name;
    els.waitingMyScore.textContent = `${myRatingObj.rating.toFixed(2)} ★`;

    if (myRatingObj.notes) {
      els.waitingMyNotes.style.display = 'block';
      els.waitingMyNotes.textContent = `"${myRatingObj.notes}"`;
    } else {
      els.waitingMyNotes.style.display = 'none';
    }

    const isCatchup = (state.viewingBeerIndex !== state.currentHostRound);
    els.btnWaitingReturnLive.style.display = isCatchup ? 'inline-flex' : 'none';

    // Populate Live Room Roster for this beer
    const statuses = state.roundStatuses[currentBeer.id] || [];
    const totalCount = statuses.length;
    const ratedCount = statuses.filter(s => s.has_rated).length;
    const pct = totalCount > 0 ? Math.round((ratedCount / totalCount) * 100) : 0;

    els.waitingProgressLabel.textContent = `${ratedCount} / ${totalCount} Rated`;
    els.waitingProgressBar.style.width = `${pct}%`;

    els.waitingRosterList.innerHTML = '';
    statuses.forEach(p => {
      const isMe = (p.id === state.participantId);
      const item = document.createElement('div');
      item.className = 'roster-item';
      if (isMe) {
        item.style.borderColor = 'var(--border-amber)';
        item.style.background = 'rgba(245, 158, 11, 0.07)';
      }

      let statusBadge = '';
      if (p.has_rated) {
        const scoreStr = (p.rating !== null && p.rating !== undefined) ? `${p.rating.toFixed(2)} ★` : 'Rated';
        statusBadge = `<span class="badge badge-emerald">${scoreStr}</span>`;
      } else {
        statusBadge = `<span class="badge badge-amber">Still tasting…</span>`;
      }

      item.innerHTML = `
        <div class="roster-name-group">
          <span style="font-size: 1.25rem;">${p.avatar}</span>
          <span>${p.name} ${isMe ? '<span style="color: var(--amber-400); font-size: 0.75rem; font-weight: 700;">(You)</span>' : ''}</span>
        </div>
        <div>${statusBadge}</div>
      `;
      els.waitingRosterList.appendChild(item);
    });
  }

  async function submitCurrentRating() {
    const currentBeer = state.beers.find(b => b.order_num === state.viewingBeerIndex);
    if (!currentBeer) return;

    els.btnSubmitRating.disabled = true;
    els.btnSubmitRating.textContent = 'Submitting…';

    try {
      const res = await fetch(`/api/events/${state.eventId}/rate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          participant_id: state.participantId,
          beer_id: currentBeer.id,
          rating: state.selectedRating,
          tags: [],
          notes: els.inputNotes.value.trim()
        })
      });

      const data = await res.json();
      if (data.rating) {
        state.myRatings[currentBeer.id] = data.rating;
        state.isEditingRating = false;
        await fetchState();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    } catch (err) {
      console.error('Submit rating error:', err);
      showToast('Failed to save rating — check connection');
    } finally {
      els.btnSubmitRating.disabled = false;
    }
  }

  // Drawer
  function openDrawer() {
    if (state.isRevealed) return;
    renderDrawerList();
    els.drawerBackdrop.classList.add('open');
    els.drawerAllRounds.classList.add('open');
  }

  function closeDrawer() {
    els.drawerBackdrop.classList.remove('open');
    els.drawerAllRounds.classList.remove('open');
  }

  function renderDrawerList() {
    els.drawerBeersList.innerHTML = '';
    state.beers.forEach(b => {
      const isCurrentView = (b.order_num === state.viewingBeerIndex);
      const isHostRound = (b.order_num === state.currentHostRound);
      const rating = state.myRatings[b.id];

      const item = document.createElement('div');
      item.className = 'history-item' + (isCurrentView ? ' active' : '');
      
      let badges = '';
      if (isHostRound && !state.isRevealed) {
        badges += `<span class="badge badge-subtle">Now Pouring</span> `;
      }
      if (rating) {
        badges += `<span class="badge badge-emerald">${rating.rating.toFixed(2)} ★</span>`;
      } else {
        badges += `<span class="badge badge-amber">Unrated</span>`;
      }

      item.innerHTML = `
        <div class="history-item-left">
          <div class="history-round-num">#${b.order_num}</div>
          <div>
            <div style="font-weight: 700; font-size: 0.92rem;">${b.name}</div>
            <div style="font-size: 0.76rem; color: var(--text-muted);">${b.brewery}</div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">${badges}</div>
      `;

      item.addEventListener('click', () => {
        if (state.isRevealed) return;
        state.viewingBeerIndex = b.order_num;
        // If tapping a previously rated round in the drawer, open the slider directly so they can adjust if desired
        state.isEditingRating = Boolean(state.myRatings[b.id]);
        renderCurrentBeerScreen();
        closeDrawer();
      });

      els.drawerBeersList.appendChild(item);
    });
  }

  // Reveal & Analytics
  function renderRevealView(analytics) {
    closeDrawer();
    els.btnOpenDrawer.style.display = 'none';
    els.viewJoin.style.display = 'none';
    els.viewTasting.style.display = 'none';
    els.viewWaiting.style.display = 'none';
    els.viewReveal.style.display = 'block';

    if (!analytics) return;

    let myTop = null;
    let myLow = null;
    let myScores = [];

    (state.beers || []).forEach(b => {
      const r = state.myRatings[b.id];
      if (r) {
        myScores.push(r.rating);
        if (!myTop || r.rating > myTop.rating) myTop = { beer: b, rating: r.rating };
        if (!myLow || r.rating < myLow.rating) myLow = { beer: b, rating: r.rating };
      }
    });

    if (myScores.length > 0 && els.myAvgBadge) {
      const avg = myScores.reduce((a, b) => a + b, 0) / myScores.length;
      els.myAvgBadge.textContent = `Your Avg: ${avg.toFixed(2)} ★`;
    }

    if (myTop) {
      els.myTopBeerName.textContent = myTop.beer.name;
      els.myTopBeerScore.textContent = `${myTop.rating.toFixed(2)} / 5.00 ★`;
    }
    if (myLow) {
      els.myLowBeerName.textContent = myLow.beer.name;
      els.myLowBeerScore.textContent = `${myLow.rating.toFixed(2)} / 5.00 ★`;
    }

    els.superlativesGrid.innerHTML = '';
    const superList = Object.values(analytics.superlatives || {});
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
      els.superlativesGrid.appendChild(card);
    });

    els.revealBeersList.innerHTML = '';
    const ranked = analytics.ranked_beers || [];
    ranked.forEach(item => {
      const card = document.createElement('div');
      card.className = 'beer-reveal-card' + (item.rank === 1 ? ' rank-1' : '');

      const myRatingObj = state.myRatings[item.beer_id];
      const myScore = myRatingObj?.rating;
      const myScoreText = myScore !== undefined ? `${myScore.toFixed(2)} ★` : '—';
      const myNote = myRatingObj?.notes ? myRatingObj.notes.trim() : '';
      const otherNotes = (item.notes_list || []).filter(n => n.participant_id !== state.participantId);

      let notesHtml = '';
      if (myNote || otherNotes.length > 0) {
        notesHtml = `<div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border-subtle);">`;
        if (myNote) {
          notesHtml += `
            <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: var(--radius-md); padding: 10px 14px; margin-bottom: ${otherNotes.length > 0 ? '10px' : '0'};">
              <div style="font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--emerald-400); margin-bottom: 2px;">Your Blind Tasting Note</div>
              <div style="font-size: 0.88rem; color: var(--text-primary); font-style: italic;">"${escapeHtml(myNote)}"</div>
            </div>
          `;
        }
        if (otherNotes.length > 0) {
          notesHtml += `<div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px;">Club Tasting Notes</div>`;
          otherNotes.forEach(n => {
            notesHtml += `
              <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; padding: 8px 12px; background: rgba(255, 255, 255, 0.03); border-radius: var(--radius-sm); margin-bottom: 6px;">
                <div style="font-size: 0.84rem; color: var(--text-secondary);">
                  <strong style="color: var(--text-primary);">${escapeHtml(n.avatar)} ${escapeHtml(n.name)}:</strong> "${escapeHtml(n.notes)}"
                </div>
                <span class="badge badge-subtle" style="flex-shrink: 0; font-family: var(--font-mono);">${n.rating.toFixed(2)} ★</span>
              </div>
            `;
          });
        }
        notesHtml += `</div>`;
      }

      card.innerHTML = `
        <div class="beer-reveal-header">
          <div class="beer-rank-badge ${item.rank === 1 ? 'top-rank' : ''}">#${item.rank}</div>
          ${item.image_url ? `<img src="${item.image_url}" class="beer-image" alt="${item.name}">` : ''}
          <div class="beer-meta">
            <div class="beer-title">${item.name}</div>
            <div class="beer-brewery">${item.brewery}</div>
            <div class="beer-subdetails">Poured as Beer #${item.order_num} • ${item.count} ${item.count === 1 ? 'vote' : 'votes'}</div>
          </div>
        </div>

        <div class="score-comparison-row">
          <div class="score-col">
            <div class="score-col-label">Room Avg</div>
            <div class="score-col-val">${item.average.toFixed(2)}</div>
          </div>
          <div class="score-col">
            <div class="score-col-label">Your Score</div>
            <div class="score-col-val" style="color: ${myScore !== undefined ? 'var(--emerald-400)' : 'var(--text-muted)'}">${myScoreText}</div>
          </div>
          <div class="score-col">
            <div class="score-col-label">Spread</div>
            <div class="score-col-val" style="color: var(--text-secondary);">±${item.std_dev.toFixed(2)}</div>
          </div>
        </div>

        <div class="histogram-container">
          <div class="histogram-header">
            <span>Rating Distribution</span>
            <span class="histogram-legend">
              <span><i class="legend-dot" style="background: var(--amber-500);"></i>Club</span>
              ${myScore !== undefined ? `<span><i class="legend-dot" style="background: var(--emerald-400);"></i>You</span>` : ''}
            </span>
          </div>
          ${renderHistogramSVG(item.histogram, myScore)}
        </div>
        ${notesHtml}
      `;
      els.revealBeersList.appendChild(card);
    });
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderHistogramSVG(histData, myScore) {
    if (!histData) return '';
    const keys = Object.keys(histData).sort((a, b) => parseFloat(a) - parseFloat(b));
    const counts = keys.map(k => histData[k]);
    const maxCount = Math.max(...counts, 1);

    const svgWidth = 460;
    const svgHeight = 114;
    const paddingX = 12;
    const paddingBottom = 22;
    const paddingTop = 20;
    const usableHeight = svgHeight - paddingBottom - paddingTop;
    const stepWidth = (svgWidth - paddingX * 2) / keys.length;
    const barWidth = Math.max(8, Math.floor(stepWidth - 5));

    let barsSvg = '';
    keys.forEach((key, idx) => {
      const valNum = parseFloat(key);
      const count = histData[key];
      const x = Math.round(paddingX + idx * stepWidth + (stepWidth - barWidth) / 2);
      const barHeight = count > 0 ? Math.max(8, Math.round((count / maxCount) * usableHeight)) : 3;
      const y = svgHeight - paddingBottom - barHeight;
      const isMine = (myScore !== undefined && Math.abs(valNum - myScore) < 0.01);
      const isMajor = Number.isInteger(valNum);

      barsSvg += `
        <rect class="hist-track" x="${x}" y="${paddingTop}" width="${barWidth}" height="${usableHeight}" rx="3" />
        <rect class="hist-bar ${isMine ? 'is-mine' : ''}" x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="3" />
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
    if (state.sse) {
      state.sse.close();
    }

    state.sse = new EventSource(`/api/events/${state.eventId}/stream`);

    state.sse.addEventListener('round_change', (e) => {
      const data = JSON.parse(e.data);
      state.currentHostRound = data.current_round;
      state.viewingBeerIndex = state.currentHostRound;
      state.isEditingRating = false;
      fetchState();
      showToast(`Now pouring Beer #${state.currentHostRound}`);
    });

    state.sse.addEventListener('reveal', () => {
      state.isRevealed = true;
      fetchState();
    });

    state.sse.addEventListener('status_change', () => {
      fetchState();
    });

    state.sse.addEventListener('lineup_change', () => {
      fetchState();
    });

    state.sse.addEventListener('participant_joined', () => {
      fetchState();
    });

    state.sse.addEventListener('rating_update', () => {
      fetchState();
    });

    state.sse.addEventListener('event_reset', () => {
      state.participantId = null;
      state.myRatings = {};
      state.roundStatuses = {};
      state.isEditingRating = false;
      localStorage.removeItem('bc_participant_id');
      showJoinView();
      fetchBasicEventMeta();
      showToast('Host started a new tasting event');
    });

    state.sse.onerror = () => {
      setTimeout(() => {
        if (!state.isRevealed) connectSSE();
      }, 3000);
    };
  }

  document.addEventListener('DOMContentLoaded', init);
})();
