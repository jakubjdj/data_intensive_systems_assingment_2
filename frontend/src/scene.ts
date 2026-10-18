export type Region = 'usa' | 'france' | 'australia';
export const places = {
  usa: { city: 'NEW YORK', country: 'United States', code: 'JFK', terminal: 'TERMINAL 04', greeting: 'WELCOME TO NEW YORK', color: '#e6b871' },
  france: { city: 'PARIS', country: 'France', code: 'CDG', terminal: 'TERMINAL 02', greeting: 'BIENVENUE À PARIS', color: '#cfb5d9' },
  australia: { city: 'SYDNEY', country: 'Australia', code: 'SYD', terminal: 'TERMINAL 01', greeting: 'WELCOME TO SYDNEY', color: '#8bd0c8' }
};

// Native pixel artwork: no remote imagery, fonts, or runtime asset services.
export function drawAirport(canvas: HTMLCanvasElement, region: Region, tick: number) {
  const g = canvas.getContext('2d')!;
  g.imageSmoothingEnabled = false;
  const rect = (x: number, y: number, w: number, h: number, c: string) => { g.fillStyle = c; g.fillRect(x, y, w, h); };
  const poly = (points: number[][], c: string) => { g.fillStyle = c; g.beginPath(); points.forEach(([x,y],i) => i ? g.lineTo(x,y) : g.moveTo(x,y)); g.closePath(); g.fill(); };
  const text = (s: string,x: number,y: number,c = '#b9d8d5',size = 5) => { g.fillStyle = c; g.font = `${size}px monospace`; g.fillText(s,x,y); };
  const p = places[region];
  rect(0,0,480,270,'#182b38');
  rect(0,58,480,110,region === 'usa' ? '#c99779' : region === 'france' ? '#b7a6bb' : '#80b6bb');
  rect(0,110,480,45,'#6c8790'); rect(0,143,480,26,'#64747a');
  // Distant city silhouettes, deliberately distinct at each destination.
  for (let i=0;i<40;i++) { const h=7+(i*13%22); rect(i*13,127-h,9,h,'#77868c'); }
  if(region === 'usa') { rect(83,77,9,49,'#6a7d89'); rect(86,62,3,15,'#6a7d89'); }
  if(region === 'france') { poly([[76,126],[95,69],[114,126]],'#73818e'); poly([[84,126],[95,97],[106,126]],'#b7a6bb'); rect(80,110,30,3,'#73818e'); }
  if(region === 'australia') { for(let i=0;i<4;i++)poly([[62+i*10,128],[67+i*10,108-i*3],[84+i*10,128]],'#dce1cd'); }
  rect(0,157,480,10,'#465d67');
  for(let x=8;x<480;x+=33)rect(x,160,18,1,'#c5c4aa');
  const planeX=335 + Math.floor(tick/4)%18;
  poly([[planeX-33,144],[planeX+18,144],[planeX+30,140],[planeX+22,148],[planeX-32,148]],'#d9dfd5');
  poly([[planeX-6,145],[planeX-20,130],[planeX-12,130],[planeX+10,145]],'#b3c9ca');
  poly([[planeX+21,144],[planeX+21,130],[planeX+29,130],[planeX+29,140]],p.color);
  for(let x=planeX-25;x<planeX+15;x+=5)rect(x,144,2,1,'#39515f');
  // Window mullions and terminal ceiling.
  for(let x=15;x<480;x+=75) { rect(x,52,5,118,'#283e49'); rect(x+5,52,2,118,'#6b8388'); }
  rect(0,87,480,3,'#344d58'); rect(0,164,480,9,'#253c48');
  poly([[0,0],[480,0],[480,48],[0,48]],'#233943');
  for(let x=-60;x<600;x+=90)poly([[x,0],[x+5,0],[x+70,48],[x+65,48]],'#3c5259');
  rect(0,46,480,9,'#122733'); rect(0,54,480,2,p.color);
  for(let x=24;x<480;x+=120) { rect(x,21,65,3,'#94a8a5'); rect(x+1,21,63,1,'#eff0cd'); }
  poly([[0,173],[480,173],[480,270],[0,270]],'#334650');
  for(let y=181;y<270;y+=Math.floor((y-150)/3))rect(0,y,480,1,'#40565d');
  for(let x=-360;x<900;x+=90)poly([[235+(x-235)*0.25,173],[236+(x-235)*0.25,173],[x+1,270],[x,270]],'#536168');
  // Structural pillars.
  for(const x of [25,421]) { rect(x,54,20,135,'#647777'); rect(x+3,54,4,135,'#85928a'); rect(x+16,54,4,135,'#253e49'); rect(x-2,184,24,6,'#233b47'); }
  // Local signage and departures board.
  rect(59,66,145,16,'#182e39'); text(p.greeting,66,76,p.color,6);
  rect(313,62,91,49,'#0f232e'); rect(316,65,85,9,'#315363'); text(region==='france'?'DÉPARTS / DEPARTURES':'DEPARTURES',320,71,'#e7cc87');
  const flights=region==='usa'?['PARIS     14:20','SYDNEY    15:45','CHICAGO   16:10']:region==='france'?['NEW YORK  14:20','LYON      15:45','SYDNEY    16:10']:['PARIS     14:20','MELBOURNE 15:45','NEW YORK  16:10'];
  flights.forEach((f,i)=>{text(f,320,84+i*9,'#c6cebc');rect(389,80+i*9,5,2,i===tick%3?'#cbbd79':'#6b9b8b');});
  // Seating and luggage.
  for(const start of [63,328]) { for(let i=0;i<3;i++){rect(start+i*21,165,18,11,'#263d51');rect(start+i*21+1,166,16,2,'#69838a');rect(start+i*21,177,19,5,'#233746');rect(start+i*21+2,182,2,8,'#9ba79c');} }
  rect(110,178,10,14,'#bb896a');rect(112,174,6,4,'#253845');rect(112,192,2,2,'#152c39');rect(117,192,2,2,'#152c39');
  // Flag.
  rect(276,62,24,14,'#e5ded1');
  if(region==='france'){rect(276,62,8,14,'#44708f');rect(292,62,8,14,'#bc6560');}
  else if(region==='usa'){for(let y=62;y<76;y+=4)rect(276,y,24,2,'#b65e5e');rect(276,62,10,8,'#33556e');for(let x=278;x<285;x+=3)rect(x,64,1,1,'#fff0ca');}
  else {rect(276,62,24,14,'#2c5277');rect(277,63,9,5,'#c9d6d0');rect(281,63,2,5,'#b66864');for(const [x,y] of [[294,65],[290,70],[297,72]])rect(x,y,2,2,'#e6e7d2');}
  // Central ATM, perspective base, screen, physical keypad and slot.
  poly([[193,231],[273,231],[297,247],[175,247]],'#1f3541');
  rect(198,110,72,125,'#142c38'); rect(201,107,66,5,'#73938f');rect(202,112,62,120,'#486a6d');
  rect(206,116,54,11,'#183541');text('GLOBAL BANK',211,124,'#e9d9aa',6);
  rect(208,132,49,39,'#0c2532');rect(211,135,43,32,'#80baa6');
  text('HELLO, TESTER',216,146,'#163e43',5);text('INSERT YOUR',216,155,'#254b4b',4);text('CURIOSITY',220,161,'#254b4b',4);
  for(let y=138;y<164;y+=9){rect(204,y,3,4,'#c0cbb2');rect(258,y,3,4,'#c0cbb2');}
  rect(211,179,43,7,'#193c48');rect(213,180,39,2,tick%4<2?'#a9cfaf':'#5d9284');
  poly([[209,192],[255,192],[260,210],[204,210]],'#a3b0a0');
  for(let y=0;y<3;y++)for(let x=0;x<3;x++)rect(215+x*7,195+y*4,5,3,'#37565b');
  rect(239,195,9,3,'#b7836a');rect(239,199,9,3,'#c8bb7d');rect(239,203,9,3,'#6a9d86');
  rect(215,216,34,4,'#1a3441');rect(222,220,20,4,'#294b55');
  text('01 / FIELD TERMINAL',199,243,'#9eb4ae',4);
  // Foreground planters.
  for(const x of [7,452]){rect(x,218,23,30,'#9d8d77');rect(x-2,215,27,5,'#baaa8d');rect(x+10,180,3,35,'#49786e');for(let i=0;i<4;i++){poly([[x+11,194+i*5],[x-5,180+i*6],[x+7,185+i*6]],'#5a8f7e');poly([[x+12,190+i*6],[x+31,177+i*7],[x+19,191+i*6]],'#73a28a');}}
}
