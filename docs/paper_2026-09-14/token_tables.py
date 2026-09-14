"""Publication tables backed only by verified_tokens.json."""
from pathlib import Path
import json
BASE=Path(__file__).resolve().parent
T=json.loads((BASE/'verified_tokens.json').read_text())
RUNS=['R460','r1','r2','r3','r4','r5']
SETS=['LCB3_medium','LCB3_hard','HumanEvalPlus','MBPPPlus']
NAMES={'HPI':'H-PI','HOC':'H-OC','HMIX':'H-MIX'}
# One spelling per bank everywhere: the body text, table 6, table 10, F3 and F4
# must all say "LCB v3 medium" so that a ratio quoted in 5.7 can be found in F3
# without the reader translating between 中 / medium / LCB3.
SETLABEL={'LCB3_medium':'LCB v3 medium','LCB3_hard':'LCB v3 hard','HumanEvalPlus':'HumanEval+','MBPPPlus':'MBPP+'}
MODES=[('','合併（兩種模式混合）'),('_reasoning','推論開（1003）'),('_no_reasoning','推論關（1004）')]
def nm(s):return NAMES.get(s,s)
def num(x):return f'{x:,.0f}' if x is not None else '未計量'
def both(a,b):return num(a)+' / '+num(b)
def mult(x):return f'{x:.3f}×' if x is not None else '—'
def pct(x):return f'{x:.1f}%' if x is not None else '未計量'

