"""Editable vector research-workflow figure matching the VTE review implementation."""
from pathlib import Path
from html import escape
import argparse
import json
import math
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import toColor as HexColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'figures'
PDF = OUT
OUT.mkdir(parents=True, exist_ok=True)
PDF.mkdir(parents=True, exist_ok=True)
W, H = 2280, 2390
SCALE = 0.24  # Vector page at 300-dpi-equivalent figure dimensions.
BASE = 'VTE_workflow_2026-10-04'
parser = argparse.ArgumentParser()
parser.add_argument('--lang', choices=('en', 'zh'), default='en')
LANG = parser.parse_args().lang
TRANSLATIONS = {}
if LANG == 'zh':
    from workflow_labels_zh import TRANSLATIONS
    BASE += '_zh'
    FONT, SVG_FONT = 'YaHei', 'Microsoft YaHei, Noto Sans CJK SC, sans-serif'
    pdfmetrics.registerFont(TTFont(FONT, 'C:/Windows/Fonts/msyh.ttc', subfontIndex=0))
    pdfmetrics.registerFont(TTFont(FONT+'-Bold', 'C:/Windows/Fonts/msyhbd.ttc', subfontIndex=0))
else:
    BASE += '_en'
    FONT, SVG_FONT = 'Arial', 'Arial, Helvetica, sans-serif'
    pdfmetrics.registerFont(TTFont(FONT, 'C:/Windows/Fonts/arial.ttf'))
    pdfmetrics.registerFont(TTFont(FONT+'-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
C = canvas.Canvas(str(PDF / (BASE + '.pdf')), pagesize=(W*SCALE,H*SCALE))
C.setTitle('VTE 抗凝决策：RAG 多智能体审核与定向修订' if LANG=='zh' else 'VTE: RAG-supported multi-agent review and targeted revision')
C.setAuthor('VTE study team')
C.scale(SCALE,SCALE)
SVG = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       '<title>VTE 研究流程图（中文版）</title>' if LANG=='zh' else '<title>VTE study workflow</title>',
       '<desc>病例与知识库、按角色检索、并行初判、协调汇总、分工审核与定向修订，以及拟定对比评价。</desc>' if LANG=='zh' else '<desc>Case preparation and role-specific retrieval, parallel specialist assessment, coordinator synthesis, targeted review and revision, and planned comparative evaluation.</desc>']
TEXT = []
INK, MUTED, BLUE, LINE = '#17365A', '#576F8A', '#367FCC', '#CADCEE'
PALE, WASH, LOOP = '#F5F9FE', '#EAF3FE', '#215CA1'
GRAY = '#899AAC'

def rect(x,y,w,h,fill='white',stroke=LINE,r=15,width=2,dash=False):
    C.setFillColor(HexColor(fill)); C.setStrokeColor(HexColor(stroke)); C.setLineWidth(width)
    C.setDash([9,6] if dash else [])
    C.roundRect(x,H-y-h,w,h,r,stroke=1,fill=1)
    C.setDash([])
    SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"'+(' stroke-dasharray="9 6"' if dash else '')+'/>')

def text(x,y,s,size=30,bold=False,color=INK,anchor='start',maxw=None):
    if LANG == 'zh' and s not in {'a','b','c','d','A','B','C','D'}:
        assert s in TRANSLATIONS, f'Missing translation: {s}'
    s = TRANSLATIONS.get(s, s)
    font = FONT+'-Bold' if bold else FONT
    sw = pdfmetrics.stringWidth(s,font,size)
    if maxw is not None: assert sw <= maxw, (s,round(sw,1),maxw)
    left = x if anchor=='start' else x-sw/2 if anchor=='middle' else x-sw
    assert 0<=left and left+sw<=W and 0<=y<=H-size, (s,x,y)
    C.setFont(font,size); C.setFillColor(HexColor(color))
    C.drawString(left,H-y-size*.83,s)
    SVG.append(f'<text x="{x}" y="{y+size*.83}" font-family="{SVG_FONT}" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" fill="{color}">{escape(s)}</text>')
    TEXT.append({'text':s,'x':left,'y':y,'width':sw,'height':size})

def lines(x,y,items,size=29,gap=40,color=MUTED,maxw=None):
    for i,s in enumerate(items): text(x,y+i*gap,s,size,color=color,maxw=maxw)

def route(points,color=BLUE,width=3.5,arrow=True,dash=False):
    C.setStrokeColor(HexColor(color)); C.setLineWidth(width); C.setDash([10,7] if dash else [])
    p=C.beginPath(); p.moveTo(points[0][0],H-points[0][1])
    for x,y in points[1:]: p.lineTo(x,H-y)
    C.drawPath(p); C.setDash([])
    SVG.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"'+(' stroke-dasharray="10 7"' if dash else '')+'/>')
    if arrow:
        (px,py),(x,y)=points[-2:]; a=math.atan2(y-py,x-px)
        tri=[(x,y),(x-15*math.cos(a)+7*math.sin(a),y-15*math.sin(a)-7*math.cos(a)),(x-15*math.cos(a)-7*math.sin(a),y-15*math.sin(a)+7*math.cos(a))]
        C.setFillColor(HexColor(color)); p=C.beginPath();p.moveTo(tri[0][0],H-tri[0][1])
        for xx,yy in tri[1:]: p.lineTo(xx,H-yy)
        p.close();C.drawPath(p,stroke=0,fill=1)
        SVG.append('<polygon points="'+' '.join(f'{xx},{yy}' for xx,yy in tri)+f'" fill="{color}"/>')

def panel(x,y,w,h,letter,title):
    rect(x,y,w,h,PALE,LINE,20)
    rect(x+24,y+24,42,42,BLUE,BLUE,10)
    text(x+45,y+30,letter,31,True,'white','middle')
    text(x+84,y+29,title,32,True,maxw=w-104)

def card(x,y,w,h,title,items,fill='white',color=BLUE,body_size=29):
    rect(x,y,w,h,fill,LINE)
    rect(x,y,6,h,color,color,3,0)
    text(x+24,y+22,title,31,True,maxw=w-48)
    lines(x+24,y+73,items,body_size,40,maxw=w-48)

def badge(x,y,letter):
    rect(x,y,47,47,BLUE,BLUE,12)
    text(x+23.5,y+8,letter,30,True,'white','middle')

rect(0,0,W,H,'white','white',0,0)
text(65,46,'VTE anticoagulation: RAG, multi-agent review and follow-up',49,True,maxw=2150)
text(65,118,'Evidence-supported recommendations from available information, with explicit assumptions',29,color=MUTED)
panel(60,185,480,1315,'a','Cases & evidence')
panel(570,185,1650,1315,'b','Multi-agent review and revision')
panel(60,1540,2160,375,'c','Clinical use and information follow-up')
panel(60,1960,2160,355,'d','Planned comparative evaluation')

# A: independently prepared case facts and versioned evidence converge on the review.
card(105,298,390,165,'VTE cases',['DVT and/or PE','Decision-specific case set'],body_size=28)
route([(300,463),(300,520)])
card(105,520,390,233,'Case preparation',['De-identification','Available clinical facts','Decision time & question','Known facts & explicit gaps'],body_size=26)
card(105,860,390,237,'Knowledge base',['Guidelines / local protocols','Drug prescribing information','Source, version & role tags','Document segmentation'],body_size=26)
route([(300,1097),(300,1150)])
card(105,1150,390,237,'Role-specific retrieval',['Case + specialist query','FTS5 / BM25; top-k = 4','Source-linked passages','Frozen evidence snapshot'],fill=WASH,body_size=26)
route([(105,694),(80,694),(80,1260),(105,1260)],width=2.5)
route([(495,625),(600,625),(600,326),(735,326)],width=3)
route([(495,1260),(625,1260),(625,353),(735,353)],width=3)
text(105,1424,'Shared case; role-specific evidence.',23,color=MUTED,maxw=400)

# B: explicit fan-out and fan-in, followed by the role-scoped audit loop.
rect(735,292,1060,98,WASH,LINE)
text(1265,309,'Structured patient facts + retrieved evidence',33,True,anchor='middle',maxw=1000)
text(1265,354,'References remain linked to their source and version',25,color=MUTED,anchor='middle')
route([(1265,390),(1265,431)],arrow=False)
route([(915,431),(1835,431)],arrow=False)
for cx in (915,1375,1835): route([(cx,431),(cx,486)])
text(735,256,'01  Independent assessment in parallel',28,True,color=BLUE)

roles=[(710,'A','Anticoagulation',['Benefit, treatment stage','and duration']),
       (1170,'B','Medication safety',['Drug eligibility, dosing','and interactions']),
       (1630,'C','Bleeding risk',['Bleeding factors, patient','constraints and monitoring'])]
for x,r,title,body in roles:
    rect(x,486,410,190)
    badge(x+23,507,r)
    text(x+88,515,title,29,True,maxw=302)
    lines(x+24,577,body,27,39,maxw=360)
    route([(x+205,676),(x+205,718)],arrow=False)
route([(915,718),(1835,718)],arrow=False)
route([(1365,718),(1365,765)])
rect(985,765,760,123,WASH,LINE)
badge(1010,791,'D')
text(1084,786,'Coordinator synthesis',34,True,maxw=610)
text(1084,840,'Shared plan + role sections + explicit assumptions',25,color=MUTED,maxw=610)
route([(1365,888),(1365,968)])
text(835,929,'02  Parallel section review',28,True,color=BLUE)
rect(835,968,940,150)
for i,(r,label) in enumerate([('A','Anticoagulation'),('B','Medication safety'),('C','Bleeding risk')]):
    x=860+i*305
    badge(x,990,r)
    text(x+63,1002,label,26,True,maxw=235)
text(1305,1070,'First pass: A + B + C  |  Later passes: affected roles only',25,color=MUTED,anchor='middle',maxw=875)
route([(1305,1118),(1305,1162)])

# Review status has separate approval, revision and stop-condition routes.
diamond=[(1305,1162),(1490,1230),(1305,1298),(1120,1230)]
C.setFillColor(HexColor(WASH));C.setStrokeColor(HexColor(BLUE));C.setLineWidth(2.5)
p=C.beginPath();p.moveTo(diamond[0][0],H-diamond[0][1])
for x,y in diamond[1:]:p.lineTo(x,H-y)
p.close();C.drawPath(p,stroke=1,fill=1)
SVG.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in diamond)+f'" fill="{WASH}" stroke="{BLUE}" stroke-width="2.5"/>')
text(1305,1215,'Review status',28,True,anchor='middle')

