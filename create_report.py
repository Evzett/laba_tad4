# -*- coding: utf-8 -*-
"""Сборка отчёта по ПР № 4 (оформление по СТУ 7.5–07–2021 СФУ).

Берёт титульный лист из report/title_template_pr4.docx и результаты
analysis.py из outputs/. Запуск: python create_report.py
"""
import csv
import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
FIG = OUT / "figures"
TAB = OUT / "tables"
REPORT = ROOT / "report" / "Отчет_ПР4_Процессная_аналитика.docx"
S = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
DASH = "–"          # короткое тире для подписей по СТУ


def rows(name):
    with (TAB / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(x, d=1):
    return f"{float(x):,.{d}f}".replace(",", " ").replace(".", ",")


def integer(x):
    return f"{int(float(x)):,}".replace(",", " ")


def pct(x, d=1):
    return num(x, d) + " %"


# ------------------------------------------------------------ документ
doc = Document(ROOT / "report" / "title_template_pr4.docx")

# титульный лист: «Преподаватель» по форме СТУ (прил. М), заголовок 16 пт
for t in doc.tables:
    for r in t.rows:
        for c in r.cells:
            for p in c.paragraphs:
                for run in p.runs:
                    if run.text.strip() == "Руководитель":
                        run.text = "Преподаватель"
for p in doc.paragraphs:
    if p.text.startswith("ОТЧЕТ О ПРАКТИЧЕСКОЙ РАБОТЕ"):
        for run in p.runs:
            run.font.size = Pt(16)
            run.bold = True

normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
normal.font.size = Pt(14)

# нумерация страниц: внизу по центру, на титуле не выводится
sec = doc.sections[0]
sec.different_first_page_header_footer = True
for p in sec.footer.paragraphs:
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)


def fmt(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=1.25, spacing=1.5, before=0, after=0):
    pf = p.paragraph_format
    p.alignment = align
    pf.first_line_indent = Cm(indent)
    pf.left_indent = Cm(0)
    pf.line_spacing = spacing
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    return p


def para(text="", **kw):
    p = fmt(doc.add_paragraph(), **kw)
    if text:
        p.add_run(text)
    return p


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def heading(text):
    """заголовок раздела/подраздела: с абзацного отступа, полужирный, без точки"""
    p = para(spacing=1.5, before=12, after=12)
    p.paragraph_format.keep_with_next = True
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.add_run(text).bold = True
    level = 1 if text.split(" ")[0].count(".") else 0
    outline(p, level)
    return p


def outline(p, level):
    """уровень структуры абзаца – по нему Word собирает содержание"""
    el = OxmlElement("w:outlineLvl")
    el.set(qn("w:val"), str(level))
    p._p.get_or_add_pPr().append(el)


def toc():
    """поле TOC; номера страниц проставляет Word при обновлении полей"""
    p = para(indent=0)
    r = p.add_run()
    for tag, attr in (("w:fldChar", "begin"), ("w:instrText", None), ("w:fldChar", "separate")):
        el = OxmlElement(tag)
        if attr:
            el.set(qn("w:fldCharType"), attr)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = r'TOC \o "1-2" \h \z \u'
        r._r.append(el)
    p.add_run("Обновите поле содержания (F9).")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    p.add_run()._r.append(end)


def struct_heading(text):
    """структурный элемент: с новой страницы, по центру, прописными, полужирный"""
    p = para(align=WD_ALIGN_PARAGRAPH.CENTER, indent=0, before=0, after=12)
    p.paragraph_format.page_break_before = True
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.all_caps = True          # прописные – форматированием, в содержании строчные
    if text != "Содержание":
        outline(p, 0)
    return p


def bullets(items):
    for i, t in enumerate(items):
        end = "." if i == len(items) - 1 else ";"
        para(f"- {t}{end}")


fig_no = 0
tab_no = 0


def figure(file, width, caption):
    global fig_no
    fig_no += 1
    p = para(align=WD_ALIGN_PARAGRAPH.CENTER, indent=0, spacing=1.0, before=12, after=6)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(FIG / file), width=Cm(width))
    para(f"Рисунок {fig_no} {DASH} {caption}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=0,
         after=12)
    return fig_no


