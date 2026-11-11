"""Сборка отчёта из титульного шаблона и сохранённых результатов анализа."""
from pathlib import Path
import csv
import json
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'outputs' / 'final'
if not (DATA / 'summary.json').exists():
    DATA = ROOT / 'outputs' / 'initial'
OUT = ROOT / 'report' / 'Отчет_ПР4_Процессная_аналитика.docx'
s = json.loads((DATA / 'summary.json').read_text(encoding='utf-8'))
def read_csv(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
activities, transitions, variants, cases = (read_csv(n) for n in ('activities.csv','transitions.csv','variants.csv','cases.csv'))
assert len(activities) == s['activities'] and len(transitions) == s['distinct_transitions']
assert len(cases) == s['cases'] and len(variants) == s['distinct_variants']
assert [r['case_id'] for r in cases[:5]] == [r['case_id'] for r in s['top_5_longest_cases']]
assert sum(int(r['events']) for r in activities) == s['events']
assert sum(int(r['count']) for r in transitions) == s['transitions'] == s['events'] - s['cases']
assert sum(int(r['count']) for r in variants) == s['cases']
def num(x, digits=2):
    return f'{float(x):,.{digits}f}'.replace(',', ' ').replace('.', ',')
def integer(x):
    return f'{int(x):,}'.replace(',', ' ')
def seq(v): return ' → '.join(v)

doc = Document(ROOT / 'report' / 'title_template_pr4.docx')
for name in ('Heading 1', 'Heading 2'):
    st = doc.styles[name]; st.font.name = 'Times New Roman'; st.font.size = Pt(14)
    st.font.bold = True; st.font.color.rgb = RGBColor.from_string('000000')
    st.paragraph_format.line_spacing = 1.5; st.paragraph_format.space_before = Pt(9)
    st.paragraph_format.space_after = Pt(3); st.paragraph_format.first_line_indent = Cm(0)


def para(text='', align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=True, bold=False):
    p = doc.add_paragraph(); p.alignment = align
    p.paragraph_format.first_line_indent = Cm(1.25 if indent else 0)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(0)
    p.add_run(text).bold = bold
    return p

def title(text, before=0, after=0, bold=False):
    p = para(text, WD_ALIGN_PARAGRAPH.CENTER, False, bold)
    p.paragraph_format.space_before = Pt(before); p.paragraph_format.space_after = Pt(after)
    return p

def heading(text): doc.add_heading(text, level=1)
def caption(text):
    p = para(text, WD_ALIGN_PARAGRAPH.CENTER, False)
    p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.keep_with_next = False
    for r in p.runs: r.font.size = Pt(12)

def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = 'Table Grid'; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if widths:
        for col, w in zip(t.columns, widths): col.width = Cm(w)
    for i, row in enumerate([headers] + list(rows)):
        cells = t.rows[0].cells if i == 0 else t.add_row().cells
        if i == 0:
            trPr = t.rows[0]._tr.get_or_add_trPr(); repeat = OxmlElement('w:tblHeader'); repeat.set(qn('w:val'),'true'); trPr.append(repeat)
        for j, (cell, value) in enumerate(zip(cells,row)):
            if widths: cell.width = Cm(widths[j])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]; p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.line_spacing = 1.0; p.paragraph_format.space_after = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(value)); r.font.name = 'Times New Roman'; r.font.size = Pt(11); r.bold = i == 0
            if i == 0:
                shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), 'E8EDF3'); cell._tc.get_or_add_tcPr().append(shade)
        trpr = t.rows[i]._tr.get_or_add_trPr(); trpr.append(OxmlElement('w:cantSplit'))
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return t

def figure(file, width, text):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(DATA / file), width=Cm(width)); caption(text)

