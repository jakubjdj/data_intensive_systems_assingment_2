import { places, Region } from './scene';

type Node = {region:Region;role:string;reachable:boolean;network:{isolated:boolean|null}};
const points:Record<Region,[number,number]>={usa:[75,85],france:[300,45],australia:[525,85]};
const links:[Region,Region][]=[['usa','france'],['france','australia'],['usa','australia']];

export default function Topology({nodes}:{nodes:Node[]}){
  return <div className="topology-graph"><svg viewBox="0 0 600 155" role="img" aria-label="Three-member replica topology with every pair connected">
    {links.map(([a,b])=>{
      const na=nodes.find(n=>n.region===a),nb=nodes.find(n=>n.region===b);
      const unknown=!na||!nb||!na.reachable||!nb.reachable||na.network.isolated===null||nb.network.isolated===null;
      const broken=na?.network.isolated||nb?.network.isolated;
      const color=unknown?'#d7b878':broken?'#e2917e':'#92c6aa';
      const [x1,y1]=points[a],[x2,y2]=points[b];
      return <line key={a+b} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth="2" strokeDasharray={broken||unknown?'5 5':undefined}><title>{a} ↔ {b}: {unknown?'unknown':broken?'partitioned':'firewall open'}</title></line>;
    })}
    {(Object.keys(points) as Region[]).map(r=>{const [x,y]=points[r],n=nodes.find(n=>n.region===r);return <g key={r}><rect x={x-55} y={y-26} width="110" height="59" fill="#203e46" stroke="#617e76"/><text x={x} y={y} textAnchor="middle" fill="#d8d5b6" fontSize="20" fontFamily="monospace">{places[r].code}</text><text x={x} y={y+20} textAnchor="middle" fill="#b2c9be" fontSize="9" fontFamily="monospace">{n?.role||'UNKNOWN'}</text></g>;})}
    <text x="300" y="141" textAnchor="middle" fill="#91aaa6" fontSize="9" fontFamily="monospace">GREEN: OPEN · RED: PARTITIONED · AMBER: UNKNOWN</text>
  </svg></div>;
}