def next_fig():
    return fig_no + 1


def next_tab():
    return tab_no + 1


def _border(cell, side, val="single", sz=4):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = tcPr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcPr.append(borders)
    el = OxmlElement(f"w:{side}")
    el.set(qn("w:val"), val)
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:color"), "000000")
    borders.append(el)


def table(caption, headers, data, widths, size=12, align_first=WD_ALIGN_PARAGRAPH.LEFT):
    global tab_no
    tab_no += 1
    cp = para(f"Таблица {tab_no} {DASH} {caption}", align=WD_ALIGN_PARAGRAPH.LEFT, indent=0,
              before=6, after=0)
    cp.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, row in enumerate([headers] + list(data)):
        cells = t.rows[0].cells if i == 0 else t.add_row().cells
        trPr = t.rows[i]._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if i == 0:
            h = OxmlElement("w:tblHeader")
            h.set(qn("w:val"), "true")
            trPr.append(h)
        for j, (cell, value) in enumerate(zip(cells, row)):
            cell.width = Cm(widths[j])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            fmt(p, align=WD_ALIGN_PARAGRAPH.CENTER if (i == 0 or j > 0) else align_first,
                indent=0, spacing=1.0)
            r = p.add_run(str(value))
            r.font.size = Pt(size)
            r.bold = i == 0
            if i == 0:
                _border(cell, "bottom", "double", 6)   # шапка отделена двойной линией
            if i < len(data):
                p.paragraph_format.keep_with_next = True
    after = para(spacing=1.0)
    after.paragraph_format.space_after = Pt(6)
    return tab_no


# =================================================================== текст
struct_heading("Содержание")
toc()
page_break()

heading("1 Цель и задачи работы")
para("Цель работы: знакомство с технологиями Process mining, формирование навыков построения "
     "графов бизнес-процессов и их анализа.")
para("Для достижения цели решены следующие задачи:")
bullets([
    "выполнить предварительную обработку журнала событий",
    "построить граф выбранного бизнес-процесса и модель процесса",
    "провести анализ графа на наличие узких мест, циклов, отклонений и оптимальных путей, "
    "определить и проанализировать экземпляры процесса, выполнение которых длится намного "
    "дольше остальных",
    "предложить варианты оптимизации бизнес-процесса",
])

heading("2 Исходные данные и инструменты")
para("Для анализа выбран открытый журнал событий Sepsis Cases – Event Log из репозитория "
     "4TU.ResearchData [1]. Журнал выгружен из ERP-системы нидерландской больницы и описывает "
     "путь пациентов с подозрением на сепсис: от регистрации в приёмном отделении через "
     "лабораторные анализы, лечение и госпитализацию до выписки и, возможно, повторного "
     f"обращения. Экземпляр процесса (case) – один пациент. Журнал содержит {integer(S['raw_events'])} "
     f"событий, {integer(S['raw_cases'])} экземпляров и {S['activities']} видов действий; у каждого "
     f"события {S['raw_columns']} атрибутов. По описанию набора данных календарные даты "
     "рандомизированы, но интервалы между событиями внутри экземпляра сохранены, поэтому "
     "временной анализ корректен.")
para(f"Действия процесса и их смысл приведены в таблице {next_tab()}.")
ACTS = [
    ("ER Registration", "Регистрация пациента в приёмном отделении"),
    ("ER Triage", "Первичная сортировка (оценка срочности)"),
    ("ER Sepsis Triage", "Сортировка по критериям сепсиса"),
    ("CRP, Leucocytes, LacticAcid", "Лабораторные анализы: С-реактивный белок, лейкоциты, лактат"),
    ("IV Liquid", "Внутривенная инфузия жидкости"),
    ("IV Antibiotics", "Внутривенное введение антибиотиков"),
    ("Admission NC", "Госпитализация в обычное отделение (перевод между отделениями)"),
    ("Admission IC", "Госпитализация в отделение интенсивной терапии"),
    ("Release A–E", "Выписка (A – основной тип; B–E – другие исходы)"),
    ("Return ER", "Повторное обращение в приёмное отделение после выписки"),
]
table("Действия бизнес-процесса", ["Действие", "Содержание"], ACTS, [5.5, 11.0])
para("Программа написана на языке Python 3. Использованы библиотеки: PM4Py [2] – чтение XES, "
     "построение графа непосредственного следования (DFG), алгоритм Inductive Miner, сети Петри, "
     "BPMN и проверка соответствия методом воспроизведения маркеров; pandas – предварительная "
     "обработка и расчёт показателей; matplotlib – диаграммы; Graphviz – визуализация графов. "
     "Текст программы приведён в приложении А.")

