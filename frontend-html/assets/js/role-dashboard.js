(() => {
const token=localStorage.getItem('wasteSetuToken');
let user=null; try{user=JSON.parse(localStorage.getItem('wasteSetuUser')||'null')}catch{}
const API='https://waste-setuu.onrender.com/api/workflow';
const $=id=>document.getElementById(id);
const view=$('view'), menu=$('menu'), notice=$('notice');
if(!token||!user||!user.portal||user.portal==='domestic'){
  window.location.replace(user?.role==='household'?'signup.html?portal=domestic&role=household':'index.html'); return;
}
const portal=user.portal, role=user.role;
const isCollector=role.includes('collector'), isRecycler=role.includes('recycler') || (portal==='organic' && ['biogas-facility','bio-cng-facility'].includes(role));
const title=s=>String(s||'').replace(/[-_]/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>'₹'+Number(n||0).toLocaleString('en-IN');
let current='home', mine=[], available=[], recyclers=[];
$('accountLine').textContent=`${title(portal)} · ${title(role)} · ${user.name||user.email}`;
$('logout').onclick=()=>{localStorage.removeItem('wasteSetuToken');localStorage.removeItem('wasteSetuUser');location.href='index.html'};
function notify(msg){notice.textContent=msg;notice.classList.remove('ws-hidden');setTimeout(()=>notice.classList.add('ws-hidden'),5000)}
async function api(path,opts={}){const r=await fetch(API+path,{...opts,headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`,...(opts.headers||{})}});const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||`Request failed (${r.status})`);return d}
const menus=isCollector?['home','my-lots','available-lots','available-recycler']:isRecycler?['dashboard','available-lots','transactions']:['home','my-lots','create-lot'];
function renderMenu(){menu.innerHTML=menus.map(m=>`<button data-view="${m}" class="${m===current?'active':''}">${title(m)}</button>`).join('');menu.querySelectorAll('button').forEach(b=>b.onclick=()=>show(b.dataset.view))}
function navButton(label,action,alt=false){return `<button class="ws-btn ${alt?'alt':''}" data-action="${action}">${label}</button>`}
function lotCard(lot,mode='mine'){
 const offers=(lot.offers||[]).map(o=>`<div class="ws-alert"><b>${esc(o.name)}</b> offered ${money(o.amount)} <span class="ws-tag">${esc(o.status)}</span><p>${esc(o.message||'')}</p>${o.status==='Pending'?navButton('Accept offer','offer:'+lot.lot_id+':'+o.offer_id,true):''}</div>`).join('');
 const requests=(lot.collector_requests||[]).map(r=>`<div class="ws-alert"><b>${esc(r.name)}</b> · ${esc(r.role)} ${r.message?'- '+esc(r.message):''} ${navButton('Accept collector','collector:'+lot.lot_id+':'+r.collector_id,true)}</div>`).join('');
 let actions='';
 if(mode==='available'&&isCollector) actions=navButton('Request lot','collect:'+lot.lot_id);
 if(mode==='available'&&isRecycler) actions=navButton('Accept lot','recycler:'+lot.lot_id);
 if(mode==='mine'&&!isCollector&&!isRecycler) actions+=requests;
 actions+=`<div class="ws-grid"><div><label class="ws-muted">Your price offer (₹)</label><input type="number" min="1" step="0.01" id="offer-${esc(lot.lot_id)}" placeholder="Enter amount"></div><div><label class="ws-muted">Message</label><input id="msg-${esc(lot.lot_id)}" placeholder="Add negotiation message"></div></div>${navButton('Send negotiation offer','negotiate:'+lot.lot_id,true)}`;
 if(lot.agreed_price) actions+=`<p><b>Agreed price:</b> ${money(lot.agreed_price)}</p>${lot.invoice_id?`<span class="ws-tag">Invoice ${esc(lot.invoice_id)}</span>`:navButton('Generate invoice','invoice:'+lot.lot_id,true)}`;
 return `<article class="ws-card"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><h3>${esc(lot.lotTitle)}</h3><span class="ws-tag">${esc(lot.status)}</span></div><p class="ws-muted">${esc(lot.lot_id)} · ${esc(title(lot.portal))} · ${esc(lot.city||'')}</p><div class="ws-grid"><p><b>Category:</b> ${esc(lot.wasteCategory)}</p><p><b>Material:</b> ${esc(lot.material)}</p><p><b>Weight:</b> ${esc(lot.estimatedWeight)} kg</p><p><b>Expected price:</b> ${money(lot.expectedPrice)}</p><p><b>Lot owner:</b> ${esc(lot.client_name)}</p><p><b>Agreed price:</b> ${lot.agreed_price?money(lot.agreed_price):'Not agreed'}</p></div><p>${esc(lot.description||'')}</p>${offers}${actions}</article>`;
}
async function show(page){
 current=page;renderMenu();view.innerHTML='<h2>Loading...</h2>';
 try{
 if(page==='home'||page==='dashboard'){
  const d=await api('/dashboard');const mineData=await api('/lots/mine');const active=(mineData.lots||[]).filter(x=>isCollector?x.collector_id===user.id:isRecycler?x.recycler_id===user.id:false);
  view.innerHTML=`<h2>${isCollector?'Collector Home':isRecycler?'Recycler Dashboard':'Portal Dashboard'}</h2><p class="ws-muted">Your workspace is restricted to the ${esc(title(portal))} portal.</p><div class="ws-grid"><div class="ws-card"><h3>${d.my_lots}</h3><p>My lots / assigned lots</p></div><div class="ws-card"><h3>${d.invoices}</h3><p>Invoices</p></div><div class="ws-card"><h3>${esc(title(role))}</h3><p>Account type</p></div></div>${!isCollector&&!isRecycler?navButton('Create a new lot','goto:create-lot'):''}${active.length?'<h3>Assigned lots · negotiation</h3>'+active.map(x=>lotCard(x,'mine')).join(''):'<p class="ws-muted">No assigned lots yet.</p>'}`;
 } else if(page==='create-lot'){
  view.innerHTML=`<h2>Create Waste Lot</h2><p class="ws-muted">Your lot and expected price will be saved in MongoDB.</p><form id="createLot" class="ws-form">
  <input name="lotTitle" required placeholder="Lot title"><input name="wasteCategory" required placeholder="Waste category">
  <input name="material" required placeholder="Material / description"><input name="estimatedWeight" type="number" min="0.01" step="0.01" required placeholder="Estimated weight (kg)">
  <input name="expectedPrice" type="number" min="1" step="0.01" required placeholder="Expected price (₹)"><input name="itemCount" type="number" min="1" placeholder="Item count (optional)">
  <input name="pickupAddress" required placeholder="Pickup address"><input name="city" required placeholder="City">
  <input name="preferredDate" type="date"><input name="preferredTime" type="time">
  <input name="wasteCondition" placeholder="Waste condition"><textarea name="description" placeholder="Additional details"></textarea>
  <button class="ws-btn" type="submit">Create Lot Passport</button></form>`;
  $('createLot').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget),p=Object.fromEntries(f.entries());p.estimatedWeight=Number(p.estimatedWeight);p.expectedPrice=Number(p.expectedPrice);p.itemCount=p.itemCount?Number(p.itemCount):null;try{const d=await api('/lots',{method:'POST',body:JSON.stringify(p)});notify(`Lot created: ${d.lot.lot_id}`);show('my-lots')}catch(err){notify(err.message)}};
 } else if(page==='my-lots'){
  const d=await api('/lots/mine');mine=d.lots||[];
  view.innerHTML=`<h2>My Lots</h2>${mine.length?mine.map(x=>lotCard(x,'mine')).join(''):'<p>No lots or assigned lots yet.</p>'}`;
 } else if(page==='available-lots'){
  const d=await api('/lots/available');available=d.lots||[];
  view.innerHTML=`<h2>Available Lots · ${esc(title(portal))}</h2><p class="ws-muted">Only lots belonging to this portal are shown.</p>${available.length?available.map(x=>lotCard(x,'available')).join(''):'<p>No available lots at the moment.</p>'}`;
 } else if(page==='available-recycler'){
  const d=await api('/collectors/recyclers');recyclers=d.recyclers||[];
  const assigned=await api('/lots/mine');mine=(assigned.lots||[]).filter(x=>x.collector_id===user.id);
  view.innerHTML=`<h2>Available Recycler · ${esc(title(portal))}</h2><p class="ws-muted">Only recyclers registered in your ${esc(title(portal))} portal appear here.</p>${recyclers.length?recyclers.map(r=>`<article class="ws-card"><h3>${esc(r.name)}</h3><p>${esc(title(r.role))} · ${esc(r.city||'')}</p></article>`).join(''):'<p>No recycler accounts are registered in this portal yet.</p>'}<h3>Send recycler requests for your assigned lots</h3>${mine.map(x=>`<article class="ws-card"><b>${esc(x.lotTitle)}</b> · ${esc(x.lot_id)}<div class="ws-grid"><select id="recycler-${esc(x.lot_id)}"><option value="">Select recycler</option>${recyclers.map(r=>`<option value="${esc(r.id)}">${esc(r.name)} (${esc(r.role)})</option>`).join('')}</select><button class="ws-btn" data-action="recycler-request:${esc(x.lot_id)}">Request selected recycler</button></div></article>`).join('')}`;
 } else if(page==='transactions'){
  const d=await api('/transactions');const arr=d.transactions||[];
  view.innerHTML=`<h2>Transactions & Invoices</h2>${arr.length?arr.map(x=>`<article class="ws-card"><b>${esc(x.invoice_id)}</b><p>Lot ${esc(x.lot_id)} · ${money(x.amount)} · ${esc(x.status)}</p></article>`).join(''):'<p>No invoices or transactions recorded yet.</p>'}`;
 }
 }catch(e){view.innerHTML=`<h2>Unable to load</h2><p>${esc(e.message)}</p>`;if(/token|account/i.test(e.message))notify('Please log out and sign in again.')}
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('[data-action]');if(!b)return;const [act,id,extra]=b.dataset.action.split(':');b.disabled=true;
 try{
 if(act==='goto'){show(id);return}
 if(act==='collect')await api(`/lots/${id}/collector-request`,{method:'POST',body:JSON.stringify({})});
 if(act==='collector')await api(`/lots/${id}/collector-accept/${extra}`,{method:'POST'});
 if(act==='recycler')await api(`/lots/${id}/recycler-accept`,{method:'POST'});
 if(act==='recycler-request'){const recyclerId=$(`recycler-${id}`)?.value;if(!recyclerId)throw Error('Select a recycler first.');await api(`/lots/${id}/recycler-request`,{method:'POST',body:JSON.stringify({recyclerId})});}
 if(act==='negotiate'){const amount=Number($(`offer-${id}`).value),message=$(`msg-${id}`).value;if(!amount)throw Error('Enter a valid offer amount.');await api(`/lots/${id}/offers`,{method:'POST',body:JSON.stringify({amount,message})})}
 if(act==='offer')await api(`/lots/${id}/offers/${extra}/accept`,{method:'POST'});
 if(act==='invoice')await api(`/lots/${id}/invoice`,{method:'POST',body:JSON.stringify({})});
 notify('Action completed and saved.');show(current);
 }catch(err){notify(err.message);b.disabled=false}
});
show(menus[0]);
})();