doc.add_page_break()
# The section heading begins on the second page.
heading('1 Цель и задачи работы')
para('Цель работы — познакомиться с технологиями Process mining и получить навыки построения и анализа графа бизнес-процесса по журналу событий.')
para('Задачи: подготовить данные, построить граф непосредственно следующих событий, исследовать частые переходы, повторы, статистические отклонения и длительные случаи, рассмотреть наблюдаемые варианты маршрутов и предложить проверяемые улучшения.')
para('Номер отчёта принят как № 4 в соответствии с именем исходного файла и последовательностью работ. На титульной странице PDF методического задания указан № 5; это расхождение нумерации исходных материалов.')
heading('2 Исходные данные и методика')
para('Использован реальный обезличенный журнал Sepsis Cases из 4TU.ResearchData: события записаны информационной системой больницы. Согласно описанию набора временные метки рандомизированы, но интервалы между событиями внутри трассы сохранены[1]. Даты нельзя трактовать как реальные календарные даты; последним событием лога не обязательно заканчивается лечение.')
para('Программа analysis.py использует идентификатор случая trace/concept:name, действие event/concept:name и event/time:timestamp. События без ID, действия или корректного timestamp с часовым поясом исключаются, время переводится в UTC, внутри каждого случая выполняется стабильная сортировка по времени. При одинаковом времени сохраняется порядок исходного файла, который не доказывает фактической последовательности.')
q=s['quality']
para(f"Обработано {integer(s['cases'])} случаев и {integer(s['events'])} событий; сохранено {integer(q['events_retained'])} из {integer(q['events_total'])} событий. Пропусков ID и действия, некорректных временных меток и пустых после фильтра случаев не обнаружено. Переупорядоченных случаев — {q['cases_reordered']}, соседних пар с одинаковым временем — {integer(q['adjacent_equal_timestamp_pairs'])}.")
para('Трасса — упорядоченная последовательность событий случая; вариант — точная последовательность названий действий. Длительность трассы измеряется от первого до последнего записанного события. Интервал перехода — разница времён соседних событий, а не установленная длительность работы или ожидания. P95 вычислен линейной интерполяцией в позиции (n − 1) × 0,95.')
heading('3 Граф процесса и активности')
para(f"Построен DFG: {s['activities']} действий, {integer(s['transitions'])} переходов и {s['distinct_transitions']} уникальных направленных пар. На рисунке 1 оставлены все узлы, но только {s['dfg_filtered_edges']} рёбер с частотой не менее {s['dfg_filtered_min_transition_count']}; редкие связи на нём не видны. Полные частоты находятся в transitions.csv и dfg_full.html.")
figure('dfg_filtered.png', 15.5, f"Рисунок 1 — DFG: все действия и переходы с частотой не менее {s['dfg_filtered_min_transition_count']}; числа на стрелках — частоты")
para('DFG отражает лишь соседство событий: он не задаёт причинность, не различает надёжно параллельность и выбор и может представлять невозможные комбинации маршрутов. При фильтрации теряются редкие связи; интервалы относятся только к наблюдавшимся соседним парам[2]. В плотном центре рисунка стрелки пересекаются; для точных направлений и частот следует пользоваться полной таблицей transitions.csv или dfg_full.html. Поэтому граф — обзор данных, а не доказанная модель реального процесса.')
caption('Таблица 1 — Частота действий и их повторов в случаях')
table(['Действие','Событий','Случаев','С повтором'], [(r['activity'], integer(r['events']), integer(r['cases']), integer(r['cases_repeated'])) for r in activities], [7.1,3,3,3])
caption('Таблица 2 — Десять наиболее частых соседних переходов')
table(['Переход','Частота','Случаев','Медиана, ч'], [(r['source']+' → '+r['target'], integer(r['count']), integer(r['case_count']), num(r['median_hours'])) for r in transitions[:10]], [7.9,2.5,2.5,3.2])
para(f"Хотя бы одно повторяющееся действие встречается в {integer(s['cases_with_repeated_activity'])} случаях; непосредственно одинаковых соседних действий — {integer(s['self_transitions'])}. Повтор действия не обязательно является циклом в смысле модели или ошибкой; причины требуют контекстной проверки.")
if (DATA / 'graph_two_node_cycles.csv').exists() and (DATA / 'observed_aba.csv').exists() and 'observed_aba_types' in s:
    graph_cycles = read_csv('graph_two_node_cycles.csv')
    aba = read_csv('observed_aba.csv')
    assert len(graph_cycles) == s['graph_two_node_cycle_count'] and len(aba) == s['observed_aba_types']
    assert sum(int(x['occurrences']) for x in aba) == s['observed_aba_occurrences']
    assert sum(int(x['occurrences_with_equal_timestamp']) for x in aba) == s['observed_aba_occurrences_with_equal_timestamp']
    para(f"Поиск многозвенных циклов ограничен двухвершинными взаимными рёбрами DFG и окнами A → B → A в отдельных трассах (A ≠ B), а не всеми циклами произвольной длины. Найдено {len(graph_cycles)} пар взаимных рёбер графа; обратные рёбра могут принадлежать разным случаям и не доказывают замкнутого фрагмента. В трассах обнаружено {len(aba)} типов A → B → A, {integer(s['observed_aba_occurrences'])} окон в {integer(s['cases_with_observed_aba'])} различных случаях; {integer(s['observed_aba_occurrences_with_equal_timestamp'])} окон содержат совпадающие метки и потому имеют неопределённый реальный порядок. Перекрывающиеся окна учитываются отдельно, случаи разных типов могут пересекаться.")
    cycle = next(x for x in graph_cycles if x['activity_a'] == 'CRP' and x['activity_b'] == 'Leucocytes')
    para(f"Пример двухвершинного цикла на агрегированном DFG: CRP → Leucocytes — {integer(cycle['a_to_b_count'])} переходов, Leucocytes → CRP — {integer(cycle['b_to_a_count'])}. В отличие от этих отдельных частот, приведённые далее окна действительно соседствуют в одной отсортированной трассе с оговоркой о совпадающем времени.")
    caption('Таблица 3 — Наиболее частые наблюдаемые фрагменты A → B → A')
    table(['A → B → A', 'Окон', 'Случаев', 'Окон с равным временем'], [(r['start']+' → '+r['middle']+' → '+r['start'],integer(r['occurrences']),integer(r['case_count']),integer(r['occurrences_with_equal_timestamp'])) for r in aba[:10]], [8.3,2.1,2.5,3.2])
    para('Частые взаимные переходы лабораторных событий могут отражать повторные измерения или одновременную регистрацию, а не неэффективный цикл; для проверки нужны регламент и временные метки первичных систем. Полные таблицы двухвершинных циклов и окон сохранены в graph_two_node_cycles.csv и observed_aba.csv.')
