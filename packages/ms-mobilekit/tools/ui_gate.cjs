const {chromium}=require("playwright");
const {start}=require("./static.cjs"); const widths=[360,375,390,414,430,768,1024];
(async()=>{const srv=await start();const b=await chromium.launch();let bad=0;
for(const scheme of ["light","dark"]){for(const w of widths){
  const p=await b.newPage({viewport:{width:w,height:900},colorScheme:scheme});await p.goto(srv.url);await p.waitForTimeout(250);
  const pages=await p.evaluate(()=>[...document.querySelectorAll('.ms-screen')].map(s=>s.dataset.screen));
  for(const pg of pages){await p.evaluate(pg=>{ const ex=document.querySelector(`[data-ex][data-screen-for="${pg}"]`); if(ex) ex.click(); else window.ms.screens.go(pg); },pg);await p.waitForTimeout(400);
    const r=await p.evaluate(()=>{const de=document.documentElement;const out={hscroll:de.scrollWidth>de.clientWidth+1,clipped:[],offscreen:[],lowContrast:[],smallTargets:[]};
      document.querySelectorAll('.btn,.ms-tab,a[href]').forEach(el=>{const r=el.getBoundingClientRect();const cs=getComputedStyle(el);if(cs.display==='none'||r.width===0)return;if(el.closest('.ms-screen:not(.on)'))return;if(r.height<44||r.width<44)out.smallTargets.push(el.tagName+':'+el.textContent.trim().slice(0,20)+' '+Math.round(r.width)+'x'+Math.round(r.height))});
      document.querySelectorAll('*').forEach(el=>{const cs=getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden')return;if(el.closest('[hidden],.hidden'))return;
        if(el.scrollWidth>el.clientWidth+2&&/auto|scroll/.test(cs.overflowX)&&el.clientWidth>0)out.clipped.push(el.tagName+'.'+el.className);
        const r=el.getBoundingClientRect();if(r.width>0&&(r.right>de.clientWidth+1||r.left<-1)&&el.children.length===0&&el.textContent.trim())out.offscreen.push(el.tagName+':'+el.textContent.trim().slice(0,30));});
      const lum=c=>{const m=c.match(/\d+(\.\d+)?/g);if(!m)return null;const [r,g,b]=m.map(Number).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*r+.7152*g+.0722*b};
      const bgOf=el=>{while(el){const c=getComputedStyle(el).backgroundColor;if(c&&!/rgba\(0, 0, 0, 0\)|transparent/.test(c))return c;el=el.parentElement}return getComputedStyle(document.body).backgroundColor};
      document.querySelectorAll('td,th,h1,h2,h3,p,li,a,span,b,small,dt,dd,summary,label,button,figcaption').forEach(el=>{if(!el.textContent.trim()||el.children.length>1)return;const cs=getComputedStyle(el);if(cs.display==='none'||el.closest('[hidden],.hidden'))return;const r=el.getBoundingClientRect();if(r.width===0)return;const l1=lum(cs.color),l2=lum(bgOf(el));if(l1==null||l2==null)return;const ratio=(Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05);if(ratio<4.5)out.lowContrast.push(el.tagName+'.'+el.className+':'+el.textContent.trim().slice(0,25)+' ('+ratio.toFixed(1)+')')});
      out.clipped=[...new Set(out.clipped)];out.lowContrast=[...new Set(out.lowContrast)].slice(0,8);out.offscreen=out.offscreen.slice(0,5);out.smallTargets=[...new Set(out.smallTargets)].slice(0,6);return out});
    const issues=(r.hscroll?1:0)+r.clipped.length+r.offscreen.length+r.lowContrast.length+r.smallTargets.length; bad+=issues;
    if(issues) console.log(`${scheme.padEnd(5)} ${String(w).padStart(4)}px ${pg.padEnd(9)} ISSUES ${r.hscroll?'page-hscroll ':''}${r.clipped.length?'clipped:'+r.clipped.join(','):''} ${r.offscreen.length?'offscreen:'+r.offscreen.join('|'):''} ${r.lowContrast.length?'contrast:'+r.lowContrast.join('|'):''} ${r.smallTargets.length?'small-targets:'+r.smallTargets.join('|'):''}`);}
  await p.close();}}
await b.close();srv.close();console.log(bad?`\n${bad} issue(s)`:'\nAll clear');process.exit(bad?1:0)})();
