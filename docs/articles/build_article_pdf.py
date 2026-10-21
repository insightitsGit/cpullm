"""Build the cpu-llm essay PDF. Run: python docs/articles/build_article_pdf.py"""

from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent
ASSETS = Path(
    r"C:\Users\parva\.cursor\projects\c-code-cpullm\assets"
)
ROUTER = ASSETS / (
    "c__Users_parva_AppData_Roaming_Cursor_User_workspaceStorage_"
    "f50ee9ff31d1c7024234447e123725af_images_"
    "Gemini_Generated_Image_l4kavpl4kavpl4ka-ef7a5f31-28a9-4acb-8837-bdc4ea709a54.jpg"
)
PIPELINE = ASSETS / (
    "c__Users_parva_AppData_Roaming_Cursor_User_workspaceStorage_"
    "f50ee9ff31d1c7024234447e123725af_images_"
    "Gemini_Generated_Image_dekwrtdekwrtdekw-5fd95a76-fca0-4519-a2c5-9088cdb8ebfd.jpg"
)
COST = ASSETS / (
    "c__Users_parva_AppData_Roaming_Cursor_User_workspaceStorage_"
    "f50ee9ff31d1c7024234447e123725af_images_"
    "Gemini_Generated_Image_pwsc8tpwsc8tpwsc-7086a0fc-bf6c-497e-b9e7-eb9bf58710b1.jpg"
)
OUT = ROOT / "stop-dropping-every-prompt-onto-gpus.pdf"

NAVY = HexColor("#0B1F33")
INK = HexColor("#1C2430")
MUTED = HexColor("#5C6A78")
AMBER = HexColor("#C47B2B")
RULE = HexColor("#E4D9CC")
PAPER = HexColor("#F7F2EC")
PAPER_RGB = (247, 242, 236)
ROW_ALT = HexColor("#FBF8F4")
FONT_DIR = Path(r"C:\Windows\Fonts")