heading("3 Предварительная обработка данных")
para("Предварительная обработка включала следующие шаги:")
bullets([
    "из 32 атрибутов оставлены идентификатор экземпляра (case:concept:name), действие "
    "(concept:name), время (time:timestamp) и группа исполнителей (org:group); время приведено "
    "к типу datetime в UTC",
    f"проверены пропуски в ключевых полях – {S['missing_key_values']}; удалены полные дубликаты "
    f"событий (тот же экземпляр, действие и время) – {S['duplicates']}",
    "события упорядочены по времени внутри экземпляра устойчивой сортировкой: при равном "
    f"времени сохранён порядок файла (таких соседних пар {integer(S['equal_timestamp_pairs'])}, "
    "в основном пакетная регистрация анализов CRP и Leucocytes)",
    f"проверена полнота экземпляров: {S['cases_not_start_registration']} экземпляров начинаются "
    f"не с регистрации, {S['cases_without_release']} не содержат выписки (журнал обрезан "
    f"на этапе приёмного отделения); для построения модели оставлено {S['complete_cases']} "
    "полных экземпляров",
    "выделен эпизод госпитализации – события от регистрации до первой выписки включительно; "
    "повторное обращение Return ER (в среднем через полтора месяца) анализируется отдельно, "
    "иначе оно искажает длительность лечения",
])
dall, dst = S["duration_all_days"], S["duration_stay_days"]
para(f"Влияние выделения эпизода видно по длительности: по всему журналу медиана "
     f"{num(dall['50%'])} сут, среднее {num(dall['mean'])} сут, максимум {num(dall['max'])} сут "
     f"(в длительность попадает период между выпиской и возвращением); для эпизода "
     f"госпитализации медиана {num(dst['50%'])} сут, среднее {num(dst['mean'])} сут, 95-й "
     f"перцентиль {num(dst['95%'])} сут. Сводные показатели приведены в таблице {next_tab()}.")
table("Характеристики журнала событий", ["Показатель", "Значение"], [
    ("Событий / экземпляров (исходно)", f"{integer(S['raw_events'])} / {integer(S['raw_cases'])}"),
    ("Видов действий", S["activities"]),
    ("Полных экземпляров (эпизодов госпитализации)", S["complete_cases"]),
    ("Вариантов (уникальных трасс) во всём журнале", f"{S['variants_all']} "
     f"(из них единичных {S['variants_all_single']})"),
    ("Доля самого частого варианта", pct(S["top_variant_share_all"], 2)),
    ("Медиана длительности эпизода, сут", num(dst["50%"], 2)),
    ("Квартили Q1 / Q3 эпизода, сут", f"{num(dst['25%'], 2)} / {num(dst['75%'], 2)}"),
    ("Максимальная длительность эпизода, сут", num(dst["max"], 2)),
], [11.0, 5.5])
para(f"Журнал очень вариативен: {S['variants_all']} вариантов на {S['raw_cases']} экземпляров, "
     "самый частый вариант покрывает лишь "
     f"{pct(S['top_variant_share_all'], 2)} и обрывается на сортировке. Причина – лабораторные "
     "анализы повторяются и регистрируются в разном порядке. Это типичная «спагетти»-структура, "
     "поэтому для поиска маршрутов далее используется агрегирование (раздел 5.4).")

heading("4 Построение графов бизнес-процесса")
heading("4.1 Граф непосредственного следования")
para(f"Граф непосредственного следования (DFG) построен функцией pm4py.discover_dfg по всему "
     f"журналу: {S['dfg_edges_total']} дуг. Для читаемости на рисунке {next_fig()} оставлены дуги с "
     f"частотой не менее 25 ({S['dfg_edges_shown']} дуг). Число в узле – частота действия, "
     "число на дуге – сколько раз одно действие непосредственно следовало за другим.")
