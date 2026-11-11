import gzip
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis

class LoaderTests(unittest.TestCase):
    def test_sort_utc_ties_duplicates_and_missing_attributes(self):
        loader = getattr(analysis, 'load_log', None)
        self.assertTrue(callable(loader), 'load_log not implemented')
        xml = '''<log><trace><string key="concept:name" value="C"/>
          <event><string key="concept:name" value="late"/><date key="time:timestamp" value="2020-01-01T02:00:00+01:00"/></event>
          <event><string key="concept:name" value="first"/><date key="time:timestamp" value="2020-01-01T00:00:00Z"/></event>
          <event><string key="concept:name" value="second"/><date key="time:timestamp" value="2019-12-31T19:00:00-05:00"/></event>
          <event><string key="concept:name" value="second"/><date key="time:timestamp" value="2019-12-31T19:00:00-05:00"/></event>
          <event><date key="time:timestamp" value="2020-01-01T00:00:00Z"/></event>
          <event><string key="concept:name" value="bad"/></event>
          <event><string key="concept:name" value="naive"/><date key="time:timestamp" value="2020-01-01T00:00:00"/></event>
        </trace><trace><event><string key="concept:name" value="x"/><date key="time:timestamp" value="2020-01-01T00:00:00Z"/></event></trace></log>'''
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'sample.xes.gz'
            with gzip.open(path,'wt',encoding='utf-8') as f: f.write(xml)
            cases, quality = loader(path)
        self.assertEqual(list(cases), ['C'])
        self.assertEqual([e['activity'] for e in cases['C']], ['first','second','second','late'])
        self.assertEqual(cases['C'][0]['timestamp'].isoformat(), '2020-01-01T00:00:00+00:00')
        self.assertEqual(quality['events_total'], 8)
        self.assertEqual(quality['events_retained'], 4)
        self.assertEqual(quality['events_missing_activity'], 1)
        self.assertEqual(quality['events_invalid_timestamp'], 2)
        self.assertEqual(quality['events_missing_case_id'], 1)
        self.assertEqual(quality['adjacent_equal_timestamp_pairs'], 2)
        self.assertEqual(quality['cases_reordered'], 1)

    def test_duplicate_case_ids_raise_even_when_first_case_has_no_valid_events(self):
        xml = '<log><trace><string key="concept:name" value="C"/></trace><trace><string key="concept:name" value="C"/></trace></log>'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'s.gz'
            with gzip.open(path,'wt',encoding='utf-8') as f: f.write(xml)
            with self.assertRaises(ValueError): analysis.load_log(path)

class CycleTests(unittest.TestCase):
    def test_graph_two_node_cycles_do_not_imply_observed_fragment(self):
        from datetime import datetime, timezone, timedelta
        t = datetime(2020, 1, 1, tzinfo=timezone.utc)
        def case(names):
            return [{'activity': name, 'timestamp': t + timedelta(hours=i)}
                    for i, name in enumerate(names)]
        # The reciprocal edges occur in different cases; the self-loop is excluded.
        result = analysis.analyze({'1': case(['A', 'B']), '2': case(['B', 'A']),
                                   '3': case(['A', 'A'])})
        self.assertEqual(result['graph_two_node_cycles'], [
            {'activity_a': 'A', 'activity_b': 'B', 'a_to_b_count': 1,
             'b_to_a_count': 1}])
        self.assertEqual(result['summary']['graph_two_node_cycle_count'], 1)
    def test_observed_aba_counts_overlaps_cases_and_equal_timestamps(self):
        from datetime import datetime, timezone, timedelta
        t = datetime(2020, 1, 1, tzinfo=timezone.utc)
        def case(names, hours):
            return [{'activity': name, 'timestamp': t + timedelta(hours=h)}
                    for name, h in zip(names, hours)]
        result = analysis.analyze({
            '1': case(['A', 'B', 'A', 'B', 'A'], [0, 1, 2, 3, 4]),
            '2': case(['A', 'B', 'A'], [0, 0, 1]),
            '3': case(['B', 'A'], [0, 1]),
            '4': case(['A', 'A', 'A'], [0, 1, 2]),
        })
        self.assertEqual(result['observed_aba'], [
            {'start': 'A', 'middle': 'B', 'occurrences': 3, 'case_count': 2,
             'occurrences_with_equal_timestamp': 1, 'case_count_with_equal_timestamp': 1},
            {'start': 'B', 'middle': 'A', 'occurrences': 1, 'case_count': 1,
             'occurrences_with_equal_timestamp': 0, 'case_count_with_equal_timestamp': 0},
        ])
        self.assertEqual(result['summary']['observed_aba_occurrences'], 4)
        self.assertEqual(result['summary']['cases_with_observed_aba'], 2)
        self.assertEqual(result['summary']['observed_aba_occurrences_with_equal_timestamp'], 1)
    def test_cycle_csv_export_with_observed_and_graph_only_cycles(self):
        import csv
        import json
        def trace(case_id, names):
            events = ''.join(f'<event><string key="concept:name" value="{name}"/>'
                             f'<date key="time:timestamp" value="2020-01-01T0{i}:00:00Z"/></event>'
                             for i, name in enumerate(names))
            return f'<trace><string key="concept:name" value="{case_id}"/>{events}</trace>'
        xml = '<log>' + trace('1', ['A', 'B', 'A']) + trace('2', ['C', 'D']) + trace('3', ['D', 'C']) + '</log>'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'sample.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as f:
                f.write(xml)
            output = Path(d) / 'out'
            analysis.run(path, output, edge_threshold=1)
            with (output / 'graph_two_node_cycles.csv').open(encoding='utf-8-sig', newline='') as f:
                graph = list(csv.DictReader(f))
            with (output / 'observed_aba.csv').open(encoding='utf-8-sig', newline='') as f:
                observed = list(csv.DictReader(f))
            self.assertEqual([(r['activity_a'], r['activity_b']) for r in graph], [('A', 'B'), ('C', 'D')])
            self.assertEqual([(r['start'], r['middle'], r['occurrences'], r['case_count']) for r in observed], [('A', 'B', '1', '1')])
            summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['graph_two_node_cycle_count'], 2)
            self.assertEqual(summary['observed_aba_occurrences'], 1)
    def test_cli_reports_cycle_totals(self):
        import subprocess
        xml = '<log><trace><string key="concept:name" value="1"/>' + ''.join(
            f'<event><string key="concept:name" value="{name}"/>'
            f'<date key="time:timestamp" value="2020-01-01T0{i}:00:00Z"/></event>'
            for i, name in enumerate(['A', 'B', 'A'])) + '</trace></log>'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 's.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as f:
                f.write(xml)
            proc = subprocess.run([sys.executable, str(Path(analysis.__file__)), '--input', str(path),
                                   '--output', str(Path(d) / 'out'), '--edge-threshold', '1'],
                                  capture_output=True, text=True, check=True)
            self.assertIn('graph two-node cycles: 1', proc.stdout)
            self.assertIn('observed ABA occurrences: 1', proc.stdout)
            self.assertIn('cases with ABA: 1', proc.stdout)


