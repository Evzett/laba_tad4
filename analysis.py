"""Reproducible analysis of a timestamped XES event log."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import xml.etree.ElementTree as ET


def load_log(path):
    """Parse case IDs and event names; keep valid UTC timestamped events."""
    quality = Counter(events_total=0, events_retained=0, events_missing_case_id=0,
                      events_missing_activity=0, events_invalid_timestamp=0,
                      traces_total=0, traces_missing_case_id=0, traces_empty_after_filter=0,
                      cases_reordered=0, adjacent_equal_timestamp_pairs=0)
    cases = {}
    seen_case_ids = set()
    with gzip.open(path, 'rb') as source:
        for _, trace in ET.iterparse(source, events=('end',)):
            if trace.tag.split('}')[-1] != 'trace':
                continue
            quality['traces_total'] += 1
            children = list(trace)
            names = [e.get('value') for e in children if e.tag.split('}')[-1] == 'string' and e.get('key') == 'concept:name']
            case_id = names[0] if names and names[0] else None
            if not case_id:
                quality['traces_missing_case_id'] += 1
            elif case_id in seen_case_ids:
                raise ValueError(f'Duplicate case identifier: {case_id}')
            else:
                seen_case_ids.add(case_id)
            events = []
            for event in (e for e in children if e.tag.split('}')[-1] == 'event'):
                quality['events_total'] += 1
                attrs = {a.get('key'): a.get('value') for a in event}
                activity = attrs.get('concept:name')
                if not case_id:
                    quality['events_missing_case_id'] += 1
                    continue
                if not activity:
                    quality['events_missing_activity'] += 1
                    continue
                try:
                    stamp = datetime.fromisoformat(attrs.get('time:timestamp', '').replace('Z', '+00:00'))
                    if stamp.utcoffset() is None:
                        raise ValueError('timezone absent')
                    stamp = stamp.astimezone(timezone.utc)
                except (ValueError, TypeError):
                    quality['events_invalid_timestamp'] += 1
                    continue
                events.append({'activity': activity, 'timestamp': stamp})
                quality['events_retained'] += 1
            if case_id:
                quality['cases_reordered'] += int(any(a['timestamp'] > b['timestamp'] for a,b in zip(events, events[1:])))
                events.sort(key=lambda e: e['timestamp'])  # stable: source order breaks ties
                quality['adjacent_equal_timestamp_pairs'] += sum(a['timestamp'] == b['timestamp'] for a,b in zip(events, events[1:]))
                if events:
                    cases[case_id] = events
                else:
                    quality['traces_empty_after_filter'] += 1
            trace.clear()
    return cases, dict(quality)


def percentile(values, p):
    """Linear interpolation at zero-based position (n-1)*p."""
    data = sorted(values)
    if not data:
        return None
    pos = (len(data) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    return data[lo] + (data[hi] - data[lo]) * (pos - lo)


def analyze(cases):
    from collections import defaultdict
    from statistics import median
    activity_counts = Counter()
    activity_cases = Counter()
    repeated_cases = Counter()
    edge_times = defaultdict(list)
    edge_cases = defaultdict(set)
    variant_data = defaultdict(list)
    aba_counts = Counter()
    aba_cases = defaultdict(set)
    aba_ties = Counter()
    aba_tie_cases = defaultdict(set)
    all_aba_cases = set()
    rows = []
    for case_id, events in cases.items():
        names = tuple(e['activity'] for e in events)
        counts = Counter(names)
        activity_counts.update(names)
        activity_cases.update(counts.keys())
        repeated_cases.update(k for k, v in counts.items() if v > 1)
        duration = (events[-1]['timestamp'] - events[0]['timestamp']).total_seconds() / 3600
        variant_data[names].append(duration)
        gaps = []
        for first, second in zip(events, events[1:]):
            hours = (second['timestamp'] - first['timestamp']).total_seconds() / 3600
            edge = (first['activity'], second['activity'])
            edge_times[edge].append(hours)
            edge_cases[edge].add(case_id)
            gaps.append((hours, first, second))
        for first, middle, last in zip(events, events[1:], events[2:]):
            a, b = first['activity'], middle['activity']
            if a == last['activity'] and a != b:
                key = (a, b)
                aba_counts[key] += 1
                aba_cases[key].add(case_id)
                all_aba_cases.add(case_id)
                if first['timestamp'] == middle['timestamp'] or middle['timestamp'] == last['timestamp']:
                    aba_ties[key] += 1
                    aba_tie_cases[key].add(case_id)
        gap = max(gaps, key=lambda x: x[0]) if gaps else None
        rows.append({'case_id': case_id, 'events': len(events), 'start_utc': events[0]['timestamp'].isoformat(),
                     'end_utc': events[-1]['timestamp'].isoformat(), 'end_activity': names[-1],
                     'duration_hours': duration, 'repeated_activities': sum(v > 1 for v in counts.values()),
                     'self_transitions': sum(a == b for a, b in zip(names, names[1:])),
                     'last_events': [{'activity': e['activity'], 'timestamp_utc': e['timestamp'].isoformat()} for e in events[-5:]],
                     'max_gap_hours': gap[0] if gap else None,
                     'max_gap_source': gap[1]['activity'] if gap else None,
                     'max_gap_target': gap[2]['activity'] if gap else None,
                     'max_gap_start_utc': gap[1]['timestamp'].isoformat() if gap else None,
                     'max_gap_end_utc': gap[2]['timestamp'].isoformat() if gap else None,
                     'variant': list(names)})
    variants = [{'variant': list(k), 'end_activity': k[-1], 'count': len(v),
                 'median_hours': median(v), 'p95_hours': percentile(v, .95)}
                for k, v in variant_data.items()]
    variants.sort(key=lambda x: (-x['count'], x['variant']))
    for i, v in enumerate(variants, 1):
        v['variant_id'] = f'V{i:04d}'
    variant_ids = {tuple(v['variant']): v['variant_id'] for v in variants}
    for row in rows:
        row['variant_id'] = variant_ids[tuple(row['variant'])]
    transitions = [{'source': a, 'target': b, 'count': len(vals), 'case_count': len(edge_cases[a,b]),
                    'median_hours': median(vals), 'p95_hours': percentile(vals,.95),
                    'total_hours': sum(vals)} for (a,b), vals in edge_times.items()]
    transitions.sort(key=lambda x: (-x['count'], x['source'], x['target']))
    edge_counts = {(e['source'], e['target']): e['count'] for e in transitions}
    graph_cycles = [{'activity_a': a, 'activity_b': b,
                     'a_to_b_count': edge_counts[a, b], 'b_to_a_count': edge_counts[b, a]}
                    for a, b in sorted(edge_counts)
                    if a < b and (b, a) in edge_counts]
    observed_aba = [{'start': a, 'middle': b, 'occurrences': count,
                     'case_count': len(aba_cases[a, b]),
                     'occurrences_with_equal_timestamp': aba_ties[a, b],
                     'case_count_with_equal_timestamp': len(aba_tie_cases[a, b])}
                    for (a, b), count in sorted(aba_counts.items(), key=lambda item: (-item[1], item[0]))]
    frequencies = [{'activity': a, 'events': c, 'cases': activity_cases[a], 'cases_repeated': repeated_cases[a]}
                   for a,c in activity_counts.most_common()]
    candidates = [v for v in variants if v['count'] >= 5]
    best = []
    for end in sorted({v['end_activity'] for v in candidates}):
        best.append(min((v for v in candidates if v['end_activity'] == end),
                        key=lambda v: (v['median_hours'], -v['count'], v['variant'])))
    rows.sort(key=lambda x: (-x['duration_hours'], x['case_id']))
    durations = [r['duration_hours'] for r in rows]
    summary = {'cases': len(rows), 'events': sum(activity_counts.values()), 'activities': len(activity_counts),
               'distinct_variants': len(variants), 'transitions': sum(x['count'] for x in transitions),
               'distinct_transitions': len(transitions), 'duration_median_hours': median(durations) if durations else None,
               'duration_p95_hours': percentile(durations,.95),
               'cases_with_repeated_activity': sum(r['repeated_activities'] > 0 for r in rows),
               'self_transitions': sum(r['self_transitions'] for r in rows),
               'graph_two_node_cycle_count': len(graph_cycles),
               'observed_aba_types': len(observed_aba),
               'observed_aba_occurrences': sum(aba_counts.values()),
               'cases_with_observed_aba': len(all_aba_cases),
               'observed_aba_occurrences_with_equal_timestamp': sum(aba_ties.values()),
               'most_frequent_variant': variants[0] if variants else None,
               'best_variants_by_end': best, 'top_5_longest_cases': rows[:5]}
    return {'summary': summary, 'cases': rows, 'variants': variants, 'transitions': transitions,
            'activities': frequencies, 'best_variants': best, 'graph_two_node_cycles': graph_cycles,
            'observed_aba': observed_aba}


def run(path, output, edge_threshold=400):
    import csv
    import hashlib
    import html
    import json
    from pathlib import Path
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import networkx as nx

    path, output = Path(path), Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Output directory is not empty: {output}')
    if edge_threshold < 1:
        raise ValueError('edge threshold must be >= 1')
    cases, quality = load_log(path)
    if not cases:
        raise ValueError('No valid cases')
    result = analyze(cases)
    summary = result['summary']
    sha256 = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            sha256.update(chunk)
    summary.update({'input_file': path.name, 'input_sha256': sha256.hexdigest(), 'quality': quality,
                    'dfg_filtered_min_transition_count': edge_threshold,
                    'dfg_filtered_edges': sum(t['count'] >= edge_threshold for t in result['transitions']),
                    'rare_variant_definition': 'variant with exactly one observed case',
                    'rare_variant_count': sum(v['count'] == 1 for v in result['variants']),
                    'rare_variant_cases': sum(v['count'] for v in result['variants'] if v['count'] == 1),
                    'case_duration_above_p95_count': sum(r['duration_hours'] > summary['duration_p95_hours'] for r in result['cases'])})
    output.mkdir(parents=True, exist_ok=True)
    for key, filename in [('transitions','transitions.csv'),('activities','activities.csv'),('cases','cases.csv'),('variants','variants.csv')]:
        data = result[key]
        with (output/filename).open('w', encoding='utf-8-sig', newline='') as f:
            fields = list(data[0]) if data else ['source', 'target', 'count', 'case_count', 'median_hours', 'p95_hours', 'total_hours']
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in data:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list,dict)) else v for k,v in row.items()})
    for key, fields in [
        ('graph_two_node_cycles', ['activity_a', 'activity_b', 'a_to_b_count', 'b_to_a_count']),
        ('observed_aba', ['start', 'middle', 'occurrences', 'case_count',
                          'occurrences_with_equal_timestamp', 'case_count_with_equal_timestamp'])]:
        with (output / f'{key}.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(result[key])
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    # A complete adjacency-list rendering is a readable directed graph, with all nodes and arcs.
    nodes = sorted(a['activity'] for a in result['activities'])
    anchors = {node: f'n{i}' for i,node in enumerate(nodes)}
    pieces = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Full directly-follows graph</title>',
              '<style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:2em}section{border:1px solid #bbb;border-radius:8px;margin:1em 0;padding:1em}li{padding:.2em}a{color:#005caa}.freq{color:#444}</style>',
              '<h1>Complete directly-follows graph</h1><p>All observed nodes and directed edges; each arrow is labeled with occurrence count and median adjacent-event interval in hours. Nodes are alphabetically sorted. Links jump to the target node. DFG does not establish causation or parallelism.</p>']
    freq = {a['activity']: a['events'] for a in result['activities']}
    for node in nodes:
        pieces.append(f'<section id="{anchors[node]}"><h2>{html.escape(node)} <span class="freq">({freq[node]} events)</span></h2><ul>')
        for e in result['transitions']:
            if e['source'] == node:
                pieces.append(f'<li>→ <a href="#{anchors[e["target"]]}">{html.escape(e["target"])}</a> — {e["count"]} transitions; median {e["median_hours"]:.2f} h</li>')
        pieces.append('</ul></section>')
    pieces.append('</html>')
    (output/'dfg_full.html').write_text('\n'.join(pieces), encoding='utf-8')
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    for e in result['transitions']:
        if e['count'] >= edge_threshold:
            graph.add_edge(e['source'],e['target'],weight=e['count'])
    positions = nx.circular_layout(graph)
    fig, ax = plt.subplots(figsize=(18, 16))
    nx.draw_networkx_nodes(graph, positions, ax=ax, node_size=1500, node_color='#bcdcf5')
    nx.draw_networkx_labels(graph, positions, ax=ax, font_size=8)
    nx.draw_networkx_edges(graph, positions, ax=ax, arrows=True, arrowsize=13,
                           connectionstyle='arc3,rad=0.12', width=1.3, node_size=1500)
    nx.draw_networkx_edge_labels(graph, positions, ax=ax,
        edge_labels={(a,b): d['weight'] for a,b,d in graph.edges(data=True)}, font_size=7,
        connectionstyle='arc3,rad=0.12', bbox={'alpha':.75, 'color':'white', 'pad':1})
    ax.set_title(f'DFG subset: edges occurring at least {edge_threshold} times; all activities shown')
    ax.axis('off'); fig.tight_layout(); fig.savefig(output/'dfg_filtered.png',dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10,6))
    durations = sorted(r['duration_hours']/24 for r in result['cases'])
    ax.plot(durations, [(i+1)/len(durations) for i in range(len(durations))])
    ax.set_xscale('symlog', linthresh=1); ax.set_xlabel('Case duration in days (symlog)')
    ax.set_ylabel('Cumulative fraction'); ax.grid(alpha=.25); ax.set_title('Distribution of observed case duration')
    fig.tight_layout(); fig.savefig(output/'case_duration_ecdf.png', dpi=150); plt.close(fig)
    return summary


def main():
    import argparse
    from pathlib import Path
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=root/'data'/'Sepsis Cases - Event Log.xes.gz')
    parser.add_argument('--output', type=Path, default=root/'outputs')
    parser.add_argument('--edge-threshold', type=int, default=400)
    args = parser.parse_args()
    summary = run(args.input, args.output, args.edge_threshold)
    print(f"Cases: {summary['cases']}; events: {summary['events']}; variants: {summary['distinct_variants']}; output: {args.output}")
    print(f"graph two-node cycles: {summary['graph_two_node_cycle_count']}; "
          f"observed ABA occurrences: {summary['observed_aba_occurrences']}; "
          f"cases with ABA: {summary['cases_with_observed_aba']}; "
          f"ABA occurrences with timestamp ties: {summary['observed_aba_occurrences_with_equal_timestamp']}")


if __name__ == '__main__':
    main()
