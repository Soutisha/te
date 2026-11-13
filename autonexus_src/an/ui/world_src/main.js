/* ===== Live state, backend commands, controls and render loop ===== */
let wsConnected=false,pollTimer=null,reconnectTimer=null,inputsDirty=false;
const labels={
  idle:"READY",detected:"SHORTAGE DETECTED",prediction:"DEMAND RISK",
  agents:"OPERATIONS ANALYSIS",searching:"SEARCHING STOCK",supplier:"SOURCE SELECTED",
  threat:"SECURITY CHECK",compliance:"SUPPLIER POLICY CHECK",route_planned:"ROUTE PLANNED",
  awaiting_approval:"AWAITING OWNER APPROVAL",loaded:"PACKAGE LOADED",in_transit:"IN TRANSIT",
  arrived:"ARRIVED",inventory_updated:"INVENTORY UPDATED",tech_assigned:"TECHNICIANS ASSIGNED",
  recovered:"RECOVERED",rejected:"REJECTED — NO DELIVERY",stalled:"STALLED — NO ROUTE"
};
function flash(message){
  const item=document.createElement("div");
  item.textContent="⚠ "+message;
  item.style.color="#FF3B3B";
  addLog(item);
}
function addLog(item){
  $("log").appendChild(item);
  while($("log").children.length>7)$("log").firstElementChild.remove();
}
async function cmd(command,extra){
  const headers={};
  const token=sessionStorage.getItem("autonexusOwnerToken");
  if(token)headers.Authorization="Bearer "+token;
  try{
    const response=await fetch("/world/"+command+(extra?"?"+extra:""),{method:"POST",headers});
    let payload={};
    try{payload=await response.json()}catch{payload={detail:await response.text()}}
    if(!response.ok)throw new Error(payload.detail||payload.error||"The operation failed.");
    if(payload.ok===false)throw new Error(payload.error||"The operation could not be completed.");
    return payload;
  }catch(error){
    const needsLogin=(command==="approve"||command==="reject")&&String(error.message).startsWith("401:");
    flash(needsLogin?`${error.message} Sign in from Operations → Security before deciding.`:error.message);
    return null;
  }
}
function setOptions(select,items,value,label){
  const current=value||select.value;
  select.replaceChildren(...items.map(item=>{
    const id=typeof item==="string"?item:item.id;
    const text=label?label(item):id;
    return new Option(text,id);
  }));
  if(items.some(item=>(typeof item==="string"?item:item.id)===current))select.value=current;
}
function syncInputs(){
  if(!st)return;
  const dest=$("dest"),part=$("part"),source=$("source"),qty=$("req");
  const active=st.phase==="idle"||st.phase==="recovered"||st.phase==="rejected";
  [dest,part,source,qty].forEach(el=>{el.disabled=!active});
  if(!dest.options.length||!inputsDirty&&document.activeElement!==dest)
    setOptions(dest,st.destinations||[],st.destination);
  if(!part.options.length||!inputsDirty&&document.activeElement!==part)
    setOptions(part,st.parts||[],st.part,item=>`${item.id} · ${item.name}`);
  const oldSource=source.value;
  const selectedDestination=inputsDirty?dest.value:st.destination;
  source.replaceChildren(new Option("Best available source",""));
  (st.sites||[]).filter(site=>site.id!==selectedDestination).forEach(site=>
    source.add(new Option(`${site.name} · ${site.kind}`,site.id)));
  if((st.sites||[]).some(site=>site.id===oldSource))source.value=oldSource;
  else if(!inputsDirty&&st.source_choice)source.value=st.source_choice;
  if(!inputsDirty&&document.activeElement!==qty)qty.value=st.required_qty||"";
}
async function configureWorld(){
  const params=new URLSearchParams({
    destination:$("dest").value,
    part:$("part").value
  });
  if($("req").value)params.set("required_qty",$("req").value);
  if($("source").value)params.set("source",$("source").value);
  const response=await cmd("configure",params.toString());
  if(response){
    inputsDirty=false;
    syncInputs();
    const item=document.createElement("div");
    item.textContent=`Inputs applied · ${response.destination} · ${response.part} · short ${response.shortage} units`;
    item.style.color="#2678f5";addLog(item);
  }
}

/* Twin / event-stream bridge: polls /api/v1/twin/state when a part is selected.
   Requires owner token in sessionStorage (same as approval actions).
   Does not replace the Living World simulation; it overlays real ledger numbers. */
let twinTimer=null, twinLast=null;
async function pollTwin(){
  const part=($("part")&&$("part").value)|| (st&&st.part)||"P000";
  const token=sessionStorage.getItem("autonexusOwnerToken");
  if(!token){return}
  try{
    const r=await fetch("/api/v1/twin/state?part="+encodeURIComponent(part),{
      headers:{Authorization:"Bearer "+token}
    });
    if(!r.ok)return;
    twinLast=await r.json();
    // Surface a short status line if the log panel exists
    if($("log")&&twinLast&&twinLast.sites){
      const zero=twinLast.sites.filter(s=>s.kind==="dealer"&&s.on_hand===0&&s.open_need>0);
      if(zero.length){
        const item=document.createElement("div");
        item.textContent="Twin: "+zero.map(s=>s.id+" needs "+s.open_need+" (on hand 0)").join("; ");
        item.style.color="#A3E635";
        addLog(item);
      }
    }
  }catch(e){/* silent — twin is optional overlay */}
}
function startTwinBridge(){
  if(twinTimer)return;
  pollTwin();
  twinTimer=setInterval(pollTwin,5000);
}