figure("dfg_frequency.png", 15.0, "Граф непосредственного следования (частоты переходов)")
para("Основной поток виден по толщине дуг: ER Registration → ER Triage (971) → ER Sepsis Triage "
     "(905), далее блок лабораторных анализов с плотными взаимными переходами CRP ⇄ Leucocytes "
     "(1 444 и 1 778), лечение IV Liquid → IV Antibiotics (501) → Admission NC (489) и выписка "
     "Release A (671). После выписки 276 пациентов вернулись (Release A → Return ER). Петли "
     "на узлах Leucocytes, CRP, LacticAcid и Admission NC – повторные анализы и переводы.")
para(f"Граф производительности (рисунок {next_fig()}) построен функцией "
     "pm4py.discover_performance_dfg: на дугах указана медиана времени перехода.")
figure("dfg_performance.png", 15.0, "Граф производительности (медиана времени перехода)")
para("Переходы в приёмном отделении занимают минуты, а наибольшее время приходится на дуги "
     "внутри стационара: повторные анализы (CRP → CRP – около 2 сут, Leucocytes → Leucocytes – "
     "1 сут), переходы от последнего анализа к выписке и Admission NC → Release A (около 2,8 сут), "
     "а также Release A → Return ER (около 47 сут).")

heading("4.2 Модель процесса: сеть Петри и BPMN")
para(f"Модель процесса построена алгоритмом Inductive Miner с фильтрацией шума (IMf, порог 0,2) "
     f"по {S['complete_cases']} эпизодам госпитализации. Алгоритм рекурсивно разбивает журнал "
     "разрезами (последовательность, исключающий выбор, параллельность, цикл) и строит дерево "
     "процесса, которое затем преобразуется в сеть Петри (рисунок "
     f"{next_fig()}) и BPMN-диаграмму (рисунок {next_fig() + 1}). Полученное дерево процесса:")
para(S["process_tree"].replace("'", ""), align=WD_ALIGN_PARAGRAPH.LEFT, indent=0, spacing=1.0)
figure("petri_net.png", 13.0, "Сеть Петри (Inductive Miner, порог шума 0,2)")
para(f"Сеть содержит {S['petri_places']} позиций и {S['petri_transitions']} переходов, из них "
     f"{S['petri_silent']} невидимых (τ, чёрные прямоугольники) – они реализуют пропуски и "
     "повторения. Модель читается так: после регистрации параллельно выполняются сортировки, "
     "анализы (каждый может повторяться), лечение (ER Sepsis Triage → IV Antibiotics, "
     "необязательная IV Liquid) и госпитализация (с необязательным переводом в Admission IC), "
     "после чего следует один из пяти типов выписки.")
figure("bpmn.png", 13.0, "Модель процесса в нотации BPMN")
para("На BPMN-диаграмме ромб «+» – параллельный шлюз (AND), «X» – исключающий шлюз (XOR); "
     "обратные дуги между парами XOR-шлюзов задают повторение действия.")

heading("4.3 Проверка соответствия модели и журнала")
para("Качество модели оценено методом воспроизведения маркеров (token-based replay): трасса "
     "проигрывается на сети Петри, подсчитываются недостающие и оставшиеся маркеры. Пригодность "
     "(fitness) показывает, насколько модель воспроизводит журнал, точность (precision) – "
     f"насколько мало лишнего поведения она допускает. Результаты приведены в таблице {next_tab()}.")
table("Метрики соответствия моделей", ["Модель", "Fitness", "Precision", "Доля полностью "
      "соответствующих трасс"], [
    ("Inductive Miner, порог 0 (без фильтрации)", num(S["fitness_im0"], 3), num(S["precision_im0"], 3),
     "100 %"),
    ("Inductive Miner, порог 0,2 (итоговая)", num(S["fitness"], 3), num(S["precision"], 3),
     pct(S["fitting_traces_%"])),
], [7.5, 2.2, 2.4, 4.4])
para("Модель без фильтрации воспроизводит все трассы, но её точность мала: она разрешает почти "
     "любой порядок действий («цветочная» модель). Фильтрация шума повышает precision в "
     f"{num(S['precision'] / S['precision_im0'], 1)} раза при снижении fitness всего до "
     f"{num(S['fitness'], 3)} – это компромисс между недообучением и переобучением. "
     f"{S['nonfit_cases']} эпизодов не соответствуют итоговой модели; это отклонения, "
     "рассмотренные в разделе 5.3.")

