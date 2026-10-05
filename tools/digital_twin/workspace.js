    const canvas = document.getElementById('gl');
    const gl = canvas.getContext('webgl', { antialias: true, alpha: false });
    const partDefs = {
      motor: { label:'2XL-430 모터', mesh:'motor', color:[.32,.56,.64], base:[0,.58,1.7] },
      bracket: { label:'EF25-F14 브라켓', mesh:'bracket', color:[.84,.42,.16], base:[1.9,.58,1.7] },
      connector: { label:'DXL TTL 케이블', mesh:'connector', color:[.18,.23,.29], base:[.3,.08,.9] },
      opencr: { label:'OpenCR REVH', mesh:'opencr', color:[.22,.62,.42], base:[-3.6,.03,-2.4], rot:[-90,0,0] },
      laptop: { label:'노트북', mesh:'laptop', color:[.35,.40,.48], base:[2,.03,-5.5] }
    };
    function makePart(key,index){const d=partDefs[key];return {id:`${key}-${index+1}`,key,pos:[d.base[0]+(index*.65),d.base[1]+(index*.35),d.base[2]],rot:d.rot?[...d.rot]:[0,0,0],stretch:1,rootSide:key==='bracket'?'plate':null,mates:key==='bracket'?{fork:null,plate:null}:null,joints:key==='motor'?{A:0,B:0}:null,axisIds:key==='motor'?{A:null,B:null}:null,assemblyRotation:null,connection:null};}
    const state = { motor:null, bracket:null, connector:null, opencr:null, laptop:null, desk:null, usbWire:null, rotor:null, workspace:null, yaw:.55, pitch:.35, distance:8, cameraTarget:[0,0,0], viewMode:'part', workspaceMode:'assembly', assemblyTool:'connect', auto:false, transformMode:'move', selectedKey:'motor', selectedId:'motor-1', pendingPort:null, parts:{motor:[makePart('motor',0)],bracket:[makePart('bracket',0)],connector:[makePart('connector',0)],opencr:[makePart('opencr',0)],laptop:[makePart('laptop',0)]}, drag:null, lastFrame:null };
    const $ = id => document.getElementById(id);
    const PROJECT_STORAGE_KEY = 'notifyi.digitalTwin.project.v2';
    const LEGACY_PROJECT_STORAGE_KEY = 'notifyi.digitalTwin.project.v1';
    let persistenceReady=false, autosaveBlocked=false, lastSavedSnapshot=null, saveTimer=null;
    const history={past:[],future:[],current:null,restoring:false};
    function projectSnapshot(){return JSON.stringify(NotifyiProjectState.capture(state.parts));}
    function updateHistoryButtons(){$('undoBtn').disabled=history.past.length===0;$('redoBtn').disabled=history.future.length===0;}
    function recordHistory(){
      if(!persistenceReady||history.restoring||state.drag)return;
      let next;try{next=projectSnapshot();}catch{return;}
      if(history.current===null){history.current=next;updateHistoryButtons();return;}
      if(next===history.current)return;
      history.past.push(history.current);if(history.past.length>80)history.past.shift();
      history.current=next;history.future=[];updateHistoryButtons();
    }
    function travelHistory(direction){
      const source=direction==='undo'?history.past:history.future,target=direction==='undo'?history.future:history.past;
      if(!source.length)return;
      const snapshot=source.pop();target.push(history.current);
      history.restoring=true;applyProject(NotifyiProjectState.decode(snapshot));history.current=snapshot;history.restoring=false;
      state.drag=null;renderPartList();updateSelectionControls();draw();updateHistoryButtons();
      setMateStatus(direction==='undo'?'이전 조립 상태로 되돌렸습니다.':'다시 실행했습니다.');
    }
    function showProjectStatus(message){$('projectStatus').textContent=message;}
    function applyProject(document){
      state.parts=Object.fromEntries(Object.keys(partDefs).map(key=>[key,document.parts[key].map((saved,index)=>Object.assign(makePart(key,index),saved))]));
      state.pendingPort=null;state.selectedKey='motor';state.selectedId='motor-1';
    }
    function restoreProject(){
      let saved;
      try{saved=localStorage.getItem(PROJECT_STORAGE_KEY)||localStorage.getItem(LEGACY_PROJECT_STORAGE_KEY);}
      catch{autosaveBlocked=true;showProjectStatus('브라우저 저장 공간을 사용할 수 없습니다. JSON 파일로 보관하세요.');return;}
      if(saved){
        try{const document=NotifyiProjectState.decode(saved);applyProject(document);lastSavedSnapshot=JSON.stringify(document);showProjectStatus('이 브라우저의 마지막 작업을 복원했습니다.');if(document.parts.bracket.some(part=>part.rootSide==='fork'&&(part.mates.fork||part.mates.plate)))setMateStatus('이전 프로젝트의 축 고정 방향을 그대로 복원했습니다. 사진 속 조립과 방향이 다를 수 있습니다.');}
        catch(error){autosaveBlocked=true;showProjectStatus(`저장본 오류: ${error.message} 기존 저장본은 덮어쓰지 않습니다.`);}
      }else showProjectStatus('자동 저장 켜짐 · 조립 변경 시 이 브라우저에 저장합니다.');
      persistenceReady=true;
      history.current=projectSnapshot();updateHistoryButtons();
    }
    function scheduleAutosave(){
      if(!persistenceReady||autosaveBlocked)return;
      let snapshot;
      try{snapshot=projectSnapshot();}
      catch(error){showProjectStatus(`저장할 수 없음: ${error.message}`);return;}
      if(saveTimer){clearTimeout(saveTimer);saveTimer=null;}
      if(snapshot===lastSavedSnapshot)return;
      showProjectStatus('자동 저장 중…');
      saveTimer=setTimeout(()=>{
        saveTimer=null;
        saveSnapshot(snapshot);
      },300);
    }
    function saveSnapshot(snapshot){
      try{localStorage.setItem(PROJECT_STORAGE_KEY,snapshot);lastSavedSnapshot=snapshot;showProjectStatus(`자동 저장됨 · ${new Date().toLocaleTimeString()}`);}
      catch{autosaveBlocked=true;showProjectStatus('자동 저장 실패 · JSON으로 내보내 보관하세요.');}
    }
    window.addEventListener('pagehide',()=>{
      if(!persistenceReady||autosaveBlocked)return;
      if(saveTimer){clearTimeout(saveTimer);saveTimer=null;}
      try{const snapshot=JSON.stringify(NotifyiProjectState.capture(state.parts));if(snapshot!==lastSavedSnapshot)saveSnapshot(snapshot);}
      catch{/* Keep the last valid save; never overwrite it with invalid state. */}
    });
    function exportProject(){
      try{
        const json=NotifyiProjectState.encode(state.parts),url=URL.createObjectURL(new Blob([json],{type:'application/json'}));
        const link=document.createElement('a');link.href=url;link.download=`notifyi-assembly-${new Date().toISOString().slice(0,19).replaceAll(':','-')}.json`;document.body.append(link);link.click();link.remove();
        setTimeout(()=>URL.revokeObjectURL(url),60_000);showProjectStatus('JSON 파일을 내보냈습니다. 다운로드 폴더를 확인하세요.');
      }catch(error){showProjectStatus(`내보내기 실패: ${error.message}`);}
    }
    async function importProject(file){
      if(!file)return;
      try{
        if(file.size>1_000_000)throw new Error('프로젝트 파일은 1MB 이하여야 합니다.');
        const document=NotifyiProjectState.decode(await file.text());
        applyProject(document);autosaveBlocked=false;persistenceReady=true;lastSavedSnapshot=null;
        renderPartList();updateSelectionControls();draw();showProjectStatus('JSON을 불러왔습니다. 자동 저장 중…');
        if(document.parts.bracket.some(part=>part.rootSide==='fork'&&(part.mates.fork||part.mates.plate)))setMateStatus('이전 프로젝트의 축 고정 방향을 그대로 불러왔습니다. 사진 속 조립과 방향이 다를 수 있습니다.');
      }catch(error){showProjectStatus(`불러오기 실패: ${error.message} 현재 작업은 유지됩니다.`);}
      finally{$('projectFile').value='';}
    }
    function compile(type, source) { const shader=gl.createShader(type); gl.shaderSource(shader,source); gl.compileShader(shader); if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader)); return shader; }
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl.VERTEX_SHADER, `attribute vec3 a_position; attribute vec3 a_normal; uniform mat4 u_model; uniform mat4 u_view; uniform mat4 u_proj; varying vec3 v_normal; varying vec3 v_pos; void main(){ vec4 p=u_model*vec4(a_position,1.0); v_pos=p.xyz; v_normal=mat3(u_model)*a_normal; gl_Position=u_proj*u_view*p; }`));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, `precision mediump float; varying vec3 v_normal; varying vec3 v_pos; uniform vec3 u_color; void main(){ vec3 n=normalize(v_normal); vec3 key=normalize(vec3(-.45,.7,1.0)); vec3 fill=normalize(vec3(.65,-.4,-.7)); float light=.58+.29*max(dot(n,key),0.0)+.13*max(dot(n,fill),0.0); gl_FragColor=vec4(u_color*light,1.0); }`));
    gl.linkProgram(program); if(!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program)); gl.useProgram(program);
    const loc = { pos:gl.getAttribLocation(program,'a_position'), normal:gl.getAttribLocation(program,'a_normal'), model:gl.getUniformLocation(program,'u_model'), view:gl.getUniformLocation(program,'u_view'), proj:gl.getUniformLocation(program,'u_proj'), color:gl.getUniformLocation(program,'u_color') };
    const pickProgram=gl.createProgram();
    gl.attachShader(pickProgram,compile(gl.VERTEX_SHADER,`attribute vec3 a_position; uniform mat4 u_model,u_view,u_proj; void main(){gl_Position=u_proj*u_view*u_model*vec4(a_position,1.0);}`));
    gl.attachShader(pickProgram,compile(gl.FRAGMENT_SHADER,`precision mediump float; uniform vec3 u_id; void main(){gl_FragColor=vec4(u_id,1.0);}`));
    gl.linkProgram(pickProgram);if(!gl.getProgramParameter(pickProgram,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(pickProgram));
    const pickLoc={pos:gl.getAttribLocation(pickProgram,'a_position'),model:gl.getUniformLocation(pickProgram,'u_model'),view:gl.getUniformLocation(pickProgram,'u_view'),proj:gl.getUniformLocation(pickProgram,'u_proj'),id:gl.getUniformLocation(pickProgram,'u_id')};
    const identity=()=>[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
    function mul(a,b){const o=new Array(16).fill(0);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)o[c*4+r]+=a[k*4+r]*b[c*4+k];return o;}
    function perspective(fovy,aspect,near,far){const f=1/Math.tan(fovy/2), nf=1/(near-far);return [f/aspect,0,0,0,0,f,0,0,0,0,(far+near)*nf,-1,0,0,2*far*near*nf,0];}
    function lookAt(eye,center,up){let z=[eye[0]-center[0],eye[1]-center[1],eye[2]-center[2]];let zl=Math.hypot(...z);z=z.map(v=>v/zl);let x=[up[1]*z[2]-up[2]*z[1],up[2]*z[0]-up[0]*z[2],up[0]*z[1]-up[1]*z[0]];let xl=Math.hypot(...x);x=x.map(v=>v/xl);let y=[z[1]*x[2]-z[2]*x[1],z[2]*x[0]-z[0]*x[2],z[0]*x[1]-z[1]*x[0]];return [x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-x[0]*eye[0]-x[1]*eye[1]-x[2]*eye[2],-y[0]*eye[0]-y[1]*eye[1]-y[2]*eye[2],-z[0]*eye[0]-z[1]*eye[1]-z[2]*eye[2],1];}
    function translate(x,y,z){const m=identity();m[12]=x;m[13]=y;m[14]=z;return m;} function scale(x,y,z){const m=identity();m[0]=x;m[5]=y;m[10]=z;return m;} function rx(a){const c=Math.cos(a),s=Math.sin(a);return [1,0,0,0,0,c,s,0,0,-s,c,0,0,0,0,1];} function ry(a){const c=Math.cos(a),s=Math.sin(a);return [c,0,-s,0,0,1,0,0,s,0,c,0,0,0,0,1];} function rz(a){const c=Math.cos(a),s=Math.sin(a);return [c,s,0,0,-s,c,0,0,0,0,1,0,0,0,0,1];}
    function parseSTL(buf){const dv=new DataView(buf);const n=dv.getUint32(80,true);const verts=new Float32Array(n*9), norms=new Float32Array(n*9);let min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];for(let i=0;i<n;i++){const off=84+i*50;const no=[dv.getFloat32(off,true),dv.getFloat32(off+4,true),dv.getFloat32(off+8,true)];for(let v=0;v<3;v++){const p=[dv.getFloat32(off+12+v*12,true),dv.getFloat32(off+16+v*12,true),dv.getFloat32(off+20+v*12,true)];for(let k=0;k<3;k++){verts[i*9+v*3+k]=p[k];norms[i*9+v*3+k]=no[k];min[k]=Math.min(min[k],p[k]);max[k]=Math.max(max[k],p[k]);}}}const center=min.map((v,k)=>(v+max[k])/2);const radius=Math.max(...max.map((v,k)=>Math.abs(v-min[k])/2));for(let i=0;i<verts.length;i+=3){verts[i]-=center[0];verts[i+1]-=center[1];verts[i+2]-=center[2];}return {verts,norms,center,radius,n};}
    function createBuffer(data){const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);return b;}
    async function loadMesh(url){const response=await fetch(url);const model=parseSTL(await response.arrayBuffer());model.vbuf=createBuffer(model.verts);model.nbuf=createBuffer(model.norms);return model;}
    function addTri(v,n,a,b,c,normal){[a,b,c].forEach(p=>v.push(p[0],p[1],p[2]));for(let i=0;i<3;i++)n.push(normal[0],normal[1],normal[2]);}
    function addBox(v,n,center,half){const [x,y,z]=center,[hx,hy,hz]=half;const p=[[x-hx,y-hy,z-hz],[x+hx,y-hy,z-hz],[x+hx,y+hy,z-hz],[x-hx,y+hy,z-hz],[x-hx,y-hy,z+hz],[x+hx,y-hy,z+hz],[x+hx,y+hy,z+hz],[x-hx,y+hy,z+hz]];[[[0,1,2],[0,0,-1]],[[0,2,3],[0,0,-1]],[[4,6,5],[0,0,1]],[[4,7,6],[0,0,1]],[[0,4,5],[-1,0,0]],[[0,5,1],[-1,0,0]],[[1,5,6],[1,0,0]],[[1,6,2],[1,0,0]],[[2,6,7],[0,1,0]],[[2,7,3],[0,1,0]],[[3,7,4],[ -1,0,0]],[[3,4,0],[-1,0,0]]].forEach(face=>{const [a,b,c]=face[0];addTri(v,n,p[a],p[b],p[c],face[1]);});}
    function addTubeSegment(verts,norms,a,b,radius,segments=10){const d=[b[0]-a[0],b[1]-a[1],b[2]-a[2]],length=Math.hypot(...d);if(!length)return;const direction=d.map(value=>value/length),helper=Math.abs(direction[1])<.85?[0,1,0]:[1,0,0];let axisU=[direction[1]*helper[2]-direction[2]*helper[1],direction[2]*helper[0]-direction[0]*helper[2],direction[0]*helper[1]-direction[1]*helper[0]];const uLength=Math.hypot(...axisU);axisU=axisU.map(value=>value/uLength);const axisV=[direction[1]*axisU[2]-direction[2]*axisU[1],direction[2]*axisU[0]-direction[0]*axisU[2],direction[0]*axisU[1]-direction[1]*axisU[0]];for(let i=0;i<segments;i++){const a0=i*Math.PI*2/segments,a1=(i+1)*Math.PI*2/segments,c0=Math.cos(a0),s0=Math.sin(a0),c1=Math.cos(a1),s1=Math.sin(a1);const radial0=[axisU[0]*c0+axisV[0]*s0,axisU[1]*c0+axisV[1]*s0,axisU[2]*c0+axisV[2]*s0],radial1=[axisU[0]*c1+axisV[0]*s1,axisU[1]*c1+axisV[1]*s1,axisU[2]*c1+axisV[2]*s1];const p0=[a[0]+radial0[0]*radius,a[1]+radial0[1]*radius,a[2]+radial0[2]*radius],p1=[b[0]+radial0[0]*radius,b[1]+radial0[1]*radius,b[2]+radial0[2]*radius],p2=[b[0]+radial1[0]*radius,b[1]+radial1[1]*radius,b[2]+radial1[2]*radius],p3=[a[0]+radial1[0]*radius,a[1]+radial1[1]*radius,a[2]+radial1[2]*radius],normal=[(radial0[0]+radial1[0])*.5,(radial0[1]+radial1[1])*.5,(radial0[2]+radial1[2])*.5];addTri(verts,norms,p0,p1,p2,normal);addTri(verts,norms,p0,p2,p3,normal);}}
    function createConnectorMesh(){const verts=[],norms=[],path=[[-18,0,0],[-12,-1.5,1.8],[-4,-2.4,2.4],[4,-2.4,2.4],[12,-1.5,1.8],[18,0,0]];addTubeSegment(verts,norms,[-20,0,0],[-17,0,0],2.1,12);for(let i=0;i<path.length-1;i++)addTubeSegment(verts,norms,path[i],path[i+1],1.2,12);addTubeSegment(verts,norms,[17,0,0],[20,0,0],2.1,12);addBox(verts,norms,[-20,0,0],[2.8,3.2,2.6]);addBox(verts,norms,[20,0,0],[2.8,3.2,2.6]);[-1.25,0,1.25].forEach(offset=>{addTubeSegment(verts,norms,[-22.9,offset,0],[-20.8,offset,0],.42,8);addTubeSegment(verts,norms,[20.8,offset,0],[22.9,offset,0],.42,8);});const model={verts:new Float32Array(verts),norms:new Float32Array(norms),n:verts.length/9,radius:Math.hypot(23,3.5,2.5),center:[0,0,0]};model.vbuf=createBuffer(model.verts);model.nbuf=createBuffer(model.norms);return model;}
    function makeProceduralMesh(verts,norms){const model={verts:new Float32Array(verts),norms:new Float32Array(norms),n:verts.length/9};model.vbuf=createBuffer(model.verts);model.nbuf=createBuffer(model.norms);return model;}
    function boxMesh(center,half){const verts=[],norms=[];addBox(verts,norms,center,half);return makeProceduralMesh(verts,norms);}
    function createDeskMeshes(){const width=9,depth=7.5,centerZ=-2;return [
      {mesh:boxMesh([0,-.25,centerZ],[width,.25,depth]),color:[.51,.42,.34]},
      {mesh:boxMesh([0,-.52,centerZ+depth-.15],[width,.11,.16]),color:[.24,.25,.24]},
      {mesh:boxMesh([0,-.52,centerZ-depth+.15],[width,.11,.16]),color:[.24,.25,.24]},
      {mesh:boxMesh([-width+.15,-.52,centerZ],[.15,.11,depth]),color:[.24,.25,.24]},
      {mesh:boxMesh([width-.15,-.52,centerZ],[.15,.11,depth]),color:[.24,.25,.24]},
      ...[-width+.7,width-.7].flatMap(x=>[centerZ-depth+1,centerZ+depth-1].map(z=>({mesh:boxMesh([x,-2.87,z],[.25,2.4,.25]),color:[.18,.20,.20]})))
    ];}
    function createLaptopMesh(){const verts=[],norms=[];addBox(verts,norms,[0,0,0],[42,1.4,25]);addBox(verts,norms,[0,23,-24],[42,23,1.2]);addBox(verts,norms,[0,1.9,-22],[40,.7,1.2]);return makeProceduralMesh(verts,norms);}
    function createUsbWireMesh(){const verts=[],norms=[];addTubeSegment(verts,norms,[-20,0,0],[20,0,0],.85,12);return makeProceduralMesh(verts,norms);}
    function createRotorMesh(){const verts=[],norms=[];addBox(verts,norms,[4.5,0,0],[4.5,.8,.5]);addBox(verts,norms,[9,0,0],[1,1.6,.5]);return makeProceduralMesh(verts,norms);}
    async function load(){const [motor,bracket,opencr]=await Promise.all([loadMesh('./assets/2XL-430.step.stl'),loadMesh('./assets/EF25-F14.stp.stl'),loadMesh('./assets/OpenCR_REVH.stl')]);state.motor=motor;state.bracket=bracket;state.opencr=opencr;state.connector=createConnectorMesh();state.laptop=createLaptopMesh();state.desk=createDeskMeshes();state.usbWire=createUsbWireMesh();state.rotor=createRotorMesh();$('statusText').textContent='STEP 부분 검토 완료 · 실물 체결 미검증';$('statusDot').classList.add('live');restoreProject();focusAssembly();renderPartList();updateSelectionControls();requestAnimationFrame(draw);loadWorkspaceStatus();}
    const configuredJoints=[
      {id:2,name:'waist_lower_yaw',label:'허리 아래 · 좌우',zero_position:1034},
      {id:3,name:'waist_lower_pitch',label:'허리 아래 · 앞뒤',zero_position:3059},
      {id:4,name:'waist_upper_yaw',label:'허리 위 · 좌우',zero_position:2040},
      {id:5,name:'waist_upper_pitch',label:'허리 위 · 앞뒤',zero_position:12},
      {id:6,name:'neck_roll',label:'목 아래 · 갸우뚱',zero_position:38},
      {id:7,name:'neck_yaw',label:'목 · 좌우',zero_position:3039}
    ];
    function renderAxisIdEditor(){
      const motor=selectedPart(),visible=motor?.key==='motor';
      $('axisIdEditor').hidden=!visible;
      if(!visible)return;
      const available=state.workspace?[...new Set([...(state.workspace.active_ids||[]),...(state.workspace.unused_ids||[])])].sort((a,b)=>a-b):[1,2,3,4,5,6,7,8];
      const assigned=new Set(state.parts.motor.flatMap(part=>Object.values(part.axisIds||{})).filter(id=>id!==null));
      for(const axis of ['A','B']){
        const select=$(`axisId${axis}`),current=motor.axisIds?.[axis]??null;
        select.replaceChildren();
        const empty=document.createElement('option');empty.value='';empty.textContent='미배정';select.append(empty);
        for(const id of new Set([...available,...(current===null?[]:[current])])){
          const option=document.createElement('option');option.value=String(id);option.textContent=`ID ${id}`;
          option.disabled=assigned.has(id)&&id!==current;select.append(option);
        }
        select.value=current===null?'':String(current);
      }
    }
    function renderMotorIdOverlay(){
      const overlay=$('motorIdOverlay');if(!state.lastFrame)return;
      const scrollTop=overlay.scrollTop;overlay.replaceChildren();
      const joints=state.workspace?.joints?.length?state.workspace.joints:configuredJoints;
      const probe=state.workspace?.motor_probe;
      const scanned=new Map((probe?.motor_states||[]).map(item=>[item.id,item]));
      const ordered=[...state.parts.motor].sort((a,b)=>Number(b.id===state.selectedId&&state.selectedKey==='motor')-Number(a.id===state.selectedId&&state.selectedKey==='motor'));
      for(const motor of ordered){
        const selected=state.selectedKey==='motor'&&state.selectedId===motor.id;
        const card=document.createElement('div');card.className=`motor-id-card${selected?'':' compact'}`;
        const heading=document.createElement('strong');heading.textContent=`모터 #${state.parts.motor.indexOf(motor)+1} · A ${motor.axisIds?.A?'ID '+motor.axisIds.A:'미배정'} / B ${motor.axisIds?.B?'ID '+motor.axisIds.B:'미배정'}`;card.append(heading);
        if(selected){
          for(const axis of ['A','B']){
            const id=motor.axisIds?.[axis],joint=joints.find(item=>item.id===id),observed=scanned.get(id),line=document.createElement('span');
            const zero=joint?.zero_position!=null?`${joint.zero_position} tick`:'미설정';
            const torque=observed?.torque_enable===0?'0 해제':observed?.torque_enable===1?'1 인가':'미확인';
            line.textContent=`${axis}: zero ${id?zero:'—'} · 토크 ${id?torque:'—'}`;card.append(line);
          }
          const source=document.createElement('span');source.textContent=probe?`토크: ${new Date(probe.checked_at*1000).toLocaleTimeString()} 수동 스캔`:'토크: 수동 스캔 기록 없음';card.append(source);
        }
        overlay.append(card);
      }
      overlay.scrollTop=scrollTop;
    }
    function renderJointMap(data){
      const joints=data?.joints?.length?data.joints:configuredJoints,probe=data?.motor_probe;
      const ids=data?[...new Set([...(data.active_ids||[]),...(data.unused_ids||[])])].sort((a,b)=>a-b):[1,2,3,4,5,6,7,8];
      const states=new Map((probe?.motor_states||[]).map(item=>[item.id,item]));
      const map=$('jointMap'),signature=JSON.stringify([joints,ids,probe?.checked_at,probe?.motor_states]);
      if(map.dataset.signature===signature)return;
      map.dataset.signature=signature;map.replaceChildren();
      const heading=document.createElement('p');
      heading.textContent=probe?`토크·현재 위치: ${new Date(probe.checked_at*1000).toLocaleTimeString()} 수동 스캔 기록 · 실시간 아님`:data?'토크·현재 위치: 스캔 기록 없음':'설정값 스냅샷 · 서버로 열면 설정을 다시 읽습니다';
      map.append(heading);
      const table=document.createElement('table'),caption=document.createElement('caption');caption.textContent='모터 ID별 설정 zero와 마지막 스캔 상태';caption.className='sr-only';table.append(caption);
      const thead=document.createElement('thead'),headrow=document.createElement('tr');
      for(const label of ['ID','관절','zero (설정)','토크 (스캔)','현재 위치 (스캔)']){const cell=document.createElement('th');cell.scope='col';cell.textContent=label;headrow.append(cell);}thead.append(headrow);table.append(thead);
      const tbody=document.createElement('tbody');
      for(const id of ids){
        const joint=joints.find(item=>item.id===id),observed=states.get(id),row=document.createElement('tr');
        if(!joint)row.className='unused';
        const torque=observed?.torque_enable===0?'0 · 해제':observed?.torque_enable===1?'1 · 인가':'미확인';
        const values=[`ID ${id}`,joint?.label||joint?.name||'비구동',joint?.zero_position!=null?`${joint.zero_position} ticks`:'미설정',torque,Number.isInteger(observed?.present_position)?`${observed.present_position} ticks`:'미확인'];
        for(const value of values){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}
        if(observed?.hw_error){const note=document.createElement('span');note.className='motor-fault';note.textContent=` · 오류 0x${observed.hw_error.toString(16).padStart(2,'0').toUpperCase()}`;row.children[3].append(note);}
        tbody.append(row);
      }
      table.append(tbody);map.append(table);
      const foot=document.createElement('p');foot.textContent='ID 1·8은 설정상 비구동이며 zero 미설정. 2XL 하우징별 두 축의 ID 조합은 아직 확인되지 않았습니다.';map.append(foot);
    }
    function renderConnectionChecks(){
      const data=state.workspace, probe=data?.motor_probe, planned=state.parts.connector.filter(item=>item.connection).length;
      const expected=data?.active_ids||[2,3,4,5,6,7],responding=new Set(probe?.responding_ids||[]);
      const allResponded=expected.length>0&&expected.every(id=>responding.has(id));
      const motorLevel=probe?.fresh?(allResponded?'detected':'absent'):'unknown';
      const motorText=probe?.fresh?(allResponded?`설정된 ID ${expected.join(', ')} 전부 응답`:`${expected.filter(id=>responding.has(id)).length}/${expected.length}개 ID 응답 · 미응답 ${expected.filter(id=>!responding.has(id)).join(', ')||'없음'}`):probe?`마지막 검사 ${new Date(probe.checked_at*1000).toLocaleTimeString()} · 현재 상태 미확인`:'모터 응답 검사 기록 없음';
      const rows=[
        {level:planned?'planned':'unknown',title:`화면 배선 · ${planned}개 연결`,detail:'3D에서 지정한 경로이며 실물 연결 증거는 아님'},
        {level:data?.port_present?'detected':data?'absent':'unknown',title:data?.port_present?'USB 장치 경로 감지':data?'설정된 USB 장치 경로 없음':'USB 장치 상태 미확인',detail:`${data?.host||'현재 컴퓨터'} · ${data?.bus?.port||'/dev/ttyACM0'} · OpenCR 식별 전`},
        {level:motorLevel,title:`모터 응답 · ${motorLevel==='detected'?'검사 시 확인':motorLevel==='absent'?'일부/전체 미응답':'현재 미확인'}`,detail:motorText}
      ];
      const container=$('connectionChecks'),signature=JSON.stringify(rows);
      if(container.dataset.signature===signature)return;
      container.dataset.signature=signature;container.replaceChildren();
      for(const row of rows){const card=document.createElement('div');card.className='connection-check';card.dataset.level=row.level;const signal=document.createElement('span');signal.className='signal';signal.setAttribute('aria-hidden','true');const body=document.createElement('div');const title=document.createElement('strong');title.textContent=row.title;const detail=document.createElement('small');detail.textContent=row.detail;body.append(title,detail);card.append(signal,body);container.append(card);}
    }
    function renderCableMeasurements(){
      if(!state.motor)return;
      const rows=[];
      for(const cable of state.parts.connector){
        if(!cable.connection)continue;
        const ends=[cable.connection.a,cable.connection.b];
        const parts=ends.map(end=>findPart(end.key,end.id));
        if(parts.some(part=>!part))continue;
        const distance=NotifyiCableMeasure.straightLineMm(partAnchor(parts[0],ends[0].anchor),partAnchor(parts[1],ends[1].anchor),state.motor.radius);
        if(distance===null)continue;
        rows.push({label:`케이블 #${state.parts.connector.indexOf(cable)+1}`,ends:ends.map((end,index)=>portLabel(parts[index],end.anchor)).join(' ↔ '),distance:distance.toFixed(1),overReference:distance>180});
      }
      const container=$('cableMeasurements'),signature=JSON.stringify(rows);
      if(container.dataset.signature===signature)return;
      container.dataset.signature=signature;container.replaceChildren();
      if(!rows.length){const empty=document.createElement('p');empty.textContent='연결된 3P 케이블이 없습니다.';container.append(empty);return;}
      for(const row of rows){const line=document.createElement('p');line.dataset.overReference=String(row.overReference);line.textContent=`${row.label} · ${row.ends} · 직선거리 약 ${row.distance} mm${row.overReference?' · 참조 180 mm 초과 후보':''}`;container.append(line);}
    }
    let statusTimer=null;
    async function loadWorkspaceStatus(){renderJointMap(null);async function refresh(){try{const response=await fetch('/api/workspace',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();state.workspace=data;renderJointMap(data);renderAxisIdEditor();renderMotorIdOverlay();renderConnectionChecks();const port=data?.bus?.port||'/dev/ttyACM0',host=data?.host||'현재 컴퓨터';$('hardwareStatus').textContent=data.port_present?`${host}: ${port} 경로 확인 · 보드 식별과 모터 응답은 별도 상태 참조`:`${host}: ${port} 장치 경로 없음 · 삼성 노트북 연결 상태는 이 컴퓨터에서 확인 불가`;return true;}catch{state.workspace=null;renderAxisIdEditor();renderMotorIdOverlay();renderConnectionChecks();$('hardwareStatus').textContent='실물 상태 미확인 · 이 화면은 배선 계획입니다. 읽기 전용 서버로 열면 해당 컴퓨터의 USB 장치 경로를 확인합니다.';if(statusTimer){clearInterval(statusTimer);statusTimer=null;}return false;}}if(await refresh()&&location.protocol.startsWith('http'))statusTimer=setInterval(refresh,3000);}
    function resize(){const dpr=Math.min(2,devicePixelRatio||1),w=canvas.clientWidth*dpr,h=canvas.clientHeight*dpr;if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}}
    function drawMesh(mesh,model,color){gl.bindBuffer(gl.ARRAY_BUFFER,mesh.vbuf);gl.enableVertexAttribArray(loc.pos);gl.vertexAttribPointer(loc.pos,3,gl.FLOAT,false,0,0);gl.bindBuffer(gl.ARRAY_BUFFER,mesh.nbuf);gl.enableVertexAttribArray(loc.normal);gl.vertexAttribPointer(loc.normal,3,gl.FLOAT,false,0,0);gl.uniformMatrix4fv(loc.model,false,new Float32Array(model));gl.uniform3f(loc.color,color[0],color[1],color[2]);gl.drawArrays(gl.TRIANGLES,0,mesh.n*3);}
    function eulerRotation(rot){return mul(rz(rot[2]*Math.PI/180),mul(ry(rot[1]*Math.PI/180),rx(rot[0]*Math.PI/180)));}
    // Preview-only viewport limits. These are not DYNAMIXEL, collision, or per-ID operating limits.
    const previewJointBounds={A:{min:-90,max:90},B:{min:-90,max:90}};
    function clampPreviewJoint(axis,angle){const bounds=previewJointBounds[axis];return Math.max(bounds.min,Math.min(bounds.max,angle));}
    function partRotation(part){return part.assemblyRotation||eulerRotation(part.rot);}
    function partModel(part){const unit=(part.key==='laptop'?2.1:1)/state.motor.radius,stretch=part.key==='connector'?part.stretch||1:1;return mul(translate(part.pos[0],part.pos[1],part.pos[2]),mul(partRotation(part),scale(unit*stretch,unit,unit)));}
    function partMesh(part){return state[partDefs[part.key].mesh];}
    function partColor(part){const c=part.key==='connector'&&part.connection?[.26,.50,.82]:partDefs[part.key].color;if(part.id===state.selectedId&&part.key===state.selectedKey)return [Math.min(1,c[0]+.22),Math.min(1,c[1]+.2),Math.min(1,c[2]+.2)];return c;}
    function visibleParts(){return Object.keys(state.parts).flatMap(key=>state.parts[key].filter((part,index)=>{
      if(key!=='bracket'&&key!=='connector')return true;
      if(state.selectedKey===key&&state.selectedId===part.id)return true;
      if(key==='bracket'&&(part.mates?.fork||part.mates?.plate))return true;
      if(key==='connector'&&part.connection)return true;
      const initial=makePart(key,index);
      return part.pos.some((value,axis)=>value!==initial.pos[axis])||part.rot.some((value,axis)=>value!==initial.rot[axis]);
    }));}
    function findPart(key,id){return state.parts[key].find(part=>part.id===id)||null;}
    function rotateOffset(offset,angle){const a=angle*Math.PI/180,c=Math.cos(a),s=Math.sin(a);return [offset[0]*c-offset[1]*s,offset[0]*s+offset[1]*c,offset[2]];}
    function transformPoint(model,point){return [model[0]*point[0]+model[4]*point[1]+model[8]*point[2]+model[12],model[1]*point[0]+model[5]*point[1]+model[9]*point[2]+model[13],model[2]*point[0]+model[6]*point[1]+model[10]*point[2]+model[14]];}
    function rotateVector(rotation,point){return [rotation[0]*point[0]+rotation[4]*point[1]+rotation[8]*point[2],rotation[1]*point[0]+rotation[5]*point[1]+rotation[9]*point[2],rotation[2]*point[0]+rotation[6]*point[1]+rotation[10]*point[2]];}
    function inverseRotation(m){return [m[0],m[4],m[8],0,m[1],m[5],m[9],0,m[2],m[6],m[10],0,0,0,0,1];}
    function eulerFromRotation(m){const y=Math.asin(Math.max(-1,Math.min(1,-m[2]))),cy=Math.cos(y);const x=Math.abs(cy)>1e-5?Math.atan2(m[6],m[10]):0,z=Math.abs(cy)>1e-5?Math.atan2(m[1],m[0]):Math.atan2(-m[4],m[5]);return [x,y,z].map(value=>value*180/Math.PI);}
    // STEP 메시의 중심 보정값은 x/z +0.45 mm. A/B 혼·아이들러의 중심은 CAD 컴포넌트 외접 범위에서 읽었다.
    // EF25-F14의 y 범위는 7.44~37.01 mm, 중심은 22.22 mm다. 포크 축은 y=19.5, 판은 y≈37 mm.
    // +Z 본체 면의 네 볼트 홀은 원본 STEP의 EF25-F14 판 홀과 축이 일치한다.
    // 조립 공차/나사/스페이서와 회전 중 간섭은 별도 검증 대상이다.
    const axisMounts={A:{center:[-0.45,12,-0.45],rotation:[0,0,0],description:'정면 상부 혼 ↔ 뒷면 아이들러'},B:{center:[-0.45,-12,-0.45],rotation:[0,90,180],description:'오른쪽 하부 혼 ↔ 왼쪽 아이들러'}};
    const bracketPivot=[0,-2.72,0],bracketPlate=[0,14.78,0];
    // 이는 브라켓→본체 회전이며 본체 고정일 때 역행렬을 써 포크가 바깥쪽으로 향한다.
    const caseAlignment={front:rx(Math.PI/2),back:rx(-Math.PI/2),right:rz(-Math.PI/2),left:rz(Math.PI/2),top:rz(Math.PI),bottom:identity()};
    const caseNormals={front:[0,0,1],back:[0,0,-1],right:[1,0,0],left:[-1,0,0],top:[0,1,0],bottom:[0,-1,0]};
    const connectionPorts={
      motor:[
        {name:'3P · −X 측면',kind:'ttl',point:[-16.85,3.85,-5.85]},
        {name:'3P · −Z 측면',kind:'ttl',point:[-5.85,-3.85,-16.85]},
        {name:'축 A · 출력',kind:'mechanical',role:'shaft',axis:'A',point:[-0.45,12,20.45]},
        {name:'축 A · 아이들러',kind:'mechanical',role:'shaft',axis:'A',point:[-0.45,12,-20.45]},
        {name:'축 B · 출력',kind:'mechanical',role:'shaft',axis:'B',point:[20.45,-12,-0.45]},
        {name:'축 B · 아이들러',kind:'mechanical',role:'shaft',axis:'B',point:[-20.45,-12,-0.45]},
        {name:'본체 · +Z 네 홀 (STEP 정렬)',kind:'mechanical',role:'case',face:'front',point:[-0.45,12,18.55]},
        {name:'본체 · −Z 면 (간섭 미검증)',kind:'mechanical',role:'case',face:'back',point:[-0.45,12,-19.45]},
        {name:'본체 · +X 면 (간섭 미검증)',kind:'mechanical',role:'case',face:'right',point:[18.55,-12,-0.45]},
        {name:'본체 · −X 면 (간섭 미검증)',kind:'mechanical',role:'case',face:'left',point:[-19.45,-12,-0.45]},
        // 이전 JSON의 윗면/아랫면 연결은 읽되 새 조립에서는 선택하지 못한다.
        {name:'기존 윗면 결합 · 체결 불가',kind:'mechanical',role:'unsupported_case',face:'top',point:[-0.45,23.25,-0.45]},
        {name:'기존 아랫면 결합 · 체결 불가',kind:'mechanical',role:'unsupported_case',face:'bottom',point:[-0.45,-23.25,-0.45]}
      ],
      bracket:[
        {name:'포크 · 한 축의 출력 혼과 아이들러',kind:'mechanical',role:'fork',point:bracketPivot},
        {name:'본체 체결 판',kind:'mechanical',role:'plate',point:bracketPlate}
      ],
      opencr:[
        {name:'TTL 1 · 공통 버스',kind:'ttl',point:[34.9,-19.8,1.8]},
        {name:'TTL 2 · 공통 버스',kind:'ttl',point:[34.9,-9.1,1.8]},
        {name:'TTL 3 · 공통 버스',kind:'ttl',point:[34.9,1.2,1.8]},
        {name:'Micro-B USB · 노트북',kind:'usb',point:[2.1,54.5,-1.5]}
      ],
      laptop:[{name:'USB · OpenCR',kind:'usb',point:[42,1.5,0]}]
    };
    function portsFor(part){return connectionPorts[part.key]||[];}
    function partAnchor(part,index){const port=portsFor(part)[index]||portsFor(part)[0];return transformPoint(partModel(part),port?port.point:[0,0,0]);}
    function cablePortIndexes(part){return portsFor(part).map((port,index)=>port.kind==='ttl'?index:null).filter(index=>index!==null);}
    function partCenter(part){return [part.pos[0],part.pos[1],part.pos[2]];}
    function pointDistance(a,b){return Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);}
    function nearestPart(part,key){return state.parts[key].filter(candidate=>candidate.id!==part.id).sort((a,b)=>pointDistance(partCenter(part),partCenter(a))-pointDistance(partCenter(part),partCenter(b)))[0]||null;}
    function nearestAnchorIndex(part,target){const indexes=cablePortIndexes(part);return indexes.sort((a,b)=>pointDistance(partAnchor(part,a),target)-pointDistance(partAnchor(part,b),target))[0]??0;}
    function setMateStatus(message){$('mateStatus').textContent=message;$('stageStatus').textContent=message;}
    function bracketRoot(bracket){return bracket.rootSide==='plate'?bracket.mates.plate:bracket.mates.fork;}
    function bracketChild(bracket){return bracket.rootSide==='plate'?bracket.mates.fork:bracket.mates.plate;}
    function incomingBracketFor(motorId){return state.parts.bracket.find(bracket=>bracket.mates?.fork&&bracket.mates?.plate&&bracketChild(bracket)?.motorId===motorId)||null;}
    function connectedJointFor(motor){
      if(!motor||motor.key!=='motor')return null;
      const bracket=incomingBracketFor(motor.id);
      if(!bracket)return null;
      const driver=bracket.rootSide==='plate'?motor:findPart('motor',bracket.mates.fork.motorId);
      return driver?{motor:driver,axis:bracket.mates.fork.axis,bracket}:null;
    }
    function outgoingBracketsFor(motorId){return state.parts.bracket.filter(bracket=>bracketRoot(bracket)?.motorId===motorId);}
    function forkBracketsFor(motorId){return state.parts.bracket.filter(bracket=>bracket.mates?.fork?.motorId===motorId);}
    function plateBracketFor(motorId,face){return state.parts.bracket.find(bracket=>bracket.mates?.plate?.motorId===motorId&&bracket.mates.plate.face===face)||null;}
    function wouldCreateCycle(parentId,childId){let cursor=parentId;const seen=new Set();while(cursor&&!seen.has(cursor)){if(cursor===childId)return true;seen.add(cursor);const bracket=incomingBracketFor(cursor);cursor=bracket?bracketRoot(bracket)?.motorId:null;}return false;}
    function alignBracketToMotor(bracket,motor,axis){
      const mount=axisMounts[axis],unit=1/state.motor.radius;
      const axisWorld=transformPoint(partModel(motor),mount.center);
      const rotation=mul(partRotation(motor),mul(eulerRotation(mount.rotation),rz((motor.joints[axis]||0)*Math.PI/180)));
      const offset=rotateVector(rotation,bracketPivot.map(v=>v*unit));
      bracket.assemblyRotation=rotation;
      bracket.pos=axisWorld.map((v,i)=>v-offset[i]);
    }
    function alignCaseMotorToBracket(motor,bracket,face){
      const port=connectionPorts.motor.find(candidate=>candidate.face===face),unit=1/state.motor.radius;
      const rotation=mul(bracket.assemblyRotation,caseAlignment[face]);
      const plateWorld=transformPoint(partModel(bracket),bracketPlate);
      const spacer=rotateVector(bracket.assemblyRotation,[0,0.5*unit,0]);
      const offset=rotateVector(rotation,port.point.map(value=>value*unit));
      motor.assemblyRotation=rotation;
      motor.pos=plateWorld.map((value,i)=>value+spacer[i]-offset[i]);
    }
    function alignBracketToCaseMotor(bracket,motor,face){
      const port=connectionPorts.motor.find(candidate=>candidate.face===face),unit=1/state.motor.radius;
      const rotation=mul(partRotation(motor),inverseRotation(caseAlignment[face]));
      const surface=transformPoint(partModel(motor),port.point);
      const spacer=rotateVector(partRotation(motor),caseNormals[face].map(value=>value*0.5*unit));
      const offset=rotateVector(rotation,bracketPlate.map(value=>value*unit));
      bracket.assemblyRotation=rotation;
      bracket.pos=surface.map((value,i)=>value+spacer[i]-offset[i]);
    }
    function alignForkMotorToBracket(motor,bracket,axis){
      const mount=axisMounts[axis],unit=1/state.motor.radius;
      const drivenRotation=mul(eulerRotation(mount.rotation),rz((motor.joints[axis]||0)*Math.PI/180));
      const rotation=mul(bracket.assemblyRotation,inverseRotation(drivenRotation));
      const pivotWorld=transformPoint(partModel(bracket),bracketPivot);
      const offset=rotateVector(rotation,mount.center.map(value=>value*unit));
      motor.assemblyRotation=rotation;
      motor.pos=pivotWorld.map((value,i)=>value-offset[i]);
    }
    function updateMatedParts(){
      state.parts.motor.forEach(motor=>{motor.assemblyRotation=null;});
      state.parts.bracket.forEach(bracket=>{
        bracket.assemblyRotation=null;
        if(bracket.mates.fork&&!findPart('motor',bracket.mates.fork.motorId))bracket.mates.fork=null;
        if(bracket.mates.plate&&!findPart('motor',bracket.mates.plate.motorId))bracket.mates.plate=null;
      });
      const visited=new Set();
      function visit(motor){
        if(visited.has(motor.id))return;
        visited.add(motor.id);
        for(const bracket of outgoingBracketsFor(motor.id)){
          if(bracket.rootSide==='plate')alignBracketToCaseMotor(bracket,motor,bracket.mates.plate.face);
          else alignBracketToMotor(bracket,motor,bracket.mates.fork.axis);
          const end=bracketChild(bracket);
          if(!end)continue;
          const child=findPart('motor',end.motorId);
          if(child&&!visited.has(child.id)){
            if(bracket.rootSide==='plate')alignForkMotorToBracket(child,bracket,end.axis);
            else alignCaseMotorToBracket(child,bracket,end.face);
            visit(child);
          }
        }
      }
      state.parts.motor.filter(motor=>!incomingBracketFor(motor.id)).forEach(visit);
      state.parts.bracket.filter(bracket=>!bracketRoot(bracket)&&bracketChild(bracket)).forEach(bracket=>{
        const end=bracketChild(bracket),motor=findPart('motor',end.motorId);
        if(!motor)return;
        if(bracket.rootSide==='plate')alignBracketToMotor(bracket,motor,end.axis);
        else alignBracketToCaseMotor(bracket,motor,end.face);
      });
    }
    function updateCablePart(cable){if(!cable.connection)return;const a=findPart(cable.connection.a.key,cable.connection.a.id),b=findPart(cable.connection.b.key,cable.connection.b.id);if(!a||!b){cable.connection=null;cable.stretch=1;return;}const pa=partAnchor(a,cable.connection.a.anchor),pb=partAnchor(b,cable.connection.b.anchor),dx=pb[0]-pa[0],dy=pb[1]-pa[1],dz=pb[2]-pa[2],length=Math.hypot(dx,dy,dz);cable.pos=[(pa[0]+pb[0])/2,(pa[1]+pb[1])/2,(pa[2]+pb[2])/2];cable.rot[1]=Math.atan2(-dz,Math.hypot(dx,dy))*180/Math.PI;cable.rot[2]=Math.atan2(dy,dx)*180/Math.PI;cable.stretch=Math.max(.25,length/(40/state.motor.radius));}
    function updateConnections(){updateMatedParts();state.parts.connector.forEach(updateCablePart);}
    function usbLinkModel(){const a=partAnchor(state.parts.laptop[0],0),b=partAnchor(state.parts.opencr[0],3),dx=b[0]-a[0],dy=b[1]-a[1],dz=b[2]-a[2],length=Math.hypot(dx,dy,dz);return partModel({key:'connector',pos:[(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2],rot:[0,Math.atan2(-dz,Math.hypot(dx,dy))*180/Math.PI,Math.atan2(dy,dx)*180/Math.PI],stretch:Math.max(.1,length/(40/state.motor.radius))});}
    let autoFrame=null;
    function rotorModel(motor,axis){
      const port=connectionPorts.motor[axis==='A'?2:4],point=transformPoint(partModel(motor),port.point);
      const base=axis==='A'?identity():ry(Math.PI/2);
      const rotation=mul(partRotation(motor),mul(base,rz(motor.joints[axis]*Math.PI/180)));
      const unit=1/state.motor.radius;
      return mul(translate(...point),mul(rotation,scale(unit,unit,unit)));
    }
    function cameraBasis(){return {right:[Math.cos(state.yaw),0,-Math.sin(state.yaw)],up:[-Math.sin(state.pitch)*Math.sin(state.yaw),Math.cos(state.pitch),-Math.sin(state.pitch)*Math.cos(state.yaw)]};}
    function panCamera(dx,dy){const {right,up}=cameraBasis(),scale=2*state.distance*Math.tan(Math.PI/8)/canvas.clientHeight;state.cameraTarget=state.cameraTarget.map((value,i)=>value-(right[i]*dx-up[i]*dy)*scale);}
    function setViewMode(mode){state.viewMode=mode;document.querySelectorAll('[data-view-mode]').forEach(button=>{const active=button.dataset.viewMode===mode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});}
    function setAssemblyTool(tool){
      if(tool!=='connect'&&tool!=='place')return;
      state.assemblyTool=tool;state.pendingPort=null;
      document.querySelectorAll('[data-assembly-tool]').forEach(button=>{const active=button.dataset.assemblyTool===tool;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
      setMateStatus(tool==='connect'?'체결: 모터 회전축을 선택하거나 브라켓 판을 선택해 본체 체결면을 표시하세요.':'배치·회전: 선택한 부품의 핸들을 드래그하세요. 체결 지점은 체결 도구에서 표시됩니다.');draw();
    }
    function focusAssembly(){
      if(!state.motor)return;
      updateMatedParts();const motors=state.parts.motor;
      const center=[0,1,2].map(axis=>motors.reduce((sum,motor)=>sum+motor.pos[axis],0)/motors.length);
      const radius=Math.max(1.6,...motors.map(motor=>Math.hypot(...motor.pos.map((value,i)=>value-center[i]))+1.15));
      state.cameraTarget=[center[0],center[1],center[2]-2];state.distance=Math.min(25,Math.max(17,radius*2.9));
    }
    function setWorkspaceMode(mode){
      if(!['assembly','wiring','motion','status'].includes(mode))return;
      state.workspaceMode=mode;state.pendingPort=null;document.body.dataset.workspaceMode=mode;
      if(mode==='wiring'){state.yaw=-Math.PI*3/4;state.pitch=.25;$('cameraView').value='sockets';}
      document.querySelectorAll('[data-workspace-mode]').forEach(button=>{const active=button.dataset.workspaceMode===mode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
      const prompts={assembly:state.assemblyTool==='connect'?'체결: 모터 회전축을 선택하거나 브라켓 판을 선택해 본체 체결면을 표시하세요.':'배치·회전: 선택한 부품의 핸들을 드래그하세요.',wiring:'USB 선은 별도입니다. OpenCR 또는 모터의 3핀 소켓을 먼저 누른 뒤 상대 소켓을 누르세요. TTL 케이블은 필요하면 자동 추가됩니다.',motion:'체결된 상대 모터 몸체를 좌우 드래그하거나 ±90° 버튼으로 자세를 바꿉니다. 실제 모터는 움직이지 않습니다.',status:'화면 배선과 마지막 수동 스캔 결과는 서로 다른 상태입니다.'};
      setMateStatus(prompts[mode]);draw();
    }
    function draw(){if(!state.motor||!state.bracket||!state.opencr||!state.laptop||!state.desk)return;updateConnections();resize();gl.enable(gl.DEPTH_TEST);gl.clearColor(.09,.13,.17,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);const aspect=canvas.width/canvas.height;let dist=state.distance;let eye=[Math.cos(state.pitch)*Math.sin(state.yaw)*dist,Math.sin(state.pitch)*dist,Math.cos(state.pitch)*Math.cos(state.yaw)*dist].map((value,i)=>value+state.cameraTarget[i]);let view=lookAt(eye,state.cameraTarget,[0,1,0]);let proj=perspective(Math.PI/4,aspect,.01,100);state.lastFrame={view,proj,eye};gl.uniformMatrix4fv(loc.view,false,new Float32Array(view));gl.uniformMatrix4fv(loc.proj,false,new Float32Array(proj));state.desk.forEach(item=>drawMesh(item.mesh,identity(),item.color));visibleParts().forEach(part=>drawMesh(partMesh(part),partModel(part),partColor(part)));for(const motor of state.parts.motor)for(const axis of ['A','B'])drawMesh(state.rotor,rotorModel(motor,axis),axis==='A'?[.42,.95,.81]:[1,.72,.35]);drawMesh(state.usbWire,usbLinkModel(),[.32,.54,.78]);updatePortOverlay();drawGizmo();renderMotorIdOverlay();renderAxisGuide();renderFitAudit();renderConnectionChecks();renderCableMeasurements();recordHistory();scheduleAutosave();if(state.auto&&autoFrame===null){autoFrame=requestAnimationFrame(()=>{autoFrame=null;state.yaw+=.008;draw();});}}
    function renderFitAudit(){
      const audits=state.parts.bracket.map(bracket=>({bracket,audit:NotifyiFitAudit.assess(bracket,state.parts.motor)}));
      const invalid=audits.filter(({audit})=>audit.holes.status==='invalid');
      const interference=audits.filter(({audit})=>audit.sweep.status==='interference');
      const target=$('fitAudit');
      target.dataset.verdict=invalid.length?'invalid':interference.length?'interference':'unverified';
      target.textContent=invalid.length?`체결 불가 · 브라켓 ${invalid.map(({bracket})=>'#'+(state.parts.bracket.indexOf(bracket)+1)).join(', ')}의 판 체결면에 STEP 홀 패턴이 없습니다. 다른 체결면과 실물 안전성은 별도 검증이 필요합니다.`:interference.length?`부분 확인 / 간섭 확인 · 브라켓 ${interference.map(({bracket})=>'#'+(state.parts.bracket.indexOf(bracket)+1)).join(', ')}의 참조 배치는 A축 ±30°에서 간섭합니다. 다른 각도·브라켓·실물 안전성은 검증되지 않았습니다.`:'미검증 · 현재 조립의 모든 체결면·회전 경로를 검사한 결과가 아닙니다. 브라켓별 검증 범위를 확인하세요.';
      target.classList.toggle('fit-warning',Boolean(invalid.length||interference.length));
      const list=$('fitAuditList');list.replaceChildren();
      const labels={holes:'판 홀 정렬',static:'정적 간섭',sweep:'회전 간섭',wiring:'배선 여유'};
      const statuses={invalid:'체결 불가',limited:'부분 확인',interference:'간섭 확인',unverified:'미검증'};
      for(const {bracket,audit} of audits){
        const card=document.createElement('div');card.className='fit-audit-card';
        const heading=document.createElement('strong');heading.textContent=`브라켓 #${state.parts.bracket.indexOf(bracket)+1} · 판 ${audit.plateMotorId||'미연결'} / 포크 ${audit.forkMotorId||'미연결'}`;card.append(heading);
        for(const [key,label] of Object.entries(labels)){
          const item=audit[key],line=document.createElement('p');line.dataset.status=item.status;
          line.textContent=`${label}: ${statuses[item.status]} · ${item.detail}`;card.append(line);
        }
        list.append(card);
      }
    }
    let axisGuideMarkup='';
    function renderAxisGuide(){
      const selected=selectedPart(),motor=selected?.key==='motor'?selected:selected?.key==='bracket'?findPart('motor',selected.mates.fork?.motorId||selected.mates.plate?.motorId):state.parts.motor[0];
      if(!motor)return;
      const motorNumber=state.parts.motor.indexOf(motor)+1;
      const entries=Object.entries(axisMounts).map(([axis,mount])=>{
        const bracket=forkBracketsFor(motor.id).find(item=>item.mates.fork.axis===axis);
        const other=bracket?.mates.plate?findPart('motor',bracket.mates.plate.motorId):null;
        return `<div class="axis-card ${bracket?'mated':''}" data-axis="${axis}"><div class="axis-card-head"><strong><span class="axis-mark">${axis}</span>모터 #${motorNumber} · 축 ${axis}</strong><small>${bracket?other?bracket.rootSide==='plate'?'본체 고정 · 이 축 이동':'축 고정 · 다음 본체 이동':'포크 연결 · 판 대기':'브라켓 대기'}</small></div><p>${mount.description} · ${bracket?`브라켓 #${state.parts.bracket.indexOf(bracket)+1}${other?` ↔ 모터 #${state.parts.motor.indexOf(other)+1}`:''}`:'원형 윤곽선 선택'} · ${motor.joints[axis]}°</p></div>`;
      });
      const needsBracket=Object.keys(axisMounts).some(axis=>!forkBracketsFor(motor.id).some(part=>part.mates.fork.axis===axis))&&!state.parts.bracket.some(part=>!part.mates.fork);
      const markup=entries.join('')+(needsBracket?'<div class="axis-guide-action"><span>빈 축에 놓을 브라켓이 더 필요합니다.</span><button type="button" data-action="add-bracket">＋ 브라켓 추가</button></div>':'');
      if(axisGuideMarkup!==markup){axisGuideMarkup=markup;$('axisGuide').innerHTML=markup;$('axisGuide').querySelector('[data-action="add-bracket"]')?.addEventListener('click',()=>addPart('bracket'));}
      const forks=state.parts.bracket.filter(part=>part.mates.fork).length,links=state.parts.bracket.filter(part=>part.mates.fork&&part.mates.plate).length;
      $('connectionSummary').textContent=`모터 ${state.parts.motor.length}개 · 브라켓 포크 ${forks}개 · 모터 간 연결 ${links}개 · 선택 모터 #${motorNumber}: ${Object.keys(axisMounts).map(axis=>`${axis} ${forkBracketsFor(motor.id).some(part=>part.mates.fork.axis===axis)?'사용':'대기'}`).join(' / ')}`;
    }
    function selectedPart(){return state.parts[state.selectedKey].find(part=>part.id===state.selectedId)||state.parts[state.selectedKey][0];}
    function selectPart(key,id){state.selectedKey=key;state.selectedId=id;document.querySelectorAll('.placement-angle-row').forEach(row=>delete row.dataset.customOpen);document.body.classList.add('inspector-open');updateSelectionControls();renderPartList();draw();}
    function renderPartList(){const list=$('partList');if(!list)return;list.innerHTML=Object.keys(partDefs).map(key=>{const d=partDefs[key],parts=state.parts[key],selected=state.selectedKey===key;const instances=parts.length>1?`<div class="instance-list">${parts.map((part,index)=>{const detail=part.key==='bracket'?(part.mates.fork?` · ${part.mates.fork.axis}${part.mates.plate?'→모터':''}`:''):'';return `<button data-action="instance" data-id="${part.id}" class="${selected&&state.selectedId===part.id?'active':''}" aria-label="${d.label} #${index+1}${detail} 선택">#${index+1}${detail}</button>`;}).join('')}</div>`:'';return `<div class="part-row ${selected?'selected':''}" data-key="${key}"><button class="part-name" data-action="select">${d.label}</button><span class="part-count">${parts.length}</span><button data-action="remove" aria-label="${d.label} 마지막 부품 삭제" title="${parts.length===1?'최소 1개라 삭제할 수 없습니다':'마지막 인스턴스 삭제'}" ${parts.length===1?'disabled':''}>−</button><button data-action="add" aria-label="${d.label} 추가" title="부품 추가">＋</button>${instances}</div>`;}).join('');}
    function updateSelectionControls(){
      const part=selectedPart();if(!part)return;updateConnections();
      const number=state.parts[state.selectedKey].indexOf(part)+1,attached=positionLocked(part);
      const bracketDetail=part.key==='bracket'?` · 포크 ${part.mates.fork?`모터 #${state.parts.motor.findIndex(m=>m.id===part.mates.fork.motorId)+1}`:'대기'} / 판 ${part.mates.plate?`모터 #${state.parts.motor.findIndex(m=>m.id===part.mates.plate.motorId)+1}`:'대기'}`:'';
      $('selectionValue').textContent=`${partDefs[state.selectedKey].label} #${number}${attached?' · 연결로 배치됨':''}${bracketDetail}`;
      $('bracketRootEditor').hidden=part.key!=='bracket';
      const contacts=$('bracketContactStatus');contacts.hidden=part.key!=='bracket';
      if(part.key==='bracket'){
        const fork=part.mates.fork,plate=part.mates.plate;
        contacts.replaceChildren();
        const heading=document.createElement('strong');heading.textContent=`화면상 체결 후보 ${(fork?2:0)+(plate?1:0)}/3`;
        contacts.append(heading);
        for(const [label,detail,connected] of [
          ['출력 혼',fork?`모터 #${state.parts.motor.findIndex(m=>m.id===fork.motorId)+1} · ${fork.axis}축`:'축 선택 대기',!!fork],
          ['반대편 아이들러',fork?`같은 모터 · 같은 ${fork.axis}축`:'포크와 함께 연결',!!fork],
          ['본체 체결 판',plate?`모터 #${state.parts.motor.findIndex(m=>m.id===plate.motorId)+1} · ${plate.face}면${['top','bottom'].includes(plate.face)?' · 체결 불가':''}`:'다른 모터 선택 대기',!!plate]
        ]){const row=document.createElement('div');row.className=`contact-row ${connected?'connected':''}`;row.textContent=`${connected?'●':'○'} ${label} · ${detail}`;contacts.append(row);}
      }
      if(part.key==='bracket'){$('bracketRootSide').value=part.rootSide;$('bracketRootSide').disabled=Boolean(part.mates.fork&&part.mates.plate);$('bracketRootSide').querySelector('[value="fork"]').disabled=Boolean(part.mates.plate&&!part.mates.fork);}
      ['X','Y','Z'].forEach((axis,i)=>{$(`part${axis}`).value=part.pos[i];$(`part${axis}Value`).textContent=part.pos[i].toFixed(2);$(`part${axis}`).disabled=attached;});
      const angles=part.assemblyRotation?eulerFromRotation(part.assemblyRotation):part.rot;
      document.querySelectorAll('.placement-angle-row').forEach((row,i)=>{
        const angle=angles[i],preset=[-90,0,90].some(value=>Math.abs(angle-value)<1e-6),customOpen=row.dataset.customOpen==='true';
        row.querySelectorAll('[data-placement-angle]').forEach(button=>{button.setAttribute('aria-pressed',String(!customOpen&&Math.abs(angle-Number(button.dataset.placementAngle))<1e-6));button.disabled=attached;});
        const customButton=row.querySelector('[data-placement-custom]'),custom=row.querySelector('.placement-custom'),input=custom.querySelector('input');
        customButton.setAttribute('aria-pressed',String(!preset||customOpen));customButton.disabled=attached;
        custom.hidden=preset&&!customOpen;input.disabled=attached;input.value=String(attached?Number(angle.toFixed(2)):angle);
      });
      for(const axis of ['A','B']){$(`joint${axis}Value`).textContent=`${part.joints?.[axis]||0}°`;document.querySelectorAll(`[data-joint="${axis}"]`).forEach(button=>button.disabled=part.key!=='motor');}
      const linked=connectedJointFor(part),pose=$('connectedPose');pose.hidden=!linked;
      if(linked)$('connectedPoseHint').textContent=`브라켓 #${state.parts.bracket.indexOf(linked.bracket)+1}의 ${linked.axis}축 · 현재 ${linked.motor.joints[linked.axis]}°. 선택한 상대 모터 몸체를 좌우로 드래그할 수 있습니다.`;
      renderAxisIdEditor();
      $('moveMode').classList.toggle('active',state.transformMode==='move');$('rotateMode').classList.toggle('active',state.transformMode==='rotate');
    }
    function addPart(key){if(state.parts[key].length>=64){setMateStatus('한 종류의 부품은 최대 64개까지 저장할 수 있습니다.');return;}const part=makePart(key,state.parts[key].length);state.parts[key].push(part);selectPart(key,part.id);}
    function removePart(key){if(state.parts[key].length<=1){$('statusText').textContent='각 부품은 최소 1개를 유지합니다';return;}const removed=state.parts[key].at(-1);detachPart(removed);state.parts[key].pop();state.parts.connector.forEach(part=>{if(part.connection&&(part.connection.a.id===removed.id||part.connection.b.id===removed.id)){part.connection=null;part.stretch=1;}});if(state.selectedKey===key&&state.selectedId===removed.id)selectPart(key,state.parts[key][0].id);else{renderPartList();draw();}}
    function disconnectBracketEnd(bracket,side){
      const child=bracket.mates?.fork&&bracket.mates?.plate&&findPart('motor',bracketChild(bracket).motorId);
      if(child?.assemblyRotation)child.rot=eulerFromRotation(child.assemblyRotation);
      if(child)child.assemblyRotation=null;
      bracket.mates[side]=null;
    }
    function releaseIncomingMotor(motor){const incoming=incomingBracketFor(motor.id);if(!incoming)return;disconnectBracketEnd(incoming,incoming.rootSide==='plate'?'fork':'plate');setMateStatus('모터를 직접 움직여 상위 브라켓 연결을 해제했습니다.');}
    function positionLocked(part){return part.key==='motor'?Boolean(incomingBracketFor(part.id)):part.key==='bracket'?Boolean(part.mates?.fork||part.mates?.plate):part.key==='connector'?Boolean(part.connection):false;}
    function detachPart(part){
      if(part.key==='bracket'&&part.mates){disconnectBracketEnd(part,'plate');part.mates.fork=null;part.assemblyRotation=null;setMateStatus('브라켓의 포크와 판 연결을 해제했습니다.');}
      if(part.key==='motor'){
        for(const bracket of state.parts.bracket.filter(item=>item.mates.fork?.motorId===part.id||item.mates.plate?.motorId===part.id)){
          disconnectBracketEnd(bracket,'plate');bracket.mates.fork=null;bracket.assemblyRotation=null;
        }
        setMateStatus('선택 모터의 기계 연결을 해제했습니다.');
      }
      if(part.connection){part.connection=null;part.stretch=1;setMateStatus('케이블 연결을 해제했습니다.');}
    }
    function releaseForManualTransform(part){
      if(positionLocked(part)){setMateStatus('결합된 부품은 위치가 고정됩니다. 먼저 「선택 부품 연결 해제」를 누르세요.');return false;}
      return true;
    }
    function resetPart(part){detachPart(part);const index=state.parts[part.key].indexOf(part),fresh=makePart(part.key,index);part.pos=fresh.pos;part.rot=fresh.rot;part.stretch=fresh.stretch;part.rootSide=fresh.rootSide;part.mates=fresh.mates;part.joints=fresh.joints;part.assemblyRotation=null;part.connection=null;updateSelectionControls();renderPartList();draw();}
    function resetAllParts(){Object.keys(state.parts).forEach(key=>state.parts[key]=state.parts[key].map((part,index)=>makePart(key,index)));autosaveBlocked=false;state.pendingPort=null;selectPart(state.selectedKey,state.parts[state.selectedKey][0].id);}
    function loadExampleAssembly(){
      const hasAssembly=state.parts.motor.length>1||state.parts.bracket.some(part=>part.mates.fork||part.mates.plate)||state.parts.connector.some(part=>part.connection);
      if(hasAssembly&&!window.confirm('현재 조립 배치를 2모터 예제로 바꿀까요? 실행 취소로 복원할 수 있습니다.'))return;
      const base=makePart('motor',0),upper=makePart('motor',1),bracket=makePart('bracket',0);
      bracket.rootSide='plate';bracket.mates.plate={motorId:base.id,face:'front'};bracket.mates.fork={motorId:upper.id,axis:'A'};
      state.parts.motor=[base,upper];state.parts.bracket=[bracket];state.parts.connector=[makePart('connector',0)];
      state.pendingPort=null;state.yaw=.55;state.pitch=.27;focusAssembly();
      selectPart('bracket',bracket.id);
      setMateStatus('2모터 예제: 본체 +Z면의 네 홀은 STEP상 정렬됩니다. 하지만 A축 ±30° 회전 시 CAD 간섭이 확인돼 실제 구동 불가입니다.');
    }
    function snapBracket(bracket,motor,axis){bracket.mates.fork={motorId:motor.id,axis};updateMatedParts();setMateStatus(`모터 #${state.parts.motor.indexOf(motor)+1} ${axis}축의 출력 혼·아이들러에 포크를 함께 연결했습니다.`);}
    function snapBracketPlate(bracket,motor,face){bracket.mates.plate={motorId:motor.id,face};updateMatedParts();setMateStatus(`브라켓 판을 모터 #${state.parts.motor.indexOf(motor)+1} 본체 ${face}면에 연결했습니다. STEP 정렬은 +Z면만 확인했으며 실제 체결·회전 가능성은 미확인입니다.`);}
    function samePort(a,b){return a&&b&&a.key===b.key&&a.id===b.id&&a.anchor===b.anchor;}
    function portInUse(port,ignoreCableId=null){if(port.kind==='usb')return true;return state.parts.connector.find(cable=>cable.id!==ignoreCableId&&cable.connection&&([cable.connection.a,cable.connection.b].some(end=>samePort(end,port))));}
    function portLabel(part,index){const port=portsFor(part)[index];const number=state.parts[part.key].indexOf(part)+1;const name={motor:`M${number}`,bracket:'Bracket',opencr:'OpenCR',laptop:'노트북'}[part.key];return `${name} · ${port?.name||'PORT'}`;}
    function projectWorldPoint(point){return projectPoint(identity(),point);}
    function mechanicalPortInUse(port){
      const part=findPart(port.key,port.id);if(!part||port.kind!=='mechanical')return false;
      const role=portsFor(part)[port.anchor]?.role;
      if(part.key==='bracket')return Boolean(part.mates[role]);
      if(role==='shaft'){const axis=portsFor(part)[port.anchor].axis;return forkBracketsFor(part.id).some(bracket=>bracket.mates.fork.axis===axis);}
      return Boolean(plateBracketFor(part.id,portsFor(part)[port.anchor].face));
    }
    function validPortPair(first,second){
      if(!first||!second||first.kind!==second.kind)return false;
      if(first.kind==='mechanical'){
        if(new Set([first.key,second.key]).size!==2||![first.key,second.key].every(key=>key==='motor'||key==='bracket'))return false;
        const motorPort=first.key==='motor'?first:second,bracketPort=first.key==='bracket'?first:second;
        const motor=findPart('motor',motorPort.id),bracket=findPart('bracket',bracketPort.id);
        if(!motor||!bracket||mechanicalPortInUse(motorPort)||mechanicalPortInUse(bracketPort))return false;
        const motorRole=portsFor(motor)[motorPort.anchor]?.role,bracketRole=portsFor(bracket)[bracketPort.anchor]?.role;
        if(motorRole==='shaft'&&bracketRole==='fork'){
          if(bracket.mates.fork)return false;
          const plate=bracket.mates.plate;
          if(!plate)return true;
          if(plate.motorId===motor.id)return false;
          const parent=bracket.rootSide==='plate'?plate.motorId:motor.id,child=bracket.rootSide==='plate'?motor.id:plate.motorId;
          return !incomingBracketFor(child)&&!wouldCreateCycle(parent,child);
        }
        if(motorRole==='case'&&bracketRole==='plate'){
          if(bracket.mates.plate||bracket.rootSide==='fork'&&!bracket.mates.fork)return false;
          const fork=bracket.mates.fork;
          if(!fork)return true;
          if(fork.motorId===motor.id)return false;
          const parent=bracket.rootSide==='plate'?motor.id:fork.motorId,child=bracket.rootSide==='plate'?fork.motorId:motor.id;
          return !incomingBracketFor(child)&&!wouldCreateCycle(parent,child);
        }
        return false;
      }
      if(first.kind==='ttl')return (first.key==='motor'||first.key==='opencr')&&(second.key==='motor'||second.key==='opencr')&&!(first.key==='opencr'&&second.key==='opencr')&&!(first.key===second.key&&first.id===second.id);
      return false;
    }
    const svgNS='http://www.w3.org/2000/svg';
    const interfaces={
      motor:[
        // S3B-EH/EHR-3 컴포넌트의 조립 위치와 외접 범위에서 근사한 클릭 윤곽이다.
        {anchor:0,name:'3P · −X 측면 연결부 (CAD 부품 외접)',normal:[-1,0,0],shape:'socket',provisional:true,corners:[[-16.85,0.3,-10.6],[-16.85,7.4,-10.6],[-16.85,7.4,-1.1],[-16.85,0.3,-1.1]]},
        {anchor:1,name:'3P · −Z 측면 연결부 (CAD 부품 외접)',normal:[0,0,-1],shape:'socket',provisional:true,corners:[[-10.6,-7.4,-16.85],[-1.1,-7.4,-16.85],[-1.1,-0.3,-16.85],[-10.6,-0.3,-16.85]]},
        {anchor:2,name:'축 A · 출력부',normal:[0,0,1],shape:'ring',center:[-0.45,12,20.45],radius:8.3},
        {anchor:3,name:'축 A · 아이들러',normal:[0,0,-1],shape:'ring',center:[-0.45,12,-20.45],radius:8.3},
        {anchor:4,name:'축 B · 출력부',normal:[1,0,0],shape:'ring',center:[20.45,-12,-0.45],radius:8.3},
        {anchor:5,name:'축 B · 아이들러',normal:[-1,0,0],shape:'ring',center:[-20.45,-12,-0.45],radius:8.3},
        {anchor:6,name:'본체 · +Z 네 홀 (STEP 정렬)',normal:[0,0,1],shape:'socket',corners:[[-8,4,18.55],[7,4,18.55],[7,20,18.55],[-8,20,18.55]]},
        {anchor:7,name:'본체 · −Z 면 (간섭 미검증)',normal:[0,0,-1],shape:'socket',provisional:true,corners:[[-8,4,-19.45],[7,4,-19.45],[7,20,-19.45],[-8,20,-19.45]]},
        {anchor:8,name:'본체 · +X 면 (간섭 미검증)',normal:[1,0,0],shape:'socket',provisional:true,corners:[[18.55,-20,-8],[18.55,-4,-8],[18.55,-4,7],[18.55,-20,7]]},
        {anchor:9,name:'본체 · −X 면 (간섭 미검증)',normal:[-1,0,0],shape:'socket',provisional:true,corners:[[-19.45,-20,-8],[-19.45,-4,-8],[-19.45,-4,7],[-19.45,-20,7]]}
      ],
      bracket:[
        {anchor:0,name:'포크 · 축 체결부',normal:[0,0,1],shape:'ring',center:[0,-2.72,22],radius:9},
        {anchor:0,name:'포크 · 반대편 지지부',normal:[0,0,-1],shape:'ring',center:[0,-2.72,-22],radius:9},
        {anchor:1,name:'본체 체결 판',normal:[0,1,0],shape:'socket',provisional:true,corners:[[-10,14.78,-17],[10,14.78,-17],[10,14.78,17],[-10,14.78,17]]}
      ],
      opencr:[
        // REVH STEP의 JST_B3B_EH_A 외접 범위를 STL 중심으로 변환. 개구면은 실측 전이다.
        {anchor:0,name:'OpenCR TTL 1 · 3핀 공통 버스',normal:[0,0,1],shape:'socket',provisional:true,corners:[[33,-24.8,1.8],[36.8,-24.8,1.8],[36.8,-14.8,1.8],[33,-14.8,1.8]]},
        {anchor:1,name:'OpenCR TTL 2 · 3핀 공통 버스',normal:[0,0,1],shape:'socket',provisional:true,corners:[[33,-14.1,1.8],[36.8,-14.1,1.8],[36.8,-4.1,1.8],[33,-4.1,1.8]]},
        {anchor:2,name:'OpenCR TTL 3 · 3핀 공통 버스',normal:[0,0,1],shape:'socket',provisional:true,corners:[[33,-3.8,1.8],[36.8,-3.8,1.8],[36.8,6.2,1.8],[33,6.2,1.8]]},
        {anchor:3,name:'Micro-B USB · 노트북 고정 연결',normal:[0,1,0],shape:'socket',provisional:true,corners:[[-1.9,54.5,-4.4],[6.1,54.5,-4.4],[6.1,54.5,-1.5],[-1.9,54.5,-1.5]]}
      ],
      laptop:[{anchor:0,name:'USB · OpenCR 고정 연결',normal:[1,0,0],shape:'socket',provisional:true,corners:[[42,-.5,-3],[42,3.5,-3],[42,3.5,3],[42,-.5,3]]}]
    };
    function zonePoints(zone){if(zone.shape!=='ring')return zone.corners;const [cx,cy,cz]=zone.center;return Array.from({length:40},(_,index)=>{const angle=index*Math.PI*2/40,u=Math.cos(angle)*zone.radius,v=Math.sin(angle)*zone.radius;return Math.abs(zone.normal[2])===1?[cx+u,cy+v,cz]:[cx,cy+v,cz+u];});}
    function interfaceFacesCamera(part,zone){
      const model=partModel(part),center=transformPoint(model,[0,0,0]),tip=transformPoint(model,zone.normal);
      const towardCamera=state.lastFrame.eye.map((value,i)=>value-center[i]);
      return tip.reduce((sum,value,i)=>sum+(value-center[i])*towardCamera[i],0)>0;
    }
    function updatePortOverlay(){
      const overlay=$('portOverlay');if(!overlay||!state.lastFrame)return;
      overlay.setAttribute('viewBox',`0 0 ${canvas.clientWidth} ${canvas.clientHeight}`);
      overlay.replaceChildren();
      if(state.workspaceMode==='motion'||state.workspaceMode==='status'||state.workspaceMode==='assembly'&&state.assemblyTool!=='connect')return;
      for(const part of visibleParts())for(const zone of interfaces[part.key]||[]){
        if(!state.pendingPort&&(part.key!==state.selectedKey||part.id!==state.selectedId))continue;
        if(!interfaceFacesCamera(part,zone))continue;
        const points=zonePoints(zone).map(point=>projectPoint(partModel(part),point));if(points.some(point=>!point))continue;
        const port=portsFor(part)[zone.anchor],candidate={key:part.key,id:part.id,anchor:zone.anchor,kind:port.kind};
        if(state.workspaceMode==='assembly'&&port.kind!=='mechanical')continue;
        if(state.workspaceMode==='assembly'&&!state.pendingPort&&part.key==='motor'&&port.role==='case')continue;
        if(state.workspaceMode==='wiring'&&port.kind!=='ttl')continue;
        const selected=samePort(state.pendingPort,candidate)||Boolean(state.pendingPort?.kind==='mechanical'&&port.role==='shaft'&&state.pendingPort.key===part.key&&state.pendingPort.id===part.id&&portsFor(part)[state.pendingPort.anchor]?.axis===port.axis),occupied=port.kind==='mechanical'?mechanicalPortInUse(candidate):Boolean(portInUse(candidate));
        const compatible=state.pendingPort&&!selected&&validPortPair(state.pendingPort,candidate)&&!occupied;
        if(state.pendingPort&&!selected&&!compatible)continue;
        const group=document.createElementNS(svgNS,'g');group.classList.add('interface-group');if(selected)group.classList.add('pending');
        const region=document.createElementNS(svgNS,'polygon');region.setAttribute('points',points.map(point=>point.join(',')).join(' '));
        region.setAttribute('class',`interface-region${zone.shape==='ring'&&port.axis==='B'?' axis-b':''}${zone.provisional?' provisional':''}${port.kind==='ttl'?' ttl':''}${port.kind==='usb'?' usb':''}${selected?' pending':''}${occupied?' occupied':''}${occupied&&port.kind==='ttl'?' wired':''}${compatible?' compatible':''}`);
        region.setAttribute('role','button');region.setAttribute('tabindex','0');region.setAttribute('aria-label',`${partDefs[part.key].label} ${zone.name} 선택`);
        region.dataset.key=part.key;region.dataset.id=part.id;region.dataset.anchor=zone.anchor;
        const activate=event=>{event.preventDefault();event.stopPropagation();handlePortClick(candidate);};
        region.addEventListener('click',activate);region.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){activate(event);}});
        const px=points.reduce((sum,point)=>sum+point[0],0)/points.length,py=points.reduce((sum,point)=>sum+point[1],0)/points.length;
        const title=document.createElementNS(svgNS,'title');title.textContent=zone.name;region.append(title);
        const label=document.createElementNS(svgNS,'text');label.classList.add('interface-label');label.textContent=zone.name;
        label.setAttribute('x',Math.min(canvas.clientWidth-150,Math.max(8,px)));
        label.setAttribute('y',Math.max(22,py-18));
        group.append(region);
        if(zone.shape==='ring'){const symbol=document.createElementNS(svgNS,'text');symbol.classList.add('interface-symbol');symbol.textContent=port.axis;symbol.setAttribute('x',px);symbol.setAttribute('y',py);group.append(symbol);}
        group.append(label);overlay.append(group);
      }
    }
    function handlePortClick(port){
      if(port.kind==='usb'){setMateStatus('노트북↔OpenCR USB는 현재 배선 계획에 고정 표시됩니다. 실제 연결 여부는 장비 상태 표시를 확인하세요.');return;}
      if(state.pendingPort&&samePort(state.pendingPort,port)){state.pendingPort=null;setMateStatus('선택을 취소했습니다.');draw();return;}
      const currentPart=findPart(port.key,port.id);if(!currentPart)return;
      if(port.key==='bracket'&&port.anchor===1&&currentPart.rootSide==='fork'&&!currentPart.mates.fork){state.pendingPort=null;setMateStatus('이 브라켓은 축 고정 방식입니다. 먼저 포크를 회전축에 연결하거나 브라켓 기준을 본체 고정으로 바꾸세요.');draw();return;}
      const prior=state.pendingPort;
      if(prior?.key==='motor'&&port.key==='motor'&&prior.id===port.id&&prior.kind==='mechanical'&&port.kind==='mechanical'&&portsFor(currentPart)[prior.anchor].axis===portsFor(currentPart)[port.anchor].axis){state.pendingPort=port;setMateStatus(`같은 ${portsFor(currentPart)[port.anchor].axis}축의 출력 혼·아이들러 한 쌍입니다. 브라켓 포크를 선택하면 양쪽이 함께 체결됩니다.`);draw();return;}
      const occupied=port.kind==='mechanical'?mechanicalPortInUse(port):Boolean(portInUse(port));
      if(occupied){
        const role=port.kind==='mechanical'?portsFor(currentPart)[port.anchor].role:null;
        if(!prior&&(role==='plate'||role==='case')){
          const bracket=role==='plate'?currentPart:plateBracketFor(currentPart.id,portsFor(currentPart)[port.anchor].face);
          if(bracket?.mates.plate){disconnectBracketEnd(bracket,'plate');setMateStatus('브라켓 판 연결만 해제했습니다.');renderPartList();updateSelectionControls();draw();return;}
        }
        state.pendingPort=null;setMateStatus(`${portLabel(currentPart,port.anchor)} 부위는 이미 연결되어 있습니다. 연결된 부품을 선택해 해제하세요.`);draw();return;
      }
      if(!state.pendingPort){state.pendingPort=port;const role=portsFor(currentPart)[port.anchor]?.role;const target=role==='shaft'?'브라켓 포크':role==='fork'?'모터 출력축':role==='plate'?'다른 모터 본체 체결면':'브라켓 본체 체결 판';if(port.kind==='ttl'){state.yaw=-Math.PI*3/4;state.pitch=.25;$('cameraView').value='sockets';}setMateStatus(port.kind==='mechanical'?`${portLabel(currentPart,port.anchor)} 선택 · ${target}${role==='shaft'?'를':'을'} 선택하세요. (Esc 취소)`:`${portLabel(currentPart,port.anchor)} 선택 · 다른 장치의 3P 포트를 선택하세요. (Esc 취소)`);draw();return;}
      if(!validPortPair(state.pendingPort,port)){setMateStatus('체결 조합이 맞지 않습니다. 모터 축↔브라켓 포크, 브라켓 판↔다른 모터 본체를 연결하세요.');draw();return;}
      if(port.kind==='mechanical'){
        const first=findPart(state.pendingPort.key,state.pendingPort.id),second=currentPart;
        const motor=first.key==='motor'?first:second,bracket=first.key==='bracket'?first:second;
        const motorAnchor=state.pendingPort.key==='motor'?state.pendingPort.anchor:port.anchor;
        const motorPort=portsFor(motor)[motorAnchor];
        if(motorPort.role==='shaft')snapBracket(bracket,motor,motorPort.axis);
        else snapBracketPlate(bracket,motor,motorPort.face);
        state.pendingPort=null;selectPart('bracket',bracket.id);
        setMateStatus(motorPort.role==='shaft'?`모터 #${state.parts.motor.indexOf(motor)+1} ${motorPort.axis}축 혼·아이들러에 포크 연결 · 판을 다른 모터 본체에 연결하세요.`:`모터 #${state.parts.motor.indexOf(motor)+1} 본체에 브라켓 판 연결 · 포크를 다른 모터의 한 회전축에 연결하세요. STEP상 홀 정렬은 +Z면만 확인했습니다.`);renderPartList();return;
      }
      let cable=state.parts.connector.find(item=>!item.connection);
      if(!cable&&state.parts.connector.length<64){cable=makePart('connector',state.parts.connector.length);state.parts.connector.push(cable);}
      if(!cable){setMateStatus('케이블 64개 제한에 도달했습니다. 사용하지 않는 연결을 정리하세요.');return;}
      cable.connection={a:state.pendingPort,b:port};state.pendingPort=null;selectPart('connector',cable.id);
      setMateStatus('DXL 연결 경로 미리보기 · 실제 포트 위치와 케이블 길이는 아직 검증되지 않았습니다.');
    }
    function projectPoint(model,point=[0,0,0]){const m=mul(state.lastFrame.proj,mul(state.lastFrame.view,model));const x=point[0],y=point[1],z=point[2];const clip=[m[0]*x+m[4]*y+m[8]*z+m[12],m[1]*x+m[5]*y+m[9]*z+m[13],m[2]*x+m[6]*y+m[10]*z+m[14],m[3]*x+m[7]*y+m[11]*z+m[15]];if(clip[3]<=0)return null;return [(clip[0]/clip[3]*.5+.5)*canvas.clientWidth,(-clip[1]/clip[3]*.5+.5)*canvas.clientHeight];}
    const gizmoColors=['#fa8185','#8de5aa','#8fb5ff'];
    function svgElement(tag,attributes){const node=document.createElementNS(svgNS,tag);for(const [key,value] of Object.entries(attributes))node.setAttribute(key,String(value));return node;}
    function drawGizmo(){
      const overlay=$('gizmoOverlay'),focusedAxis=overlay.contains(document.activeElement)?document.activeElement.dataset.gizmoAxis:null;
      overlay.setAttribute('viewBox',`0 0 ${canvas.clientWidth} ${canvas.clientHeight}`);overlay.replaceChildren();
      if(state.workspaceMode!=='assembly'||state.assemblyTool!=='place'||state.pendingPort||state.drag?.kind==='camera'||state.drag?.kind==='pan')return;
      const part=selectedPart();if(!part||positionLocked(part))return;
      const center=projectWorldPoint(part.pos);if(!center)return;
      const axes=[[1,0,0],[0,1,0],[0,0,1]],radius=.82;
      axes.forEach((axis,index)=>{
        if(state.transformMode==='move'){
          const tip=projectWorldPoint(part.pos.map((value,i)=>value+axis[i]*radius));
          if(!tip||Math.hypot(tip[0]-center[0],tip[1]-center[1])<15)return;
          const line=`M ${center[0]} ${center[1]} L ${tip[0]} ${tip[1]}`;
          const target=svgElement('path',{d:line,class:'gizmo-axis',stroke:gizmoColors[index],'data-gizmo-axis':index,tabindex:0,role:'button','aria-label':`${'XYZ'[index]}축으로 이동`});
          overlay.append(target,svgElement('path',{d:line,class:'gizmo-axis-core',stroke:gizmoColors[index]}),svgElement('circle',{cx:tip[0],cy:tip[1],r:6,fill:gizmoColors[index],class:'gizmo-handle','data-gizmo-axis':index}));
          const label=svgElement('text',{x:tip[0]+9,y:tip[1]+4,class:'gizmo-label'});label.textContent='XYZ'[index];overlay.append(label);
        }else{
          const one=axes[(index+1)%3],two=axes[(index+2)%3],points=[];
          for(let step=0;step<=48;step++){
            const theta=step*Math.PI*2/48;
            const point=projectWorldPoint(part.pos.map((value,i)=>value+radius*(one[i]*Math.cos(theta)+two[i]*Math.sin(theta))));
            if(!point)return;points.push(point);
          }
          const path=points.map((point,i)=>`${i?'L':'M'} ${point[0]} ${point[1]}`).join(' ');
          overlay.append(svgElement('path',{d:path,class:'gizmo-rotate',stroke:gizmoColors[index],'data-gizmo-axis':index,tabindex:0,role:'button','aria-label':`${'XYZ'[index]}축으로 회전`}),svgElement('path',{d:path,class:'gizmo-rotate-core',stroke:gizmoColors[index]}));
        }
      });
      if(focusedAxis!==null)overlay.querySelector(`.gizmo-axis[data-gizmo-axis="${focusedAxis}"],.gizmo-rotate[data-gizmo-axis="${focusedAxis}"]`)?.focus();
    }
    const gizmoOverlay=$('gizmoOverlay');
    gizmoOverlay.addEventListener('pointerdown',event=>{
      if(event.button!==0||event.target.dataset.gizmoAxis===undefined)return;
      const part=selectedPart();if(!part||positionLocked(part))return;
      event.preventDefault();event.stopPropagation();
      const axis=Number(event.target.dataset.gizmoAxis),rect=gizmoOverlay.getBoundingClientRect(),center=projectWorldPoint(part.pos);
      const tip=projectWorldPoint(part.pos.map((value,i)=>value+(i===axis ? .82 : 0)));
      if(!center||!tip)return;
      state.drag={kind:'gizmo',part,axis,mode:state.transformMode,start:[event.clientX,event.clientY],startValue:state.transformMode==='move'?part.pos[axis]:part.rot[axis],screenAxis:[tip[0]-center[0],tip[1]-center[1]],center:[center[0]+rect.left,center[1]+rect.top],startAngle:Math.atan2(event.clientY-rect.top-center[1],event.clientX-rect.left-center[0])};
      gizmoOverlay.setPointerCapture(event.pointerId);
    });
    gizmoOverlay.addEventListener('pointermove',event=>{
      const drag=state.drag;if(drag?.kind!=='gizmo')return;
      const part=drag.part;
      if(drag.mode==='move'){
        const lengthSquared=drag.screenAxis[0]**2+drag.screenAxis[1]**2;
        const amount=((event.clientX-drag.start[0])*drag.screenAxis[0]+(event.clientY-drag.start[1])*drag.screenAxis[1])/lengthSquared*.82;
        part.pos[drag.axis]=Math.max(-12,Math.min(12,drag.startValue+amount));
      }else{
        const angle=Math.atan2(event.clientY-drag.center[1],event.clientX-drag.center[0]);
        let delta=angle-drag.startAngle;while(delta>Math.PI)delta-=Math.PI*2;while(delta< -Math.PI)delta+=Math.PI*2;
        part.rot[drag.axis]=Math.max(-180,Math.min(180,drag.startValue+Math.round(delta*180/Math.PI)));
      }
      updateSelectionControls();draw();
    });
    gizmoOverlay.addEventListener('keydown',event=>{
      if(event.target.dataset.gizmoAxis===undefined||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
      const part=selectedPart();if(!part||positionLocked(part))return;
      event.preventDefault();const axis=Number(event.target.dataset.gizmoAxis),direction=event.key==='ArrowRight'||event.key==='ArrowUp'?1:-1;
      if(state.transformMode==='move')part.pos[axis]=Math.max(-12,Math.min(12,part.pos[axis]+direction*(event.shiftKey?.5:.1)));
      else part.rot[axis]=Math.max(-180,Math.min(180,part.rot[axis]+direction*(event.shiftKey?15:5)));
      updateSelectionControls();draw();
    });
    function finishGizmo(){if(state.drag?.kind==='gizmo'){state.drag=null;recordHistory();draw();}}
    gizmoOverlay.addEventListener('pointerup',finishGizmo);
    gizmoOverlay.addEventListener('pointercancel',finishGizmo);
    gizmoOverlay.addEventListener('lostpointercapture',finishGizmo);
    function pickPart(x,y){
      if(!state.lastFrame)return null;
      gl.useProgram(pickProgram);gl.enable(gl.DEPTH_TEST);gl.disable(gl.BLEND);gl.disable(gl.DITHER);
      gl.clearColor(0,0,0,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      gl.uniformMatrix4fv(pickLoc.view,false,new Float32Array(state.lastFrame.view));
      gl.uniformMatrix4fv(pickLoc.proj,false,new Float32Array(state.lastFrame.proj));
      const parts=visibleParts();
      parts.forEach((part,index)=>{const mesh=partMesh(part);gl.bindBuffer(gl.ARRAY_BUFFER,mesh.vbuf);gl.enableVertexAttribArray(pickLoc.pos);gl.vertexAttribPointer(pickLoc.pos,3,gl.FLOAT,false,0,0);gl.uniformMatrix4fv(pickLoc.model,false,new Float32Array(partModel(part)));gl.uniform3f(pickLoc.id,(index+1)/255,0,0);gl.drawArrays(gl.TRIANGLES,0,mesh.n*3);});
      const pixel=new Uint8Array(4);
      gl.readPixels(Math.floor(x*canvas.width/canvas.clientWidth),Math.floor((canvas.clientHeight-y)*canvas.height/canvas.clientHeight),1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
      gl.enable(gl.DITHER);gl.useProgram(program);draw();
      return parts[pixel[0]-1]||null;
    }
    function canvasPoint(e){const r=canvas.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top];}
    let last=[0,0];
    canvas.addEventListener('contextmenu',event=>event.preventDefault());
    canvas.addEventListener('pointerdown',e=>{
      if(e.button!==0&&e.button!==1&&e.button!==2)return;
      const [x,y]=canvasPoint(e);
      const navigation=e.button===1||e.button===2||e.shiftKey?'pan':e.altKey?'camera':state.viewMode==='orbit'?'camera':state.viewMode==='pan'?'pan':null;
      if(navigation){state.drag={kind:navigation,moved:false};last=[x,y];canvas.classList.add('dragging');canvas.setPointerCapture(e.pointerId);return;}
      const hit=pickPart(x,y);
      if(hit&&state.pendingPort?.key==='motor'&&state.pendingPort.kind==='mechanical'&&hit.key==='bracket'){
        const motor=findPart('motor',state.pendingPort.id),role=portsFor(motor)[state.pendingPort.anchor].role;
        handlePortClick({key:'bracket',id:hit.id,anchor:role==='shaft'?0:1,kind:'mechanical'});return;
      }
      if(hit&&state.pendingPort?.kind==='ttl')setMateStatus('3핀 연결은 보라색 소켓 윤곽선을 직접 선택하세요. 몸체 클릭은 배선으로 처리하지 않습니다.');
      if(state.pendingPort&&!hit)setMateStatus('모델 몸체를 선택하지 못했습니다. 보이는 부품 표면을 클릭하거나 시점을 바꿔 보세요.');
      if(hit)selectPart(hit.key,hit.id);
      const linked=state.workspaceMode==='motion'&&!state.pendingPort?connectedJointFor(hit):null;
      if(linked){state.drag={kind:'joint',control:linked,startX:x,startAngle:linked.motor.joints[linked.axis]};last=[x,y];canvas.classList.add('dragging');canvas.setPointerCapture(e.pointerId);setMateStatus(`브라켓 체결 유지 · ${linked.axis}축을 좌우 드래그해 상대 모터를 회전하세요. 화면 시뮬레이션입니다.`);return;}
      state.drag={kind:'camera',moved:false};last=[x,y];canvas.classList.add('dragging');canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener('pointermove',e=>{
      if(!state.drag)return;const [x,y]=canvasPoint(e),dx=x-last[0],dy=y-last[1];
      if(Math.abs(dx)+Math.abs(dy)<.2)return;
      if(state.drag.kind==='camera'){state.yaw+=dx*.008;state.pitch=Math.max(-1.45,Math.min(1.45,state.pitch+dy*.008));}
      else if(state.drag.kind==='pan')panCamera(dx,dy);
      else if(state.drag.kind==='joint'){
        const turn=state.drag.control;
        turn.motor.joints[turn.axis]=clampPreviewJoint(turn.axis,Math.round(state.drag.startAngle+(x-state.drag.startX)*.5));
        updateSelectionControls();setMateStatus(`체결 유지 · ${turn.axis}축 ${turn.motor.joints[turn.axis]}° (시각화만, 실제 가동 가능 여부 미확인)`);
      }
      last=[x,y];draw();
    });
    function finishDrag(){if(state.drag?.kind==='joint'){state.drag=null;recordHistory();draw();}else state.drag=null;canvas.classList.remove('dragging');}
    canvas.addEventListener('pointerup',finishDrag);canvas.addEventListener('pointercancel',finishDrag);
    canvas.addEventListener('wheel',e=>{e.preventDefault();state.distance=Math.max(1.1,Math.min(25,state.distance*(e.deltaY>0?1.08:.92)));draw();},{passive:false});
    document.querySelectorAll('[data-workspace-mode]').forEach(button=>button.addEventListener('click',()=>setWorkspaceMode(button.dataset.workspaceMode)));
    document.querySelectorAll('[data-assembly-tool]').forEach(button=>button.addEventListener('click',()=>setAssemblyTool(button.dataset.assemblyTool)));
    $('undoBtn').addEventListener('click',()=>travelHistory('undo'));
    $('redoBtn').addEventListener('click',()=>travelHistory('redo'));
    window.addEventListener('keydown',event=>{
      if(!(event.metaKey||event.ctrlKey)||event.key.toLowerCase()!=='z'||event.target.closest?.('input,textarea,select,[contenteditable]'))return;
      event.preventDefault();travelHistory(event.shiftKey?'redo':'undo');
    });
    $('focusPartBtn').addEventListener('click',()=>{const part=selectedPart();if(!part)return;state.cameraTarget=[...part.pos];state.distance=Math.max(2.4,Math.min(state.distance,6));draw();});
    $('bracketRootSide').addEventListener('change',event=>{const bracket=selectedPart();if(bracket?.key!=='bracket'||bracket.mates.fork&&bracket.mates.plate)return;if(event.target.value==='fork'&&bracket.mates.plate&&!bracket.mates.fork){updateSelectionControls();setMateStatus('축 고정 방식으로 바꾸려면 판 연결을 먼저 해제하세요.');return;}bracket.rootSide=event.target.value;state.pendingPort=null;updateSelectionControls();draw();setMateStatus(bracket.rootSide==='plate'?'본체 고정: 판이 아래 모터 본체, 포크가 위 모터 회전축에 연결됩니다.':'축 고정: 포크가 기준 모터 축, 판이 다음 모터 본체에 연결됩니다.');});
    $('partList').addEventListener('click',e=>{const row=e.target.closest('.part-row');if(!row)return;const key=row.dataset.key,action=e.target.dataset.action;if(action==='add')addPart(key);else if(action==='remove')removePart(key);else if(action==='instance')selectPart(key,e.target.dataset.id);else if(action==='select')selectPart(key,state.parts[key][0].id);});
    $('exampleAssemblyBtn').addEventListener('click',loadExampleAssembly);
    $('closeInspectorBtn').addEventListener('click',()=>{document.body.classList.remove('inspector-open');draw();});
    $('exportProjectBtn').addEventListener('click',exportProject);
    $('importProjectBtn').addEventListener('click',()=>$('projectFile').click());
    $('projectFile').addEventListener('change',event=>importProject(event.target.files?.[0]));
    $('resetBtn').addEventListener('click',()=>{state.yaw=.55;state.pitch=.3;focusAssembly();setViewMode('part');draw();}); $('autoBtn').addEventListener('click',()=>{state.auto=!state.auto;$('autoBtn').textContent=state.auto?'회전 중지':'자동 회전';$('statusText').textContent=state.auto?'3D 자동 회전 중':'STEP 부분 검토 완료 · 실물 체결 미검증';if(!state.auto&&autoFrame!==null){cancelAnimationFrame(autoFrame);autoFrame=null;}if(state.auto)draw();}); $('moveMode').addEventListener('click',()=>{state.transformMode='move';updateSelectionControls();draw();}); $('rotateMode').addEventListener('click',()=>{state.transformMode='rotate';updateSelectionControls();draw();}); $('resetPartBtn').addEventListener('click',()=>resetPart(selectedPart())); $('resetAllBtn').addEventListener('click',resetAllParts); $('detachBtn').addEventListener('click',()=>{detachPart(selectedPart());state.pendingPort=null;updateSelectionControls();renderPartList();draw();});
    window.addEventListener('keydown',event=>{if(event.key==='Escape'&&state.pendingPort){state.pendingPort=null;setMateStatus('연결 선택을 취소했습니다.');draw();}});
    [['partX',0],['partY',1],['partZ',2]].forEach(([id,index])=>$(id).addEventListener('change',e=>{const part=selectedPart(),value=Number(e.target.value);if(!Number.isFinite(value)||value< -12||value>12||!releaseForManualTransform(part)){updateSelectionControls();return;}part.pos[index]=value;updateSelectionControls();renderPartList();draw();}));
    $('placementRotation').addEventListener('click',event=>{
      const button=event.target.closest('button'),row=button?.closest('.placement-angle-row');if(!row)return;
      const part=selectedPart(),axis='XYZ'.indexOf(row.dataset.placementAxis);if(axis<0||!releaseForManualTransform(part)){updateSelectionControls();return;}
      if(button.hasAttribute('data-placement-custom')){
        row.dataset.customOpen='true';updateSelectionControls();const input=row.querySelector('input');input.focus();input.select();return;
      }
      if(!button.hasAttribute('data-placement-angle'))return;
      delete row.dataset.customOpen;part.rot[axis]=Number(button.dataset.placementAngle);
      updateSelectionControls();draw();
    });
    $('placementRotation').addEventListener('change',event=>{
      const input=event.target;if(!input.matches('.placement-custom input'))return;
      const row=input.closest('.placement-angle-row'),part=selectedPart(),axis='XYZ'.indexOf(row.dataset.placementAxis),raw=input.value.trim(),value=Number(raw);
      if(!raw||!Number.isFinite(value)||value< -180||value>180){input.setCustomValidity('−180°에서 180° 사이의 각도를 입력하세요.');input.reportValidity();return;}
      input.setCustomValidity('');if(axis<0||!releaseForManualTransform(part)){updateSelectionControls();return;}
      part.rot[axis]=value;row.dataset.customOpen='true';updateSelectionControls();draw();
    });
    $('placementRotation').addEventListener('input',event=>{if(event.target.matches('.placement-custom input'))event.target.setCustomValidity('');});
    let activeJointTurn=null;
    function stopJointTurn(){if(activeJointTurn?.frame)cancelAnimationFrame(activeJointTurn.frame);activeJointTurn=null;}
    function applyJointTurn(turn,steps){
      if(selectedPart()!==turn.motor){stopJointTurn();return;}
      const value=clampPreviewJoint(turn.axis,turn.motor.joints[turn.axis]+turn.direction*steps);
      if(value===turn.motor.joints[turn.axis]){stopJointTurn();return;}
      turn.motor.joints[turn.axis]=value;updateSelectionControls();draw();
      setMateStatus(`모터 #${state.parts.motor.indexOf(turn.motor)+1} 축 ${turn.axis} ${value}° · 화면 시뮬레이션 (실물 명령 없음)`);
    }
    function startJointTurn(button){
      stopJointTurn();const motor=selectedPart();if(motor?.key!=='motor')return;
      const turn={motor,axis:button.dataset.joint,direction:Number(button.dataset.direction),last:performance.now(),remainder:0,frame:null};
      activeJointTurn=turn;applyJointTurn(turn,1);
      function advance(now){if(activeJointTurn!==turn)return;turn.remainder+=Math.min(100,now-turn.last)*.06;turn.last=now;const steps=Math.floor(turn.remainder);if(steps){turn.remainder-=steps;applyJointTurn(turn,steps);}if(activeJointTurn===turn)turn.frame=requestAnimationFrame(advance);}
      if(activeJointTurn===turn)turn.frame=requestAnimationFrame(advance);
    }
    document.querySelectorAll('[data-joint]').forEach(button=>{
      button.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();button.setPointerCapture(event.pointerId);startJointTurn(button);});
      button.addEventListener('pointerup',stopJointTurn);button.addEventListener('pointercancel',stopJointTurn);button.addEventListener('lostpointercapture',stopJointTurn);
      button.addEventListener('keydown',event=>{if((event.key===' '||event.key==='Enter')&&!event.repeat){event.preventDefault();startJointTurn(button);}});
      button.addEventListener('keyup',event=>{if(event.key===' '||event.key==='Enter'){event.preventDefault();stopJointTurn();}});
    });
    document.querySelectorAll('[data-pose-angle]').forEach(button=>button.addEventListener('click',()=>{
      const linked=connectedJointFor(selectedPart());if(!linked)return;
      linked.motor.joints[linked.axis]=clampPreviewJoint(linked.axis,Number(button.dataset.poseAngle));
      updateSelectionControls();draw();
      setMateStatus(`체결 유지 · ${linked.axis}축 ${linked.motor.joints[linked.axis]}° 자세 미리보기. 실물 가동각이나 간섭 안전을 뜻하지 않습니다.`);
    }));
    window.addEventListener('blur',stopJointTurn);
    for(const axis of ['A','B'])$(`axisId${axis}`).addEventListener('change',e=>{
      const motor=selectedPart();if(motor.key!=='motor')return;
      const id=e.target.value?Number(e.target.value):null;
      if(id!==null&&state.parts.motor.some(part=>Object.entries(part.axisIds||{}).some(([otherAxis,otherId])=>otherId===id&&(part.id!==motor.id||otherAxis!==axis)))){
        setMateStatus(`ID ${id}는 이미 다른 축에 배정되어 있습니다.`);renderAxisIdEditor();return;
      }
      motor.axisIds[axis]=id;renderAxisIdEditor();draw();
      setMateStatus(`모터 #${state.parts.motor.indexOf(motor)+1} 축 ${axis}: ${id===null?'실물 ID 배정 해제':`ID ${id} 배정`} · 실제 축과 대조하세요.`);
    });
    $('cameraView').addEventListener('change',e=>{const v=e.target.value;if(v==='sockets'){state.yaw=-Math.PI*3/4;state.pitch=.25;}else if(v==='front'){state.yaw=0;state.pitch=0;}else if(v==='back'){state.yaw=Math.PI;state.pitch=0;}else if(v==='side'){state.yaw=Math.PI/2;state.pitch=0;}else if(v==='left'){state.yaw=-Math.PI/2;state.pitch=0;}else if(v==='top'){state.yaw=0;state.pitch=Math.PI/2-.05;}else if(v==='bottom'){state.yaw=0;state.pitch=-Math.PI/2+.05;}else{state.yaw=.55;state.pitch=.35;}draw();}); window.addEventListener('resize',draw);document.body.dataset.workspaceMode='assembly';load().catch(err=>{$('statusText').textContent='모델 로딩 실패';console.error(err);});
