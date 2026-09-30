from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output" / "pdf" / "PROFESSOR_MEETING_FEEDBACK.pdf"
FONT_PATH = Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf")
FONT_NAME = "AppleGothic"
pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2C6EAA")
PALE_BLUE = colors.HexColor("#EAF3FA")
PALE_GRAY = colors.HexColor("#F3F5F7")
MID_GRAY = colors.HexColor("#697586")
TEXT = colors.HexColor("#25313C")
GREEN = colors.HexColor("#2D7A55")
ORANGE = colors.HexColor("#B86416")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="TitleKR", fontName=FONT_NAME, fontSize=22, leading=29,
    textColor=NAVY, alignment=TA_LEFT, spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="SubtitleKR", fontName=FONT_NAME, fontSize=10.5, leading=16,
    textColor=MID_GRAY, spaceAfter=15,
))
styles.add(ParagraphStyle(
    name="H1KR", fontName=FONT_NAME, fontSize=14, leading=19,
    textColor=NAVY, spaceBefore=13, spaceAfter=7,
))
styles.add(ParagraphStyle(
    name="H2KR", fontName=FONT_NAME, fontSize=10.5, leading=15,
    textColor=BLUE, spaceBefore=8, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="BodyKR", fontName=FONT_NAME, fontSize=8.9, leading=14,
    textColor=TEXT, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="SmallKR", fontName=FONT_NAME, fontSize=7.5, leading=11,
    textColor=MID_GRAY, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="BulletKR", fontName=FONT_NAME, fontSize=8.8, leading=13.5,
    leftIndent=12, firstLineIndent=-8, textColor=TEXT, spaceAfter=3,
))
styles.add(ParagraphStyle(
    name="CalloutKR", fontName=FONT_NAME, fontSize=10, leading=15,
    textColor=NAVY, spaceAfter=0,
))
styles.add(ParagraphStyle(
    name="TableKR", fontName=FONT_NAME, fontSize=7.0, leading=9.5,
    textColor=TEXT,
))
styles.add(ParagraphStyle(
    name="TableHeadKR", fontName=FONT_NAME, fontSize=7.1, leading=9.5,
    textColor=colors.white,
))


def p(text, style="BodyKR"):
    return Paragraph(text, styles[style])


def bullet(text):
    return p("• " + text, "BulletKR")


def table_cell(text, head=False):
    return p(escape(str(text)), "TableHeadKR" if head else "TableKR")


def make_table(rows, widths, header=True, row_heights=None):
    data = []
    for r, row in enumerate(rows):
        data.append([table_cell(v, head=(header and r == 0)) for v in row])
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0,
                  rowHeights=row_heights)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5DDE5")),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY),
        ])
        if len(rows) > 1:
            for i in range(1, len(rows)):
                if i % 2 == 0:
                    commands.append(("BACKGROUND", (0, i), (-1, i), PALE_GRAY))
    table.setStyle(TableStyle(commands))
    return table


def footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D5DDE5"))
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFont(FONT_NAME, 7.2)
    canvas.setFillColor(MID_GRAY)
    canvas.drawString(18 * mm, 9.5 * mm, "자세 피드백 로봇 | 교수님 미팅용")
    canvas.drawRightString(width - 18 * mm, 9.5 * mm,
                           f"{doc.page}")
    canvas.restoreState()


class MeetingDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, pagesize=A4, **kwargs)
        frame = Frame(self.leftMargin, self.bottomMargin,
                      self.width, self.height, id="normal")
        self.addPageTemplates([PageTemplate(id="main", frames=frame,
                                            onPage=footer)])


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = MeetingDocTemplate(
        str(OUTPUT), leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=22 * mm,
        title="자세 피드백 로봇 파일럿 설문 분석 및 교수님 미팅 논의안",
        author="NOTIFYI MIRRORING",
    )
    story = []

    story.append(p("자세 피드백 로봇", "TitleKR"))
    story.append(p("파일럿 설문 분석 및 교수님 미팅 논의안", "SubtitleKR"))
    callout = Table([[p(
        "<b>핵심 결론</b><br/>"
        "로봇의 움직임은 잘 보이고 자세 교정 신호로도 이해되었다. "
        "다음 단계에서는 짧은 자세 변화와 자연스러운 작업 자세에 대한 오검출을 줄이고, "
        "피드백을 놓친 사용자에게 부담이 적은 추가 반응을 설계해야 한다.",
        "CalloutKR")]], colWidths=[doc.width])
    callout.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(callout)
    story.append(Spacer(1, 7))
    story.append(p("응답 4건 기준. 이 자료는 효과 검증보다 문제 발견과 다음 실험 설계를 위한 논의 자료다.", "SmallKR"))

    story.append(p("1. 이번 설문에서 확인된 핵심", "H1KR"))
    story.append(p(
        "응답 4건을 보면 로봇의 움직임은 대체로 잘 인지되었고, 움직임이 자세 교정 신호라는 점도 전달되었다. "
        "참가자들은 로봇이 잘못된 자세를 포착한다고 느꼈으며, 로봇이 반응한 뒤 자세를 확인하거나 바꾸려는 행동도 나타났다.",
        "BodyKR"))
    story.append(p(
        "반면 짧은 자세 변화나 자연스러운 작업 자세까지 잘못된 자세로 판단할 가능성이 확인되었다. "
        "로봇이 너무 자주 반응하거나, 반응의 의미를 시각적으로 알아차리지 못하는 상황도 있었다. "
        "따라서 다음 단계의 핵심은 필요한 순간에만 확실하게 반응하고, 반응을 놓쳤을 때는 부담이 적은 방식으로 한 번 더 알려주는 것이다.",
        "BodyKR"))

    story.append(p("2. 정량 응답 요약", "H1KR"))
    story.append(p("척도는 1점(전혀 그렇지 않다)부터 5점(매우 그렇다)이다. 평균은 응답이 모두 있는 문항만 4명 기준으로 계산했다.", "BodyKR"))
    rows = [
        ["영역", "문항", "평균", "응답 분포", "해석"],
        ["인지", "로봇이 움직이는 것을 알아차렸다", "4.50", "4점 2명, 5점 2명", "움직임 자체는 잘 보임"],
        ["인지", "집중 중에도 움직임을 알아차렸다", "4.25", "2점 1명, 5점 3명", "집중 중에도 대체로 인지"],
        ["이해", "움직임이 자세 교정 의미임을 알았다", "4.50", "4점 2명, 5점 2명", "의미 전달은 명확함"],
        ["행동", "움직인 후 자세를 바꾸었다", "4.00", "3점 1명, 4점 2명, 5점 1명", "교정 행동으로 이어짐"],
        ["행동", "움직인 후 내 자세를 확인했다", "4.25", "4점 3명, 5점 1명", "자기 자세 확인을 유도"],
        ["행동", "바른 자세를 유지하려고 했다", "4.25", "3점 1명, 4점 1명, 5점 2명", "유지 의도도 확인됨"],
        ["빈도", "로봇이 자주 움직인다고 느꼈다", "3.25", "2점 2명, 4점 1명, 5점 1명", "빈도에 대한 의견이 갈림"],
        ["민감도", "잠깐 흐트러져도 움직였다", "4.25", "3점 1명, 4점 1명, 5점 2명", "짧은 이탈에도 민감하게 반응"],
        ["방해감", "작업 집중을 방해했다", "2.75", "2점 2명, 3점 1명, 4점 1명", "방해감은 낮지만 제거되지는 않음"],
        ["거슬림", "로봇 움직임이 거슬렸다", "-", "1명 응답: 2점", "표본 부족으로 판단 보류"],
        ["수용성", "바른 자세라고 생각했는데 반응했다", "-", "1명 응답: 4점", "오검출 가능성 확인"],
        ["사용 의향", "실제 작업 중에도 사용하고 싶다", "-", "1명 응답: 4점", "긍정 신호이나 추가 측정 필요"],
    ]
    story.append(make_table(rows, [35, 175, 35, 145, 120]))
    story.append(Spacer(1, 5))
    story.append(p("해석상 주의: 전체 응답은 4건이며 마지막 3개 문항은 1명만 응답했다. 따라서 해당 문항은 평균 비교가 아니라 후속 질문을 정하는 참고 신호로만 사용한다.", "SmallKR"))

    story.append(p("3. 자유응답에서 반복된 의견", "H1KR"))
    story.append(p("확인된 강점", "H2KR"))
    for item in [
        "앞으로 구부정한 자세를 로봇이 따라 하는 반응이 인상적이었다.",
        "다양한 잘못된 자세를 생각보다 잘 잡아냈다.",
        "자세가 무너지는 순간을 알려줘 다시 교정할 수 있었다.",
        "바른 자세로 돌아왔을 때 반응이 빨라 교정한 보람을 느꼈다.",
    ]:
        story.append(bullet(item))
    story.append(p("개선이 필요한 문제", "H2KR"))
    for item in [
        "좌우로 삐뚤어진 자세는 반응하지 않는다.",
        "짧은 자세 변화나 자연스러운 고개 숙임까지 잘못된 자세로 판단할 수 있다.",
        "한 번 반응한 뒤 자세를 계속 유지해도 후속 반응이 없다.",
        "이어폰을 사용하거나 화면에 집중하면 로봇의 움직임을 놓칠 수 있다.",
        "피드백은 분명해야 하지만 작업 흐름을 끊으면 안 된다.",
        "노트북 카메라는 노트북을 닫으면 사용할 수 없으므로 외부 USB 카메라가 필요하다.",
    ]:
        story.append(bullet(item))

    story.append(p("4. 교수님과 논의할 핵심 연구 질문", "H1KR"))
    questions = [
        ("언제 반응해야 하는가?", "잘못된 자세가 몇 초 이상 지속되어야 하는가? 자연스러운 작업 자세와 교정이 필요한 자세를 어떤 기준으로 구분할 것인가?"),
        ("한 번 반응한 뒤에는 어떻게 할 것인가?", "1차 반응을 놓쳤을 때 2차 반응을 언제 제공할 것인가? 반복 반응은 더 강하게 할 것인가, 다른 방식으로 바꿀 것인가?"),
        ("어떤 피드백이 작업을 방해하지 않는가?", "로봇 움직임만으로 충분한가? 시각 피드백을 놓치는 경우 LED, 짧은 소리, 화면 표시 중 무엇을 추가할 것인가?"),
        ("무엇을 감지 범위에 포함할 것인가?", "앞뒤 굽힘, 좌우 기울기, 엉덩이가 앞으로 빠지는 자세를 어떤 우선순위로 추가할 것인가?"),
    ]
    q_rows = [["논의 주제", "교수님께 확인할 내용"]] + [[a, b] for a, b in questions]
    story.append(make_table(q_rows, [150, 360]))

    story.append(p("5. 다음 실험에서 제안하는 최소 변경", "H1KR"))
    for item in [
        "나쁜 자세가 일정 시간 유지될 때만 1차 반응하도록 지속 시간 조건을 둔다.",
        "good 판정이 한 프레임만 잡혀도 즉시 복귀하지 않도록 정상 자세 확인 시간을 둔다.",
        "1차 반응 뒤에도 나쁜 자세가 지속되면 한 번만 추가 반응한다.",
        "좌우 기울기 판정을 별도 축으로 기록해 기존 앞굽힘 판정과 비교한다.",
    ]:
        story.append(bullet(item))
    cond_rows = [
        ["조건", "나쁜 자세 지속", "추가 반응", "목적"],
        ["A. 현재 방식", "3초", "없음", "기준선 확보"],
        ["B. 지속시간 강화", "5초", "없음", "오검출 감소 확인"],
        ["C. 2단계 피드백", "3초", "10~15초 후 1회", "놓친 피드백 보완"],
        ["D. 작업 적합형", "5초", "15초 후 다른 방식 1회", "방해감과 효과 균형 확인"],
    ]
    story.append(make_table(cond_rows, [105, 115, 140, 150]))

    story.append(p("6. 다음 실험 운영안", "H1KR"))
    for item in [
        "참가자가 실제로 하던 작업을 직접 가져오게 하여 자연스러운 작업 자세를 관찰한다.",
        "한 조건당 10~15분을 권장하고, 5분 조건은 탐색용으로만 사용한다.",
        "참가자마다 카메라 위치와 의자 위치를 고정한다.",
        "외부 USB 카메라를 사용하고, 로봇 상단에 장착할 경우 시작 시 정면을 향하도록 맞춘다.",
        "반응 횟수, 오검출 횟수, 반응을 놓친 횟수, 자세 교정까지 걸린 시간, 작업 중단 여부를 기록한다.",
        "설문은 인지, 의미 이해, 자세 변화, 작업 방해를 행동 중심으로 묻는다.",
    ]:
        story.append(bullet(item))

    story.append(p("7. 이번 미팅에서 결정하면 좋은 사항", "H1KR"))
    for i, item in enumerate([
        "다음 버전에서 좌우 기울기 감지를 바로 추가할 것인가?",
        "오검출 감소를 위해 나쁜 자세 지속 시간을 3초에서 5초로 늘릴 것인가?",
        "반응을 놓친 사용자를 위한 2차 피드백을 어떤 방식으로 만들 것인가?",
        "외부 USB 카메라를 최종 실험 장비로 확정할 것인가?",
        "다음 실험은 실제 작업 10~15분 조건으로 진행할 것인가?",
        "1순위 성공 기준을 자세 교정 효과와 작업 방해 최소화 중 어디에 둘 것인가?",
    ], 1):
        story.append(bullet(f"{i}. {item}"))

    story.append(Spacer(1, 6))
    final_box = Table([[p(
        "<b>한 문장 결론</b><br/>"
        "현재 프로토타입은 로봇의 움직임이 보이고 자세 교정 신호로 이해되는 단계까지 가능성을 보였다. "
        "다음 단계에서는 오검출과 과도한 반응을 줄이면서 놓친 사용자에게 한 번 더 전달하는 설계를 검증해야 한다.",
        "CalloutKR")]], colWidths=[doc.width])
    final_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF7F1")),
        ("BOX", (0, 0), (-1, -1), 0.7, GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(final_box)
    story.append(Spacer(1, 8))
    story.append(p(
        '출처: <link href="https://docs.google.com/forms/d/1_hxZl7CBLI056WTIhxe7DMdtkhvtPdQ7QC6Q0AJZIxI/edit#responses" color="#2C6EAA">자세 피드백 방식 체험 설문 응답</link>',
        "SmallKR"))
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
