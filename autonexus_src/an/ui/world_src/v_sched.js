/* ===== SCHEDULING: dealership bays and technicians from the current dataset ===== */
function populateSchedule(scene,assets,state){
 while(assets.children.length)assets.remove(assets.children[0]);
 const bays=state.bays||[],technicians=state.techs||{};
 const columns=Math.max(1,Math.min(4,bays.length)),baySpacing=8;
 const rows=Math.ceil(bays.length/columns);
 const bayDepth=12;
 const bayGroup=new THREE.Group(),techGroup=new THREE.Group();
 assets.add(bayGroup,techGroup);
 const builtBays=[];
 bays.forEach((bay,index)=>{
  const column=index%columns,row=Math.floor(index/columns);
  const x=8+(column-(columns-1)/2)*baySpacing,z=2+row*bayDepth;
  const pad=box(6,.15,9,COB,.4);pad.position.set(x,.12,z);bayGroup.add(pad);
  for(const offset of[-2.6,2.6]){
   const post=box(.35,3.4,.35,GREY);post.position.set(x+offset,1.7,z-4.2);bayGroup.add(post)
  }
  const vehicle=car([NEO,0xE8EDF5,0x929BAA,0xFF9E2C][index%4]);
  vehicle.rotation.y=Math.PI/2;vehicle.position.set(x,-3,26+row*bayDepth);bayGroup.add(vehicle);
  const sign=label(`${bay.id}${bay.available?" · AVAILABLE":" · OCCUPIED"}`,
   bay.available?"#929BAA":"#FF3B3B",.72);
  sign.position.set(x,5.2,z-4);bayGroup.add(sign);
  const glow=new THREE.PointLight(bay.available?0xFFB020:0xFF3B3B,0,12);
  glow.position.set(x,2,z);bayGroup.add(glow);
  builtBays.push({id:bay.id,x,z,car:vehicle,glow,available:bay.available})
 });
 const technicianEntries=Object.entries(technicians);
 const techColumns=Math.max(1,Math.min(4,technicianEntries.length));
 const builtTechnicians={};
 technicianEntries.forEach(([id,skills],index)=>{
  const column=index%techColumns,row=Math.floor(index/techColumns);
  const x=24+column*2.2,z=2+row*4;
  const person=human({shirt:index%2?GREY:LIME,hat:"helmet",hatColor:0xFF9E2C,scale:1.6});
  person.position.set(x,0,z);techGroup.add(person);
  const name=label(id,"#F5F7FA",.6);name.position.y=2.45;
  name.scale.multiplyScalar(1/1.6);person.add(name);
  const skillLabel=label((skills||[]).join("/")||"No listed skills","#929BAA",.55,320);
  skillLabel.position.y=2.1;skillLabel.scale.multiplyScalar(1/1.6);person.add(skillLabel);
  builtTechnicians[id]={person,skillLabel,x,z}
 });
 return{bays:builtBays,technicians:builtTechnicians}
}

