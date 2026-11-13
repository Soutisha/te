/* ===== FEDERATED: replays the REAL FedAvg run (GET /world/federated); raw data never leaves the dealers, only weights move ===== */
function populateFederatedClients(scene,group,clients){
 while(group.children.length)group.remove(group.children[0]);
 return clients.map((name,index)=>{
  const angle=index/Math.max(1,clients.length)*Math.PI*2+Math.PI/2;
  const x=Math.cos(angle)*30,z=Math.sin(angle)*30,model=new THREE.Group();
  model.position.set(x,0,z);
  const buildingMesh=building(6,4.5,6,0x0f2a66,index+31);buildingMesh.position.y=2.25;model.add(buildingMesh);
  const database=cyl(1.6,1.6,2.4,0x16233d,.1,18);database.position.set(0,1.2,5.5);model.add(database);
  const dataLabel=label("local data","#929BAA",.55);dataLabel.position.set(0,3.8,5.5);model.add(dataLabel);
  const nameLabel=label(name,"#F5F7FA",.9);nameLabel.position.y=8.2;model.add(nameLabel);
  const f1=label("","#2678f5",.7);f1.position.y=10.6;model.add(f1);group.add(model);
  const packets=[];
  for(let packetIndex=0;packetIndex<5;packetIndex++){
   const packet=sph(.4,LIME,1);scene.add(packet);packets.push(packet)
  }
  return{g:model,x,z,f1,pk:packets,n:name}
 })
}
V.fed={name:"Federated",rig:rig({th:.2,ph:.55,d:78,ttx:0,tty:6,ttz:6,min:45,max:170}),fed:null,init(){
 const sc=this.scene=stage(new THREE.Scene(),[100,320]),O=this.O={cl:[],pk:[],clientKey:null};
 const sv=building(8,14,8,0x1558C9,21);sv.position.set(0,7,0);sc.add(sv);O.core=sph(2.6,LIME,.9);O.core.position.y=17;sc.add(O.core);const sl=label("GLOBAL MODEL (FedAvg)","#2678f5",1.1,384);sl.position.set(0,23,0);sc.add(sl);
 O.clientGroup=new THREE.Group();sc.add(O.clientGroup);
 const sh=box(80,.05,80,COB,.1);sh.visible=false;sc.add(sh);O.chart=panel(46,24,820);O.chart.position.set(0,16,-46);sc.add(O.chart);O.bars=panel(26,18,520);O.bars.position.set(-48,10,-8);O.bars.rotation.y=.9;sc.add(O.bars);
 O.ds=human({shirt:0xF5F7FA,pants:0x1b1f27,vest:false,hair:0x2a1b12,scale:2.4});O.ds.position.set(10,0,12);O.ds.rotation.y=-.5;sc.add(O.ds);
 fetch("/world/federated").then(response=>{
  if(!response.ok)throw new Error(`Federated result request failed (${response.status})`);
  return response.json()
 }).then(result=>{this.fed=result}).catch(error=>{this.fedError=error.message})},
 update(st,t,dt){const O=this.O,R=this.rig,F=this.fed;
 if(!F){const message=this.fedError||"Loading federated results from backend…";redraw(O.chart,message,(g,W,H)=>{g.fillStyle="#080A0Dee";g.fillRect(0,0,W,H);g.fillStyle="#929BAA";g.font="28px monospace";g.fillText(message.slice(0,48),30,70)});stepRig(R,dt);return}
 const clientNames=F.clients||[],clientKey=JSON.stringify(clientNames);
 if(clientKey!==O.clientKey){O.cl=populateFederatedClients(this.scene,O.clientGroup,clientNames);O.clientKey=clientKey}
 const rounds=F.rounds,r=clamp(st.fed_round,0,rounds),training=st.phase!="idle"&&r<rounds,u=training?(t*.9)%1:(t*.25)%1;
 O.cl.forEach((c,i)=>{const up=u<.5,e=ease(up?u*2:(u-.5)*2);c.pk.forEach((p,k)=>{if(r==0){p.visible=false;return}const s=clamp(e*1.15-k*.04,0,1),a=up?s:1-s;p.position.set(lerp(c.x,0,a),lerp(3,16,a)+Math.sin(a*Math.PI)*4,lerp(c.z,0,a));p.material.color.setHex(up?NEO:LIME);p.material.emissive.setHex(up?NEO:LIME);p.visible=s>0&&s<1});setLabel(c.f1,`local F1 ${F.local_only_f1[c.n].toFixed(2)}`,"#929BAA")});
 O.core.scale.setScalar(1+.15*Math.sin(t*5));
 redraw(O.chart,"c"+r+st.phase,(g,W,H)=>{g.fillStyle="#080A0Dee";g.fillRect(0,0,W,H);g.strokeStyle="#202A39";g.strokeRect(1,1,W-2,H-2);g.font="bold 26px monospace";g.fillStyle="#2678f5";g.fillText(`PredictX federated training — round ${r}/${rounds}  (live: follows world phase)`,24,40);
  const L=70,T=70,w=W-L-30,h=H-T-60,all=F.fed_f1_curve.concat(F.central_f1_curve,[F.local_only_mean_f1]),lo=Math.min(...all)-.03,hi=Math.max(...all)+.03,X=i=>L+i/Math.max(1,rounds-1)*w,Y=v=>T+h-(v-lo)/(hi-lo)*h;
  g.strokeStyle="#202A39";g.fillStyle="#929BAA";g.font="16px monospace";for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4;g.beginPath();g.moveTo(L,Y(v));g.lineTo(L+w,Y(v));g.stroke();g.fillText(v.toFixed(2),12,Y(v)+5)}
  const line=(c,col,n,dash)=>{g.strokeStyle=col;g.lineWidth=3;g.setLineDash(dash||[]);g.beginPath();for(let i=0;i<=n;i++){i?g.lineTo(X(i),Y(c[i])):g.moveTo(X(i),Y(c[i]))}g.stroke();g.setLineDash([])};
  if(r>0){line(F.central_f1_curve,"#2385FF",r-1);line(F.fed_f1_curve,"#2678f5",r-1)}g.strokeStyle="#929BAA";g.lineWidth=2;g.setLineDash([8,6]);g.beginPath();g.moveTo(L,Y(F.local_only_mean_f1));g.lineTo(L+w,Y(F.local_only_mean_f1));g.stroke();g.setLineDash([]);
  g.font="18px monospace";g.fillStyle="#2678f5";g.fillText("federated",L,H-24);g.fillStyle="#2385FF";g.fillText("centralised",L+130,H-24);g.fillStyle="#929BAA";g.fillText("local-only mean",L+280,H-24);g.fillStyle="#F5F7FA";g.fillText(`final F1  fed ${F.federated.f1.toFixed(3)} · central ${F.centralised.f1.toFixed(3)} · local ${F.local_only_mean_f1.toFixed(3)}`,L+w-430,40+0)});
 redraw(O.bars,"b",(g,W,H)=>{g.fillStyle="#080A0Dee";g.fillRect(0,0,W,H);g.strokeStyle="#202A39";g.strokeRect(1,1,W-2,H-2);g.font="bold 24px monospace";g.fillStyle="#2678f5";g.fillText("BYTES MOVED",20,38);const a=F.communication_bytes_federated,b=F.raw_bytes_centralised,mx=b;
  g.fillStyle="#2678f5";g.fillRect(40,70,(W-80)*a/mx,36);g.fillStyle="#2385FF";g.fillRect(40,150,(W-80),36);g.fillStyle="#F5F7FA";g.font="20px monospace";g.fillText(`federated (weights) ${a.toLocaleString()} B`,40,128);g.fillText(`centralised (raw rows) ${b.toLocaleString()} B`,40,208);
  g.fillStyle="#FF9E2C";g.font="16px monospace";const w=(F.privacy_note||"").match(/.{1,40}(\s|$)/g)||[];w.forEach((l,i)=>g.fillText(l.trim(),40,250+i*22));g.fillStyle="#929BAA";g.fillText(F.label,40,H-16)});
 POSE.idle(O.ds,t);if(auto(R)){R.ttx=0;R.tty=6;R.ttz=0;if(!reduce)R.th=.2+Math.sin(t*.1)*.4}stepRig(R,dt)},
 info(st){const F=this.fed;return F?`FedAvg round ${st.fed_round}/${F.rounds} · ${F.clients.length} dealers\nfinal F1 fed ${F.federated.f1.toFixed(2)} · central ${F.centralised.f1.toFixed(2)} · local ${F.local_only_mean_f1.toFixed(2)}\nnot a privacy guarantee (no secure aggregation / DP)`:this.fedError||"Loading federated results…"}};
