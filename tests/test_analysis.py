# -*- coding: utf-8 -*-
"""Проверка analysis.py: запуск, инварианты summary.json, таблицы, рисунки,
воспроизводимость результата.

Запуск:  python -m unittest discover -s tests -v
(analysis.py перезаписывает каталог outputs/)
"""
import csv
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
TAB = OUT / "tables"
FIG = OUT / "figures"

CHARTS = ["duration_distribution.png", "variants_top10.png", "rework.png",
          "antibiotics_delay.png", "labs_vs_duration.png"]
GRAPHS = ["dfg_frequency", "dfg_performance", "petri_net", "bpmn"]
TABLES = ["bottlenecks_by_median.csv", "bottlenecks_by_total.csv", "deviations.csv",
          "dfg_edges_all.csv", "fastest_variants.csv", "lab_groups.csv",
          "long_vs_normal.csv", "long_where_time.csv", "rework.csv",
          "routes_fastest.csv", "routes_top10.csv", "self_loops.csv",
          "top5_long_cases.csv", "two_node_cycles.csv", "variants_top10_all.csv",
          "variants_top10_stay.csv"]


def run_analysis():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(ROOT / "analysis.py")], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600)


def read_csv(name):
    with open(TAB / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def snapshot():
    """Содержимое summary.json и всех CSV-результатов."""
    files = [OUT / "summary.json", OUT / "cases.csv", OUT / "clean_log.csv"]
    files += [TAB / t for t in TABLES]
    return {p.relative_to(OUT).as_posix(): p.read_bytes() for p in files}


class AnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = run_analysis()
        if cls.proc.returncode == 0:
            cls.S = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
            cls.snap = snapshot()

    def setUp(self):
        self.assertEqual(self.proc.returncode, 0,
                         "analysis.py завершился с ошибкой:\n" + self.proc.stderr[-3000:])

    # ------------------------------------------------------------ запуск
    def test_exit_code(self):
        self.assertEqual(self.proc.returncode, 0)
        self.assertIn("Graphviz:", self.proc.stdout)

    # ------------------------------------------------------- summary.json
    def test_summary_keys(self):
        keys = {"raw_events", "raw_cases", "complete_cases", "incomplete_cases",
                "complete_events", "activities", "period", "duration_all_days",
                "duration_stay_days", "variants_all", "variants_stay", "process_tree",
                "fitness", "precision", "f1", "nonfit_cases", "deviations", "happy_path",
                "happy_route", "happy_route_cases", "fastest_route", "long_threshold_days",
                "long_cases", "top_long_all_cases", "self_loop_events", "two_node_cycles",
                "antibiotics_median_h", "return_er_cases"}
        self.assertFalse(keys - set(self.S), f"нет ключей: {sorted(keys - set(self.S))}")

    def test_summary_invariants(self):
        S = self.S
        self.assertEqual(S["raw_cases"], 1050)
        self.assertEqual(S["raw_events"], 15214)
        self.assertEqual(S["complete_cases"] + S["incomplete_cases"], S["raw_cases"])
        self.assertGreater(S["complete_cases"], 0)
        self.assertLessEqual(S["complete_events"], S["raw_events"])
        self.assertEqual(S["activities"], 16)
        for k in ("fitness", "precision", "f1", "fitness_im0", "precision_im0"):
            self.assertGreaterEqual(S[k], 0, k)
            self.assertLessEqual(S[k], 1, k)
        self.assertGreater(S["long_cases"], 0)
        self.assertLess(S["long_cases"], S["complete_cases"])
        self.assertGreater(S["happy_route_cases"], 0)
        self.assertLessEqual(S["happy_route_cases"], S["complete_cases"])
        self.assertLessEqual(S["nonfit_cases"], S["complete_cases"])
        self.assertEqual(S["duration_all_days"]["count"], S["raw_cases"])
        self.assertEqual(S["duration_stay_days"]["count"], S["complete_cases"])
        self.assertEqual(sum(S["start_activities"].values()), S["raw_cases"])
        self.assertEqual(sum(S["end_activities"].values()), S["raw_cases"])
        self.assertLessEqual(S["variants_all_single"], S["variants_all"])
        self.assertLessEqual(S["variants_all"], S["raw_cases"])
        self.assertLessEqual(S["dfg_edges_shown"], S["dfg_edges_total"])
        self.assertEqual(len(S["top_long_all_cases"]), 5)
        self.assertTrue(S["happy_route"].startswith("ER Registration"))

    # ----------------------------------------------------------- таблицы
    def test_tables_exist(self):
        for t in TABLES:
            self.assertTrue((TAB / t).is_file(), t)
            self.assertGreater(len(read_csv(t)), 0, t)

    def test_deviations_table(self):
        S = self.S
        rows = {r["rule"]: int(float(r["cases"])) for r in read_csv("deviations.csv")}
        self.assertEqual(rows, S["deviations"])
        for rule, n in rows.items():
            self.assertGreaterEqual(n, 0, rule)
            self.assertLessEqual(n, S["raw_cases"], rule)
        self.assertEqual(rows["Начало не с ER Registration"], S["cases_not_start_registration"])
        self.assertEqual(rows["Нет выписки (Release) – незавершённый экземпляр"],
                         S["cases_without_release"])
        self.assertEqual(rows["Не соответствуют модели (token replay)"], S["nonfit_cases"])
        # незавершённые = не с регистрации ИЛИ без выписки
        self.assertLessEqual(S["incomplete_cases"],
                             S["cases_not_start_registration"] + S["cases_without_release"])
        self.assertGreaterEqual(S["incomplete_cases"],
                                max(S["cases_not_start_registration"], S["cases_without_release"]))

    def test_dfg_and_cycles_tables(self):
        S = self.S
        edges = read_csv("dfg_edges_all.csv")
        self.assertEqual(len(edges), S["dfg_edges_total"])
        self.assertEqual(len(edges), S["distinct_transitions_all"])
        # переходов на 1 меньше, чем событий, в каждом случае (после удаления дубликатов)
        events = S["raw_events"] - S["duplicates"]
        self.assertEqual(sum(int(r["count"]) for r in edges), events - S["raw_cases"])
        loops = read_csv("self_loops.csv")
        self.assertEqual(sum(int(r["count"]) for r in loops), S["self_loop_events"])
        self.assertEqual(len(read_csv("two_node_cycles.csv")), S["two_node_cycles"])

    def test_case_level_tables(self):
        S = self.S
        with open(OUT / "cases.csv", encoding="utf-8-sig", newline="") as f:
            cases = list(csv.DictReader(f))
        self.assertEqual(len(cases), S["complete_cases"])
        self.assertEqual(sum(r["long"] == "True" for r in cases), S["long_cases"])
        labs = read_csv("lab_groups.csv")
        self.assertEqual(sum(int(r["cases"]) for r in labs), S["complete_cases"])
        routes = read_csv("routes_top10.csv")
        self.assertEqual(routes[0]["route"], S["happy_route"])
        self.assertEqual(int(routes[0]["cases"]), S["happy_route_cases"])
        self.assertLessEqual(sum(float(r["share_%"]) for r in routes), 100.01)
        for r in read_csv("rework.csv"):
            self.assertLessEqual(int(r["cases_with_repeat"]), S["raw_cases"])
        var = read_csv("variants_top10_all.csv")
        self.assertEqual(sum(int(r["cases"]) for r in var[:1]),
                         round(S["top_variant_share_all"] / 100 * S["raw_cases"]))

    # ----------------------------------------------------------- рисунки
    def test_figures(self):
        for name in CHARTS:
            p = FIG / name
            self.assertTrue(p.is_file(), name)
            self.assertEqual(p.read_bytes()[:8], b"\x89PNG\r\n\x1a\n", name)
        for name in GRAPHS:
            gv = FIG / f"{name}.gv"
            self.assertTrue(gv.is_file(), gv.name)
            self.assertIn("digraph", gv.read_text(encoding="utf-8"))

    # -------------------------------------------------- воспроизводимость
    def test_reproducible(self):
        first_summary, first = self.S, self.snap
        proc = run_analysis()
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
        second_summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
        diff_keys = sorted(k for k in set(first_summary) | set(second_summary)
                           if first_summary.get(k) != second_summary.get(k))
        self.assertEqual(diff_keys, [], f"summary.json различается по ключам: {diff_keys}")
        second = snapshot()
        diff_files = sorted(k for k in first if first[k] != second.get(k))
        self.assertEqual(diff_files, [], f"различаются файлы: {diff_files}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
