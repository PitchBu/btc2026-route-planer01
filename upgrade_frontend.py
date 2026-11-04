from pathlib import Path
p=Path(__file__).resolve().parents[1]/'index.html'
s=p.read_text()
start=s.index('// API integration:')
end=s.index('</script>',start)
replacement=r'''// Scheduled snapshot sync: the deployed static site reads a validated JSON file
// committed by GitHub Actions. It does NOT claim a direct official API connection.
const baselineSessions=sessions.map(x=>({...x}));
const baselineById=new Map(baselineSessions.map(s=>[String(s.id),s]));
let lastFeed=null,syncWorking=false,changeEntries=[],deletedSessions=[];
const statusEl=()=>document.getElementById('syncstatus');
function setSyncStatus(message,cls=''){const e=statusEl();e.textContent=message;e.className='syncstatus '+cls}
function validateFeed(obj){
 if(!obj||!Array.isArray(obj.sessions)||obj.sessions.length<55||obj.sessions.length>250)throw Error('จำนวนหัวข้อในข้อมูลไม่สมบูรณ์');
 const ids=new Set();const result=obj.sessions.map((s,i)=>{
  const day=Number(s.day),stage=String(s.stage),id=Number(s.id);
  const start=String(s.start||''),end=String(s.end||''),title=String(s.title||'').trim();
  if(!Number.isSafeInteger(id)||ids.has(id)||![1,2].includes(day)||!['M','C','W'].includes(stage)||!/^\d\d:\d\d$/.test(start)||!/^\d\d:\d\d$/.test(end)||mins(end)<=mins(start)||!title)throw Error('พบรายการไม่สมบูรณ์ #'+i);
  ids.add(id);return {id,day,stage,start,end,title:title.slice(0,500),type:String(s.type||'Session').slice(0,100),speaker:String(s.speaker||'').slice(0,700)};
 });
 if(result.filter(s=>s.day===1).length<25||result.filter(s=>s.day===2).length<20)throw Error('ข้อมูลวันใดวันหนึ่งไม่ครบ');
 return result;
}
function describeDiff(change){
 const p=change.previous,c=change.current;
 if(change.kind==='removed')return `ยกเลิก/ไม่พบแล้ว: ${p?.title||'หัวข้อเดิม'}`;
 if(change.kind==='added')return `เพิ่มหัวข้อ: ${c?.title||'หัวข้อใหม่'}`;
 const changed=Array.isArray(change.fields)?change.fields:[];
 let details=[];
 if(changed.includes('start')||changed.includes('end'))details.push(`เวลา ${p?.start}–${p?.end} → ${c?.start}–${c?.end}`);
 if(changed.includes('stage'))details.push(`เวที ${stageNames[p?.stage]||p?.stage} → ${stageNames[c?.stage]||c?.stage}`);
 if(changed.includes('speaker'))details.push('เปลี่ยนรายชื่อวิทยากร');
 if(changed.includes('title'))details.push('เปลี่ยนชื่อหัวข้อ');
 return `${c?.title||p?.title}: ${details.join(', ')||'แก้ไขข้อมูล'}`;
}
function renderUpdates(){
 const root=$('updates');if(!root)return;
 const changes=changeEntries.filter(c=>c.kind!=='added'||c.current?.day===day);
 const selectedChanges=changes.filter(c=>picked.has(Number(c.id)));
 const relevant=selectedChanges.length?selectedChanges:changes.slice(0,8);
 if(!relevant.length){root.innerHTML='';return;}
 root.innerHTML=`<div class="changebox"><strong>🔔 ${selectedChanges.length?'หัวข้อที่คุณเลือกมีการเปลี่ยนแปลง':'การเปลี่ยนแปลงล่าสุดจากตารางที่ตรวจสอบได้'}</strong><div class="small muted">แสดงความต่างระหว่างการตรวจสอบ 2 ครั้งล่าสุด · ตรวจสอบเว็บงานก่อนเข้าห้อง</div><ul>${relevant.slice(0,12).map(c=>`<li>${esc(describeDiff(c))}</li>`).join('')}</ul></div>`;
}
const oldRender=render;
render=function(){oldRender();renderUpdates();renderMissing()};
function renderMissing(){
 const root=$('missing');if(!root)return;
 const missing=[...picked].filter(id=>!sessions.some(s=>s.id===id));
 root.innerHTML=missing.length?`<div class="notice"><strong>⚠ ${missing.length} หัวข้อที่เคยเลือก ไม่พบในตารางล่าสุด</strong><p>ระบบยังเก็บการเลือกไว้ ไม่ลบออกอัตโนมัติ</p>${missing.map(id=>`<p>${esc(baselineById.get(String(id))?.title||'หัวข้อ #'+id)} <button class="syncbtn" data-forget="${id}">ลบรายการนี้</button></p>`).join('')}</div>`:'';
 root.querySelectorAll('[data-forget]').forEach(b=>b.addEventListener('click',()=>change(Number(b.dataset.forget),false)));
}
function setFeed(data,fromCache){
 const updated=validateFeed(data);
 sessions=updated;
 changeEntries=Array.isArray(data.changes)?data.changes:[];
 lastFeed=data;
 render();
 const stamp=data.verifiedAt?new Date(data.verifiedAt):null;
 const fmt=stamp&&!isNaN(stamp.getTime())?new Intl.DateTimeFormat('th-TH',{timeZone:'Asia/Bangkok',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(stamp):'ยังไม่เคยตรวจสอบอัตโนมัติ';
 const source=data.source==='official-web-page'?'ดึงจากหน้าเว็บทางการผ่านระบบตรวจสอบ':'ตารางสำรองจากภาพกำหนดการ';
 setSyncStatus(`${fromCache?'ข้อมูลบันทึกล่าสุด':'ข้อมูลที่เผยแพร่ล่าสุด'} · ${source} · ตรวจสอบ ${fmt} · ${updated.length} รายการ`,data.source==='official-web-page'?'live':'error');
}
async function syncSchedule(manual=false){
 if(syncWorking)return;
 if(location.protocol==='file:'){
  setSyncStatus('โหมดไฟล์ออฟไลน์ · ตารางสำรอง 3 พ.ย. 2569 · การซิงก์ต้องเผยแพร่เว็บไซต์','error');
  if(manual)toast('การอัปเดตอัตโนมัติต้องเปิดจากเว็บไซต์ที่เผยแพร่แล้ว');return;
 }
 syncWorking=true;$('sync').disabled=true;
 try{
  const res=await fetch('/data/schedule.json?ts='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(15000)});
  if(!res.ok)throw Error('HTTP '+res.status);
  const feed=await res.json();
  setFeed(feed,false);
  try{localStorage.setItem('btc26_last_verified_feed',JSON.stringify(feed))}catch{}
  if(manual)toast('โหลดตารางที่เผยแพร่ล่าสุดเรียบร้อย');
 }catch(err){
  let restored=false;
  try{const feed=JSON.parse(localStorage.getItem('btc26_last_verified_feed')||'null');if(feed){setFeed(feed,true);restored=true}}catch{}
  if(!restored)setSyncStatus('ไม่สามารถดึงตารางล่าสุด · กำลังใช้ตารางสำรอง 3 พ.ย. 2569','error');
  else setSyncStatus(statusEl().textContent+' · ขณะนี้ตรวจสอบออนไลน์ไม่ได้','error');
  if(manual)toast('อัปเดตไม่ได้: กำลังใช้ตารางสำรอง');
 }finally{syncWorking=false;$('sync').disabled=false}
}
$('sync').addEventListener('click',()=>syncSchedule(true));
if(location.protocol==='https:'||location.protocol==='http:'){
 syncSchedule();setInterval(()=>{if(!document.hidden)syncSchedule()},5*60*1000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)syncSchedule()});
}else{setSyncStatus('โหมดไฟล์ออฟไลน์ · ตารางสำรอง 3 พ.ย. 2569','error')}
'''
s=s[:start]+replacement+s[end:]
s=s.replace('<div id="cards" class="cards"></div>','<div id="updates" aria-live="polite"></div><div id="cards" class="cards"></div>')
s=s.replace('<div id="selected" class="selected">','<div id="missing"></div><div id="selected" class="selected">')
s=s.replace('จะระบุว่าซิงก์สดเฉพาะเมื่อ API ตอบกลับข้อมูลสำเร็จ','ข้อมูลถูกตรวจสอบตามรอบ GitHub Actions และอาจล่าช้ากว่าเว็บไซต์ทางการ')
s=s.replace('ข้อมูลสำรองจากกำหนดการ 3 พ.ย. 2569','กำลังตรวจสอบข้อมูลที่เผยแพร่ล่าสุด…')
s=s.replace('</style>','''.changebox{border:1px solid #f5cf91;background:#fffaf0;border-radius:13px;padding:12px;margin:0 0 13px;font-size:13px}.changebox ul{margin:8px 0 0;padding-left:20px}.changebox li{margin:5px 0}.changebox strong{color:#92400e}.changebox .muted{margin-top:4px}.notice p{margin:6px 0}.syncstatus.live{color:#047857}.syncstatus.error{color:#a16207}
</style>''')
p.write_text(s)