heading("5 Анализ бизнес-процесса")
heading("5.1 Узкие места")
bm = rows("bottlenecks_by_median.csv")
para("Узкие места определялись по медиане времени перехода (медиана устойчива к выбросам) и по "
     "суммарному времени, которое процесс проводит на дуге. Рассмотрены переходы, встречающиеся "
     f"не менее 30 раз, в пределах эпизода госпитализации (таблица {next_tab()}).")
table("Переходы с наибольшей медианой времени", ["Переход", "Число", "Медиана, ч",
      "90-й перцентиль, ч", "Доля общего времени"], [
    (f"{r['from']} → {r['to']}", integer(r["count"]), num(r["median_h"]), num(r["p90_h"]),
     pct(r["share_time_%"])) for r in bm[:7]], [6.8, 1.8, 2.3, 2.8, 2.8])
para(f"Выявлены следующие узкие места:")
bullets([
    "время пребывания в отделении до выписки: Admission NC → Release A – медиана "
    f"{num(float(bm[0]['median_h']) / 24)} сут; от госпитализации до выписки в целом медиана "
    f"{num(S['admission_to_release_median_days'])} сут, 90-й перцентиль "
    f"{num(S['admission_to_release_p90_days'])} сут",
    "ожидание повторных анализов: CRP → CRP – 48 ч, Leucocytes → Leucocytes – 24 ч; переходы "
    f"между анализами в сумме занимают {pct(S['lab_block_time_share_%'])} всего времени эпизодов – анализы "
    "повторяются по суточному графику, и выписка привязана к их результатам "
    "(CRP → Release A, Leucocytes → Release A – 30–32 ч)",
    "задержка антибиотикотерапии: медиана от ER Sepsis Triage до IV Antibiotics – "
    f"{num(S['antibiotics_median_h'], 2)} ч, норматив «не позднее 1 ч» выполнен лишь в "
    f"{pct(S['antibiotics_within_1h_%'])} случаев, в {pct(S['antibiotics_over_3h_%'])} – "
    "позднее 3 ч (рисунок " + str(next_fig()) + ")",
])
figure("antibiotics_delay.png", 16.0, "Распределение времени от сортировки по сепсису "
       "до введения антибиотиков")
para(f"Для сравнения: регистрация → сортировка по сепсису занимает в медиане "
     f"{num(S['registration_to_triage_median_min'])} мин, регистрация → госпитализация – "
     f"{num(S['registration_to_admission_median_h'])} ч, то есть приёмное отделение не является "
     "узким местом по длительности, но является им по своевременности лечения.")

heading("5.2 Циклы и повторная работа")
rw = rows("rework.csv")
para(f"В графе найдено {S['two_node_cycles']} пар взаимных дуг (двухвершинных циклов A ⇄ B) и "
     f"{integer(S['self_loop_events'])} самопетель (повтор действия подряд). Хотя бы одно действие "
     f"повторяется в {S['cases_with_any_repeat']} экземплярах ({pct(S['cases_with_any_repeat_%'])}). "
     f"Частота повторов по действиям показана на рисунке {next_fig()}.")
figure("rework.png", 16.0, "Число экземпляров с повторным выполнением действия")
bullets([
    f"CRP и Leucocytes повторяются в {pct(rw[0]['share_%'])} и {pct(rw[1]['share_%'])} "
    f"экземпляров, до {rw[0]['max_per_case']} и {rw[1]['max_per_case']} раз за эпизод; самый "
    "плотный цикл графа – CRP ⇄ Leucocytes (1 444 + 1 778 переходов): анализы берутся парой, "
    "порядок их регистрации случаен",
    f"Admission NC повторяется в {pct(rw[2]['share_%'])} экземпляров – переводы между "
    "отделениями",
    f"макроцикл «выписка → повторное обращение»: Return ER у {S['return_er_cases']} из "
    f"{S['complete_cases']} выписанных пациентов ({pct(S['return_er_%'])}), медиана интервала "
    f"{num(S['release_to_return_median_days'])} сут, {pct(S['return_within_30d_%_of_returns'])} "
    "возвратов происходят в течение 30 сут",
])
para(f"Число анализов сильно связано с длительностью (коэффициент Спирмена "
     f"{num(S['corr_days_crp'], 2)} для CRP), рисунок {next_fig()}.")
