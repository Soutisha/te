/* ===== articulated characters + vehicles (procedural, no external models) =====
   Human faces +Z. Joints: hips > chest > shoulders > elbows ; hips > hip > knee ; chest > head. */
function human(o={}){
 const sh=o.shirt??LIME,pn=o.pants??0x1a2236,sk=o.skin??0xD9A47E,M=c=>new THREE.MeshStandardMaterial({color:c,roughness:.75});
 const g=new THREE.Group(),u={};const C=(r1,r2,h,c,y)=>{const m=new THREE.Mesh(new THREE.CylinderGeometry(r1,r2,h,10),M(c));m.position.y=y;return m};
 u.hips=new THREE.Group();u.hips.position.y=.95;g.add(u.hips);u.hips.add(new THREE.Mesh(new THREE.BoxGeometry(.42,.2,.26),M(pn)));
 const leg=sx=>{const hp=new THREE.Group();hp.position.set(sx*.13,-.02,0);hp.add(C(.09,.075,.46,pn,-.23));const kn=new THREE.Group();kn.position.y=-.46;kn.add(C(.07,.06,.44,pn,-.22));const ft=new THREE.Mesh(new THREE.BoxGeometry(.12,.07,.26),M(0x111111));ft.position.set(0,-.46,.06);kn.add(ft);hp.add(kn);u.hips.add(hp);return[hp,kn]};
 [u.legL,u.kneeL]=leg(1);[u.legR,u.kneeR]=leg(-1);
 u.chest=new THREE.Group();u.chest.position.y=.1;u.hips.add(u.chest);
 const tor=new THREE.Mesh(new THREE.BoxGeometry(.46,.6,.26),M(sh));tor.position.y=.32;u.chest.add(tor);
 if(o.vest!==false){const s=new THREE.Mesh(new THREE.BoxGeometry(.475,.06,.275),new THREE.MeshStandardMaterial({color:0xF5F7FA,emissive:0xF5F7FA,emissiveIntensity:.5}));s.position.y=.28;u.chest.add(s)}
 const arm=sx=>{const sp=new THREE.Group();sp.position.set(sx*.3,.55,0);const j=new THREE.Mesh(new THREE.SphereGeometry(.085,10,8),M(sh));sp.add(j);sp.add(C(.065,.055,.3,sh,-.15));const el=new THREE.Group();el.position.y=-.3;el.add(C(.055,.045,.28,sk,-.14));const hd=new THREE.Mesh(new THREE.SphereGeometry(.06,8,8),M(sk));hd.position.y=-.3;el.add(hd);sp.add(el);u.chest.add(sp);return[sp,el,el]};
 [u.armL,u.elbL]=arm(1);[u.armR,u.elbR]=arm(-1);
 u.head=new THREE.Group();u.head.position.y=.68;u.chest.add(u.head);u.head.add(C(.05,.05,.1,sk,0));const hh=new THREE.Mesh(new THREE.SphereGeometry(.15,14,12),M(sk));hh.position.y=.16;u.head.add(hh);
 for(const sx of[-1,1]){const e=new THREE.Mesh(new THREE.SphereGeometry(.018,6,6),M(0x111111));e.position.set(sx*.055,.18,.14);u.head.add(e)}
 const hat=o.hat||"none";if(hat!="none"){const hc=o.hatColor??COB;const h=new THREE.Mesh(new THREE.SphereGeometry(hat=="helmet"?.175:.16,14,10,0,Math.PI*2,0,Math.PI*(hat=="helmet"?.58:.5)),M(hc));h.position.y=.17;u.head.add(h);
  if(hat=="helmet"){const v=new THREE.Mesh(new THREE.BoxGeometry(.24,.07,.05),new THREE.MeshStandardMaterial({color:0x0a0f1c,roughness:.2,metalness:.5}));v.position.set(0,.2,.15);u.head.add(v)}else{const b=new THREE.Mesh(new THREE.BoxGeometry(.22,.02,.12),M(hc));b.position.set(0,.2,.2);u.head.add(b)}}
 if(o.hair){const hr=new THREE.Mesh(new THREE.SphereGeometry(.155,12,8,0,Math.PI*2,0,Math.PI*.45),M(o.hair));hr.position.set(0,.18,-.01);u.head.add(hr)}
 g.userData={u,p:0};g.scale.setScalar(o.scale||1);g.traverse(m=>{if(m.isMesh)m.castShadow=false});return g}