def register(table):
    # Probe accounting is read from the ledger, not typed in: 38 wire_probe calls
    # is not 38 metered calls, and the paper distinguishes known from unknown cost
    # everywhere else.
    hp=T['cross_pooled']['arms']['HMIX']
    PROBE=(f"全套共 {hp['probe_calls']} 通 wire_probe，全部歸 H-MIX；其中 {hp['probe_metered_calls']} 通有回報用量、"
           f"已知合計 {hp['probe_tokens']:,} token，使 H-MIX 合併每題成本單邊上偏 "
           f"{100*(hp['per_task']/hp['per_task_excl_probe']-1):.2f}%，其餘 {hp['probe_calls']-hp['probe_metered_calls']} 通失敗且未回報用量，列為未知消耗。")
    rows=[]
    for k in RUNS:
        v=T[k]['pairs']['HMIX_vs_OFF'];w=T[k]['pairs']['HMIX_vs_CONFORM']
        rows.append([k,f"{v['delta_pp']:+.2f}",f"{v['extra_token_pct']:+.1f}%",f"{v['tpc_ratio']:.2f}×",f"{w['delta_pp']:+.2f}",f"{w['extra_token_pct']:+.1f}%",f"{w['tpc_ratio']:.2f}×"])
    table('token_summary','表 9　H-MIX 的交付增益與額外 token 消耗',
      ['階段','對 OFF\nΔ pp','對 OFF\ntoken 增減','對 OFF\n每件成本比','對 C\nΔ pp','對 C\ntoken 增減','對 C\n每件成本比'],rows,
      'C 為 CONFORM。兩欄的 token 都是已回報的 prompt 與 completion 之和（reasoning 為 completion 的子集合，不重複相加），含可歸屬該臂的 wire_probe，且只取兩臂共同題目上的有效題呼叫，不含作廢題的消耗。token 增減是共同題目總量的相對變動；每件成本比為每件正確交付 token 的比率，大於 1 表示成本較高。r5 的比較使用各自共同題目，故不同配對的 H-MIX 成本分子不相同。統計判定沿用表 5；比率未作新的顯著性檢定。完整分子、分母及作廢成本見附錄 F。',[1.1,1.6,2.2,2.1,1.6,2.2,2.1])

    rows=[]
    for k in RUNS:
        r5=T[k]['arm_ratios']
        rows.append([k,mult(r5['OFF5_over_CONFORM']['per_task_excl_void']),mult(r5['OFF5_over_CONFORM']['tpc_incl_void']),
                     mult(r5['HMIX_over_CONFORM']['per_task_excl_void']),mult(r5['HMIX_over_CONFORM']['tpc_incl_void']),
                     mult(r5['HMIX_over_OFF5']['tpc_incl_void'])])
    for k in SETS+['cross_pooled']:
        r5=T[k]['arm_ratios'];label='R529 合併' if k=='cross_pooled' else 'R529 '+SETLABEL[k]
        rows.append([label,'—','—',mult(r5['HMIX_over_CONFORM']['per_task_excl_void']),mult(r5['HMIX_over_CONFORM']['tpc_incl_void']),'—'])
    table('token_ratio','表 10　多數決與修訂流程相對驗收重抽的 token 倍率',
      ['階段或題目集','OFF5 ÷ C\ntoken / 題','OFF5 ÷ C\ntoken / 正確件','H-MIX ÷ C\ntoken / 題','H-MIX ÷ C\ntoken / 正確件','H-MIX ÷ OFF5\ntoken / 正確件'],rows,
      'C 為 CONFORM。每一格是兩臂各自全臂帳本的比值，不是共同題目的比值（共同題目版見表 F2）。token／題的分子排除作廢題、分母為該臂有效題數；token／正確件的分子保留作廢呼叫。兩者都是 prompt 加 completion，並含可歸屬該臂的 wire_probe。第五次逐臂分母不同（OFF 119、CONFORM 117、OFF5 118、H-PI 120、H-OC 120、H-MIX 119）；若把作廢呼叫也計入每題成本，第五次的 OFF5 ÷ C 為 2.246 倍。R529 沒有 OFF5 臂，亦無作廢列。最後一欄對應 R460 四狀態的第三項條件（每件成本不高於同次的 OFF5），六次全部成立；R529 改用「合併每件成本 H-MIX 不高於 CONFORM」，實測 1.383 倍，不成立。R529 逐集的兩臂承接相同區塊，後端組成相同，故比值可讀；其絕對 token 仍是兩種推論條件的混合。',[2.9,2.0,2.4,2.0,2.4,2.4])

    rows=[]
    for k in RUNS:
        for a in ['OFF','CONFORM','OFF5','HPI','HOC','HMIX']:
            v=T[k]['arms'][a]
            rows.append([k+' '+nm(a),f"{v['correct']}/{v['n']}",num(v['reported_total']),num(v['per_task']),num(v['tpc_all']),num(v.get('void_total',0)),str(v.get('unmetered_calls',0))])
    table('token_arms','表 F1　六臂逐次每題 token 與每件正確交付 token',
      ['階段與臂','成功 / n','已知總 token','有效題 token / 題','含作廢 token / 正確件','作廢 token','未知用量呼叫'],rows,
      '已知總量包含該臂成功回報的 prompt 與 completion，以及可歸屬該臂的 wire_probe；reasoning 已包含在 completion，不重複相加。有效題每題成本排除作廢題，分母為該臂有效題數，第五次因此逐臂不同（OFF 119、CONFORM 117、OFF5 118、H-PI 120、H-OC 120、H-MIX 119）；每件成本分子保留作廢。不含 wire_probe 的每題版本保存在 verified_tokens.json 的 per_task_excl_probe；六次同題庫實驗中只有 H-PI 帶可歸屬的探針，每次 6 通、324 至 420 token，占該臂已知總量的 0.03% 至 0.05%，其餘五臂兩種口徑相同。未知用量呼叫均為失敗請求，實際消耗不能當作零。未歸臂 preflight 另存 JSON，不任意分攤。',[2.8,1.7,2.5,2.5,2.9,1.6,1.5])

    rows=[]
    for k in RUNS:
        for pair,v in T[k]['pairs'].items():
            a,b=pair.split('_vs_')
            rows.append([k+'\n'+nm(a)+' / '+nm(b),str(v['n']),f"{v['delta_pp']:+.2f}",both(v['a_per_task'],v['b_per_task']),f"{v['token_ratio']:.3f}×\n{v['extra_token_pct']:+.1f}%",both(v['a_tpc'],v['b_tpc'])])
    table('token_pairs','表 F2　六臂比較的增益與同題 token 成本',
      ['階段 A / B','共同 n','A−B\nΔ pp','token / 題\nA / B','總 token 比\n與增減','token / 正確件\nA / B'],rows,
      '每一列的效果、成本分子與正確件數均取相同共同題目；有效題總量可由每題未四捨五入值乘 n 得到，精確整數保存在 verified_tokens.json。此表同時列正負與零差值，避免只選有利結果。H 臂對 OFF 與 CONFORM 的檢定沿用原六項家族；其他對照為探索性。每件成本是觀測批次平均值，不是單題的因果效果。',[3.1,1.1,1.5,3.1,2.6,3.4])

    rows=[]
    for s in SETS:
        for suffix,label in MODES:
            for a in ['OFF','CONFORM','HMIX']:
                v=T[s+suffix]['arms'][a]
                rows.append([SETLABEL[s]+'\n'+label,nm(a),f"{v['correct']}/{v['n']}",num(v['reported_total']),
                             num(v['per_task_incl_void']),num(v['tpc_all']),pct(v.get('reasoning_pct_of_completion'))])
    table('token_cross_arms','表 F3　R529 逐題目集與逐後端的 token、每件成本與 reasoning 占比',
      ['題目集與推論條件','臂','成功 / n','已知總 token','token / 題','token / 正確件','reasoning ÷ completion'],rows,
      '推論開為 1003（LM Studio 0.4.24），推論關為 1004（0.4.17）；模式由保存的 usage 行為確認，不是後端自報的設定。合併列是兩種推論條件的混合物，只能與同列的兩條拆分列一起讀，不可單獨引用，也不可用於集間難度比較。reasoning token 是 completion 的子集合，本欄為 reasoning 除以 completion，不另外加進總量。R529 無作廢列，故含與不含作廢的每件成本相同；每題成本的分母為該臂在該條件下承接的題數。'+PROBE+'兩後端承接不同題目，本表只描述各自條件，不把兩台當作隨機化的推論模式實驗。',[3.0,1.8,1.4,2.0,1.8,2.0,2.1])

    rows=[]
    for s in SETS:
        for mode,label in [('reasoning','推論開'),('no_reasoning','推論關')]:
            for pair in ['CONFORM_vs_OFF','HMIX_vs_OFF','HMIX_vs_CONFORM']:
                v=T[s+'_'+mode]['pairs'][pair];a,b=pair.split('_vs_')
                rows.append([SETLABEL[s]+' '+label+'\n'+nm(a)+' / '+nm(b),str(v['n']),f"{v['delta_pp']:+.2f}",both(v['a_per_task'],v['b_per_task']),f"{v['token_ratio']:.3f}×\n{v['extra_token_pct']:+.1f}%",both(v['a_tpc'],v['b_tpc'])])
    table('token_cross_pairs','表 F4　R529 同後端同題的增益與 token 比較',
      ['題目集 模式 A / B','共同 n','A−B\nΔ pp','token / 題\nA / B','總 token 比\n與增減','token / 正確件\nA / B'],rows,
      '本表每格的 token 皆為已回報的 prompt 與 completion 之和，含可歸屬該臂的 wire_probe，分子只取同一後端上兩臂的共同題目；R529 沒有作廢列，故含與不含作廢的口徑一致。逐後端分析是發現模式差異後的描述性分層；原跨題庫主要檢定仍以預註冊合併值為準，不新增分層顯著性主張。完整正確件數、總量、prompt、completion 與 reasoning 的拆分保存在 verified_tokens.json。',[3.9,1.0,1.4,3.0,2.4,3.1])

    rows=[]
    for k,label in [('early_MBPP','R444+445 MBPP+'),('early_LCB2','r447 LCB v2')]:
        v=T[k]['pairs']['CONFORM_vs_OFF']
        rows.append([label,f"{v['delta_pp']:+.2f}",both(v['a_tokens'],v['b_tokens']),both(v['a_per_task'],v['b_per_task']),f"{v['token_ratio']:.3f}×",both(v['a_tpc'],v['b_tpc'])])
    rows.append(['r461 LCB v3','+7.94','未計量','未計量','未確定','未計量'])
    for k in ['r446','r448','r449b','r449c']:
        pair=T['eq5'][k]['selection_pair'];ca=pair['gate_correct'];cb=pair['vote_correct'];d=pair['delta_pp']
        v=T['eq5'][k].get('arms',{}).get('EQ5')
        rows.append([k+' EQ5',f'{d:+.2f}',num(v['reported_total'])+'（共用）' if v else '總量缺失（共用候選）',num(v['per_task']) if v else '未計量','1.000×（設計）',both(v['reported_total']/ca,v['reported_total']/cb) if v else '未計量'])
    table('token_early','表 F5　早期增益的 token 證據與缺口',
      ['階段','Δ pp','總 token\nA / B 或共用','token / 題\nA / B 或共用','總量比 A/B','token / 正確件\nA / B'],rows,
      '前兩列 A 為 CONFORM、B 為 OFF；EQ5 的 A 為驗收選擇、B 為多數決。全部數字皆為已回報的 prompt 與 completion 之和；前兩列只取兩臂共同題目的有效題呼叫，EQ5 列的總量與每件成本則為該 run 共用候選池的全臂已知總量，三者都沒有作廢列，也沒有可歸屬的 wire_probe。r448 與 r461 主實驗缺 calls.jsonl，rows 與 summary 只有呼叫數，不能轉換成 token。r461_off_gate 是另一個先導 run，不能代替主實驗。EQ5 的 1 倍表示共用同一候選池，沒有第二筆生成消耗；不涵蓋沙箱及測試維護成本。前三個有 token 原始檔的 EQ5 分別有 1、2、8 通用量未知的失敗呼叫。',[3.0,1.2,3.6,2.7,2.3,3.7])

if __name__=='__main__':
    tables={}
    def collect(k,title,h,rows,note,widths):tables[k]=(title,h,rows,note)
    register(collect)
    text=['# 交付增益與 token 成本核對','以各次原始 calls.jsonl 對照同題 rows.jsonl；未知用量不補零。完整精確數據、每筆來源檔 SHA-256 與可重算程式同目錄保存。']
    for title,h,rows,note in tables.values():
        text+=['## '+title,'|'+'|'.join(x.replace('\n','<br>') for x in h)+'|','|'+'|'.join('---' for _ in h)+'|']
        text += ['|'+'|'.join(str(x).replace('\n','<br>') for x in row)+'|' for row in rows]
        text+=['',note,'']
    (BASE/'TOKEN_AUDIT.md').write_text('\n\n'.join(text)+'\n')