figure("labs_vs_duration.png", 16.0, "Длительность эпизода в зависимости от числа анализов")

heading("5.3 Отклонения")
dev = rows("deviations.csv")
para("Отклонения выявлены двумя способами: проверкой соответствия модели (раздел 4.3) и "
     f"проверкой бизнес-правил по трассам. Результаты приведены в таблице {next_tab()}.")
table("Отклонения от правил процесса", ["Правило / признак", "Экземпляров", "Доля"],
      [(r["rule"], integer(r["cases"]), pct(r["share_%"])) for r in dev], [10.5, 3.0, 3.0])
para("Нарушений порядка (госпитализация раньше сортировки, антибиотики раньше сортировки по "
     "сепсису, выписка без госпитализации) не обнаружено – регламентная последовательность "
     "соблюдается. Основное отклонение – несвоевременное введение антибиотиков "
     f"({integer(S['deviations']['Антибиотики позднее 1 ч после ER Sepsis Triage'])} экземпляров). "
     "Незавершённые экземпляры – особенность выгрузки, они исключены из построения модели. "
     f"Не соответствующие модели эпизоды имеют медиану {num(S['nonfit_median_days'], 2)} сут "
     f"против {num(S['fit_median_days'], 2)} сут у соответствующих: это в основном редкие "
     "переходы (повторная сортировка, нетипичный порядок), а не затяжные случаи.")

heading("5.4 Оптимальные пути")
rt = rows("routes_top10.csv")
para("Точные варианты почти уникальны, поэтому маршрут пациента агрегирован: лабораторные "
     "анализы исключены, подряд идущие повторы объединены. Получено "
     f"{S['routes']} маршрутов вместо {S['variants_stay']} вариантов; пять самых частых покрывают "
     f"{pct(S['routes_top5_cum_%'])} эпизодов (таблица {next_tab()}).")
SHORT = {"ER Registration": "Reg", "ER Triage": "Triage", "ER Sepsis Triage": "Sepsis",
         "IV Liquid": "Liquid", "IV Antibiotics": "AB", "Admission NC": "NC",
         "Admission IC": "IC"}


def short_route(s):
    return " → ".join(SHORT.get(a, a.replace("Release ", "Rel ")) for a in s.split(" → "))


table("Наиболее частые маршруты эпизода госпитализации",
      ["Маршрут", "Число", "Доля", "Медиана, сут", "Return ER"],
      [(short_route(r["route"]), r["cases"], pct(r["share_%"]), num(r["median_days"], 2),
        pct(float(r["return_er"]) * 100, 0)) for r in rt[:6]], [8.2, 2.0, 1.9, 2.3, 2.1],
      size=11)
para("Сокращения: Reg – ER Registration, Triage – ER Triage, Sepsis – ER Sepsis Triage, "
     "Liquid – IV Liquid, AB – IV Antibiotics, NC/IC – Admission NC/IC, Rel – Release.",
     indent=0, spacing=1.0)
para(f"Основной путь (happy path) – Reg → Triage → Sepsis → Liquid → AB → NC → Rel A: "
     f"{S['happy_route_cases']} эпизодов ({pct(S['happy_route_share_%'])}), медиана "
     f"{num(S['happy_route_median_days'], 2)} сут. Самый быстрый из маршрутов с числом эпизодов "
     f"не менее 10 – {short_route(S['fastest_route'])}: медиана "
     f"{num(S['fastest_route_median_days'], 2)} сут ({S['fastest_route_cases']} эпизодов), "
     "в нём инфузия начата сразу после регистрации. Маршруты с переводом в реанимацию (IC) "
     "длиннее: 7,1 и 13,9 сут. Оптимальным следует считать основной путь без перевода в "
     "реанимацию и с ранним началом инфузии и антибиотиков; среди точных вариантов "
     f"самый быстрый с не менее чем 5 экземплярами длится {num(S['fastest_variant_median_days'], 2)} сут "
     "(Reg → Triage → Sepsis → Leucocytes → CRP → NC → Rel A).")

