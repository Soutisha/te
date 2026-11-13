/* ===== ROUTE: A* vs Dijkstra exploration order (real backend visited lists), route growth, closures, live vehicle ===== */
V.route={name:"Route",rig:rig({th:0,ph:1.15,d:95,ttx:12,tty:0,ttz:5,min:50,max:200,phMin:.5}),init(){
 const sc=this.scene=stage(new THREE.Scene(),[140,400]),O=this.O={n:{},e:{},key:"",t0:0,tube:null};
 for(const n in st.nodes){const[x,z]=st.nodes[n],wh=n.startsWith("WH"),g=new THREE.Group();g.position.set(x,0,z);const pad=cyl(4.4,4.4,.4,wh?COB:0x0f2a66,.2,24);pad.position.y=.2;g.add(pad);const ra=new THREE.Mesh(new THREE.RingGeometry(5,5.8,32),new THREE.MeshBasicMaterial({color:LIME,transparent:true,opacity:0,side:THREE.DoubleSide}));ra.rotation.x=-Math.PI/2;ra.position.y=.5;g.add(ra);
  const rd=new THREE.Mesh(new THREE.RingGeometry(6.4,7,32),new THREE.MeshBasicMaterial({color:NEO,transparent:true,opacity:0,side:THREE.DoubleSide}));rd.rotation.x=-Math.PI/2;rd.position.y=.5;g.add(rd);
  const b=building(wh?4:3,wh?2.4:4.2,3,wh?0x1558C9:0x0f2a66,n.length+1);b.position.y=wh?1.6:2.3;g.add(b);const lb=label(n,"#F5F7FA",.9);lb.position.y=7.5;g.add(lb);const ord=label("","#2678f5",.8);ord.position.y=10;g.add(ord);sc.add(g);O.n[n]={g,ra,rd,pad,ord}}
 for(const[a,b]of st.edges){const A=st.nodes[a],B=st.nodes[b],len=Math.hypot(B[0]-A[0],B[1]-A[1]),m=box(len,.1,1.2,0x16233d,.3);m.position.set((A[0]+B[0])/2,.1,(A[1]+B[1])/2);m.rotation.y=-Math.atan2(B[1]-A[1],B[0]-A[0]);sc.add(m);O.e[a+"|"+b]=O.e[b+"|"+a]=m;
  const w=label("","#929BAA",.6);w.position.set((A[0]+B[0])/2,2,(A[1]+B[1])/2);sc.add(w);setLabel(w,String(Math.round(Math.hypot(B[0]-A[0],B[1]-A[1])*1.2)),"#929BAA")}
 O.cones=[];O.rg=new THREE.Group();sc.add(O.rg);O.pg=new THREE.Group();sc.add(O.pg);
 O.veh=new THREE.Group();O.vs=scooter();O.vt=truck();O.veh.add(O.vs,O.vt);O.veh.visible=false;sc.add(O.veh);O.hdg=0;
 O.panel=panel(44,13,768);O.panel.position.set(-12,1,-46);O.panel.rotation.x=-Math.PI/2.4;sc.add(O.panel)},
 update(st,t,dt){const O=this.O,R=this.rig,ex=st.explore,key=JSON.stringify([ex&&ex.id,st.route.map(r=>r.n),st.blocked]);
 if(key!=O.key){O.key=key;O.t0=performance.now()/1000;while(O.rg.children.length)O.rg.remove(O.rg.children[0]);while(O.pg.children.length)O.pg.remove(O.pg.children[0]);O.tube=null;
  for(const k in O.e){O.e[k].material.color.setHex(0x16233d);O.e[k].material.emissive.setHex(0x16233d)}
  if(st.prev_route.length>1&&st.blocked.length)O.pg.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(st.prev_route.map(n=>new THREE.Vector3(st.nodes[n][0],.5,st.nodes[n][1])),false,"catmullrom",0),30,.25,6),mat(GREY,.15)));
  O.cones.forEach(c=>this.scene.remove(c));O.cones=[];for(const[a,b]of st.blocked){const A=st.nodes[a],B=st.nodes[b],m=[(A[0]+B[0])/2,(A[1]+B[1])/2];for(let i=-1;i<=1;i++){const c=cyl(0,.9,2.2,0xFF9E2C,.8,8);c.position.set(m[0]+i*1.5,1.1,m[1]+i*1.5);this.scene.add(c);O.cones.push(c)}const e=O.e[a+"|"+b];e.material.color.setHex(RED);e.material.emissive.setHex(RED)}
  if(st.route.length>1){const pts=st.route.map(p=>new THREE.Vector3(p.xy[0],.6,p.xy[1])),geo=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts,false,"catmullrom",0),60,.45,8),m=new THREE.Mesh(geo,mat(LIME,.9));O.rg.add(m);O.tube=geo}}
 const el=performance.now()/1000-O.t0,step=.7;
 for(const n in O.n){const k=O.n[n],ai=ex?ex.astar.indexOf(n):-1,di=ex?ex.dijkstra.indexOf(n):-1,aOn=ai>=0&&el>ai*step,dOn=di>=0&&el>di*step;k.ra.material.opacity=aOn?.85:0;k.rd.material.opacity=dOn?.6:0;setLabel(k.ord,aOn?"A* #"+(ai+1):"",dOn&&!aOn?"#2385FF":"#2678f5");k.pad.material.emissiveIntensity=aOn?.8:.2;k.ra.rotation.z=t}
 const exEnd=ex?Math.max(ex.astar.length,ex.dijkstra.length)*step+.3:0;if(O.tube){const total=O.tube.index.count,u=clamp((el-exEnd)/2,0,1);O.tube.setDrawRange(0,Math.floor(total*(reduce?1:u)/6)*6)}
 O.cones.forEach((c,i)=>c.position.y=1.1+Math.abs(Math.sin(t*4+i))*.2);
 const r=st.rider,tm=r.type=="truck";O.veh.visible=r.visible&&!!r.xy;O.vs.visible=!tm;O.vt.visible=!tm?false:true;O.veh.scale.setScalar(tm?1.2:2);
 if(r.xy){const tg=new THREE.Vector3(r.xy[0],0,r.xy[1]);if(O.veh.position.distanceTo(tg)>30)O.veh.position.copy(tg);const pv=O.veh.position.clone();O.veh.position.lerp(tg,Math.min(1,dt*9));const d=O.veh.position.clone().sub(pv);if(d.length()>.002){const h=Math.atan2(-d.z,d.x);let dh=h-O.hdg;while(dh>Math.PI)dh-=2*Math.PI;while(dh<-Math.PI)dh+=2*Math.PI;O.hdg+=dh*Math.min(1,dt*6)}O.veh.rotation.y=O.hdg;(tm?O.vt:O.vs).userData.wheels.forEach(w=>w.rotation.z-=r.moving?9*dt:0)}
 redraw(O.panel,JSON.stringify([ex,st.blocked,st.phase]),(g,W,H)=>{g.fillStyle="#080A0Dee";g.fillRect(0,0,W,H);g.strokeStyle="#202A39";g.strokeRect(1,1,W-2,H-2);g.font="bold 28px monospace";g.fillStyle="#2678f5";g.fillText("PATHFINDING (backend result)",20,40);g.font="24px monospace";
  if(!ex){g.fillStyle="#929BAA";g.fillText("waiting for a planned route…",20,90);return}g.fillStyle="#2678f5";g.fillText(`A*        explored ${ex.astar.length} nodes`,20,90);g.fillStyle="#2385FF";g.fillText(`Dijkstra  explored ${ex.dijkstra.length} nodes`,20,125);g.fillStyle="#F5F7FA";g.fillText(`from ${ex.from} → ${st.dest}   cost ${ex.cost}`,20,170);
  g.fillStyle="#929BAA";g.font="20px monospace";g.fillText(st.blocked.length?`${st.blocked.length} road(s) closed → recomputed`:"no closures",20,205)});
 if(auto(R)){R.ttx=12;R.ttz=5;R.tty=0}stepRig(R,dt)},
 info(st){const e=st.explore;return e?`A* explored <b style="color:#2678f5">${e.astar.length}</b> · Dijkstra <b style="color:#2385FF">${e.dijkstra.length}</b> · cost ${e.cost}<br>route: ${st.route.map(r=>r.n).join(" › ")||"—"}`:"No route planned yet."}};