else:
    para('В текущем наборе результатов расчёт двухвершинных графовых циклов и окон A → B → A отсутствует; требуется повторный запуск анализа и пересборка отчёта.')
r = next(x for x in transitions if x['source']=='Release A' and x['target']=='Return ER')
a = next(x for x in transitions if x['source']=='Admission NC' and x['target']=='Release A')
para(f"Пример потенциально большого интервала: Release A → Return ER — {r['count']} переходов, медиана {num(r['median_hours'])} ч, P95 {num(r['p95_hours'])} ч. Для Admission NC → Release A: {a['count']} переходов, медиана {num(a['median_hours'])} ч. Это разные пары и разные выборки; первый интервал включает период после выписки и не является временем ожидания в больнице. Оба показателя сами по себе не устанавливают узкое место.")
heading('4 Варианты маршрутов и их сравнение')
most = s['most_frequent_variant']; best = next(v for v in s['best_variants_by_end'] if v['end_activity']=='Release A')
para(f"Наблюдается {integer(s['distinct_variants'])} различных вариантов; {integer(s['rare_variant_count'])} встречены ровно в одном случае. Самый частый — {most['variant_id']}: {seq(most['variant'])}; {most['count']} случаев, медиана {num(most['median_hours'],3)} ч, P95 {num(most['p95_hours'],3)} ч. Он заканчивается ER Sepsis Triage, а не выпиской; возможна неполнота регистрации.")
para('Для описательного поиска кандидата на «оптимальный» маршрут рассматривается точная наблюдаемая последовательность минимум в пяти случаях. В пределах каждого последнего события выбирается вариант с минимальной медианой общей наблюдаемой длительности; при равенстве — большая частота, затем лексикографический порядок. Для конца без достаточного числа наблюдений кандидат не выбирается.')
para(f"Для Release A выбран {best['variant_id']}: {seq(best['variant'])}; {best['count']} случаев, медиана {num(best['median_hours'],2)} ч, P95 {num(best['p95_hours'],2)} ч. Самый частый {most['variant_id']} и кандидат {best['variant_id']} имеют разные последние события и не являются сопоставимыми маршрутами до одного результата. Пять случаев — малая выборка; клиническая сложность пациентов и полнота журнала могут различаться. Минимум медианы не доказывает эффективность или клиническую оптимальность.")
heading('5 Длительность и статистические отклонения')
med=s['duration_median_hours']; p95=s['duration_p95_hours']
para(f"Общая медиана длительности — {num(med)} ч ({num(med/24)} дня), P95 — {num(p95)} ч ({num(p95/24)} дня), то есть примерно в {num(p95/med,1)} раза больше медианы. Строго выше P95 — {s['case_duration_above_p95_count']} случаев. Порог описывает верхний хвост распределения, а не нарушения; P95 — не максимальная длительность.")
figure('case_duration_ecdf.png', 15.5, 'Рисунок 2 — Эмпирическая функция распределения длительностей: дни по горизонтали (symlog), доля случаев по вертикали')
caption('Таблица 4 — Пять самых длинных наблюдаемых трасс')
longrows=[]
for r in s['top_5_longest_cases']:
    assert r['end_activity']=='Return ER' and r['max_gap_source']=='Release A' and r['max_gap_target']=='Return ER'
    longrows.append([r['case_id'],num(r['duration_hours']),r['end_activity'],num(r['max_gap_hours']),num(100*r['max_gap_hours']/r['duration_hours'],1)+' %'])