route([(1490,1230),(1805,1230),(1805,1262),(2000,1262),(2000,1226)],LOOP)
text(1560,1193,'Changes needed',25,True,LOOP,maxw=235)
rect(1830,973,355,253,WASH,LINE)
badge(1852,996,'D')
text(1915,1004,'Targeted revision',27,True,maxw=245)
lines(1853,1064,['Resolve specific issues','Supplement retrieval','Update affected sections','Retain other approvals'],25,35,maxw=310)
route([(2000,973),(2000,928),(1680,928),(1680,968)],LOOP,width=4)
text(1840,895,'Re-review affected roles',24,True,LOOP,anchor='middle',maxw=380)
text(1850,1325,'Plan / assumptions changed?',24,True,color=LOOP,maxw=345)
text(1850,1362,'Re-review A, B and C.',24,color=MUTED,maxw=345)

route([(1120,1230),(815,1230)],GRAY,width=2.7,dash=True)
text(885,1194,'Stop criteria',25,color=MUTED,maxw=210)
rect(655,1010,160,413,'#F8FAFC','#DCE4ED',12,2,dash=True)
text(735,1030,'Human',25,True,anchor='middle')
text(735,1064,'review',25,True,anchor='middle')
for y,part in [(1124,['Unresolved','objections']),(1213,['Revision limit','(up to 3)']),(1302,['No change /','call failure'])]:
    for j,s in enumerate(part):text(735,y+j*30,s,21,color=MUTED,anchor='middle',maxw=146)

