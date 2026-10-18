import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { drawAirport, places, Region } from './scene';
import './style.css';
import Topology from './Topology';

type Account = {id:string;holder:string;number:string;balance_cents:number;currency:string;status:string};
type Receipt = {id:string;account_id:string;type:string;amount_cents:number;balance_after_cents:number;region:Region;primary:string;timestamp:string;status:string};
type Node = {region:Region;host:string;role:string;reachable:boolean;applied_at?:string;optime?:string;accounts:Account[];latest_transaction?:Receipt;network:{isolated:boolean|null;rules?:Record<string,string[]>};peers?:{name:string;health:number;state:string;message:string}[]};
type Observation = {id:string;timestamp?:string;message:string;kind?:'record'|'replication'|'accepted'|'majority'|'election';collection?:string;record_id?:string;transaction_id?:string;source?:string;destinations?:string[];record?:Record<string,unknown>};
type Status = {nodes:Node[];observed_at:string;note:string;events:Observation[]};
type Pending = {request_id:string;account_id:string;type:string;amount_cents:number;region:Region};
type Scenario = {running:boolean;number?:number;passed?:boolean;steps:string[]};
const regions:Region[] = ['usa','france','australia'];
const money = (c:number) => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(c/100);
const errorText = (e:unknown) => e instanceof Error ? e.message : String(e);
class ApiError extends Error {constructor(message:string,public status:number){super(message);}}
async function api<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch('/api'+path, {method:body === undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Lab-Control':'1'},body:body===undefined?undefined:JSON.stringify(body)});
  const data = await response.json();
  if(!response.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail),response.status);
  return data;
}
function readPending():Pending|null {try{return JSON.parse(localStorage.getItem('bank-pending')||'null');}catch{return null;}}

function Airport({region}:{region:Region}) {
  const canvas=useRef<HTMLCanvasElement>(null);
  useEffect(()=>{let tick=0; const draw=()=>canvas.current&&drawAirport(canvas.current,region,tick++);draw();const timer=setInterval(draw,700);return()=>clearInterval(timer);},[region]);
  return <canvas ref={canvas} width="480" height="270" aria-label={`Pixel art airport terminal in ${places[region].city}`} role="img"/>;
}

function ObservationEntry({entry}:{entry:Observation}) {
  const date=entry.timestamp?new Date(entry.timestamp):null;
  const stamp=date&&!Number.isNaN(date.getTime())?<time className="observation-stamp" dateTime={entry.timestamp}><span>{date.toLocaleDateString()}</span><span>{date.toLocaleTimeString(undefined,{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3})}</span></time>:<span className="observation-stamp">Unavailable</span>;
  if(!entry.record)return <div className="observation-row">{stamp}<p className="observation-system">{entry.message}</p></div>;
  const {id,...fields}=entry.record;
  return <div className="observation-row">{stamp}<details className={'observation-entry '+entry.kind}>
    <summary><span aria-hidden="true" className="observation-toggle"><span className="observation-plus">+</span><span className="observation-minus">−</span></span><span className="observation-kind">{entry.kind==='replication'?'REPLICATED':entry.kind==='accepted'?'ACCEPTED':entry.kind==='majority'?'MAJORITY':'RECORD CHANGE'}</span><span>{entry.message}</span></summary>
    <div className="observation-content"><p>Collection: <strong>{entry.collection}</strong> / Record: <strong>{entry.record_id}</strong></p>
      <p>Originating transaction: <code>{entry.transaction_id}</code></p>
      {entry.destinations&&<p>Verified copies: {entry.destinations.join(', ')}</p>}
      <pre aria-label="Database record contents">{JSON.stringify({_id:id,...fields},null,2)}</pre>
    </div>
  </details></div>;
}

