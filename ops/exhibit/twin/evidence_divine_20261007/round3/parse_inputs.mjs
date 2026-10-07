// 第三輪的 12 份「像真 AI 回答」：先用雲端 server.js 真正的 parseCard 解析（raw），
// 再做一個最小的清理（去粗體記號、把「／」攤平成換行、去編號、「欄位 - 值」→「欄位：值」）後再解析（cleaned）。
// 用法：node parse_inputs.mjs <server.js> <inputs12_raw.json> <out.json>
import fs from 'node:fs'; import vm from 'node:vm';
const [,, serverJs, inFile, outFile] = process.argv;
const src = fs.readFileSync(serverJs,'utf8').split('\n');
const start = src.findIndex(l=>l.startsWith('const SHAPES'));
const endI = src.findIndex((l,i)=>i>start && l.startsWith('function fortuneOf'));
const ctx = {}; ctx.globalThis = ctx; vm.createContext(ctx);
vm.runInContext(src.slice(start-3, endI).join('\n') + '\nglobalThis.parseCard = parseCard;', ctx);
const LABELS = '形狀|質感|色系|氣質|MBTI|星座|血型|他心裡一直想試|他來到新世界';
function clean(t) {
  t = t.replace(/\*\*/g, '');
  t = t.replace(new RegExp(`／(?=\\s*(?:${LABELS}))`, 'g'), '\n');
  t = t.replace(/^\s*\d+[．.、]\s*/gm, '');
  t = t.replace(new RegExp(`^(${LABELS})\\s+-\\s+`, 'gm'), '$1：');
  t = t.replace(/\s*←[^\n]*/g, '');
  return t;
}
const inputs = JSON.parse(fs.readFileSync(inFile,'utf8'));
const out = inputs.map(x => ({name: x.name, voice: x.voice, text_raw: x.text, text: clean(x.text),
  card_raw: ctx.parseCard(x.text), card: ctx.parseCard(clean(x.text))}));
fs.writeFileSync(outFile, JSON.stringify(out, null, 1) + '\n');
const fields = ['shape','texture','color','vibe','mbti','zodiac','blood','want','first_line'];
for (const o of out) {
  const miss = fields.filter(k => !o.card_raw[k]), miss2 = fields.filter(k => !o.card[k]);
  console.log(o.name, 'raw缺:', miss.join(',')||'-', '| cleaned缺:', miss2.join(',')||'-');
}