function _rst(u){u.hips.position.set(0,.95,0);for(const k in u)u[k].rotation.set(0,0,0)}
/* poses: pure functions of (human, phase/time, amount) – call once per frame */
const POSE={
 idle(h,t){const u=h.userData.u;_rst(u);u.chest.rotation.x=Math.sin(t*1.6)*.02;u.armL.rotation.z=-.08;u.armR.rotation.z=.08;u.head.rotation.y=Math.sin(t*.7)*.25},
 walk(h,ph,k=1){const u=h.userData.u;_rst(u);const s=Math.sin(ph);u.legL.rotation.x=s*.7*k;u.legR.rotation.x=-s*.7*k;u.kneeL.rotation.x=Math.max(0,-s)*.9*k;u.kneeR.rotation.x=Math.max(0,s)*.9*k;
  u.armL.rotation.x=-s*.6*k;u.armR.rotation.x=s*.6*k;u.elbL.rotation.x=-.3;u.elbR.rotation.x=-.3;u.hips.position.y=.95+Math.abs(Math.cos(ph))*.04*k;u.chest.rotation.y=s*.12*k},
 carry(h,ph,k=1){POSE.walk(h,ph,k);const u=h.userData.u;u.armL.rotation.x=-1.25;u.armR.rotation.x=-1.25;u.armL.rotation.z=-.25;u.armR.rotation.z=.25;u.elbL.rotation.x=-.5;u.elbR.rotation.x=-.5},
 work(h,t){const u=h.userData.u;_rst(u);u.chest.rotation.x=.3;u.legL.rotation.x=-.25;u.legR.rotation.x=-.25;u.kneeL.rotation.x=.5;u.kneeR.rotation.x=.5;u.hips.position.y=.88;
  u.armR.rotation.x=-1.1+Math.sin(t*9)*.35;u.elbR.rotation.x=-.9;u.armL.rotation.x=-.9;u.elbL.rotation.x=-.8;u.head.rotation.x=.25},
 wave(h,t){const u=h.userData.u;_rst(u);u.armR.rotation.z=2.6;u.armR.rotation.x=0;u.elbR.rotation.z=Math.sin(t*8)*.5;u.elbR.rotation.x=-.4;u.armL.rotation.z=.1;u.chest.rotation.y=-.15},
 thumbs(h,t){const u=h.userData.u;_rst(u);u.armR.rotation.x=-1.3;u.elbR.rotation.x=-1.4;u.head.rotation.x=Math.sin(t*5)*.18;u.armL.rotation.z=.1},
 ride(h,t){const u=h.userData.u;_rst(u);u.hips.position.y=.95;u.legL.rotation.x=-1.25;u.legR.rotation.x=-1.25;u.kneeL.rotation.x=1.35;u.kneeR.rotation.x=1.35;u.legL.rotation.z=-.1;u.legR.rotation.z=.1;
  u.chest.rotation.x=.18;u.armL.rotation.x=-1.05;u.armR.rotation.x=-1.05;u.elbL.rotation.x=-.45;u.elbR.rotation.x=-.45;u.armL.rotation.z=-.12;u.armR.rotation.z=.12}
};
function scooter(){const g=new THREE.Group(),W=[];const wheel=x=>{const w=new THREE.Group();const tire=new THREE.Mesh(new THREE.CylinderGeometry(.34,.34,.2,16),mat(0x111418,0));tire.rotation.x=Math.PI/2;const hub=new THREE.Mesh(new THREE.CylinderGeometry(.16,.16,.22,10),mat(LIME,.4));hub.rotation.x=Math.PI/2;w.add(tire,hub);w.position.set(x,.34,0);W.push(w);return w};
 const fl=box(1.5,.12,.56,COB,.15);fl.position.set(.05,.42,0);g.add(fl);const cw=box(.9,.55,.6,COB,.2);cw.position.set(-.75,.78,0);g.add(cw);const seat=box(.7,.12,.46,0x101318,0);seat.position.set(-.45,1.1,0);g.add(seat);
 const fork=new THREE.Group();fork.position.set(.9,0,0);const col=box(.1,.95,.12,GREY,.1);col.position.set(-.08,.85,0);col.rotation.z=-.18;const bar=box(.1,.08,.82,0x1b1f27,0);bar.position.set(-.18,1.35,0);const hl=sph(.1,0xFFFFFF,1.2);hl.position.set(.02,1.15,0);const fw=wheel(0);fw.position.set(0,.34,0);fork.add(col,bar,hl,fw);g.add(fork);
 const rw=wheel(-.95);g.add(rw);const fen=box(.8,.06,.5,COB,.1);fen.position.set(-.95,.72,0);g.add(fen);const rack=box(.6,.05,.5,GREY,0);rack.position.set(-1.0,1.05,0);g.add(rack);
 const tl=sph(.06,RED,1);tl.position.set(-1.25,.8,0);g.add(tl);g.userData={wheels:W,fork};return g}
