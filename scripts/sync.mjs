/** BTC2026 independent schedule monitor. Browser-rendered official PUBLIC page.
 * Fail closed: an unexpected page structure never overwrites the last good feed.
 * Does not bypass access controls; respect organizers' terms and rate limits.
 */
import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
const ROOT = new URL('../', import.meta.url);
const SOURCE = 'https://www.bitcointhailand.co/schedule';
const outfile = new URL('../data/schedule.json', import.meta.url);
const prior = JSON.parse(await readFile(outfile, 'utf8'));
const baseline = JSON.parse(await readFile(new URL('../data/baseline.json', import.meta.url), 'utf8'));
const clean = s => String(s??'').replace(/\s+/g,' ').trim();
const minutes=s=>parseInt(s.slice(0,2))*60+parseInt(s.slice(3,5));
const norm=s=>clean(s).toLocaleLowerCase().replace(/[\p{P}\p{S}]/gu,'').replace(/\s+/g,' ');
const tokens=s=>new Set(norm(s).split(' ').filter(w=>w.length>2));
function similarity(a,b){
  if(norm(a)===norm(b))return 1;
  const aa=tokens(a),bb=tokens(b);let intersect=0;for(const t of aa)if(bb.has(t))intersect++;
  return intersect / Math.max(aa.size,bb.size,1);
}
async function extractDay(page,day){
  const button=page.getByRole('button',{name:new RegExp(`Day\\s*${day}\\b`,'i')}).first();
  if(await button.count())await button.click();
  else {
    // Some designs render day selectors as tabs or other clickable elements.
    const tab=page.getByText(new RegExp(`Day\\s*${day}\\b`,'i')).first();
    if(!await tab.count())throw Error(`Day ${day} switch missing`);
    await tab.click();
  }
  await page.waitForTimeout(1400);
  return await page.evaluate((day)=>{
    const trim=s=>String(s||'').replace(/\s+/g,' ').trim();
    const stages=[['M','Main Stage'],['C','Citadel Stage'],['W','Workshop Room']];
    const timeRe=/\b([01]\d|2[0-3]):[0-5]\d\s*[–—-]\s*([01]\d|2[0-3]):[0-5]\d\b/g;
    const typeNames=/^(Keynote|Panel|Project Presentation|Opening Ceremony|Arrival & Welcome|Break|Workshop|Talk)$/i;
    const unwanted=/^(Full Schedule|Every Session, Every Stage|All talks|Day [12]|Register|Back to Home|Buy Ticket|Sponsor|Home|Speakers|Tickets|Venue)$/i;
    // Locate the narrowest ancestor containing the stage's session list.
    function getSection(label){
      const heads=[...document.querySelectorAll('h1,h2,h3,h4,h5,div,span,p,strong')].filter(el=>{
        if(el.children.length && trim(el.innerText)!==label)return false;
        return trim(el.textContent)===label;
      });
      const candidates=[];
      for(const h of heads){
        let el=h.parentElement;
        for(let n=0;el&&n<7;n++,el=el.parentElement){
          const t=el.innerText||'';
          const times=[...t.matchAll(timeRe)];timeRe.lastIndex=0;
          if(times.length<3||times.length>35)continue;
          const other=stages.filter(x=>x[1]!==label).some(x=>new RegExp(`(^|\\n)\\s*${x[1]}\\s*(\\n|$)`,'m').test(t));
          if(other)continue;
          candidates.push({el,count:times.length,len:t.length,score:times.length*100-t.length*.005});
        }
      }
      candidates.sort((a,b)=>b.score-a.score);
      return candidates[0]?.el||null;
    }
    function parseStage(text,stage){
      const lines=text.split(/\n+/).map(trim).filter(Boolean);
      const records=[];
      let cur=null;
      function finish(){
        if(!cur)return;
        const arr=cur.lines.filter(x=>!unwanted.test(x)&&x!=='⚡');
        const typeIx=arr.findIndex(x=>typeNames.test(x));
        const type=typeIx>=0?arr[typeIx]:'Session';
        const titleIx=typeIx>=0?typeIx+1:0;
        const title=arr[titleIx]||'';
        const speakers=arr.slice(titleIx+1).filter(x=>!typeNames.test(x)&&!/^Register\b/i.test(x));
        if(title&&title.length>3&&title.length<500)records.push({day,stage,start:cur.start,end:cur.end,type,title,speaker:speakers.join(' · ').slice(0,700)});
      }
      for(let line of lines){
        const tm=line.match(/^([01]\d|2[0-3]):([0-5]\d)\s*[–—-]\s*([01]\d|2[0-3]):([0-5]\d)$/);
        if(tm){finish();cur={start:`${tm[1]}:${tm[2]}`,end:`${tm[3]}:${tm[4]}`,lines:[]};continue}
        if(cur)cur.lines.push(line);
      }
      finish();return records;
    }
    let output=[];
    for(const [key,label] of stages){
      const section=getSection(label);
      if(section)output.push(...parseStage(section.innerText,key));
    }
    // The public site also has a mobile chronological schedule; stage columns
    // are preferred to avoid duplicate records from the mobile view.
    return output;
  },day);
}
const browser = await chromium.launch({headless:true});
let incoming=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'en-US',timezoneId:'Asia/Bangkok'});
 await page.goto(SOURCE,{waitUntil:'domcontentloaded',timeout:45000});
 await page.getByText('Every Session, Every Stage').first().waitFor({timeout:25000});
 for(const day of [1,2]){
   const results=await extractDay(page,day);
   console.log(`Extracted day ${day}: ${results.length}`);
   incoming.push(...results);
 }
}finally{await browser.close()}
// Data-integrity gates. Reject suspicious partial page or accidental duplicate extraction.
const count=d=>incoming.filter(x=>x.day===d).length;
const signature=x=>[x.day,x.stage,x.start,norm(x.title)].join('|');
const sigs=new Set(incoming.map(signature));
if(incoming.length<55||count(1)<25||count(2)<20||sigs.size!==incoming.length||new Set(incoming.filter(x=>x.day===1).map(x=>x.stage)).size!==3){
 throw Error(`REJECTED scraper output: total=${incoming.length}, day1=${count(1)}, day2=${count(2)}, unique=${sigs.size}. Last good data retained.`);
}
for(const x of incoming){
 if(!x.title||x.title.length>500||!/^\d\d:\d\d$/.test(x.start)||!/^\d\d:\d\d$/.test(x.end)||minutes(x.end)<=minutes(x.start))throw Error(`REJECTED invalid record: ${JSON.stringify(x)}`);
}
const old=prior.sessions?.length?prior.sessions:baseline;
let maxId=Math.max(999,...old.map(x=>Number(x.id)||0),...baseline.map(x=>Number(x.id)||0));
const unmatched=new Map(old.map(s=>[String(s.id),s]));
const used=new Set();
function match(x){
 const candidates=[...unmatched.values()].filter(y=>y.day===x.day);
 const scores=candidates.map(y=>{
  const sim=similarity(x.title,y.title);
  const delta=Math.abs(minutes(x.start)-minutes(y.start));
  const score=sim*80+(x.stage===y.stage?12:0)+(delta<=15?8:delta<=60?4:0);
  return {y,sim,score};
 }).sort((a,b)=>b.score-a.score);
 const best=scores[0];
 // Same title even if stage/time changed; or highly similar in same stage.
 if(!best || !(best.sim>=.82 || (best.sim>=.64&&best.y.stage===x.stage&&Math.abs(minutes(x.start)-minutes(best.y.start))<=50)))return null;
 unmatched.delete(String(best.y.id));return best.y;
}
const newSessions=incoming.map(x=>{const original=match(x);const id=original?original.id:++maxId;used.add(String(id));return {id,...x}});
const fields=['day','stage','start','end','title','speaker','type'];
const changes=[];
for(const cur of newSessions){const original=old.find(s=>String(s.id)===String(cur.id));if(!original){changes.push({kind:'added',id:cur.id,current:cur});continue}
 const changed=fields.filter(f=>clean(original[f])!==clean(cur[f]));
 if(changed.length)changes.push({kind:'updated',id:cur.id,fields:changed,previous:original,current:cur});
}
for(const v of unmatched.values())changes.push({kind:'removed',id:v.id,previous:v});
const changed=changes.length>0 || prior.source!=='official-web-page';
if(!changed){console.log('No schedule changes. Keeping published snapshot unchanged (avoid unnecessary Pages builds).');process.exit(0)}
const now=new Date().toISOString();
const result={source:'official-web-page',sourceUrl:SOURCE,method:'scheduled-browser-extraction',verifiedAt:now,lastChangedAt:changed?now:(prior.lastChangedAt||null),sessions:newSessions,changes,notes:'Independent extraction of public official schedule; not organizer operated.'};
await writeFile(outfile,JSON.stringify(result,null,2)+'\n');
console.log(`Validated ${newSessions.length} sessions; ${changes.length} changes; verified ${now}`);