function connect(){
  const protocol=location.protocol==="https:"?"wss":"ws";
  ws=new WebSocket(protocol+"://"+location.host+"/ws/world");
  ws.onopen=()=>{wsConnected=true;clearTimeout(pollTimer);pollTimer=null};
  ws.onmessage=event=>{st=JSON.parse(event.data);onState()};
  ws.onclose=()=>{wsConnected=false;if(!pollTimer)poll();clearTimeout(reconnectTimer);reconnectTimer=setTimeout(connect,1500)};
}
async function poll(){
  if(wsConnected)return;
  try{st=await fetch("/world/state").then(response=>{
    if(!response.ok)throw new Error(`World state request failed: ${response.status}`);
    return response.json();
  });onState()}catch(error){flash(error.message)}
  if(!wsConnected)pollTimer=setTimeout(poll,1000);
}
const PH=labels;
const ORDER=["overview","inventory","suppliers","cyber","sched","route","fed"];
function setView(id,instant){
  if(!V[id]||id===cur&&V[id].scene)return;
  const go=()=>{
    cur=id;
    if(!V[id].scene)V[id].init();
    if(V[id].enter)V[id].enter();
    document.querySelectorAll("#tabs button").forEach(button=>
      button.classList.toggle("on",button.dataset.v===id));
    try{history.replaceState(null,"","#"+id)}catch(error){flash("Could not update scene link.")}
  };
  if(instant||reduce||!window.gsap){go();return}
  gsap.to("#fade",{opacity:1,duration:.22,onComplete(){
    go();gsap.to("#fade",{opacity:0,duration:.35});
  }});
}
function buildHud(){
  const tabs=$("tabs");
  ORDER.forEach(id=>{
    const button=document.createElement("button");
    button.dataset.v=id;button.textContent=V[id].name;
    button.onclick=()=>setView(id);tabs.appendChild(button);
  });
  $("dest").onchange=()=>{inputsDirty=true;if(st)syncInputs()};
  $("part").onchange=()=>{inputsDirty=true;if(!$("req").value)$("req").placeholder="Uses repair-order demand"};
  $("source").onchange=()=>{inputsDirty=true};
  $("req").oninput=()=>{inputsDirty=true};
  const placeTabs=()=>$("tabs").style.top=`${Math.ceil($("hud").getBoundingClientRect().bottom+8)}px`;
  placeTabs();
  new ResizeObserver(placeTabs).observe($("hud"));
}
let started=false;
function onState(){
  if(!started){
    try{renderer=new THREE.WebGLRenderer({antialias:true})}
    catch(error){$("fb").style.display="block";fallback();return}
    started=true;
    renderer.setSize(innerWidth,innerHeight);
    renderer.setPixelRatio(Math.min(2,devicePixelRatio));
    document.body.prepend(renderer.domElement);
    cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,.1,900);
    buildHud();
    const initial=location.hash.slice(1);
    cur=V[initial]?initial:"overview";
    V[cur].init();
    if(V[cur].enter)V[cur].enter();
    document.querySelectorAll("#tabs button").forEach(button=>
      button.classList.toggle("on",button.dataset.v===cur));
    inputs();
    requestAnimationFrame(frame);
    addEventListener("hashchange",()=>{
      const view=location.hash.slice(1);
      if(V[view])setView(view);
    });
  }
  syncInputs();
  $("ph").textContent=PH[st.phase]||String(st.phase||"").replaceAll("_"," ").toUpperCase();
  $("ap").style.display=st.approval_pending?"block":"none";
  const log=$("log");
  const events=st.events||[];
  if(events.length&&events[events.length-1].seq!==lastSeq){
    lastSeq=events[events.length-1].seq;
    log.replaceChildren(...events.slice(-6).map(event=>{
      const entry=document.createElement("div");
      entry.textContent=event.msg;return entry;
    }));
  }
  if(V[cur]&&V[cur].info)$("info").textContent=String(V[cur].info(st))
    .replace(/<br\s*\/?>/gi,"\n").replace(/<[^>]*>/g,"");
  const overview=V.overview.O;
  window.__dbg={
    view:cur,phase:st.phase,scenario:st.scenario,rider:st.rider,
    stock:st.stock,visibleRider:overview&&overview.rider.visible,
    riderXY:overview&&[overview.rider.position.x,overview.rider.position.z],
    routeKey:JSON.stringify(st.route.map(route=>route.n)),
    wsOpen:ws&&ws.readyState===1,blockedRoads:st.blocked.length,
    bays:overview&&overview.bays.map(bay=>bay.car.position.y),
    shown:V.inventory.O&&V.inventory.O.shown
  };
}
function fallback(){
  function displayState(){
    if(!st)return;
    const lines=[
      `Current journey: ${labels[st.phase]||st.phase}.`,
      `Destination: ${st.destination} · part: ${st.part_name} (${st.part}).`,
      `Required: ${st.need} · on hand: ${st.stock[st.destination]} · shortage: ${st.shortage}.`,
      st.route.length?`Route: ${st.route.map(node=>node.n).join(" to ")}.`:"Route not planned yet.",
      `Latest activity: ${(st.events||[]).slice(-5).map(event=>event.msg).join(" | ")}`
    ];
    $("fbt").textContent=lines.join("\n");
  }
  setInterval(displayState,500);
}
function frame(time){
  requestAnimationFrame(frame);
  if(!st)return;
  const now=performance.now()/1000;
  const dt=Math.min(.05,now-lastT);
  lastT=now;clock+=dt;
  const view=V[cur];
  if(!view||!view.scene)return;
  view.update(st,clock,dt);
  renderer.render(view.scene,cam);
}
connect();
