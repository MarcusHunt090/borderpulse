"""PR metric regression checks against scikit-learn's average precision."""
import unittest
import numpy as np
from sklearn.metrics import average_precision_score
import backtest as bt


class PrecisionRecallTests(unittest.TestCase):
    def test_constant_scores_equal_prevalence(self):
        self.assertAlmostEqual(bt.pr_auc(np.zeros(6), np.array([0, 1, 0, 0, 1, 0])), 1 / 3)

    def test_tied_scores_are_invariant_to_row_order(self):
        scores = np.array([0.1, 0.1, 0.1, 0.9, 0.9, 0.9])
        labels = np.array([1, 0, 0, 1, 0, 1])
        expected = bt.pr_auc(scores, labels)
        rng = np.random.default_rng(42)
        for _ in range(50):
            order = rng.permutation(len(scores))
            self.assertAlmostEqual(bt.pr_auc(scores[order], labels[order]), expected)

    def test_tied_and_distinct_scores_match_reference(self):
        rng = np.random.default_rng(42)
        for decimals in (0, 1, 5):
            scores = np.round(rng.random(100), decimals)
            labels = rng.integers(0, 2, 100)
            self.assertAlmostEqual(bt.pr_auc(scores, labels), average_precision_score(labels, scores))

    def test_no_positive_labels_stays_undefined(self):
        self.assertTrue(np.isnan(bt.pr_auc(np.array([0.1, 0.2]), np.zeros(2))))

    def test_all_positive_labels_equal_one(self):
        self.assertEqual(bt.pr_auc(np.array([0.1, 0.1, 0.9]), np.ones(3)), 1)

    def test_published_score_metric_matches_reference(self):
        self.assertAlmostEqual(bt.pr_auc(bt.score_arr, bt.Y), average_precision_score(bt.Y, bt.score_arr))


if __name__ == "__main__":
    unittest.main()
