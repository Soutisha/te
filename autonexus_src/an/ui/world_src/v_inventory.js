/* ===== INVENTORY: seven racks; crates physically fly from source rack to destination rack ===== */
V.inventory={name:"Inventory",rig:rig({th:0,ph:.32,d:62,ttx:0,tty:4,ttz:0,min:30,max:150}),init(){
 const sc=this.scene=stage(new THREE.Scene(),[80,260]),O=this.O={rack:{},shown:{},fly:[],last:null};const names=Object.keys(st.nodes);
 names.forEach((n,i)=>{const x=(i-(names.length-1)/2)*11,g=new THREE.Group();g.position.set(x,0,0);const wh=n.startsWith("WH");
  for(const px of[-3.4,3.4])for(const pz of[-.8,.8]){const p=box(.2,6.4,.2,0x2a3550,0);p.position.set(px,3.2,pz);g.add(p)}
  for(let r=0;r<=5;r++){const b=box(7,.14,1.8,wh?COB:0x23406e,.15);b.position.set(0,r*1.1+.1,0);g.add(b)}
  const im=new THREE.InstancedMesh(new THREE.BoxGeometry(.95,.9,1.2),mat(LIME,.4),30);im.position.set(-2.75,.65,0);g.add(im);
  const gh=new THREE.InstancedMesh(new THREE.BoxGeometry(.95,.9,1.2),new THREE.MeshBasicMaterial({color:RED,wireframe:true,transparent:true,opacity:.8}),30);gh.position.copy(im.position);g.add(gh);
  const lb=label(n,"#F5F7FA",.9);lb.position.set(0,8.6,0);g.add(lb);const ct=label("0",wh?"#2385FF":"#2678f5",1.3);ct.position.set(0,7.2,0);g.add(ct);
  sc.add(g);O.rack[n]={g,im,gh,ct,x};O.shown[n]=st.stock[n]});
 O.worker=human({shirt:NEO,hat:"helmet",hatColor:LIME,scale:2});sc.add(O.worker);O.wbox=crate(LIME,.45,.7);O.worker.userData.u.chest.add(O.wbox);O.wbox.position.set(0,.4,.4);
 O.floor=panel(40,2.6,1024);O.floor.position.set(0,13.5,0);sc.add(O.floor)},
 enter(){const O=this.O;for(const n in O.shown)O.shown[n]=st.stock[n];O.last={...st.stock};O.flying=0},
 update(st,t,dt){const O=this.O,R=this.rig,names=Object.keys(st.nodes),sc2=this.scene;
 /* detect a backend transfer: exactly one site decreased and one increased -> animate crates, update counts on landing */
 if(O.last){const ch=names.filter(n=>st.stock[n]!==O.last[n]);const dn=ch.filter(n=>st.stock[n]<O.last[n]),up=ch.filter(n=>st.stock[n]>O.last[n]);
  if(dn.length==1&&up.length==1&&ch.length==2){const a=dn[0],b=up[0],q=O.last[a]-st.stock[a],from=O.rack[a],to=O.rack[b];O.shown[a]=st.stock[a];const land=st.stock[b];O.flying=(O.flying||0)+1;
   for(let i=0;i<q;i++){const c=crate(LIME,.9,.6);c.position.set(from.x-2.75+(i%6)*1.1,5,0);this.scene.add(c);const o={u:0},sx=c.position.x,tx=to.x-2.75+(i%6)*1.1,ty=.65+Math.floor((O.shown[b]+i)/6)*1.1;
    gsap.to(o,{u:1,duration:1.8,delay:i*.12,ease:"power2.inOut",onUpdate(){c.position.x=lerp(sx,tx,o.u);c.position.y=lerp(5,ty,o.u)+Math.sin(o.u*Math.PI)*7;c.position.z=Math.sin(o.u*Math.PI)*3;c.rotation.y=o.u*6},onComplete(){sc2.remove(c);O.shown[b]=Math.min(land,O.shown[b]+1);O.flying--}})}
   O.work=performance.now()+q*120+1800}
  else if(ch.length){ch.forEach(n=>O.shown[n]=st.stock[n])}}
 O.last={...st.stock};
 if(!O.flying)for(const n of names)O.shown[n]=st.stock[n];/* safety net: never leave counts out of sync with the backend */
 const m=new THREE.Matrix4();for(const n of names){const k=O.rack[n],cnt=Math.min(30,Math.round(O.shown[n]));for(let i=0;i<30;i++){m.setPosition((i%6)*1.1,Math.floor(i/6)*1.1,0);k.im.setMatrixAt(i,m);k.gh.setMatrixAt(i,m)}k.im.count=cnt;k.im.instanceMatrix.needsUpdate=true;
  const gap=n==st.dest&&st.need>st.stock[n]&&st.phase!="idle"?Math.min(30,st.need)-cnt:0;
  setLabel(k.ct,n==st.dest&&st.need?`${Math.round(O.shown[n])} / ${st.need} needed`:String(Math.round(O.shown[n])),n==st.dest&&st.shortage>0&&st.phase!="idle"?"#FF3B3B":(n.startsWith("WH")?"#2385FF":"#2678f5"))}
 /* ghost slots: render only the missing ones (instances [cnt, cnt+gap)) via drawRange trick */
 for(const n of names){const k=O.rack[n],cnt=Math.min(30,Math.round(O.shown[n])),gap=n==st.dest&&st.need>st.stock[n]&&st.phase!="idle"?Math.min(30,st.need)-cnt:0;k.gh.visible=gap>0;if(gap>0){const mm=new THREE.Matrix4();for(let i=0;i<30;i++){const j=i<gap?cnt+i:0;mm.setPosition((j%6)*1.1,Math.floor(j/6)*1.1,0);k.gh.setMatrixAt(i,mm)}k.gh.count=gap;k.gh.instanceMatrix.needsUpdate=true}}
 /* worker: stands at source while crates leave, walks to destination with the last box */
 const w=O.worker,src=st.src&&O.rack[st.src],dst=O.rack[st.dest],busy=performance.now()<(O.work||0);
 if(src&&dst){const a=src.x+4.2,b=dst.x-4.2,u=busy?clamp(1-(O.work-performance.now())/(1800+120*(st.transfer?st.transfer.qty:6)),0,1):(st.phase=="idle"||st.phase=="detected"?0:(st.stock[st.dest]>=st.need?1:0));
  const px=lerp(a,b,ease(u)),mv=u>0&&u<1;w.position.set(px,0,3.2);w.rotation.y=mv?(b>a?Math.PI/2:-Math.PI/2):0;O.wbox.visible=busy&&mv;mv?POSE.carry(w,t*8):POSE.idle(w,t)}else{w.position.set(0,0,12);POSE.idle(w,t)}
 redraw(O.floor,JSON.stringify([st.src,st.dest,st.transfer]),(g,W,H)=>{g.fillStyle="#2678f5";g.font="bold 40px monospace";g.textAlign="center";g.fillText(st.transfer?`TRANSFER ${st.transfer.qty} × ${st.part}  ${st.transfer.from} → ${st.transfer.to}`:`${st.part} (${st.part_name.toUpperCase()}) · STOCK PER SITE`,W/2,H*.62)});
 if(auto(R)){R.ttx=0;R.tty=4;R.ttz=0;if(!reduce)R.th=Math.sin(t*.1)*.35}stepRig(R,dt)},
 info(st){return`Part ${st.part} ${st.part_name} · need ${st.need} at ${st.dest}<br>`+Object.keys(st.stock).map(n=>`${n}: <b style="color:${n==st.dest&&st.shortage?'#FF3B3B':'#2678f5'}">${st.stock[n]}</b>`).join(" · ")+(st.transfer?`<br>moved ${st.transfer.qty} from ${st.transfer.from}`:"")}};
