/* ===== CYBERSHIELD: attack packets hit a shield dome; risk ring + reasons come from the backend analysis ===== */
V.cyber={name:"CyberShield",rig:rig({th:.6,ph:.5,d:130,ttx:-15,tty:8,ttz:0,min:60,max:220}),init(){
 const sc=this.scene=stage(new THREE.Scene(),[120,380],400),O=this.O={pk:[],hits:[]};
 O.net=new THREE.Group();const mini=Object.keys(st.nodes);mini.forEach(n=>{const[x,z]=st.nodes[n];const b=building(4,n.startsWith("WH")?2:3.4,4,n.startsWith("WH")?0x1558C9:0x0f2a66,n.length);b.position.set(x*.7,1.7,z*.7);O.net.add(b)});
 for(const[a,b]of st.edges){const A=st.nodes[a],B=st.nodes[b];O.net.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(A[0]*.7,.4,A[1]*.7),new THREE.Vector3(B[0]*.7,.4,B[1]*.7)]),new THREE.LineBasicMaterial({color:COB})))}O.net.position.set(-10,0,5);sc.add(O.net);
 O.dome=new THREE.Mesh(new THREE.SphereGeometry(42,32,20,0,Math.PI*2,0,Math.PI/2),new THREE.MeshBasicMaterial({color:NEO,transparent:true,opacity:.1,side:THREE.DoubleSide,depthWrite:false}));O.dome.position.set(-10,0,5);sc.add(O.dome);
 O.wire=new THREE.Mesh(new THREE.SphereGeometry(42.2,24,14,0,Math.PI*2,0,Math.PI/2),new THREE.MeshBasicMaterial({color:NEO,wireframe:true,transparent:true,opacity:.25}));O.wire.position.copy(O.dome.position);sc.add(O.wire);
 O.atk=new THREE.Group();O.atk.position.set(-110,12,-20);const oc=new THREE.Mesh(new THREE.OctahedronGeometry(4),mat(RED,.9));O.atk.add(oc);O.oc=oc;const al=label("sup_x  (supplier account)","#FF3B3B",1.2,512);al.position.y=8;O.atk.add(al);sc.add(O.atk);
 O.halo=new THREE.Mesh(new THREE.RingGeometry(6,6.6,32),new THREE.MeshBasicMaterial({color:RED,transparent:true,opacity:.7,side:THREE.DoubleSide}));O.atk.add(O.halo);
 for(let i=0;i<40;i++){const p=sph(.7,RED,1);p.visible=false;sc.add(p);O.pk.push({m:p,u:Math.random(),sp:.25+Math.random()*.2,off:new THREE.Vector3((Math.random()-.5)*14,(Math.random()-.5)*10,(Math.random()-.5)*14)})}
 O.gauge=new THREE.Mesh(new THREE.RingGeometry(9,11,48,1,0,.01),new THREE.MeshBasicMaterial({color:LIME,side:THREE.DoubleSide}));O.gauge.position.set(-10,32,-60);sc.add(O.gauge);O.gbg=new THREE.Mesh(new THREE.RingGeometry(9,11,48),new THREE.MeshBasicMaterial({color:0x16233d,side:THREE.DoubleSide}));O.gbg.position.copy(O.gauge.position);O.gbg.position.z-=.1;sc.add(O.gbg);
 O.risk=label("RISK 0","#2678f5",2);O.risk.position.set(-10,32,-59);sc.add(O.risk);O.rs=panel(40,18,640);O.rs.position.set(-10,12,-60);sc.add(O.rs);
 O.lock=new THREE.Group();const lb=box(4,3.2,1.2,GREY,.2);lb.position.y=1.6;const sh=new THREE.Mesh(new THREE.TorusGeometry(1.3,.3,8,16,Math.PI),mat(GREY,.2));sh.position.y=3.2;O.lock.add(lb,sh);O.lock.position.set(-110,26,-20);O.lock.visible=false;sc.add(O.lock);
 O.sec=human({shirt:0x1b1f27,pants:0x0a0f1c,vest:false,hat:"cap",hatColor:COB,scale:3});O.sec.position.set(30,0,30);O.sec.rotation.y=-2.2;sc.add(O.sec);const sl=label("SECURITY ANALYST","#2678f5",.9);sl.position.set(30,12,30);sc.add(sl)},
 update(st,t,dt){const O=this.O,R=this.rig,th=st.threat,sec=st.sec,active=th.active&&!th.contained,risk=sec?sec.risk:0,hex=th.contained?GREY:RED;
 O.oc.rotation.y=t*2;O.oc.visible=th.active;O.atk.visible=th.active;O.halo.rotation.x=t;O.oc.material.color.setHex(hex);O.oc.material.emissive.setHex(th.contained?0x222222:RED);O.halo.material.color.setHex(hex);O.lock.visible=th.contained;
 const tgt=new THREE.Vector3(-10,12,5).sub(O.atk.position),len=tgt.length();
 O.pk.forEach(p=>{p.m.visible=active;if(!active)return;p.u+=p.sp*dt;if(p.u>1){p.u=0;O.hits.push({pos:p.m.position.clone(),a:1})}const e=Math.min(1,p.u/.78);if(p.u>.78){p.m.visible=false;return}p.m.position.copy(O.atk.position).addScaledVector(tgt,e*.8).add(p.off.clone().multiplyScalar(1-e))});
 /* shield hits */
 O.dome.material.opacity=.1+(active?.08*Math.abs(Math.sin(t*6)):0);O.dome.material.color.setHex(th.contained?LIME:active?0xFFB020:NEO);O.wire.material.color.setHex(th.contained?LIME:NEO);
 if(O.gr!==risk){O.gr=risk;O.gauge.geometry.dispose();O.gauge.geometry=new THREE.RingGeometry(9,11,48,1,Math.PI/2,-Math.max(.01,risk/100*Math.PI*2))}O.gauge.material.color.setHex(risk>=70?RED:risk>=40?0xFFB020:LIME);
 setLabel(O.risk,sec?`RISK ${risk}`:"RISK —",risk>=70?"#FF3B3B":"#2678f5");
 redraw(O.rs,JSON.stringify([sec,th]),(g,W,H)=>{g.fillStyle="#080A0Dcc";g.fillRect(0,0,W,H);g.strokeStyle="#202A39";g.strokeRect(1,1,W-2,H-2);g.font="bold 28px monospace";g.fillStyle=th.contained?"#2678f5":th.active?"#FF3B3B":"#929BAA";g.fillText(th.contained?"✔ ACCOUNT CONTAINED":th.active?"⚠ ANOMALY DETECTED":"MONITORING…",20,44);g.font="22px monospace";g.fillStyle="#F5F7FA";
  (sec?sec.reasons.map(r=>"• "+r):["• no anomalies yet"]).concat(sec&&sec.actions.length?["→ "+sec.actions.join(" → ")]:[]).forEach((l,i)=>g.fillText(l,20,84+i*30))});
 /* impact flashes where packets land on the dome */
 O.hits=O.hits.filter(h=>(h.a-=dt*2)>0);if(!O.flash){O.flash=[];for(let i=0;i<12;i++){const f=new THREE.Mesh(new THREE.RingGeometry(1,1.5,20),new THREE.MeshBasicMaterial({color:0xFFB020,transparent:true,side:THREE.DoubleSide}));f.visible=false;this.scene.add(f);O.flash.push(f)}}
 O.flash.forEach((f,i)=>{const h=O.hits[i];f.visible=!!h;if(h){f.position.copy(h.pos);f.lookAt(O.dome.position);f.scale.setScalar(1+(1-h.a)*4);f.material.opacity=h.a}});
 if(th.contained){O.lock.position.y=26+Math.sin(t*2)}POSE.idle(O.sec,t);if(th.contained)POSE.thumbs(O.sec,t);
 if(auto(R)){R.ttx=-25;R.tty=10;R.ttz=-10;if(!reduce)R.th=.6+Math.sin(t*.1)*.25}stepRig(R,dt)},
 info(st){const s=st.sec;return s?`CyberShield risk <b style="color:${s.risk>=70?'#FF3B3B':'#2678f5'}">${s.risk}</b> · ${st.threat.contained?"contained":"active"}<br>${s.reasons.join(", ")}`:"Shield idle — monitoring. Start the scenario to trigger the simulated attack."}};