function truck(){const g=new THREE.Group(),W=[];const cargo=box(3.4,2.1,1.9,0xE8EDF5,0);cargo.position.set(-.9,1.75,0);g.add(cargo);const st=box(3.42,.35,1.92,LIME,.3);st.position.set(-.9,1.5,0);g.add(st);
 const ch=box(5.3,.3,1.7,0x1b1f27,0);ch.position.set(0,.65,0);g.add(ch);const cab=box(1.5,1.65,1.9,COB,.15);cab.position.set(2.05,1.5,0);g.add(cab);const glass=new THREE.MeshStandardMaterial({color:0x9FD0FF,transparent:true,opacity:.35,roughness:.1});
 const ws=new THREE.Mesh(new THREE.BoxGeometry(.05,.8,1.7),glass);ws.position.set(2.82,1.95,0);g.add(ws);for(const z of[-.96,.96]){const sw=new THREE.Mesh(new THREE.BoxGeometry(1.1,.8,.05),glass);sw.position.set(2.2,1.95,z);g.add(sw)}
 const hl=box(.08,.2,.5,0xFFFFFF,1.3);hl.position.set(2.82,1.0,0);g.add(hl);for(const[x,z]of[[1.9,.95],[1.9,-.95],[-.2,.95],[-.2,-.95],[-1.8,.95],[-1.8,-.95]]){const w=new THREE.Group();const t=new THREE.Mesh(new THREE.CylinderGeometry(.46,.46,.4,16),mat(0x111418,0));t.rotation.x=Math.PI/2;const h=new THREE.Mesh(new THREE.CylinderGeometry(.2,.2,.42,10),mat(LIME,.3));h.rotation.x=Math.PI/2;w.add(t,h);w.position.set(x,.46,z);W.push(w);g.add(w)}
 const dr=human({shirt:LIME,hat:"cap",hatColor:COB,scale:.82});dr.position.set(1.85,.55,.45);dr.rotation.y=Math.PI/2;POSE.ride(dr,0);dr.userData.u.hips.position.y=.62;dr.userData.u.chest.rotation.x=0;g.add(dr);g.userData={wheels:W,driver:dr};return g}
function car(color=NEO){const g=new THREE.Group();const b=box(3.6,.7,1.7,color,.12);b.position.y=.65;g.add(b);const glass=new THREE.MeshStandardMaterial({color:0x9FD0FF,transparent:true,opacity:.45,roughness:.1});const c=new THREE.Mesh(new THREE.BoxGeometry(1.9,.6,1.5),glass);c.position.set(-.2,1.3,0);g.add(c);
 for(const[x,z]of[[1.15,.85],[1.15,-.85],[-1.15,.85],[-1.15,-.85]]){const w=new THREE.Mesh(new THREE.CylinderGeometry(.34,.34,.25,14),mat(0x111418,0));w.rotation.x=Math.PI/2;w.position.set(x,.34,z);g.add(w)}
 for(const z of[-.55,.55]){const h=box(.06,.14,.3,0xFFFFFF,1.2);h.position.set(1.8,.7,z);g.add(h)}return g}
function crate(c=LIME,s=.9,e=.35){return box(s,s,s,c,e)}