route([(1305,1298),(1305,1352)])
text(1340,1310,'Accept, including explicit conditions',24,True,color=BLUE,maxw=435)
rect(880,1352,865,115,BLUE,BLUE)
text(1312,1372,'Reviewed recommendation',34,True,'white','middle')
text(1312,1422,'Reviewed draft + conditions + citations + revision trail',25,color='#EDF5FF',anchor='middle')
text(1312,1470,'Available for physician review and sign-off',23,color=MUTED,anchor='middle')
route([(1312,1500),(1312,1540)],width=4)

# C: conditional recommendations are distinct from optional data collection.
route([(1312,1540),(1312,1612),(415,1612),(415,1637)],width=3)
card(90,1637,650,210,'Physician review',['Recommendation + explicit assumptions','Accept, amend or reject','No need to complete every field'],body_size=27)
route([(740,1742),(795,1742)],dash=True)
card(795,1637,650,210,'Information follow-up',['Provide data / confirm absent','Mark not relevant / unknown','Upload records when available'],body_size=27)
route([(1445,1742),(1500,1742)],dash=True)
card(1500,1637,690,210,'Updated recommendation',['Apply explicit clinician responses','Repeat RAG and targeted review','Retain the original report'],fill=WASH,body_size=27)
text(95,1870,'Routine gaps are optional. Missing facts remain unknown; decision-changing gaps become assumptions.',25,color=MUTED,maxw=2100)
# Explicit clinician action creates a new run; no automatic patient-fact invention.
route([(2190,1742),(2245,1742),(2245,342),(1795,342)],LOOP,width=3,dash=True)

# D: research design, not claims of completed experiments.
card(90,2057,650,201,'Model comparisons',['LLM alone  /  single-agent RAG','Parallel agents without iterative review','Full system with targeted revision'],body_size=28)
route([(740,2157),(795,2157)])
card(795,2057,650,201,'Blinded clinical review',['Guideline concordance & accuracy','Completeness, safety & citation support','Independent ratings and adjudication'],body_size=27)
route([(1445,2157),(1500,2157)])
card(1500,2057,690,201,'Outcomes & process measures',['Safety errors and recommendation quality','Errors corrected / newly introduced','Latency, model calls and token usage'],body_size=27)
text(95,2278,'Paired case-level comparisons  |  Ablation analysis  |  Prespecified clinical subgroups',25,color=MUTED,maxw=2020)
text(65,2345,'VTE: venous thromboembolism   DVT: deep vein thrombosis   PE: pulmonary embolism   RAG: retrieval-augmented generation',23,color=MUTED,maxw=2150)

C.showPage();C.save()
SVG.append('</svg>')
(OUT/(BASE+'.svg')).write_text('\n'.join(SVG),encoding='utf-8')
layout_dir = ROOT / 'runs' / 'figure-qa'
layout_dir.mkdir(parents=True, exist_ok=True)
(layout_dir/(BASE+'_text-layout.json')).write_text(json.dumps(TEXT,indent=2),encoding='utf-8')
print(PDF/(BASE+'.pdf'))
print(OUT/(BASE+'.svg'))