class AnalysisTests(unittest.TestCase):
    def test_post_sort_counts_cycles_longest_gap_and_end_specific_variants(self):
        analyze = getattr(analysis, 'analyze', None)
        self.assertTrue(callable(analyze), 'analyze not implemented')
        from datetime import datetime, timezone, timedelta
        t = datetime(2020, 1, 1, tzinfo=timezone.utc)
        def case(names, hours):
            return [{'activity': n, 'timestamp': t + timedelta(hours=h)} for n,h in zip(names,hours)]
        cases = {str(i): case(['A','B','A','Z'], [0,1,2,4]) for i in range(5)}
        cases.update({str(i): case(['A','B','B','Z'], [0,2,3,10]) for i in range(5,10)})
        cases.update({str(i): case(['A','Q'], [0,1]) for i in range(10,15)})
        result = analyze(cases)
        self.assertEqual(result['summary']['events'], 50)
        self.assertEqual(result['summary']['cases'], 15)
        edge = next(x for x in result['transitions'] if (x['source'],x['target']) == ('B','B'))
        self.assertEqual(edge['count'], 5)
        self.assertEqual(edge['median_hours'], 1)
        self.assertEqual(result['summary']['cases_with_repeated_activity'], 10)
        self.assertEqual(result['summary']['self_transitions'], 5)
        selected = {v['end_activity']:v for v in result['best_variants']}
        self.assertEqual(selected['Z']['median_hours'], 4)
        self.assertEqual(selected['Q']['median_hours'], 1)
        row = next(x for x in result['cases'] if x['case_id'] == '5')
        self.assertEqual(row['max_gap_hours'], 7)
        self.assertEqual((row['max_gap_source'],row['max_gap_target']), ('B','Z'))
        self.assertEqual(result['summary']['duration_median_hours'], 4)

    def test_single_event_log_exports_empty_transitions(self):
        import csv
        import json
        xml = '''<log><trace><string key="concept:name" value="one"/><event><string key="concept:name" value="A"/><date key="time:timestamp" value="2020-01-01T00:00:00Z"/></event></trace></log>'''
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'single.xes.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as f:
                f.write(xml)
            output = Path(d) / 'result'
            analysis.run(path, output, edge_threshold=1)
            summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['transitions'], 0)
            with (output / 'transitions.csv').open(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, ['source', 'target', 'count', 'case_count', 'median_hours', 'p95_hours', 'total_hours'])
                self.assertEqual(list(reader), [])
            for filename, fields in [
                ('graph_two_node_cycles.csv', ['activity_a', 'activity_b', 'a_to_b_count', 'b_to_a_count']),
                ('observed_aba.csv', ['start', 'middle', 'occurrences', 'case_count',
                                      'occurrences_with_equal_timestamp', 'case_count_with_equal_timestamp'])]:
                with (output / filename).open(encoding='utf-8-sig', newline='') as f:
                    reader = csv.DictReader(f)
                    self.assertEqual(reader.fieldnames, fields)
                    self.assertEqual(list(reader), [])

    def test_run_writes_complete_artifacts(self):
        run = getattr(analysis, 'run', None)
        self.assertTrue(callable(run), 'run not implemented')
        import json
        xml = '''<log><trace><string key="concept:name" value="1"/><event><string key="concept:name" value="A"/><date key="time:timestamp" value="2020-01-01T00:00:00Z"/></event><event><string key="concept:name" value="B"/><date key="time:timestamp" value="2020-01-02T00:00:00Z"/></event></trace></log>'''
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'s.gz'
            with gzip.open(path,'wt',encoding='utf-8') as f: f.write(xml)
            output = Path(d)/'result'
            run(path, output, edge_threshold=1)
            summary = json.loads((output/'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['events'], 2)
            self.assertTrue((output/'dfg_full.html').exists())
            self.assertTrue((output/'transitions.csv').exists())
            self.assertTrue((output/'dfg_filtered.png').exists())
            self.assertIn('A', (output/'dfg_full.html').read_text(encoding='utf-8'))
            with self.assertRaises(FileExistsError): run(path, output, edge_threshold=1)

if __name__ == '__main__': unittest.main()