V.sched={
 name:"Scheduling",
 rig:rig({th:-.15,ph:.5,d:36,ttx:10,tty:2.5,ttz:2,min:18,max:100}),
 init(){
  const scene=this.scene=stage(new THREE.Scene(),[60,200],200);
  const O=this.O={bays:[],mech:{},datasetKey:null};
  const floor=box(40,.1,44,0x0c1220,.1);floor.position.set(8,.02,8);scene.add(floor);
  const wall=building(40,14,1,0x0b1a3d,9);wall.position.set(8,7,-5.5);scene.add(wall);
  const sign=label("SERVICE","#2678f5",1.4,512);sign.position.set(26,7,-4.8);scene.add(sign);O.sign=sign;
  const bench=box(8,1.1,1.6,0x1b2335,.1);bench.position.set(26,.55,-2);scene.add(bench);
  const benchLabel=label("TOOL BENCH","#929BAA",.8);benchLabel.position.set(26,3,-2);scene.add(benchLabel);
  O.assets=new THREE.Group();scene.add(O.assets);
  O.board=panel(16,9.6,640);O.board.position.set(8,8.6,-4.9);scene.add(O.board)
 },
 update(state,time,dt){
  const O=this.O,R=this.rig,assignments=state.mechs||{};
  const key=JSON.stringify([state.dest,state.techs,state.bays]);
  if(key!==O.datasetKey){
   const built=populateSchedule(this.scene,O.assets,state);
   O.bays=built.bays;O.mech=built.technicians;O.datasetKey=key
  }
  setLabel(O.sign,"SERVICE · "+state.dest,"#2678f5");
  O.bays.forEach((bay,index)=>{
   const occupied=Object.values(assignments).includes(index);
   const paused=state.phase==="recovered";
   bay.car.position.y+=((occupied?.1:-3)-bay.car.position.y)*Math.min(1,dt*3);
   bay.car.position.z+=((occupied?bay.z:26+Math.floor(index/Math.max(1,(state.bays||[]).length))*12)-bay.car.position.z)*Math.min(1,dt*3);
   bay.glow.intensity=occupied&&!paused?1.2+Math.sin(time*14)*.6:0
  });
  for(const [id,technician] of Object.entries(O.mech)){
   const bayIndex=assignments[id],bay=bayIndex==null?null:O.bays[bayIndex];
   const targetX=bay?bay.x:technician.x,targetZ=bay?bay.z+4:technician.z;
   const dx=targetX-technician.person.position.x,dz=targetZ-technician.person.position.z;
   const distance=Math.hypot(dx,dz);
   if(distance>.25){
    const step=Math.min(distance,4*dt);
    technician.person.position.x+=dx/distance*step;
    technician.person.position.z+=dz/distance*step;
    technician.person.rotation.y=Math.atan2(dx,dz);
    POSE.walk(technician.person,time*9,1)
   }else if(bay){
    technician.person.rotation.y=Math.PI;POSE.work(technician.person,time+bayIndex)
   }else{
    technician.person.rotation.y=Math.PI;POSE.idle(technician.person,time+id.length)
   }
  }
  redraw(O.board,JSON.stringify(state.ros)+state.phase+state.part,(g,width,height)=>{
   g.fillStyle="#080A0Dee";g.fillRect(0,0,width,height);
   g.strokeStyle="#2678f5";g.lineWidth=2;g.strokeRect(2,2,width-4,height-4);
   g.font="bold 26px monospace";g.fillStyle="#2678f5";
   g.fillText(`REPAIR ORDERS — ${state.part} ${state.part_name}`,20,38);
   g.font="20px monospace";g.fillStyle="#929BAA";
   g.fillText("RO        PRIORITY   TECH   BAY   STATUS",20,74);
   (state.ros||[]).slice(0,10).forEach((repair,index)=>{
    g.fillStyle=repair.status==="in_progress"?"#2678f5":"#F5F7FA";
    g.fillText(`${repair.id}    ${"★".repeat(repair.priority).padEnd(5," ")}   ${(repair.tech||"—").padEnd(6)}   ${repair.bay!=null?repair.bay+1:"—"}     ${repair.status}`,20,108+index*34)
   });
   if(state.phase==="recovered"){
    g.fillStyle="#2678f5";g.font="bold 24px monospace";
    g.fillText("✔ recovery verified",20,height-18)
   }
  });
  if(auto(R)){
   R.ttx=11;R.tty=2.5;R.ttz=2;
   if(!reduce)R.th=-.25+Math.sin(time*.12)*.25
  }
  stepRig(R,dt)
 },
 info(state){
  const repairs=state.ros||[],bays=state.bays||[];
  return repairs.length
   ?`Repair orders at ${state.dest}: ${repairs.length}<br>in progress: <b style="color:#2678f5">${repairs.filter(row=>row.status==="in_progress").length}</b> · dataset bays ${bays.length}`
   :"Waiting for stock to arrive — bays idle."
 }
};