heading("5.5 Экземпляры с аномально большой длительностью")
para(f"Порог аномальной длительности определён по правилу межквартильного размаха: "
     f"Q3 + 1,5·IQR = {num(S['long_threshold_days'], 2)} сут (рисунок {next_fig()}). "
     f"Длиннее порога {S['long_cases']} эпизодов ({pct(S['long_share_%'])}), но на них приходится "
     f"{pct(S['long_time_share_%'])} всего времени пребывания пациентов.")
figure("duration_distribution.png", 16.5, "Распределение длительности эпизода госпитализации")
lv = rows("long_vs_normal.csv")
table("Сравнение длительных и остальных экземпляров", ["Показатель", "Длительные", "Остальные"],
      [(r["index"], num(r["Длительные"]), num(r["Остальные"])) for r in lv], [10.5, 3.0, 3.0])
para(f"По таблице {tab_no} длительные экземпляры отличаются прежде всего числом анализов (в 3 раза "
     "больше), долей переводов в реанимацию (40 % против 11 %, почти в 4 раза) и числом переводов между "
     "отделениями; доля повторных обращений почти не отличается. Время длительных экземпляров "
     "в основном тратится на циклы анализов: CRP → Leucocytes, Leucocytes → Leucocytes и "
     "CRP → CRP дают около половины их времени.")
tl = rows("top5_long_cases.csv")
para("Пять самых длительных эпизодов: " + "; ".join(
    f"{r['case:concept:name']} – {num(r['days'])} сут, {r['n_events']} событий, "
    f"{r['n_crp']} анализов CRP{', реанимация' if r['icu'] == 'True' else ''}" for r in tl) +
    ". Это тяжёлые случаи с переводами между отделениями и десятками анализов. Если не "
    "выделять эпизод, самыми длинными оказались бы экземпляры по 387–422 сут, которые "
    "почти целиком состоят из интервала между выпиской и повторным обращением.")

heading("6 Предложения по оптимизации бизнес-процесса")
para("По результатам анализа предложены следующие меры:")
bullets([
    "внедрить протокол «антибиотик в течение часа» (sepsis bundle): назначение антибиотика "
    "одновременно с ER Sepsis Triage, заранее подготовленные наборы препаратов; целевой "
    f"показатель – доля введений не позднее 1 ч выше текущих {pct(S['antibiotics_within_1h_%'])}",
    "стандартизировать лабораторный блок: единая панель CRP + Leucocytes + LacticAcid с одной "
    "регистрацией и повтор анализов по клиническим критериям, а не по ежедневному графику; "
    "это сократит самопетли и цикл CRP ⇄ Leucocytes; переходы между анализами занимают "
    f"{pct(S['lab_block_time_share_%'])} времени эпизодов",
    "планировать выписку заранее: решение о выписке по результатам утренних анализов и "
    "ежедневный разбор пациентов, находящихся дольше "
    f"{num(S['long_threshold_days'], 0)} сут (на {pct(S['long_share_%'])} эпизодов приходится "
    f"{pct(S['long_time_share_%'])} койко-дней)",
    "снизить число переводов между отделениями и в реанимацию за счёт раннего выявления "
    "ухудшения по лактату: длительные эпизоды почти в 4 раза чаще проходят через Admission IC",
    f"организовать наблюдение после выписки: {pct(S['return_er_%'])} пациентов возвращаются, "
    f"медиана интервала {num(S['release_to_return_median_days'])} сут – контрольный визит или "
    "звонок через 2–4 недели после выписки",
    "повысить качество данных: фиксировать фактическое время выполнения, а не пакетной "
    f"регистрации ({integer(S['equal_timestamp_pairs'])} пар событий с одинаковым временем), "
    "и выгружать экземпляры полностью",
])
para("Эффект мер предлагается контролировать теми же показателями после внедрения: временем до "
     "антибиотиков, числом анализов на эпизод, медианой длительности госпитализации и долей "
     "повторных обращений.")