PAGE_W, PAGE_H = letter
LEFT = 0.82 * inch
RIGHT = 0.82 * inch
TOP = 0.68 * inch
BOTTOM = 0.62 * inch
CONTENT_W = PAGE_W - LEFT - RIGHT


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Georgia", str(FONT_DIR / "georgia.ttf")))
    pdfmetrics.registerFont(TTFont("Georgia-Bold", str(FONT_DIR / "georgiab.ttf")))
    pdfmetrics.registerFont(TTFont("Georgia-Italic", str(FONT_DIR / "georgiai.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri", str(FONT_DIR / "calibri.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", str(FONT_DIR / "calibrib.ttf")))
    pdfmetrics.registerFont(TTFont("Calibri-Italic", str(FONT_DIR / "calibrii.ttf")))


def styles() -> dict[str, ParagraphStyle]:
    body = ParagraphStyle(
        "body",
        fontName="Calibri",
        fontSize=11,
        leading=15.6,
        textColor=INK,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    return {
        "kicker": ParagraphStyle(
            "kicker",
            fontName="Calibri-Bold",
            fontSize=8.5,
            leading=11,
            textColor=AMBER,
            tracking=1.2,
            spaceAfter=8,
        ),
        "title": ParagraphStyle(
            "title",
            fontName="Georgia",
            fontSize=26,
            leading=31,
            textColor=NAVY,
            spaceAfter=10,
        ),
        "dek": ParagraphStyle(
            "dek",
            fontName="Georgia-Italic",
            fontSize=12,
            leading=17,
            textColor=HexColor("#3E4C5A"),
            spaceAfter=8,
        ),
        "byline": ParagraphStyle(
            "byline",
            fontName="Calibri",
            fontSize=9.5,
            leading=13,
            textColor=MUTED,
            spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName="Georgia",
            fontSize=16,
            leading=20,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "body": body,
        "bullet": ParagraphStyle(
            "bullet",
            fontName="Calibri",
            fontSize=11,
            leading=15.6,
            textColor=INK,
            alignment=TA_LEFT,
            leftIndent=18,
            firstLineIndent=-14,
            spaceBefore=1,
            spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "caption",
            fontName="Calibri-Italic",
            fontSize=9,
            leading=12.2,
            textColor=MUTED,
            spaceBefore=5,
            spaceAfter=2,
        ),
        "figlabel": ParagraphStyle(
            "figlabel",
            fontName="Calibri-Bold",
            fontSize=8,
            leading=11,
            textColor=AMBER,
            spaceBefore=0,
            spaceAfter=8,
        ),
        "th": ParagraphStyle(
            "th",
            fontName="Calibri-Bold",
            fontSize=8,
            leading=10.5,
            textColor=white,
        ),
        "td": ParagraphStyle(
            "td",
            fontName="Calibri",
            fontSize=8.5,
            leading=11.2,
            textColor=INK,
        ),
        "tdstrong": ParagraphStyle(
            "tdstrong",
            fontName="Calibri-Bold",
            fontSize=8.5,
            leading=11.2,
            textColor=NAVY,
        ),
        "source": ParagraphStyle(
            "source",
            fontName="Calibri",
            fontSize=8.5,
            leading=11.4,
            textColor=MUTED,
            leftIndent=12,
            firstLineIndent=-12,
            spaceAfter=3,
        ),
        "footer_note": ParagraphStyle(
            "footer_note",
            fontName="Calibri-Italic",
            fontSize=8.5,
            leading=11.4,
            textColor=MUTED,
            spaceBefore=6,
        ),
    }


def prepare_pipeline() -> PILImage.Image:
    """Drop the faded duplicate row the generator left under the diagram."""
    image = PILImage.open(PIPELINE).convert("RGB")
    top = image.crop((0, 36, image.width, 228))
    caption = image.crop((0, 498, image.width, 552))
    gap = 18
    canvas = PILImage.new(
        "RGB",
        (image.width, top.height + gap + caption.height),
        PAPER_RGB,
    )
    canvas.paste(top, (0, 0))
    canvas.paste(caption, (0, top.height + gap))
    return canvas


def load_figure(path: Path) -> PILImage.Image:
    return PILImage.open(path).convert("RGB")


def save_png(image: PILImage.Image, name: str) -> Path:
    path = ROOT / name
    image.save(path, format="PNG")
    return path


def figure(path: Path, number: str, caption: str, s: dict) -> KeepTogether:
    with PILImage.open(path) as image:
        width = CONTENT_W
        height = width * image.height / image.width
    picture = Image(str(path), width=width, height=height)
    framed = Table([[picture]], colWidths=[width])
    framed.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PAPER),
                ("BOX", (0, 0), (-1, -1), 0.6, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    label = Paragraph(
        f"FIGURE {number} &nbsp;&nbsp;<font color='#5C6A78' name='Calibri-Italic'>{caption}</font>",
        s["figlabel"],
    )
    return KeepTogether([Spacer(1, 8), framed, label])


def bullets(items: list[str], s: dict) -> list[Paragraph]:
    mark = '<font color="#C47B2B">•</font>&nbsp;&nbsp;'
    return [Paragraph(mark + item, s["bullet"]) for item in items]


def comparison(s: dict) -> Table:
    header = [
        Paragraph("Dimension", s["th"]),
        Paragraph("Generative path on a GPU", s["th"]),
        Paragraph("cpu-llm on CPU", s["th"]),
    ]
    rows_raw = [
        (
            "What actually runs",
            "A generative model, usually behind an API or on a rented GPU node.",
            "A frozen CPU encoder, PostgreSQL with pgvector, and a checked sentence.",
        ),
        (
            "Nameplate power",
            "A DGX H100-class server is specified at about 10.2 kW maximum. An H100 SXM is a 700 W part.",
            "No GPU is attached to this path. The process refuses to start if CUDA is already visible.",
        ),
        (
            "When the documents are silent",
            "A fluent sentence is still possible.",
            "Recognized question forms quote a stored sentence, or they say the corpus does not settle it.",
        ),
        (
            "A measured lookup",
            "Often hundreds of milliseconds to the first token, and sometimes seconds. Not one universal number.",
            "37.6 ms median and 58.9 ms p95 on one warmed workstation run. Encoder startup was 11.5 s and is paid once.",
        ),
    ]
    data = [header]
    for label, left, right in rows_raw:
        data.append(
            [
                Paragraph(label, s["tdstrong"]),
                Paragraph(left, s["td"]),
                Paragraph(right, s["td"]),
            ]
        )
    col = CONTENT_W
    widths = [col * 0.20, col * 0.40, col * 0.40]
    table = Table(data, colWidths=widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Calibri-Bold"),
        ("BACKGROUND", (0, 1), (-1, 1), ROW_ALT),
        ("BACKGROUND", (0, 2), (-1, 2), white),
        ("BACKGROUND", (0, 3), (-1, 3), ROW_ALT),
        ("BACKGROUND", (0, 4), (-1, 4), white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, RULE),
        ("BOX", (0, 0), (-1, -1), 0.6, NAVY),
        ("LINEAFTER", (0, 0), (0, -1), 0.3, RULE),
        ("LINEAFTER", (1, 0), (1, -1), 0.3, RULE),
    ]
    table.setStyle(TableStyle(style_cmds))
    return table


def draw_page(canvas, doc, first: bool) -> None:
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(LEFT, 0.46 * inch, PAGE_W - RIGHT, 0.46 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont("Calibri", 8)
    canvas.drawString(LEFT, 0.30 * inch, "Amin Parva  ·  cpu-llm")
    canvas.drawRightString(PAGE_W - RIGHT, 0.30 * inch, f"{doc.page}")
    if not first:
        canvas.setFillColor(NAVY)
        canvas.setFont("Calibri", 8)
        canvas.drawString(LEFT, PAGE_H - 0.40 * inch, "Stop dropping every prompt onto GPUs")
        canvas.setStrokeColor(AMBER)
        canvas.setLineWidth(1.4)
        canvas.line(LEFT, PAGE_H - 0.48 * inch, LEFT + 0.72 * inch, PAGE_H - 0.48 * inch)
    canvas.restoreState()


def build_story(s: dict) -> list:
    cost = save_png(load_figure(COST), "_fig_cost.png")
    pipeline = save_png(prepare_pipeline(), "_fig_pipeline.png")
    router = save_png(load_figure(ROUTER), "_fig_router.png")
    link = (
        '<link href="https://pypi.org/project/cpu-llm/" color="#C47B2B"><u>cpu-llm</u></link>'
    )
    source = (
        '<link href="https://github.com/insightitsGit/cpullm" color="#C47B2B"><u>source</u></link>'
    )
    story: list = [
        Paragraph("AN ESSAY FOR BUILDERS", s["kicker"]),
        Paragraph("Why We Need to Stop Dropping Every Prompt onto GPUs", s["title"]),
        Paragraph(
            "Most enterprise prompts are lookups. The expensive mistake is sending all of them through a generative model.",
            s["dek"],
        ),
        Paragraph("Amin Parva&nbsp;&nbsp;·&nbsp;&nbsp;20 October 2026&nbsp;&nbsp;·&nbsp;&nbsp;cpu-llm 1.9.0", s["byline"]),
        HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=4, spaceAfter=10),
        figure(
            cost,
            "1",
            "A cluster kept hot for every prompt has a physical appetite: electricity, cooling, and a machine that stays on for questions a lookup could have answered.",
            s,
        ),
        Paragraph(
            "In 2024 the International Energy Agency compared a typical Google search, about 0.3 watt-hours, with a ChatGPT request, about 2.9 watt-hours. That comparison is the source of the familiar “ten times” line. Later measurements put a short, modern query much closer to a search, and a long or reasoning-heavy query well above it. The waste is not the hard question. The waste is sending a date lookup, an invoice check, or a record filter through that same machine.",
            s["body"],
        ),
        Paragraph(
            "Software is in an AI fever. The default design for a feature has become a multi-billion-parameter model and a GPU cluster.",
            s["body"],
        ),
        bullets(
            [
                "Need a date in a PDF? Call a frontier model.",
                "Need to know whether an invoice total matches? Send it to a GPU.",
                "Need to filter records the database already holds? Prompt a 70-billion-parameter model.",
            ],
            s,
        ),
        Paragraph(
            "That default raises power and cloud cost, and it adds a wait that a lookup never needed. Most of those prompts do not need a generative model.",
            s["body"],
        ),
        Paragraph("The physical cost", s["h2"]),
        Paragraph(
            "Treat the published hardware numbers as nameplate limits, not as a measurement of every query.",
            s["body"],
        ),
        bullets(
            [
                "<b>Power.</b> An NVIDIA DGX H100 system is specified at about 10.2 kW maximum. That is an eight-GPU server: each H100 SXM is a 700 W part, and the rest of the node is CPUs, memory, networking, and cooling. At that ceiling it is in the range of several home air conditioners left on together. Real workloads often sit below the nameplate. The machine is still in that class of power while it waits.",
                "<b>Water.</b> Evaporative cooling is the second bill. NVIDIA has put conventional cooling-tower use near 2.6 million gallons per megawatt per year, and has described newer dry-cooler designs that cut evaporative water to nearly nothing. The design question is why a date-in-a-PDF query is on a machine that needs either system.",
                "<b>Latency.</b> A hosted generative call often spends hundreds of milliseconds, and sometimes seconds, before the first token. On a warmed cpu-llm process, a small diagnostic run measured a 37.6 ms median and a 58.9 ms p95, on an Intel Core Ultra 9 275HX, with encoding included and with startup excluded. Cold start is a different number: loading the encoder took 11.5 seconds in an earlier run. Load it once and reuse the process.",
            ],
            s,
        ),
        Paragraph("cpu-llm is not a small LLM", s["h2"]),
        Paragraph(
            f"{link} ({source}) is an embeddable Python library for question answering over documents you already hold. Version 1.9.0 runs on Python 3.11 or newer and a 64-bit CPU, with PostgreSQL and pgvector. It does not call OpenAI, Gemini, or Anthropic, and it is built to run with no GPU.",
            s["body"],
        ),
        Paragraph(
            "Despite the name, it does not sample the next token. A frozen all-mpnet-base-v2 encoder runs on CPU. Each paragraph is stored as a 1024-dimensional VectorPrism vector. Search uses the dense slice of that vector, then re-ranks. For question forms the library recognizes — definitions, attributes, locations, weights, and simple event questions such as color, place, and who did what — the reply is a checked sentence, a source quotation, or an explicit non-answer. If the retrieved passages conflict, that conflict is the result.",
            s["body"],
        ),
        figure(
            pipeline,
            "2",
            "Files are encoded on CPU, stored in PostgreSQL with pgvector, and answered from a stored sentence — or the library says the documents do not contain the answer. The GPU is not on this path.",
            s,
        ),
        Paragraph(
            "Scanned pages are out of scope: there is no OCR pipeline. The grammars are narrow English forms. Open chat, translation, and code generation are outside what the library demonstrates.",
            s["body"],
        ),
        Paragraph("What that is good for", s["h2"]),
        bullets(
            [
                "<b>No GPU on the lookup path.</b> The process is CPU-only by construction, including a guard that will not start if CUDA is already visible.",
                "<b>A gap stays a gap.</b> Recognized questions abstain or surface a conflict instead of inventing a fact. That is the contract for those forms. It is not a universal proof that every string the process can emit is true. Evaluate it on your own documents. Creative mode can vary between runs, and a local FLAN-T5 checkpoint, if one is installed, can be used on the rule path.",
                "<b>A quote you can open.</b> Paragraphs live in your database, under a tenant namespace you choose. A local authenticated HTTP entry exists for callers that are not already trusted code.",
                "<b>A few jobs that are not chat.</b> Supported arithmetic is evaluated as arithmetic. Policy-style questions can return a bounded verdict such as YES, NO, UNKNOWN, or CONTESTED. Supplied-field finance checks run on the fields you pass in.",
            ],
            s,
        ),
        Paragraph(
            "Accepted files are plain text, Markdown, HTML, PDF, DOCX, CSV, XLSX, XLSM, and EPUB. Readers extract text that is already in the file.",
            s["body"],
        ),
        Paragraph("The migration that actually happens", s["h2"]),
        Paragraph(
            "Teams tend to walk the same three steps.",
            s["body"],
        ),
        bullets(
            [
                "<b>Public model APIs.</b> Fast to try. At volume, the bill tracks tokens, and compliance teams start asking where the documents went.",
                "<b>Self-hosted GPUs.</b> Open models on your own cluster, or on a rented GPU node, keep the data closer and can lower the per-token price. The new cost is a 700 W-class accelerator, often an entire 10 kW-class server, held ready for prompts that never needed it.",
                "<b>A router in front of the model.</b> A fast CPU classifier decides what the prompt actually is. Lookups, exact checks, and recognized document questions stay on CPU. Compact models handle light parsing. The GPU cluster is reserved for work that needs open-ended reasoning.",
            ],
            s,
        ),
        Paragraph(
            "Call that a hyper-agentic layout if you want a name: agents where an agent is warranted, and deterministic automation everywhere else. Inside cpu-llm, the same idea shows up as a decision to answer, ask for a missing fact, refuse, or escalate, before anything is shown to the user.",
            s["body"],
        ),
        figure(
            router,
            "3",
            "One front door, three lanes. Read it left to right. Routine documents stay on the CPU lookup. A thinner lane uses a small model. The GPU is the remaining lane, drawn in amber.",
            s,
        ),
        Paragraph(
            "A planning split many teams can start from, and then measure on their own traffic:",
            s["body"],
        ),
        bullets(
            [
                "<b>Routine lookups</b> go to SQL, pgvector, or cpu-llm. Warmed latency is on the order of tens of milliseconds. No GPU.",
                "<b>Light parsing</b> goes to a small model on CPU or an NPU.",
                "<b>Deep reasoning</b> is the traffic that should wake the GPU cluster.",
            ],
            s,
        ),
        Paragraph(
            "Do not adopt 80/15/5, or any other ratio, as an industry fact. Log a week of production prompts and set the split from that log.",
            s["body"],
        ),
        Paragraph("Side by side", s["h2"]),
        Paragraph(
            "The cells below are either published hardware specifications or measurements from this project. They are not a price quote and not a service-level agreement.",
            s["body"],
        ),
        comparison(s),
        Spacer(1, 10),
        Paragraph("What to take from this", s["h2"]),
        bullets(
            [
                "<b>Stop sending simple prompts through a generative model.</b> If the database, a vector index, or a rule can answer, that is the system of record.",
                "<b>cpu-llm is one demonstration that document questions can run on a CPU:</b> retrieve a paragraph, rebuild only what that paragraph supports, or say the corpus does not settle it.",
                "<b>Efficiency is a routing problem.</b> A larger GPU pool does not fix a front door that treats every prompt as a reasoning task.",
            ],
            s,
        ),
        Paragraph(
            "Pair a deterministic CPU path with a generative model and the model gets a smaller, more defensible job. The GPU is still there. It is no longer the default.",
            s["body"],
        ),
        Paragraph("Sources", s["h2"]),
        Paragraph(
            'International Energy Agency, <link href="https://www.iea.org/reports/electricity-2024" color="#0B1F33"><u>Electricity 2024</u></link>. The widely cited comparison of about 0.3 Wh for a search and about 2.9 Wh for a ChatGPT request.',
            s["source"],
        ),
        Paragraph(
            'Epoch AI, <link href="https://epoch.ai/gradient-updates/how-much-energy-does-chatgpt-use" color="#0B1F33"><u>How much energy does ChatGPT use?</u></link> A later estimate of about 0.3 Wh for a typical short GPT-4o query, and a much higher figure for long inputs.',
            s["source"],
        ),
        Paragraph(
            'NVIDIA, <link href="https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/nvidia-dgx-h100-datasheet.pdf" color="#0B1F33"><u>DGX H100 datasheet</u></link>. System power about 10.2 kW maximum.',
            s["source"],
        ),
        Paragraph(
            'NVIDIA, <link href="https://blogs.nvidia.com/blog/liquid-cooling-ai-factories/" color="#0B1F33"><u>liquid cooling for AI factories</u></link>. About 2.6 million gallons per megawatt per year for cooling-tower designs, and dry-cooler designs aimed at near-zero evaporative use.',
            s["source"],
        ),
        Paragraph(
            'cpu-llm latency and scope: warmed in-process median 37.6 ms and p95 58.9 ms at commit 1183b77, Intel Core Ultra 9 275HX; encoder startup of 11.5 s from the 18 October 2026 question-time note. Package and repository: <link href="https://pypi.org/project/cpu-llm/" color="#0B1F33"><u>pypi.org/project/cpu-llm</u></link> and <link href="https://github.com/insightitsGit/cpullm" color="#0B1F33"><u>github.com/insightitsGit/cpullm</u></link>. These figures describe those runs. They are not an API service level. Apache-2.0.',
            s["source"],
        ),
        Paragraph(
            "The 80/15/5 split sometimes quoted for this kind of router is a planning sketch. It is not a measurement from cpu-llm or from a cited study.",
            s["footer_note"],
        ),
    ]
    flat: list = []
    for item in story:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)
    for item in flat:
        if isinstance(item, Paragraph) and item.getPlainText() in {
            "Side by side",
            "The cells below are either published hardware specifications or measurements from this project. They are not a price quote and not a service-level agreement.",
        }:
            item.keepWithNext = True
    return flat


def main() -> None:
    register_fonts()
    s = styles()
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=letter,
        title="Why We Need to Stop Dropping Every Prompt onto GPUs",
        author="Amin Parva",
        subject="A cpu-llm essay on routing routine prompts away from GPUs",
        creator="cpu-llm article builder",
    )
    frame_first = Frame(
        LEFT,
        BOTTOM,
        CONTENT_W,
        PAGE_H - TOP - BOTTOM,
        id="first",
        showBoundary=0,
    )
    frame_later = Frame(
        LEFT,
        BOTTOM,
        CONTENT_W,
        PAGE_H - (0.62 * inch) - BOTTOM,
        id="later",
        showBoundary=0,
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="first", frames=[frame_first], onPage=lambda c, d: draw_page(c, d, True)),
            PageTemplate(id="later", frames=[frame_later], onPage=lambda c, d: draw_page(c, d, False)),
        ]
    )
    story = build_story(s)
    story.append(NextPageTemplate("later"))
    # Switch after the first page naturally: BaseDocTemplate uses the first
    # template until nextPageTemplate is consumed. Put the switch at the start
    # so page 2 onward uses the later template. A NextPageTemplate at index 0
    # applies to the following page break, not the current page.
    story.insert(0, NextPageTemplate("later"))
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    main()
