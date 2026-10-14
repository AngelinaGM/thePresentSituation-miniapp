const tg = window.Telegram?.WebApp;
const root = document.querySelector('#app');
let token = '';
let currentInvite = new URLSearchParams(location.search).get('startapp') || tg?.initDataUnsafe?.start_param || '';
const apiUrl = path => `${window.location.protocol}//${window.location.host}${path}`;

if (tg) { tg.ready(); tg.expand(); }

const escape = value => String(value || '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));

async function api(url, options = {}) {
  const response = await fetch(apiUrl(url), {
    ...options,
    headers: { 'content-type': 'application/json', authorization: `Bearer ${token}`, ...(options.headers || {}) },
  });
  if (response.status === 204) return null;
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Something went wrong.');
  return body;
}

function message(error) { root.insertAdjacentHTML('afterbegin', `<div class="notice">${escape(error.message || error)}</div>`); }
function giftCard(gift, action = '') {
  return `<article class="card gift"><div class="gift-main"><div class="gift-title">${escape(gift.title)}</div>${gift.price ? `<div class="meta">${escape(gift.price)}</div>` : ''}${gift.note ? `<div class="meta">${escape(gift.note)}</div>` : ''}${gift.url ? `<a class="link" href="${escape(gift.url)}" target="_blank" rel="noreferrer">Open link</a>` : ''}</div>${action}</article>`;
}

async function renderHome() {
  const lists = await api('/api/wishlists/mine');
  root.innerHTML = `<h1>My wishlists</h1><p class="sub">Create a list, add gifts, and share the link with your guests.</p><form id="new-list" class="card"><input name="title" required maxlength="100" placeholder="For example, Birthday wishes"><button>Create wishlist</button></form>${lists.length ? lists.map(list => `<section class="card"><div class="row"><strong>${escape(list.title)}</strong><button class="secondary" data-open="${list.inviteToken}">Open</button></div><div class="meta">${list.gifts.length} gifts</div></section>`).join('') : '<p class="empty">Your wishlists will appear here.</p>'}`;
  document.querySelector('#new-list').onsubmit = async event => {
    event.preventDefault();
    try { const list = await api('/api/wishlists', { method: 'POST', body: JSON.stringify({ title: new FormData(event.target).get('title') }) }); currentInvite = list.inviteToken; renderOwner(list); }
    catch (error) { message(error); }
  };
  root.querySelectorAll('[data-open]').forEach(element => { element.onclick = () => { currentInvite = element.dataset.open; openInvite(); }; });
}

function renderOwner(list) {
  const invite = list.inviteUrl;
  root.innerHTML = `<button class="secondary" id="back">← My wishlists</button><h1>${escape(list.title)}</h1><p class="sub">Only you can see this view. Guest selections are intentionally hidden.</p><div class="card"><strong>Guest link</strong><p class="link">${escape(invite)}</p><button id="share">Share invite</button></div><h2>Add a gift</h2><form id="gift-form" class="card"><input name="title" required maxlength="160" placeholder="Gift name"><input name="url" type="url" placeholder="Product link (optional)"><input name="price" maxlength="60" placeholder="Price or budget (optional)"><textarea name="note" maxlength="500" placeholder="Note (optional)"></textarea><button>Add gift</button></form><h2>Gifts</h2>${list.gifts.length ? list.gifts.map(gift => giftCard(gift, `<button class="danger" data-delete="${gift.id}">Delete</button>`)).join('') : '<p class="empty">Add your first gift.</p>'}`;
  document.querySelector('#back').onclick = renderHome;
  document.querySelector('#share').onclick = () => {
    if (tg?.openTelegramLink) tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(invite)}&text=${encodeURIComponent(`My wishlist: ${list.title}`)}`);
    else navigator.clipboard.writeText(invite);
  };
  document.querySelector('#gift-form').onsubmit = async event => {
    event.preventDefault();
    try {
      const payload = Object.fromEntries(new FormData(event.target));
      Object.keys(payload).forEach(key => { if (!String(payload[key]).trim()) delete payload[key]; });
      await api(`/api/wishlists/${list.id}/gifts`, { method: 'POST', body: JSON.stringify(payload) });
      openInvite();
    } catch (error) { message(error); }
  };
  root.querySelectorAll('[data-delete]').forEach(element => { element.onclick = async () => { try { await api(`/api/gifts/${element.dataset.delete}`, { method: 'DELETE' }); openInvite(); } catch (error) { message(error); } }; });
}

function renderGuest(list) {
  root.innerHTML = `<h1>${escape(list.title)}</h1><p class="sub">Choose a gift you plan to buy. It will disappear for other guests.</p>${list.gifts.length ? list.gifts.map(gift => giftCard(gift, gift.reservedByMe ? `<button class="secondary" data-cancel="${gift.id}">Change my mind</button>` : `<button data-reserve="${gift.id}">Choose gift</button>`)).join('') : '<p class="empty">There are no available gifts right now.</p>'}`;
  root.querySelectorAll('[data-reserve]').forEach(element => { element.onclick = async () => { try { await api(`/api/gifts/${element.dataset.reserve}/reserve`, { method: 'POST', body: '{}' }); tg?.showAlert?.('Done! The organizer will not know about your choice.'); openInvite(); } catch (error) { message(error); openInvite(); } }; });
  root.querySelectorAll('[data-cancel]').forEach(element => { element.onclick = async () => { try { await api(`/api/gifts/${element.dataset.cancel}/reservation`, { method: 'DELETE' }); openInvite(); } catch (error) { message(error); } }; });
}

async function openInvite() { try { const result = await api(`/api/invites/${currentInvite}`); result.isOwner ? renderOwner(result.list) : renderGuest(result.list); } catch (error) { root.innerHTML = ''; message(error); } }
async function start() {
  try {
    if (!tg?.initData) throw new Error('Open this app through Telegram.');
    const auth = await fetch(apiUrl('/api/auth/telegram'), { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ initData: tg.initData }) });
    const body = await auth.json();
    if (!auth.ok) throw new Error(body.error);
    token = body.token;
    currentInvite ? await openInvite() : await renderHome();
  } catch (error) { console.error('Wishlist startup failed:', error); root.innerHTML = ''; message(error); }
}

start();