heading("7 Воспроизводимость результатов")
para("Все результаты получены программой analysis.py без ручных правок: при повторном запуске "
     "создаются те же таблицы, рисунки и файл summary.json; генератор случайных чисел "
     "зафиксирован. Отчёт формируется скриптом create_report.py из сохранённых результатов. "
     "Порядок запуска: установить зависимости (pip install -r requirements.txt) и Graphviz, "
     "выполнить python analysis.py, затем python create_report.py. Корректность расчётов "
     "проверяется тестами (python -m unittest discover -s tests).")

struct_heading("Заключение")
para("В работе выполнен процессный анализ пути пациентов с подозрением на сепсис по журналу "
     f"Sepsis Cases ({integer(S['raw_events'])} событий, {integer(S['raw_cases'])} экземпляров). "
     "Проведена предварительная обработка: удалены дубликаты, проверена полнота экземпляров, "
     "выделены эпизоды госпитализации. С помощью PM4Py построены граф непосредственного "
     "следования (частотный и временной), модель процесса алгоритмом Inductive Miner в виде "
     f"сети Петри и BPMN; проверка соответствия дала fitness {num(S['fitness'], 3)} и "
     f"precision {num(S['precision'], 3)}.")
para("Узкие места процесса – ожидание повторных анализов и выписки в стационаре, а также "
     f"задержка антибиотиков (норматив 1 ч выполнен в {pct(S['antibiotics_within_1h_%'])} случаев). "
     f"Основные циклы – повторные анализы CRP и Leucocytes ({pct(S['cases_with_any_repeat_%'])} "
     f"экземпляров с повторами) и повторные обращения ({pct(S['return_er_%'])}). Основной путь "
     f"покрывает {pct(S['happy_route_share_%'])} эпизодов. Длительные экземпляры "
     f"({pct(S['long_share_%'])}) связаны с тяжестью состояния: в 3 раза больше анализов и почти в "
     "4 раза чаще реанимация. Предложены меры по оптимизации: протокол ранней "
     "антибиотикотерапии, стандартизация лабораторного блока, планирование выписки и "
     "наблюдение после неё. Цель работы достигнута.")

struct_heading("Список использованных источников")
SRC = [
    "Mannhardt, F. Sepsis Cases – Event Log // 4TU.ResearchData : репозиторий. – 2016. – "
    "DOI 10.4121/uuid:915d2bfb-7e84-49ad-a286-dc35f063a460. – URL: "
    "https://data.4tu.nl/articles/dataset/Sepsis_Cases_-_Event_Log/12707639 "
    "(дата обращения: 10.11.2026).",
    "PM4Py – Process Mining for Python : документация // Fraunhofer FIT : официальный сайт. – "
    "URL: https://processintelligence.solutions/pm4py (дата обращения: 10.11.2026).",
    "Ван дер Аалст, В. Process Mining: Data Science in Action / В. ван дер Аалст. – 2-е изд. – "
    "Berlin : Springer, 2016. – 467 с.",
    "Михалев, А. С. Лекция 7. Process mining : конспект лекций по дисциплине «Технологии "
    "анализа данных» / А. С. Михалев. – Красноярск : СФУ, 2026. – 52 с.",
]
for i, s in enumerate(SRC, 1):
    para(f"{i} {s}")

# ------------------------------------------------- приложение А: листинг
struct_heading("Приложение А")
p = para("Листинг программы analysis.py", align=WD_ALIGN_PARAGRAPH.CENTER, indent=0, after=12)
p.runs[0].bold = True
for line in (ROOT / "analysis.py").read_text(encoding="utf-8").splitlines():
    cp = fmt(doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.LEFT, indent=0, spacing=1.0)
    r = cp.add_run(line if line else " ")
    r.font.name = "Courier New"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Courier New")
    r.font.size = Pt(10)

doc.core_properties.title = "Отчёт о практической работе № 4 «Процессная аналитика»"
doc.core_properties.author = ""
doc.save(REPORT)
print("Создан:", REPORT)
