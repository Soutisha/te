/* ===== core: constants, helpers, camera rig, view registry ===== */
const $=i=>document.getElementById(i),LIME=0xD4FF24,COB=0x1558C9,NEO=0x2385FF,RED=0xFF3B3B,GREY=0x929BAA,INK=0x030407,reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;
let st=null,renderer,cam,ws,lastSeq=0,cur="overview",lastPhase=null;const V={};let clock=0,lastT=performance.now()/1000;
const mat=(c,e=0,o={})=>new THREE.MeshStandardMaterial(Object.assign({color:c,emissive:c,emissiveIntensity:e,roughness:.6},o));
const box=(w,h,d,c,e=0,o)=>new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat(c,e,o));
const cyl=(r1,r2,h,c,e=0,seg=12)=>new THREE.Mesh(new THREE.CylinderGeometry(r1,r2,h,seg),mat(c,e));
const sph=(r,c,e=0)=>new THREE.Mesh(new THREE.SphereGeometry(r,14,12),mat(c,e));
const lerp=(a,b,u)=>a+(b-a)*u,clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),ease=u=>u<.5?2*u*u:1-Math.pow(-2*u+2,2)/2;
function label(txt,col="#F5F7FA",s=1,w=256){const c=document.createElement("canvas");c.width=w;c.height=64;const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),transparent:true,depthTest:false}));sp.userData={c,col,w};sp.scale.set(8*s*w/256,2*s,1);setLabel(sp,txt,col);return sp}
function setLabel(sp,txt,col){const u=sp.userData;if(u.txt===txt&&u.col===(col||u.col))return;u.txt=txt;if(col)u.col=col;const g=u.c.getContext("2d");g.clearRect(0,0,u.w,64);g.font="bold 26px monospace";g.fillStyle=u.col;g.textAlign="center";g.fillText(txt,u.w/2,40);sp.material.map.needsUpdate=true}
/* a flat canvas "screen" in 3D (boards, charts) */
function panel(w,h,px=512){const c=document.createElement("canvas");c.width=px;c.height=Math.round(px*h/w);const t=new THREE.CanvasTexture(c);const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:t,transparent:true,side:THREE.DoubleSide}));m.userData={c,g:c.getContext("2d"),t,key:""};return m}
function redraw(p,key,fn){if(p.userData.key===key)return;p.userData.key=key;const g=p.userData.g,c=p.userData.c;g.clearRect(0,0,c.width,c.height);fn(g,c.width,c.height);p.userData.t.needsUpdate=true}
/* lit-window facade texture so buildings read as buildings, not boxes */
const _tex={};function facade(col,rows=5,cols=6,seed=1){const k=col+rows+cols+seed;if(_tex[k])return _tex[k];const c=document.createElement("canvas");c.width=cols*16;c.height=rows*16;const g=c.getContext("2d");g.fillStyle="#"+col.toString(16).padStart(6,"0");g.fillRect(0,0,c.width,c.height);let s=seed;const R=()=>(s=(s*16807)%2147483647)/2147483647;
 for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){g.fillStyle=R()>.35?"#D8E8FF":"#0A1226";g.fillRect(x*16+3,y*16+4,10,8)}const t=new THREE.CanvasTexture(c);t.magFilter=THREE.NearestFilter;return _tex[k]=t}
function building(w,h,d,col,seed){const tex=facade(col,Math.max(2,Math.round(h/1.2)),Math.max(3,Math.round(w/1.2)),seed||1);const side=new THREE.MeshStandardMaterial({map:tex,emissiveMap:tex,emissive:0xffffff,emissiveIntensity:.35,roughness:.7});const top=mat(0x0a0f1c,0);return new THREE.Mesh(new THREE.BoxGeometry(w,h,d),[side,side,top,top,side,side])}
function stage(scene,fog=[80,300],ground=300){scene.background=new THREE.Color(INK);scene.fog=new THREE.Fog(INK,fog[0],fog[1]);scene.add(new THREE.HemisphereLight(0x8fb0ff,0x10131c,.9));const dl=new THREE.DirectionalLight(0xffffff,.8);dl.position.set(40,80,30);scene.add(dl);
 const gr=new THREE.GridHelper(ground,ground/5,0x202A39,0x0B1020);scene.add(gr);const g=box(ground,.2,ground,0x080A0D);g.position.y=-.2;scene.add(g);return scene}
/* camera rig: orbit around a target; manual drag overrides auto-focus for 6 s */
const rig=o=>Object.assign({th:.9,ph:.85,d:95,tx:0,ty:0,tz:0,ttx:0,tty:0,ttz:0,manual:-1e9,min:20,max:200,spin:.0007,phMin:.2,phMax:1.5},o);
function stepRig(R,dt){if(R.td!=null&&auto(R))R.d+=(R.td-R.d)*Math.min(1,dt*1.5);R.tx+=(R.ttx-R.tx)*Math.min(1,dt*3);R.ty+=(R.tty-R.ty)*Math.min(1,dt*3);R.tz+=(R.ttz-R.tz)*Math.min(1,dt*3);
 cam.position.set(R.tx+Math.sin(R.th)*Math.cos(R.ph)*R.d,R.ty+Math.sin(R.ph)*R.d,R.tz+Math.cos(R.th)*Math.cos(R.ph)*R.d);cam.lookAt(R.tx,R.ty,R.tz)}
const auto=R=>performance.now()-R.manual>6000;
function inputs(){let px,py,down=false,pan=false;const c=renderer.domElement;c.onpointerdown=e=>{down=true;pan=e.shiftKey||e.button==2;px=e.clientX;py=e.clientY;V[cur].rig.manual=performance.now()};c.oncontextmenu=e=>e.preventDefault();
 addEventListener("pointerup",()=>down=false);addEventListener("pointermove",e=>{if(!down)return;const R=V[cur].rig,dx=e.clientX-px,dy=e.clientY-py;px=e.clientX;py=e.clientY;R.manual=performance.now();if(pan){R.ttx-=dx*.15;R.ttz-=dy*.15}else{R.th-=dx*.006;R.ph=clamp(R.ph+dy*.005,R.phMin,R.phMax)}});
 c.onwheel=e=>{const R=V[cur].rig;R.d=clamp(R.d+e.deltaY*.1,R.min,R.max);R.manual=performance.now();e.preventDefault()};
 addEventListener("resize",()=>{renderer.setSize(innerWidth,innerHeight);cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix()})}
