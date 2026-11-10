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
function giftForm(gift = {}, submitLabel = 'Add gift') {
  return `<form id="gift-form" class="card"><input name="title" required maxlength="160" placeholder="Gift name" value="${escape(gift.title)}"><input name="url" type="url" placeholder="Product link (optional)" value="${escape(gift.url)}"><input name="price" maxlength="60" placeholder="Price or budget (optional)" value="${escape(gift.price)}"><textarea name="note" maxlength="500" placeholder="Note (optional)">${escape(gift.note)}</textarea><button>${submitLabel}</button></form>`;
}
function giftPayload(form) {
  const payload = Object.fromEntries(new FormData(form));
  Object.keys(payload).forEach(key => { if (!String(payload[key]).trim()) delete payload[key]; });
  return payload;
}

async function renderHome() {
  const [lists, shared] = await Promise.all([api('/api/wishlists/mine'), api('/api/wishlists/shared')]);
  const ownLists = lists.length ? lists.map(list => `<section class="card"><div class="row"><strong>${escape(list.title)}</strong><button class="secondary" data-open="${list.inviteToken}">Open</button></div><div class="meta">${list.gifts.length} gifts</div></section>`).join('') : '<p class="empty">Your wishlists will appear here.</p>';
  const sharedLists = shared.length ? shared.map(list => `<section class="card"><div class="row"><strong>${escape(list.title)}</strong><span><button class="secondary" data-open-shared="${list.id}">Open</button><button class="danger" data-hide-shared="${list.id}">Remove</button></span></div></section>`).join('') : '<p class="empty">No wishlists have been shared with you yet.</p>';
  root.innerHTML = `<h1>My wishlists</h1><p class="sub">Create a list, add gifts, and share the link with your guests.</p><form id="new-list" class="card"><input name="title" required maxlength="100" placeholder="For example, Birthday wishes"><button>Create wishlist</button></form>${ownLists}<h2>Shared with me</h2>${sharedLists}`;
  document.querySelector('#new-list').onsubmit = async event => {
    event.preventDefault();
    try { const list = await api('/api/wishlists', { method: 'POST', body: JSON.stringify({ title: new FormData(event.target).get('title') }) }); currentInvite = list.inviteToken; renderOwner(list); }
    catch (error) { message(error); }
  };
  root.querySelectorAll('[data-open]').forEach(element => { element.onclick = () => { currentInvite = element.dataset.open; openInvite(); }; });
  root.querySelectorAll('[data-open-shared]').forEach(element => { element.onclick = () => openShared(element.dataset.openShared); });
  root.querySelectorAll('[data-hide-shared]').forEach(element => { element.onclick = async () => { try { await api(`/api/wishlists/shared/${element.dataset.hideShared}`, { method: 'DELETE' }); renderHome(); } catch (error) { message(error); } }; });
}

function renderOwner(list, editingGift = null) {
  const invite = list.inviteUrl;
  const formTitle = editingGift ? 'Edit gift' : 'Add a gift';
  const submitLabel = editingGift ? 'Save changes' : 'Add gift';
  const cancelEdit = editingGift ? '<button class="secondary" id="cancel-edit" type="button">Cancel editing</button>' : '';
  root.innerHTML = `<button class="secondary" id="back">← My wishlists</button><h1>${escape(list.title)}</h1><p class="sub">Only you can see this view. Guest selections are intentionally hidden.</p><div class="card"><strong>Guest link</strong><p class="link">${escape(invite)}</p><button id="share">Share invite</button></div><h2>${formTitle}</h2>${giftForm(editingGift || {}, submitLabel)}${cancelEdit}<h2>Gifts</h2>${list.gifts.length ? list.gifts.map(gift => giftCard(gift, `<button class="secondary" data-edit="${gift.id}">Edit</button><button class="danger" data-delete="${gift.id}">Delete</button>`)).join('') : '<p class="empty">Add your first gift.</p>'}`;
  document.querySelector('#back').onclick = renderHome;
  document.querySelector('#share').onclick = () => {
    if (tg?.openTelegramLink) tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(invite)}&text=${encodeURIComponent(`My wishlist: ${list.title}`)}`);
    else navigator.clipboard.writeText(invite);
  };
  document.querySelector('#gift-form').onsubmit = async event => {
    event.preventDefault();
    try {
      const url = editingGift ? `/api/gifts/${editingGift.id}` : `/api/wishlists/${list.id}/gifts`;
      const method = editingGift ? 'PUT' : 'POST';
      await api(url, { method, body: JSON.stringify(giftPayload(event.target)) });
      openInvite();
    } catch (error) { message(error); }
  };
  document.querySelector('#cancel-edit')?.addEventListener('click', () => renderOwner(list));
  root.querySelectorAll('[data-edit]').forEach(element => { element.onclick = () => renderOwner(list, list.gifts.find(gift => gift.id === Number(element.dataset.edit))); });
  root.querySelectorAll('[data-delete]').forEach(element => { element.onclick = async () => { try { await api(`/api/gifts/${element.dataset.delete}`, { method: 'DELETE' }); openInvite(); } catch (error) { message(error); } }; });
}

function renderGuest(list, refresh) {
  root.innerHTML = `<button class="secondary" id="home">← Home</button><h1>${escape(list.title)}</h1><p class="sub">Choose a gift you plan to buy. It will disappear for other guests.</p>${list.gifts.length ? list.gifts.map(gift => giftCard(gift, gift.reservedByMe ? `<button class="secondary" data-cancel="${gift.id}">Change my mind</button>` : `<button data-reserve="${gift.id}">Choose gift</button>`)).join('') : '<p class="empty">There are no available gifts right now.</p>'}`;
  document.querySelector('#home').onclick = renderHome;
  root.querySelectorAll('[data-reserve]').forEach(element => { element.onclick = async () => { try { await api(`/api/gifts/${element.dataset.reserve}/reserve`, { method: 'POST', body: '{}' }); tg?.showAlert?.('Done! The organizer will not know about your choice.'); refresh(); } catch (error) { message(error); refresh(); } }; });
  root.querySelectorAll('[data-cancel]').forEach(element => { element.onclick = async () => { try { await api(`/api/gifts/${element.dataset.cancel}/reservation`, { method: 'DELETE' }); refresh(); } catch (error) { message(error); } }; });
}

async function openInvite() { try { const result = await api(`/api/invites/${currentInvite}`); result.isOwner ? renderOwner(result.list) : renderGuest(result.list, openInvite); } catch (error) { root.innerHTML = ''; message(error); } }
async function openShared(id) { try { const result = await api(`/api/wishlists/shared/${id}`); renderGuest(result.list, () => openShared(id)); } catch (error) { root.innerHTML = ''; message(error); } }
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
