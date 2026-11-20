"""Render the newcomer workflow as PNG and editable SVG, without external services."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from html import escape

OUT = Path(__file__).resolve().parents[1] / 'docs/diagrams'
W, H = 1920, 1080
im = Image.new('RGB', (W, H), '#F7FAFE')
d = ImageDraw.Draw(im)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<rect width="1920" height="1080" fill="#F7FAFE"/>']
NAVY, BLUE, TEAL = '#18304D', '#1455D9', '#118C8C'


def rect(x, y, w, h, fill, stroke=BLUE, radius=18):
    d.rounded_rectangle((x, y, x+w, y+h), radius=radius, fill=fill, outline=stroke, width=2)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')


def text(x, y, s, size=26, color=NAVY, bold=False):
    font = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc', size)
    d.text((x, y), s, font=font, fill=color)
    svg.append(f'<text x="{x}" y="{y+size}" font-family="Microsoft YaHei, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(s)}</text>')


def arrow(points, color=BLUE, dashed=False):
    for (x1,y1),(x2,y2) in zip(points, points[1:]):
        if dashed:
            length=max(abs(x2-x1),abs(y2-y1))
            for pos in range(0,int(length),20):
                a,b=pos/length,min(pos+11,length)/length
                d.line((x1+(x2-x1)*a,y1+(y2-y1)*a,x1+(x2-x1)*b,y1+(y2-y1)*b),fill=color,width=3)
        else: d.line((x1,y1,x2,y2),fill=color,width=3)
    import math
    x,y=points[-1]; px,py=points[-2]; angle=math.atan2(y-py,x-px)
    tri=[(x,y),(x-15*math.cos(angle-.45),y-15*math.sin(angle-.45)),(x-15*math.cos(angle+.45),y-15*math.sin(angle+.45))]
    d.polygon(tri,fill=color)
    dash=' stroke-dasharray="11 9"' if dashed else ''
    svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="3"{dash}/>')
    svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in tri)}" fill="{color}"/>')


text(60, 38, 'JARVIS 如何帮你完成一项任务', 52, bold=True)
text(62, 112, '你提出目标，JARVIS 负责推进、检查与交付；关键决定由你掌握。', 29)
text(60, 194, '日常工作流程', 28, BLUE, True)
cards = [
    ('01  你提出需求', ['想解决什么问题？', '希望拿到什么成果？', '有哪些时间或范围限制？']),
    ('02  明确目标与计划', ['确认交付物和验收标准', '读取相关知识与协作偏好', '简单任务直接开始']),
    ('03  推进执行', ['优先直接处理', '按需使用工具、Skill', '确有收益时委派 Worker']),
    ('04  检查与修正', ['核对成果与证据', '有依据时有限重试', '遇到阻碍说明缺口']),
    ('05  交付给你验收', ['给出成果与验证结果', '说明限制和待决定事项', '按反馈修订并记录状态']),
]
for i,(title,lines) in enumerate(cards):
    x=60+i*370
    rect(x,250,310,220,'#FFFFFF')
    text(x+20,272,title,27,BLUE,True)
    for j,line in enumerate(lines): text(x+20,329+j*39,line,22)
    if i<4: arrow([(x+315,360),(x+363,360)])
arrow([(1385,475),(1385,515),(955,515),(955,475)],dashed=True)
text(1020,527,'需要修正：返回执行',23,BLUE)
text(62,491,'一般任务在已授权范围内连续推进，无需逐步确认。',23)

rect(60,590,1790,104,'#FFF8E9','#C18A24')
text(85,610,'何时需要你决定？',27,'#92600D',True)
text(420,610,'目标或范围实质变化  ·  超预算  ·  未授权的对外或不可逆操作',25)
text(420,649,'JARVIS 会带上已有成果、缺口与选项，集中请你判断。',23)

text(60,734,'持续支持与维护',28,TEAL,True)
support=[
    ('工具与临时 Worker', ['按任务需要调用，管家复核结果', '总目标与最终交付责任仍在 JARVIS']),
    ('项目级协作画像', ['按已确认偏好协作；当前要求优先', '新增或修订长期条目，经你确认发布']),
    ('知识整理：由你手动触发', ['知识库管理员离线整理候选与提案', '正式写入前按批准差异执行']),
]
for i,(title,lines) in enumerate(support):
    x=60+i*610
    rect(x,790,570,155,'#EDF8F7',TEAL)
    text(x+22,808,title,27,TEAL,True)
    for j,line in enumerate(lines): text(x+22,857+j*36,line,23)
text(60,985,'当前形态：项目主会话角色；不是独立常驻服务。自检通过 ≠ 你已验收。',23)
text(60,1027,'JARVIS 项目工作流程  |  2026-11-18  |  实线：主流程    虚线：修正反馈',20,'#62758B')
im.save(OUT/'JARVIS-新用户工作流程.png')
svg.append('</svg>')
(OUT/'JARVIS-新用户工作流程.svg').write_text('\n'.join(svg),encoding='utf-8')
print(OUT/'JARVIS-新用户工作流程.png')
