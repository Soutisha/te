/* ===== OVERVIEW: the whole living world, every object a function of backend state ===== */
function populateOverviewService(state,service){
 while(service.children.length)service.remove(service.children[0]);
 const bays=state.bays||[],entries=Object.entries(state.techs||{}),builtBays=[],builtTechs={};
 bays.forEach((bay,index)=>{
  const x=(index-(bays.length-1)/2)*6,z=10;
  const pad=box(5,.15,7,COB,.4);pad.position.set(x,.12,z);service.add(pad);
  const vehicle=car([NEO,0xE8EDF5,0x929BAA,0xFF9E2C][index%4]);
  vehicle.rotation.y=Math.PI/2;vehicle.position.set(x,-3,z+30);service.add(vehicle);
  const sign=label(bay.id,bay.available?"#929BAA":"#FF3B3B",.65);
  sign.position.set(x,5,z-4);service.add(sign);builtBays.push({id:bay.id,x,z,car:vehicle})
 });
 entries.forEach(([id],index)=>{
  const x=10+(index%4)*2,z=20+Math.floor(index/4)*4;
  const person=human({shirt:index%2?GREY:LIME,hat:"helmet",hatColor:0xFF9E2C,scale:1.5});
  person.position.set(x,0,z);service.add(person);
  const name=label(id,"#F5F7FA",.5);name.position.y=2.6;name.scale.multiplyScalar(1/1.5);person.add(name);
  builtTechs[id]={person,x,z}
 });
 return{bays:builtBays,technicians:builtTechs}
}
V.overview={name:"Overview",rig:rig({th:.9,ph:.85,d:95,ttx:10}),init(){
 const sc=this.scene=stage(new THREE.Scene(),[90,260]),O=this.O={nodes:{},roads:{},shelf:{},glow:{},sup:{}};
 for(const n in st.nodes){const[x,z]=st.nodes[n],w=n.startsWith("WH"),g=new THREE.Group();g.position.set(x,0,z);
  const b=w?building(9,3.6,7,0x1558C9,3):building(7,6,7,0x0f2a66,n.charCodeAt(6)||5);b.position.y=w?1.8:3;g.add(b);
  if(w){const door=box(3,2.4,.2,0x030407);door.position.set(0,1.2,3.55);g.add(door)}else{const r=box(7.6,.6,7.6,INK);r.position.y=6.2;g.add(r);const sg=box(4,.7,.3,LIME,.9);sg.position.set(0,5.2,3.6);g.add(sg)}
  const lb=label(n,"#F5F7FA");lb.position.y=10;g.add(lb);
  const ring=new THREE.Mesh(new THREE.RingGeometry(6.5,7.3,40),new THREE.MeshBasicMaterial({color:LIME,transparent:true,opacity:0,side:THREE.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.position.y=.3;g.add(ring);O.glow[n]=ring;
  const im=new THREE.InstancedMesh(new THREE.BoxGeometry(.9,.9,.9),mat(LIME,.35),30);im.position.set(-6,.5,6);g.add(im);O.shelf[n]=im;sc.add(g);O.nodes[n]={g}}
 for(const[a,b]of st.edges){const A=st.nodes[a],B=st.nodes[b],len=Math.hypot(B[0]-A[0],B[1]-A[1]),m=box(len,.12,1.6,COB,.3);m.position.set((A[0]+B[0])/2,.1,(A[1]+B[1])/2);m.rotation.y=-Math.atan2(B[1]-A[1],B[0]-A[0]);sc.add(m);O.roads[a+"|"+b]=m;O.roads[b+"|"+a]=m}
 const vendorEntries=Object.entries(st.vendors);vendorEntries.forEach(([id,vendor],i)=>{const g=new THREE.Group();g.position.set((i-(vendorEntries.length-1)/2)*18,0,-62);const b=building(10,5,6,0x111827,i+7);b.position.y=2.5;g.add(b);const ch=cyl(.7,.9,5,0x1b2335,0);ch.position.set(3,6.5,0);g.add(ch);const l=label(vendor.name||id,"#929BAA");l.position.y=9;g.add(l);sc.add(g);O.sup[id]=b});
 O.threat=new THREE.Mesh(new THREE.OctahedronGeometry(2),mat(RED,.8));O.threat.position.set(-60,6,-35);O.threat.visible=false;sc.add(O.threat);O.threatLabel=label("","#FF3B3B");O.threatLabel.position.y=4;O.threat.add(O.threatLabel);
 /* rider: scooter+human, or truck+driver; one group, backend decides which */
 const R=new THREE.Group(),L=new THREE.Group();R.add(L);O.lean=L;O.sc=scooter();O.tr=truck();O.rh=human({shirt:LIME,hat:"helmet",hatColor:COB,scale:.9});O.rh.position.set(-.5,.245,0);O.rh.rotation.y=Math.PI/2;O.sc.add(O.rh);L.add(O.sc,O.tr);
 O.pkg=crate(LIME,.5,.6);O.pkg.position.set(-1.0,1.4,0);O.sc.add(O.pkg);const bc=new THREE.Mesh(new THREE.CylinderGeometry(.12,.12,9,6),new THREE.MeshBasicMaterial({color:LIME,transparent:true,opacity:.5}));bc.position.y=6;R.add(bc);O.bc=bc;R.visible=false;sc.add(R);O.rider=R;O.hdg=0;
 /* loader (at source) + manager (at destination) */
 O.loader=human({shirt:NEO,hat:"cap",hatColor:LIME,scale:1.5});O.loader.visible=false;sc.add(O.loader);O.lbox=crate(LIME,.5,.6);O.loader.userData.u.chest.add(O.lbox);O.lbox.position.set(0,.4,.42);
 O.mgr=human({shirt:0xF5F7FA,pants:0x1b1f27,hair:0x2a1b12,vest:false,scale:1.6});sc.add(O.mgr);O.mgrL=label("MANAGER","#2678f5",.7);O.mgrL.position.y=3.8;O.mgr.add(O.mgrL);O.mgrL.scale.multiplyScalar(1/1.6);O.excl=label("APPROVE?","#2678f5",.8);O.excl.position.y=5.4;O.mgr.add(O.excl);O.excl.scale.multiplyScalar(1/1.6);
 /* route + agents */
 O.routeG=new THREE.Group();sc.add(O.routeG);O.routeKey="";
 O.agents=[];["ORCH","INVENTORY","VENDOR","PREDICT","COMPLY","SCHEDULE"].forEach((n,i)=>{const s=sph(1.1,LIME,.7);const l=label(n,"#2678f5",.7);l.position.y=2.4;s.add(l);s.visible=false;sc.add(s);O.agents.push(s)});
 O.agLines=new THREE.LineSegments(new THREE.BufferGeometry(),new THREE.LineBasicMaterial({color:LIME,transparent:true,opacity:.5}));sc.add(O.agLines);
 /* service area follows the destination dealer */
 O.svc=new THREE.Group();sc.add(O.svc);const service=populateOverviewService(st,O.svc);O.bays=service.bays;O.mech=service.technicians;O.serviceKey=JSON.stringify([st.dest,st.techs,st.bays]);
 O.alert=new THREE.PointLight(RED,0,30);sc.add(O.alert);O.part=box(1.6,1.6,1.6,RED,1);sc.add(O.part);
 this.routeKey="";this.zone=0},
 update(st,t,dt){const O=this.O,R=this.rig,dest=st.nodes[st.dest],ph=st.phase;
 const serviceKey=JSON.stringify([st.dest,st.techs,st.bays]);
 if(serviceKey!==O.serviceKey){const service=populateOverviewService(st,O.svc);O.bays=service.bays;O.mech=service.technicians;O.serviceKey=serviceKey}
 /* routes */
 const key=JSON.stringify([st.route.map(r=>r.n),st.prev_route,st.blocked,st.scenario]);if(key!=O.routeKey){O.routeKey=key;while(O.routeG.children.length)O.routeG.remove(O.routeG.children[0]);
  if(st.prev_route.length&&st.blocked.length)O.routeG.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(st.prev_route.map(n=>new THREE.Vector3(st.nodes[n][0],.4,st.nodes[n][1])),false,"catmullrom",0),20,.18,6),mat(GREY,.2)));
  if(st.route.length>1)O.routeG.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(st.route.map(p=>new THREE.Vector3(p.xy[0],.5,p.xy[1])),false,"catmullrom",0),40,.35,8),mat(LIME,.9)));
  for(const k in O.roads){O.roads[k].material.color.setHex(COB);O.roads[k].material.emissive.setHex(COB);O.roads[k].material.emissiveIntensity=.3}
  for(const[a,b]of st.blocked){const m=O.roads[a+"|"+b];if(m){m.material.color.setHex(RED);m.material.emissive.setHex(RED);m.material.emissiveIntensity=1}}}
 /* shelves reflect backend stock */
 for(const n in O.shelf){const im=O.shelf[n],q=Math.min(30,st.stock[n]),m=new THREE.Matrix4();for(let i=0;i<30;i++){m.setPosition((i%6)*1.1,Math.floor(i/6)*1.1,0);im.setMatrixAt(i,m)}im.count=q;im.instanceMatrix.needsUpdate=true}
 /* shortage */
 const short=st.shortage>0&&ph!="idle";O.alert.position.set(dest[0],8,dest[1]);O.alert.intensity=short?(1.5+Math.sin(t*6))*2:0;O.part.visible=short;O.part.position.set(dest[0],11.5,dest[1]);O.part.rotation.y=t*2;
 const lit=["supplier","threat","compliance","route_planned","awaiting_approval","loaded"];
 for(const n in O.glow){const on=st.search_lit.includes(n)||(n==st.src&&lit.includes(ph));O.glow[n].material.opacity=on?.5+.4*Math.sin(t*5):(n==st.dest&&short?.6+.4*Math.sin(t*6):0);O.glow[n].material.color.setHex(n==st.dest&&short?RED:LIME)}
 for(const v in O.sup){const s=st.suppliers[v];O.sup[v].material[0].emissive.setHex(s=="selected"?NEO:s=="flagged"?RED:0xffffff);O.sup[v].material[0].emissiveIntensity=s=="idle"?.35:.8+.3*Math.sin(t*4)}
 O.threat.visible=st.threat.active;setLabel(O.threatLabel,st.threat.account||"security risk","#FF3B3B");if(st.threat.active){O.threat.rotation.y=t*2;const m=O.threat.material;m.color.setHex(st.threat.contained?GREY:RED);m.emissive.setHex(st.threat.contained?0x222222:RED);if(!st.threat.contained)O.threat.position.x=-60+((t*8)%40)}
 const ag=st.agents_active&&ph!="recovered",ctr=new THREE.Vector3(0,14,0),pts=[];O.agents.forEach((s,i)=>{s.visible=ag;const a=t*.5+i*Math.PI/3;s.position.set(Math.cos(a)*14,14+Math.sin(t*2+i)*1.2,Math.sin(a)*14);pts.push(ctr.clone(),s.position.clone())});O.agLines.visible=ag;O.agLines.geometry.setFromPoints(pts);
 /* rider: position only from backend; heading from movement; roll from turn rate */
 const r=st.rider,truckMode=r.type=="truck";O.rider.visible=r.visible&&!!r.xy;O.sc.visible=!truckMode;O.tr.visible=truckMode;O.pkg.visible=r.loaded&&(ph!="loaded"||st.pt>1.8);O.bc.visible=!reduce||true;
 O.rider.scale.setScalar(truckMode?1.5:2.4);
 if(r.xy){const tg=new THREE.Vector3(r.xy[0],0,r.xy[1]);if(O.rider.position.distanceTo(tg)>30)O.rider.position.copy(tg);const pv=O.rider.position.clone();O.rider.position.lerp(tg,Math.min(1,dt*9));const d=O.rider.position.clone().sub(pv);
  if(d.length()>.002){const h=Math.atan2(-d.z,d.x);let dh=h-O.hdg;while(dh>Math.PI)dh-=2*Math.PI;while(dh<-Math.PI)dh+=2*Math.PI;O.hdg+=dh*Math.min(1,dt*6);O.lean.rotation.x=lerp(O.lean.rotation.x,clamp(-dh*2.2,-.35,.35),.2)}else O.lean.rotation.x*=.9;
  O.rider.rotation.y=O.hdg;const mv=r.moving,spin=(mv?9:0)*dt;(truckMode?O.tr:O.sc).userData.wheels.forEach(w=>w.rotation.z-=spin);if(!truckMode)O.sc.userData.fork.rotation.y=lerp(O.sc.userData.fork.rotation.y,-O.lean.rotation.x*.6,.2);
  O.rider.position.y=mv?Math.abs(Math.sin(t*14))*.05:0;if(!truckMode)POSE.ride(O.rh,t)}
 /* loader carries the package from the building door to the vehicle while phase==loaded (timing from backend phase clock) */
 const L=O.loader;L.visible=!!st.src&&(lit.includes(ph)||ph=="in_transit"&&st.progress<.05)&&r.visible!==undefined;
 if(st.src){const S=st.nodes[st.src],door=new THREE.Vector3(S[0],0,S[1]+5),rx=r.xy?new THREE.Vector3(r.xy[0]-2.6,0,r.xy[1]+2):door.clone().add(new THREE.Vector3(4,0,3));
  if(ph=="loaded"){const u=clamp(st.pt/1.8,0,1),e=ease(u);L.position.lerpVectors(door,rx,e);L.rotation.y=Math.atan2(rx.x-door.x,rx.z-door.z);O.lbox.visible=u<1;u<1?POSE.carry(L,t*9,1):POSE.thumbs(L,t)}
  else{L.position.copy(door);L.rotation.y=Math.PI;O.lbox.visible=false;ph=="awaiting_approval"||ph=="route_planned"?POSE.idle(L,t):POSE.idle(L,t)}}
 /* manager at destination: waves while approval pending, nods after */
 O.mgr.position.set(dest[0]-8,0,dest[1]+8);O.mgr.rotation.y=Math.PI/4+.5;O.excl.visible=O.mgrL.visible=true;O.excl.visible=st.approval_pending;
 if(st.approval_pending)POSE.wave(O.mgr,t);else if(st.approver&&["loaded","in_transit"].includes(ph))POSE.thumbs(O.mgr,t);else POSE.idle(O.mgr,t);
 /* bays + mechanics from backend assignment, in destination-local space */
 O.svc.position.set(dest[0],0,dest[1]);const asg=st.mechs;
 O.bays.forEach((b,i)=>{const occ=Object.values(asg).includes(i);b.car.position.y+=((occ?.1:-3)-b.car.position.y)*Math.min(1,dt*3);b.car.position.z+=((occ?b.z:b.z+30)-b.car.position.z)*Math.min(1,dt*3)});
 for(const tn in O.mech){const technician=O.mech[tn],p=technician.person,bi=asg[tn],bay=bi!=null?O.bays[bi]:null,tx=bay?bay.x:technician.x,tz=bay?bay.z+4:technician.z,dx=tx-p.position.x,dz=tz-p.position.z,dd=Math.hypot(dx,dz);
  if(dd>.25){const s=Math.min(dd,5*dt);p.position.x+=dx/dd*s;p.position.z+=dz/dd*s;p.rotation.y=Math.atan2(dx,dz);POSE.walk(p,t*9,1)}else if(bay){p.rotation.y=Math.PI;POSE.work(p,t)}else{p.rotation.y=Math.PI;POSE.idle(p,t+tn.length)}}
 /* camera: cinematic focus on backend phase */
 const f=({detected:"dest",prediction:"dest",supplier:"src",loaded:"src",in_transit:"rider",arrived:"dest",inventory_updated:"dest",tech_assigned:"bays",rejected:"dest",awaiting_approval:"dest"})[ph]||"center";let tx=10,tz=0;
 if(f=="dest")[tx,tz]=dest;if(f=="src"&&st.src)[tx,tz]=st.nodes[st.src];if(f=="rider"&&r.xy)[tx,tz]=r.xy;if(f=="bays")[tx,tz]=[dest[0]+18,dest[1]+10];
 R.td=({dest:62,src:58,rider:40,bays:44,center:95})[f];if(auto(R)){R.ttx=tx;R.ttz=tz;if(!reduce&&ph!="in_transit")R.th+=.0007}stepRig(R,dt)},
 info(st){return`stock ${st.dest}: <b style="color:#2678f5">${st.stock[st.dest]}</b> / need ${st.need}<br>progress ${(st.progress*100).toFixed(0)}% ${st.hold?"(rerouting…)":""}<br>vehicle: ${st.rider.type}${st.src?" from "+st.src:""}<br>audit ${st.audit.records} rec · ${st.audit.valid?"valid ✓":"INVALID"}<br>repair orders in progress: ${Object.keys(st.ro_status).length}`}};
