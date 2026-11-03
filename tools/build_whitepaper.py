"""Build the implementation whitepaper PDF (requires reportlab and pypdf)."""
from pathlib import Path
import ast
import html
import json
import re
import textwrap
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/whitepapers'
SOURCE = DOC / 'cpu-llm-1.10.0-whitepaper.md'

def inline(value):
    value = html.escape(value)
    value = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', value)
    value = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', value)
    value = re.sub(r'(https://[^\s<]+)', r'<link href="\1" color="#145c88">\1</link>', value)
    return value

def main():
    tree = ast.parse((ROOT/'src/cpu_llm/pipeline.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Appliance')
    methods = {n.name: 'def '+n.name+'('+ast.unparse(n.args)+') -> '+ast.unparse(n.returns)
               for n in cls.body if isinstance(n, ast.FunctionDef) and (not n.name.startswith('_') or n.name == '__init__') and n.returns}
    (DOC/'cpu-llm-1.10.0-api-reference.json').write_text(json.dumps({
        'version':'1.10.0', 'source':'src/cpu_llm/pipeline.py',
        'runtime_revision':'0102bc0', 'signatures':methods,
        'http_ask_fields':['discover','imagine','deep','math','finance','as_of','session_id','strict_evidence','small_talk'],
        'notes':['style is Python-only','grade and per-request child_safety are not enforced by _ask_single',
                 'Direct ingest/delete_source are not authenticated public endpoints; use Entry'],
        'node_reference':'cpu-llm-1.10.0-whitepaper.md section 6'
        ,'nodes':['guard','retrieve','resonate','dense','relational','disentangled','hyperbolic','identity','causal','catalog','detail','spans','think','cognize','grammar','shine','reply','imagine','gather','deep','compare','brief','math','finance','frame','model01','discover']
    },indent=2)+'\n',encoding='utf-8')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyPaper',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=8,splitLongWords=True))
    styles.add(ParagraphStyle(name='TitlePaper',fontName='Helvetica-Bold',fontSize=25,leading=30,textColor=colors.HexColor('#12334a'),spaceAfter=16))
    styles.add(ParagraphStyle(name='SectionPaper',fontName='Helvetica-Bold',fontSize=15,leading=19,textColor=colors.HexColor('#12334a'),spaceBefore=16,spaceAfter=9,keepWithNext=True))
    styles.add(ParagraphStyle(name='SubPaper',fontName='Helvetica-Bold',fontSize=11,leading=15,spaceBefore=10,spaceAfter=7,keepWithNext=True))
    code_style=ParagraphStyle(name='CodePaper',fontName='Courier',fontSize=7.8,leading=10.5,backColor=colors.HexColor('#f1f5f8'),borderPadding=7,spaceBefore=5,spaceAfter=10)
    story=[]; paragraph=[]; code=[]; fenced=False
    def flush():
        if paragraph:
            story.append(Paragraph(inline(' '.join(paragraph)),styles['BodyPaper']))
            paragraph.clear()
    content=SOURCE.read_text(encoding='utf-8')
    for line in content.splitlines():
        if line.startswith('```'):
            flush()
            if fenced:
                if code and code_lang == 'python': ast.parse('\n'.join(code))
                wrapped=[]
                for part in code:
                    wrapped.extend(textwrap.wrap(part,91,replace_whitespace=False,drop_whitespace=False) or [''])
                story.append(Preformatted('\n'.join(wrapped),code_style)); code=[]
            else: code_lang=line[3:].strip()
            fenced=not fenced; continue
        if fenced: code.append(line); continue
        if not line.strip(): flush(); continue
        if line.startswith('#'):
            flush(); level=len(line)-len(line.lstrip('#'))
            if line.startswith('## References'): story.append(PageBreak())
            story.append(Paragraph(inline(line[level:].strip()),styles['TitlePaper' if level==1 else 'SectionPaper' if level==2 else 'SubPaper']))
        elif re.match(r'^([-*] |\d+\. )',line):
            flush(); paragraph.append(line)
        else: paragraph.append(line.strip())
    flush()
    output=ROOT/'output/pdf/cpu-llm-1.10.0-whitepaper.pdf'; output.parent.mkdir(parents=True,exist_ok=True)
    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor('#c4d3de')); canvas.line(48,40,564,40)
        canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#40576a'))
        canvas.drawString(48,28,'Insight ITS | cpu-llm 1.10.0 | Implementation whitepaper')
        canvas.drawRightString(564,28,str(doc.page))
    SimpleDocTemplate(str(output),pagesize=(612,792),rightMargin=48,leftMargin=48,topMargin=44,bottomMargin=56,
        title='CPU LLM for Local Document Question Answering',author='Amin Parva, Insight IT Solutions LLC').build(story,onFirstPage=footer,onLaterPages=footer)
    (DOC/output.name).write_bytes(output.read_bytes())
    print(output)

if __name__ == '__main__': main()
