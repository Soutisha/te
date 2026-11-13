/* ===== SUPPLIERS: towers and policy gates reflect the loaded supplier CSV ===== */
function populateSupplierScene(state,group){
 while(group.children.length)group.remove(group.children[0]);
 const entries=Object.entries(state.vendors||{}),vendors={};
 entries.forEach(([id,vendor],index)=>{
  const x=(index-(entries.length-1)/2)*22,g=new THREE.Group();
  g.position.set(x,0,-18);
  const buildingMesh=building(10,6,7,0x111827,index+11);buildingMesh.position.y=3;g.add(buildingMesh);
  const chimney=cyl(.8,1,6,0x1b2335);chimney.position.set(3.5,8,0);g.add(chimney);
  const tower=cyl(1.1,1.1,10,0x0a0f1c);tower.material.transparent=true;tower.material.opacity=.3;tower.position.set(-7.5,5,0);g.add(tower);
  const fill=cyl(1,1,1,LIME,.8);fill.position.set(-7.5,.5,0);g.add(fill);
  const name=label(vendor.name||id,"#F5F7FA",.9);name.position.set(0,11,0);g.add(name);
  const details=label("","#929BAA",.7,512);details.position.set(0,9,0);g.add(details);
  const reliability=label("","#2678f5",.7,512);reliability.position.set(-3,12.5,0);g.add(reliability);
  const lane=box(2.4,.1,40,0x16233d,.3);lane.position.set(0,.06,5);g.add(lane);
  const gate=new THREE.Group();gate.position.set(0,0,12);
  const left=box(.4,3.4,.4,GREY);left.position.set(-1.6,1.7,0);
  const right=box(.4,3.4,.4,GREY);right.position.set(1.6,1.7,0);
  gate.add(left,right);
  const arm=new THREE.Group();arm.position.set(-1.6,2.8,0);
  const bar=box(3.2,.25,.25,RED,.8);bar.position.x=1.6;arm.add(bar);gate.add(arm);g.add(gate);
  const gateLabel=label("","#FF3B3B",.7,512);gateLabel.position.set(0,6,12);g.add(gateLabel);
  const pulses=[];
  for(let pulseIndex=0;pulseIndex<6;pulseIndex++){
   const pulse=sph(.35,NEO,.9);g.add(pulse);pulses.push(pulse)
  }
  group.add(g);
  vendors[id]={group:g,fill,details,reliability,arm,bar,gateLabel,pulses,
   building:buildingMesh,open:0}
 });
 return{vendors,key:JSON.stringify(entries.map(([id,vendor])=>[id,vendor.name]))}
}

V.suppliers={
 name:"Suppliers",
 rig:rig({th:.35,ph:.5,d:55,ttx:0,tty:3,ttz:0,min:30,max:130}),
 init(){
  const scene=this.scene=stage(new THREE.Scene(),[70,240]),O=this.O={v:{}};
  O.depot=building(10,6,8,0x0f2a66,5);O.depot.position.set(0,3,24);scene.add(O.depot);
  const depotLabel=label("DEALER DEPOT","#F5F7FA",.9);depotLabel.position.set(0,9,24);scene.add(depotLabel);
  O.vendorGroup=new THREE.Group();scene.add(O.vendorGroup);
  const populated=populateSupplierScene(st,O.vendorGroup);O.v=populated.vendors;O.vendorKey=populated.key;
  O.manager=human({shirt:0x1b1f27,pants:0x0a0f1c,vest:false,hair:0x111111,scale:2});
  O.manager.position.set(10,0,10);scene.add(O.manager);
  const sign=label("COMPLYAI","#2678f5",.9);sign.position.set(10,6,10);scene.add(sign)
 },
 update(state,time,dt){
  const O=this.O,R=this.rig,entries=Object.entries(state.vendors||{});
  const key=JSON.stringify(entries.map(([id,vendor])=>[id,vendor.name]));
  if(key!==O.vendorKey){
   const populated=populateSupplierScene(state,O.vendorGroup);
   O.v=populated.vendors;O.vendorKey=populated.key
  }
  for(const [id,vendor] of entries){
   const item=O.v[id];if(!item)continue;
   const status=vendor.status,blocked=state.compliance&&state.compliance.checked===id&&!state.compliance.approved;
   const reliability=vendor.reliability;
   item.fill.scale.set(1,reliability*10,1);item.fill.position.y=reliability*5;
   const tone=reliability>.9?LIME:reliability>.8?NEO:RED;
   item.fill.material.color.setHex(tone);item.fill.material.emissive.setHex(tone);
   setLabel(item.reliability,"reliability "+reliability.toFixed(2),
    reliability>.9?"#2678f5":reliability>.8?"#2385FF":"#FF3B3B");
   setLabel(item.details,`${vendor.name} · limit $${vendor.limit}${vendor.restricted?" · RESTRICTED":""}`,
    vendor.restricted?"#FF3B3B":"#929BAA");
   item.building.material[0].emissive.setHex(status==="selected"?NEO:status==="flagged"?RED:0xffffff);
   item.building.material[0].emissiveIntensity=status==="idle"?.35:.8+.3*Math.sin(time*4);
   const open=status==="selected"&&!blocked?1:0;
   item.open+=(open-item.open)*Math.min(1,dt*3);
   item.arm.rotation.z=item.open*Math.PI/2*.9;
   item.bar.material.color.setHex(open?LIME:RED);item.bar.material.emissive.setHex(open?LIME:RED);
   const reasons=state.compliance?.reasons||[];
   setLabel(item.gateLabel,blocked?"BLOCKED: "+reasons.slice(0,2).join(", "):
    status==="selected"?"APPROVED LANE":status==="flagged"?"UNDER REVIEW":"IDLE",
    blocked?"#FF3B3B":status==="selected"?"#2678f5":"#929BAA");
   item.pulses.forEach((pulse,index)=>{
    const active=status!=="idle";pulse.visible=active;
    const fraction=((time*.18+index/6)%1);let z=lerp(-3,26,fraction);
    if(!item.open&&z>10.5)z=10.5-index*.7;
    pulse.position.set(0,.8,z);
    pulse.material.color.setHex(blocked||status==="flagged"?RED:NEO);
    pulse.material.emissive.setHex(blocked||status==="flagged"?RED:NEO)
   })
  }
  O.manager.rotation.y=-Math.PI/2.2;
  state.compliance?POSE.thumbs(O.manager,time):POSE.idle(O.manager,time);
  if(auto(R)){R.ttx=0;R.tty=3;R.ttz=2;if(!reduce)R.th=.35+Math.sin(time*.12)*.3}
  stepRig(R,dt)
 },
 info(state){
  return Object.entries(state.vendors||{}).map(([id,vendor])=>
   `${id} ${vendor.name}: ${vendor.status} · reliability ${vendor.reliability}`)
   .join("\n")+(state.compliance
    ?`\nPolicy check ${state.compliance.checked}: ${(state.compliance.reasons||[]).join(", ")}`
    :"")
 }
};