function App(){
  const [region,setRegion]=useState<Region>('usa');
  const [panel,setPanel]=useState<'atm'|'notebook'|'jammer'|'travel'|'scenarios'|null>(null);
  const [status,setStatus]=useState<Status|null>(null);
  const [monitorError,setMonitorError]=useState('');
  const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const [accounts,setAccounts]=useState<Account[]>([]);const [aid,setAid]=useState('ACC-1001');
  const [bankObservedAt,setBankObservedAt]=useState('');const bankRead=useRef(0);
  const [history,setHistory]=useState<Receipt[]>([]); const [receipt,setReceipt]=useState<Receipt|null>(null);
  const [amount,setAmount]=useState('100.00');const [kind,setKind]=useState('deposit');
  const [pending,setPending]=useState<Pending|null>(readPending);
  const [inspectAid,setInspectAid]=useState('ACC-1001');
  const [jamTarget,setJamTarget]=useState<Region>('australia');const [jamPower,setJamPower]=useState(false);
  const [resetConfirm,setResetConfirm]=useState(false); const [arrival,setArrival]=useState(false);
  const [scenario,setScenario]=useState<Scenario>({running:false,steps:[]});
  const [scenarioNumber,setScenarioNumber]=useState(1);
  const account=accounts.find(a=>a.id===aid);
  const here=status?.nodes.find(n=>n.region===region);
  const scenarioNames=['Global replication','Secondary failure','Primary election','Consistency protection','Recovery & convergence','Concurrent withdrawals'];

  async function refresh(){try{setStatus(await api<Status>('/status'));setMonitorError('');}catch(e){setMonitorError(errorText(e));}}
  useEffect(()=>{let live=true;let timer:ReturnType<typeof setTimeout>;const poll=async()=>{await refresh();if(live)timer=setTimeout(poll,2500);};void poll();return()=>{live=false;clearTimeout(timer);};},[]);
  useEffect(()=>{if(panel!=='scenarios')return;let live=true;let timer:ReturnType<typeof setTimeout>;const poll=async()=>{try{const s=await api<Scenario>('/scenarios');if(live)setScenario(s);}catch(e){if(live)setError(errorText(e));}if(live)timer=setTimeout(poll,1500);};void poll();return()=>{live=false;clearTimeout(timer);};},[panel]);
  useEffect(()=>{if(!panel)return;const prior=document.activeElement as HTMLElement;const el=document.querySelector<HTMLElement>('[role="dialog"]');el?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){setPanel(null);}if(e.key==='Tab'&&el){const items=Array.from(el.querySelectorAll<HTMLElement>('button:not(:disabled),select,input,summary,[tabindex="0"]'));const first=items[0],last=items[items.length-1];if(e.shiftKey&&(document.activeElement===first||document.activeElement===el)){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}};window.addEventListener('keydown',key);return()=>{window.removeEventListener('keydown',key);prior?.focus();};},[panel]);
  async function loadBank(){const version=++bankRead.current;setAccounts([]);setHistory([]);setBankObservedAt('');const list=await api<Account[]>(`/bank/${region}/accounts`);if(version!==bankRead.current)return;setAccounts(list);setBankObservedAt(new Date().toLocaleTimeString());const rows=await api<Receipt[]>(`/bank/${region}/accounts/${aid}/transactions`);if(version===bankRead.current)setHistory(rows);}
  useEffect(()=>{if(panel==='atm'){setAccounts([]);setHistory([]);void perform(loadBank);}},[panel,region,aid]);
  async function perform(fn:()=>Promise<unknown>){setBusy(true);setError('');try{await fn();}catch(e){setError(errorText(e));}finally{setBusy(false);}}
  function savePending(p:Pending|null){setPending(p);if(p)localStorage.setItem('bank-pending',JSON.stringify(p));else localStorage.removeItem('bank-pending');}
  async function submit(){
    if(!/^\d+(\.\d{1,2})?$/.test(amount))throw new Error('Enter a positive USD amount with at most two decimal places.');
    const [dollars,fraction='']=amount.split('.');const cents=Number(dollars)*100+Number(fraction.padEnd(2,'0'));
    if(!Number.isSafeInteger(cents)||cents<=0||cents>100000000)throw new Error('Amount must be between $0.01 and $1,000,000.00.');
    const p:Pending={request_id:crypto.randomUUID(),account_id:aid,type:kind,amount_cents:cents,region};
    savePending(p);setReceipt(null);
    try {const r=await api<Receipt>(`/bank/${region}/transactions`,p);setReceipt(r);savePending(null);await loadBank();}
    catch(e){if(e instanceof ApiError&&e.status>=400&&e.status<500){savePending(null);throw e;}throw new Error(errorText(e)+' Request saved. Reconcile before making another transaction.');}
  }
  async function reconcile(retry=false){if(!pending)return;
    const p=pending;
    const result=await api<{transaction:Receipt|null}>(`/bank/${p.region}/transactions/${p.request_id}`);
    if(result.transaction){setReceipt(result.transaction);savePending(null);if(p.region===region)await loadBank();}
    else if(retry){const r=await api<Receipt>(`/bank/${p.region}/transactions`,p);setReceipt(r);savePending(null);if(p.region===region)await loadBank();}
    else throw new Error('No committed record found. Retry the saved operation with its original ID, or discard it if no request is still in flight.');
  }
  const open=(p:typeof panel)=>{setError('');setResetConfirm(false);setPanel(p);};
  const networkAction=(path:string,body:unknown={})=>perform(async()=>{await api(path,body);await refresh();});
  return <div className="app-shell">
    <header><a className="brand" href="#" onClick={e=>e.preventDefault()}><span className="brand-mark">G<span>✦</span></span><span>GLOBAL BANK<small>DISTRIBUTED SYSTEMS FIELD LAB</small></span></a><div className="session"><span className={'led '+(status?'green':'amber')}/>{status?'CONTROL STATION ONLINE':'CONNECTING TO LAB'}<span className="badge">TESTER 001</span></div></header>
    <main>
      <div className="mission-bar"><span>FIELD ASSIGNMENT <b>02</b> <i>/</i> THE WORLD IS YOUR TEST ENVIRONMENT</span><button className="text-button" onClick={()=>open('scenarios')}>GUIDED TESTS ↗</button></div>
      <section className={'world '+(arrival?'arriving':'')} aria-label="Airport scene">
        <Airport region={region}/>
        <div className="location"><span className="eyebrow">YOU ARE HERE</span><h1>{places[region].city}<span>{places[region].code}</span></h1><p>{places[region].country} <span>·</span> {places[region].terminal}</p></div>
        <div className="scene-tag"><span className={'led '+(here?.network.isolated?'red':'green')}/>{here?.network.isolated?'REGIONAL PARTITION':'REGIONAL ACCESS POINT'}<br/><small>{here?.host||`mongo-${region}`}</small></div>
        <button className="atm-hotspot" onClick={()=>open('atm')} aria-label="Use Global Bank ATM"><span>USE ATM <b>↗</b></span></button>
        <div className="world-footer"><span>CLICK THE ATM TO BEGIN</span><button onClick={()=>open('travel')}>✈ DEPARTURES / TRAVEL →</button></div>
      </section>
      <section className="toolbelt" aria-label="Tester tools"><div className="inventory-label">YOUR FIELD KIT<span>INSPECT. DISRUPT. DISCOVER.</span></div>
        <button onClick={()=>open('notebook')}><span className="tool-icon">▤</span><span>ENGINEER'S NOTEBOOK<small>Inspect the real replica set</small></span><b>01 ↗</b></button>
        <button onClick={()=>open('jammer')}><span className="tool-icon jammer-icon">⌁</span><span>NETWORK JAMMER<small>Put consistency to the test</small></span><b>02 ↗</b></button>
      </section>
      <section className="telemetry"><span className="eyebrow">LIVE DATABASE SIGNAL</span>{regions.map(r=>{const n=status?.nodes.find(n=>n.region===r);return <button key={r} onClick={()=>open('notebook')}><span className={'led '+(!n?.reachable?'amber':n.network.isolated?'red':'green')}/><b>{places[r].code}</b><span>{n?.role||'AWAITING SIGNAL'}</span></button>;})}<span className="telemetry-note">3 INSTANCES · 1 REPLICA SET</span></section>
      {monitorError&&<p className="error" role="alert">Monitoring unavailable: {monitorError}</p>}
      <footer><span>A SMALL ADVENTURE IN DISTRIBUTED SYSTEMS.</span><span>LOCAL LAB <b>●</b> REAL DATABASES</span></footer>
    </main>
    {panel&&<div className="overlay" onMouseDown={e=>{if(e.target===e.currentTarget)setPanel(null);}}><section className={'panel '+panel} role="dialog" aria-modal="true" aria-labelledby="panel-title" tabIndex={-1}>
      <div className="panel-heading"><div><span className="eyebrow">GLOBAL BANK / FIELD EQUIPMENT</span><h2 id="panel-title">{panel==='atm'?'ATM · '+places[region].code:panel==='notebook'?"Engineer's notebook":panel==='jammer'?'Network jammer':panel==='travel'?'Choose your next stop':'Guided field tests'}</h2></div><button aria-label="Close dialog" onClick={()=>setPanel(null)}>✕</button></div>
      {error&&<p className="error" role="alert">{error}</p>}
      {busy&&<p className="working" role="status">CONTACTING THE LAB…</p>}
      {panel==='atm'&&<>
        <div className="notice">Accessing <b>{here?.host||`mongo-${region}`}</b>. Financial requests route through this region to the elected primary. Balances below use authoritative reads.{bankObservedAt&&<> Last successful balance check: <b>{bankObservedAt}</b>.</>}</div>
        {pending&&<div className="pending"><b>SAVED REQUEST · OUTCOME NEEDS RECONCILIATION</b><p>{pending.type} {money(pending.amount_cents)} · {pending.account_id} · {pending.region.toUpperCase()}</p><code>{pending.request_id}</code><div className="actions"><button disabled={busy} onClick={()=>void perform(()=>reconcile())}>CHECK RESULT</button><button disabled={busy} onClick={()=>void perform(()=>reconcile(true))}>RETRY SAME ID</button></div><small>If a validated request was rejected, correct the inputs after clearing this saved request. An absent record alone does not prove an in-flight request was aborted.</small><button className="text-button" disabled={busy} onClick={()=>{if(window.confirm('Discard saved reconciliation information? Only do this after confirming the request failed and is no longer in flight.'))savePending(null);}}>DISCARD SAVED REQUEST</button></div>}
        <div className="atm-grid"><div><label>SELECT ACCOUNT<select value={aid} onChange={e=>setAid(e.target.value)}>{(accounts.length?accounts:[{id:aid,holder:'Loading / unavailable'}]).map(a=><option key={a.id} value={a.id}>{a.id} · {a.holder}</option>)}</select></label><div className="balance"><span>AVAILABLE BALANCE / USD</span><strong>{account?money(account.balance_cents):'—'}</strong><small>{account?.holder||'Awaiting authoritative database response'}</small></div>
          <form onSubmit={e=>{e.preventDefault();void perform(submit);}}><label>OPERATION<select value={kind} onChange={e=>setKind(e.target.value)}><option value="deposit">Deposit</option><option value="withdrawal">Withdrawal</option></select></label><label>AMOUNT / USD<input inputMode="decimal" value={amount} onChange={e=>setAmount(e.target.value)} placeholder="100.00"/></label><button className="primary" disabled={busy||!!pending||!account}>CONFIRM {kind.toUpperCase()} →</button></form><button className="text-button" disabled={busy} onClick={()=>void perform(loadBank)}>↻ REFRESH BALANCE & HISTORY</button>
        </div><div>{receipt?<article className="receipt" aria-label="Transaction receipt"><h3>GLOBAL BANK</h3><p>ATM: {places[receipt.region].city}</p><hr/><p>{receipt.type.toUpperCase()} <b>{money(receipt.amount_cents)}</b></p><p>STATUS: {receipt.status.toUpperCase()}</p><p>BALANCE: {money(receipt.balance_after_cents)}</p><p>PRIMARY: {receipt.primary}</p><p>{new Date(receipt.timestamp).toLocaleString()}</p><code>{receipt.id}</code><hr/><p>THANK YOU FOR TESTING WITH US.</p><button onClick={()=>window.print()}>PRINT RECEIPT</button></article>:<div className="receipt-placeholder">YOUR NEXT RECEIPT<br/>STARTS WITH A REAL<br/>DATABASE TRANSACTION.<span>▧</span></div>}</div></div>
        <h3>RECENT TRANSACTIONS</h3><div className="table-scroll"><table><thead><tr><th>TIME</th><th>OPERATION</th><th>AMOUNT</th><th>BALANCE AFTER</th><th>REQUEST</th></tr></thead><tbody>{history.map(t=><tr key={t.id}><td>{new Date(t.timestamp).toLocaleString()}</td><td>{t.type}</td><td>{money(t.amount_cents)}</td><td>{money(t.balance_after_cents)}</td><td title={t.id}>{t.id.slice(0,12)}</td></tr>)}</tbody></table></div>
      </>}
      {panel==='travel'&&<><p>Same account. Different airport. Your destination determines the regional banking connection.</p><div className="destinations">{regions.map(r=><button key={r} disabled={region===r} onClick={()=>{setRegion(r);setPanel(null);setReceipt(null);setAccounts([]);setArrival(true);setTimeout(()=>setArrival(false),900);}}><span className="airport-code">{places[r].code}</span><b>{places[r].city}</b><small>{places[r].country}</small><span>{region===r?'CURRENT LOCATION':'BOARD FLIGHT →'}</span></button>)}</div></>}
      {panel==='notebook'&&<><p className="notice">{status?.note||'Waiting for live inspection.'} Stale replica balances must never be used to authorize withdrawals.</p><label>COMPARE ACCOUNT<select value={inspectAid} onChange={e=>setInspectAid(e.target.value)}>{['1001','1002','1003','1004','1005'].map(n=><option key={n}>ACC-{n}</option>)}</select></label><Topology nodes={status?.nodes||[]}/><p className="muted">Links reflect verified firewall rules. Peer heartbeat health below is MongoDB's own observation.</p><div className="node-grid">{status?.nodes.map(n=><article key={n.region} className="node-card"><span className="eyebrow">{places[n.region].city}</span><h3>{n.host}</h3><span className={'role '+(n.role==='PRIMARY'?'leader':'')}>{n.role}</span><dl><dt>Control reachability</dt><dd>{n.reachable?'Reachable':'Unreachable'}</dd><dt>Firewall</dt><dd>{n.network.isolated===null?'Unknown':n.network.isolated?'PARTITIONED':'Open'}</dd><dt>Local balance</dt><dd>{n.accounts.find(a=>a.id===inspectAid)?money(n.accounts.find(a=>a.id===inspectAid)!.balance_cents):'Unavailable'}</dd><dt>Latest local transaction</dt><dd>{n.latest_transaction?.id||'Unknown'}</dd></dl>{n.peers?.map(p=><p className="peer" key={p.name}>{p.health?'●':'○'} {p.name} · {p.state}{p.message&&<small>{p.message}</small>}</p>)}</article>)}</div><h3>OBSERVATION LOG <small>session memory</small></h3><p className="muted">Times show when this session observed each event. Entries within one inspection present record changes, acceptances, then confirmed majority once two copies are observed. Expand an entry to inspect its database record.</p><div className="observation-columns"><span>OBSERVED DATE / TIME (LOCAL)</span><span>EVENT / NEWEST FIRST</span></div><div className="event-log">{status?.events.length ? status.events.map(e=><ObservationEntry key={e.id} entry={e}/>) : <p>Waiting for record changes.</p>}</div><button onClick={()=>void refresh()}>↻ INSPECT NOW</button></>}
      {panel==='jammer'&&<><div className="notice">This device changes actual firewall rules inside the database containers. Isolated regions lose access to the majority. Local inspection and recovery stay available.</div><div className="jammer-device"><span className="eyebrow">GB / LINK DISRUPTOR v1</span><div className="radio-display">{jamPower?'ARMED / SELECT TARGET':'STANDBY'}<span>DATABASE PEER LINKS / LOCAL LAB</span></div><label className="power"><input type="checkbox" checked={jamPower} onChange={e=>setJamPower(e.target.checked)}/>ARM DEVICE</label><label>TARGET NODE<select value={jamTarget} onChange={e=>setJamTarget(e.target.value as Region)}>{regions.map(r=><option key={r} value={r}>{places[r].city} / mongo-{r}</option>)}</select></label><div className="actions"><button className="danger" disabled={!jamPower||busy||scenario.running} onClick={()=>void networkAction(`/network/${jamTarget}`,{isolated:true})}>ISOLATE NODE</button><button disabled={busy} onClick={()=>void networkAction('/restore')}>RESTORE ALL LINKS</button></div></div><div className="network-indicators">{status?.nodes.map(n=><span key={n.region}><span className={'led '+(n.network.isolated===null?'amber':n.network.isolated?'red':'green')}/>{places[n.region].code} · {n.network.isolated===null?'UNKNOWN':n.network.isolated?'ISOLATED':'CONNECTED'}</span>)}</div><p>When a primary loses its majority, it steps down. The remaining two members can elect a new primary. Election and catch-up take time; the notebook shows observed roles.</p><details><summary>Reset demonstration data</summary><p>Restores connectivity, replaces all account balances and transaction history with the original five-account seed.</p>{!resetConfirm?<button onClick={()=>setResetConfirm(true)}>PREPARE RESET</button>:<button className="danger" disabled={busy||scenario.running||!!pending} onClick={()=>void perform(async()=>{await api('/reset',{});setResetConfirm(false);setReceipt(null);await refresh();})}>CONFIRM: REPLACE DEMO DATA</button>}</details></>}
      {panel==='scenarios'&&<><p>These tests operate on the real lab. Tests 1–5 leave a $1 deposit; the concurrency test withdraws and returns Ethan's balance on success. Run one at a time without other banking activity.</p><label>TEST SCENARIO<select value={scenarioNumber} disabled={scenario.running} onChange={e=>setScenarioNumber(Number(e.target.value))}>{scenarioNames.map((s,i)=><option key={s} value={i+1}>{String(i+1).padStart(2,'0')} / {s}</option>)}</select></label><p className="notice">Every test checks live API results. Network tests apply real partitions and restore links on completion, including failures.</p><button className="primary" disabled={busy||scenario.running||!!pending} onClick={()=>void perform(async()=>setScenario(await api<Scenario>(`/scenarios/${scenarioNumber}`,{})))}>{scenario.running?'TEST IN PROGRESS…':'RUN LIVE TEST →'}</button><div className="test-result"><h3>{scenario.running?'RUNNING':scenario.passed===true?'PASS ✓':scenario.passed===false?'FAIL / SEE RESULTS':'AWAITING TEST'}</h3>{scenario.steps.map((s,i)=><p key={i}>{String(i+1).padStart(2,'0')} · {s}</p>)}</div></>}
    </section></div>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