table(['Случай','Длитель-\nность, ч','Последнее событие','Макс. интервал, ч','Доля'],longrows,[2,3.3,3.4,4,3.4])
para('Во всех пяти случаях максимальный интервал — Release A → Return ER: он занимает показанную в таблице долю полной длительности. Следовательно, в этих пяти трассах доминирует период между выпиской и возвращением, а не длительность одной госпитализации. Интервал может включать неотражённые события; его причина и клинический смысл по этому журналу не устанавливаются.')
para('Редкие варианты, повторения и большие интервалы — статистические признаки для дальнейшего изучения, а не доказательства нарушений, ненужных действий или диагнозы. Длинная трасса сравнивается с общей медианой и P95 условно: состав конечных событий и границы эпизодов различаются.')
heading('6 Предложения по совершенствованию процесса и анализа')
for t in [
'Разделить трассы по согласованным с владельцем процесса границам эпизодов выписки: отдельно измерять эпизод до выписки и время до возвращения, учитывая повторные выписки и неполные трассы. Сверить распределения до и после разбиения, не считать интервал вне больницы ожиданием внутри неё.',
'Совместно с владельцами ER проверить, какой момент фиксируют Registration, Triage и Sepsis Triage, точность часов и возможное пакетное внесение записей. Измерять интервалы регистрации → triage и triage → зарегистрированного события IV Antibiotics только при наличии сопоставимых пар; раздельно учитывать пропуски и усечённые трассы, контролировать доступные показатели сложности случая. Время регистрации события не обязательно равно времени выполнения лечения.',
'При частых повторениях лабораторных событий провести ревью инфраструктуры записи и связи лаборатории с ER: идентификаторы образцов, отправку и получение результатов, задержки обмена и повторную регистрацию. Проверять гипотезы на дополнительных данных и с персоналом; повторное обследование может быть необходимо, убирать его на основании DFG нельзя.',
'Для организационных изменений зафиксировать базовые распределения и размеры сопоставимых групп, проверить качество меток, затем сравнивать с последующими данными по согласованным показателям и сложности. Вывод о снижении задержек или улучшении исходов без такой проверки не делается; медицинские решения остаются за специалистами.'
]: para('• '+t, WD_ALIGN_PARAGRAPH.JUSTIFY, False)
heading('7 Проверка программы и воспроизводимость')
para('В каталоге проекта выполнена команда C:/Users/ntise/Downloads/process_mining_lab/.venv/Scripts/python.exe -m unittest discover -s tests -v: 9 тестов, OK. Проверены обработка часовых поясов и совпадающих временных меток, пропусков и повторов, отклонение повторного ID, расчёт частот, одно событие без рёбер и сохранение результатов, а также различие графовых циклов и наблюдаемых окон, их подсчёт, CSV и вывод командной строки.')
para('Независимый повторный анализ выполнен командой C:/Users/ntise/Downloads/process_mining_lab/.venv/Scripts/python.exe analysis.py --output C:/Users/ntise/AppData/Local/hermes/profiles/team-lead/cache/scratch/pr4_report_verify_20261110. Получено 1 050 случаев, 15 214 событий и 846 вариантов; 40 двухвершинных циклов DFG и 1 324 окна A → B → A в 390 случаях. SHA-256 файлов summary.json, activities.csv, transitions.csv, variants.csv, cases.csv, graph_two_node_cycles.csv и observed_aba.csv побайтово совпал с outputs/final. Графические файлы в данное сравнение не входили.')
para('Контроль согласованности: сумма частот действий равна числу событий, сумма частот переходов — числу событий минус число непустых случаев, сумма частот вариантов — числу случаев. Эти проверки выполнены скриптом сборки по считанным таблицам. Для повторного анализа используйте новый пустой каталог; для пересборки отчёта запустите create_report.py тем же интерпретатором.')
heading('8 Вывод')
para(f"По готовым результатам анализа рассмотрен журнал из {integer(s['cases'])} случаев, построен DFG и выделены частоты действий и переходов. Значительное разнообразие вариантов и длинный верхний хвост требуют осторожной интерпретации. Длительность пяти крупнейших трасс преимущественно определяется последующим возвращением после выписки; описательный кандидат для Release A не доказывает лучший исход.")
heading('Вопросы для подготовки к защите')
para('Следующие вопросы составлены самостоятельно для подготовки; в исходном задании контрольные вопросы не приведены.', indent=False)
qa=[('Что такое трасса и вариант?', 'Трасса — последовательность событий одного случая; вариант — последовательность названий действий, общая для совпадающих трасс.'),('Что показывает ребро DFG?', 'Частоту непосредственного следования двух действий внутри случая; причинность и параллельность из одного ребра не следуют.'),('Почему равные временные метки важны?', 'Порядок таких событий берётся из файла и может не соответствовать реальной последовательности.'),('Почему интервал не равен времени ожидания?', 'Между записанными событиями могут происходить другие незарегистрированные действия или период вне больницы.'),('Почему выбранный маршрут нельзя считать клинически оптимальным?', 'Критерий использует только наблюдаемую медиану для конкретного последнего события; группы могут отличаться сложностью, а журнал — быть неполным.'),('Что означает P95?', 'Это эмпирический 95-й процентиль длительности по принятому правилу интерполяции; случаи выше него статистически длинные, но не обязательно ошибочные.')]
for i,(question,answer) in enumerate(qa,1): para(f'{i}. {question} {answer}', indent=False)
heading('Источники')
para('[1] Mannhardt F. Sepsis Cases — Event Log. Version 1. 4TU.ResearchData, 2016. DOI: 10.4121/uuid:915d2bfb-7e84-49ad-a286-dc35f063a460. https://data.4tu.nl/articles/dataset/Sepsis_Cases_-_Event_Log/12707639', indent=False)
para('[2] van der Aalst W. M. P. A practitioner’s guide to process mining: Limitations of the directly-follows graph. 2019. https://www.vdaalst.com/publications/p1101.pdf', indent=False)
para(f'Расчётные данные: outputs/{DATA.name}/summary.json, activities.csv, transitions.csv, variants.csv, cases.csv; графики: dfg_filtered.png и case_duration_ecdf.png. Полные таблицы доступны в каталоге результатов; скрипт отчёта не перезапускает анализ.', indent=False)
doc.core_properties.title = 'Отчёт по практической работе № 4 — Процессная аналитика'
doc.save(OUT)
print(f'Создан: {OUT}')
