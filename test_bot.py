import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import bot


GOOD = {"state": "SUCCESS", "status_code": 10, "run_success": True, "status_msg": "Accepted"}
BAD = {"state": "SUCCESS", "status_code": 11, "status_msg": "Wrong Answer", "last_testcase": "[1]"}
CFG = {"username": "test-user", "max_attempts": 3}


def problem():
    return {"date": bot.today(), "titleSlug": "test-problem", "questionId": "1",
            "title": "Test Problem", "snippet": "class Solution {};", "content": "Solve it."}


class FakeLC:
    def __init__(self, results):
        self.results, self.starts, self.polls = list(results), [], []

    def daily(self):
        return problem()

    def start(self, q, code, kind):
        self.starts.append(kind)
        return str(len(self.starts))

    def poll(self, identifier):
        self.polls.append(identifier)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeSolver:
    def __init__(self):
        self.calls = []

    def solve(self, q, previous, feedback):
        self.calls.append((previous, feedback))
        return "class Solution {};\n", {"total_tokens": 100}


class FakeCheckpoint:
    def __init__(self):
        self.state = None

    def load(self, date):
        return json.loads(json.dumps(self.state))

    def save(self, state):
        self.state = json.loads(json.dumps(state))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.sleep = patch("bot.time.sleep")
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def state(self):
        return json.loads((self.path / bot.today() / "state.json").read_text())

    def test_success_and_second_run_skips(self):
        lc, solver = FakeLC([GOOD, GOOD]), FakeSolver()
        self.assertEqual(bot.run_day(CFG, lc, solver, self.path), 0)
        self.assertEqual(bot.run_day(CFG, lc, solver, self.path), 0)
        self.assertEqual(lc.starts, ["test", "submit"])
        self.assertEqual(len(solver.calls), 1)
        self.assertEqual(self.state()["phase"], "accepted")

    def test_wrong_submission_is_repaired(self):
        lc, solver = FakeLC([GOOD, BAD, GOOD, GOOD]), FakeSolver()
        self.assertEqual(bot.run_day(CFG, lc, solver, self.path), 0)
        self.assertEqual(lc.starts, ["test", "submit", "test", "submit"])
        self.assertEqual(solver.calls[1][1]["status_msg"], "Wrong Answer")

    def test_failed_test_never_submitted(self):
        lc, solver = FakeLC([BAD, GOOD, GOOD]), FakeSolver()
        self.assertEqual(bot.run_day(CFG, lc, solver, self.path), 0)
        self.assertEqual(lc.starts, ["test", "test", "submit"])

    def test_attempt_limit_survives_restart(self):
        lc, solver = FakeLC([BAD, BAD, BAD]), FakeSolver()
        self.assertEqual(bot.run_day(CFG, lc, solver, self.path), 1)
        self.assertEqual(bot.run_day(CFG, lc, solver, self.path), 1)
        self.assertEqual(len(solver.calls), 3)

    def test_resume_submit_poll_without_duplicate(self):
        lc, solver = FakeLC([GOOD, bot.BotError("timeout")]), FakeSolver()
        with self.assertRaises(bot.BotError):
            bot.run_day(CFG, lc, solver, self.path)
        self.assertEqual(self.state()["phase"], "poll_submit")
        resumed = FakeLC([GOOD])
        self.assertEqual(bot.run_day(CFG, resumed, solver, self.path), 0)
        self.assertEqual(resumed.starts, [])
        self.assertEqual(resumed.polls, ["2"])

    def test_resume_test_poll_without_duplicate(self):
        lc, solver = FakeLC([bot.BotError("timeout")]), FakeSolver()
        with self.assertRaises(bot.BotError):
            bot.run_day(CFG, lc, solver, self.path)
        resumed = FakeLC([GOOD, GOOD])
        self.assertEqual(bot.run_day(CFG, resumed, solver, self.path), 0)
        self.assertEqual(resumed.starts, ["submit"])

    def test_uncertain_submit_stops_instead_of_retrying(self):
        class Uncertain(FakeLC):
            def start(self, q, code, kind):
                if kind == "submit":
                    raise bot.BotError("timeout")
                return super().start(q, code, kind)
        lc, solver = Uncertain([GOOD]), FakeSolver()
        with self.assertRaises(bot.BotError):
            bot.run_day(CFG, lc, solver, self.path)
        self.assertEqual(self.state()["phase"], "sending_submit")
        resumed = FakeLC([])
        with self.assertRaisesRegex(bot.BotError, "uncertain"):
            bot.run_day(CFG, resumed, solver, self.path)
        self.assertEqual(resumed.starts, [])

    def test_failed_model_call_consumes_attempt(self):
        solver = FakeSolver()
        with patch.object(solver, "solve", side_effect=bot.BotError("API failed")):
            with self.assertRaises(bot.BotError):
                bot.run_day(CFG, FakeLC([]), solver, self.path)
        self.assertEqual(self.state()["attempts"], 1)
        bot.run_day(CFG, FakeLC([GOOD, GOOD]), solver, self.path)
        self.assertEqual(self.state()["attempts"], 2)

    def test_uncertain_test_resumes_saved_code(self):
        lc, solver = FakeLC([]), FakeSolver()
        with patch.object(lc, "start", side_effect=bot.BotError("missing ID")):
            with self.assertRaises(bot.BotError):
                bot.run_day(CFG, lc, solver, self.path)
        self.assertEqual(self.state()["phase"], "sending_test")
        resumed = FakeLC([GOOD, GOOD])
        self.assertEqual(bot.run_day(CFG, resumed, solver, self.path), 0)
        self.assertEqual(len(solver.calls), 1)
        self.assertEqual(resumed.starts, ["test", "submit"])

    def test_explicit_503_preserves_attempt(self):
        solver = FakeSolver()
        with patch.object(solver, "solve", side_effect=bot.ModelUnavailable("HTTP 503")):
            with self.assertRaises(bot.ModelUnavailable):
                bot.run_day(CFG, FakeLC([]), solver, self.path)
        self.assertEqual(self.state()["attempts"], 0)
        self.assertEqual(self.state()["phase"], "ready")
        self.assertEqual(bot.run_day(CFG, FakeLC([GOOD, GOOD]), solver, self.path), 0)
        self.assertEqual(self.state()["attempts"], 1)

    def test_generation_retries_explicit_503_only(self):
        http = bot.HTTP()
        error = urllib.error.HTTPError("https://example.com", 503, "busy", {}, None)
        with patch.object(http.opener, "open", side_effect=error) as opened, patch("bot.time.sleep") as sleep:
            with self.assertRaises(bot.ModelUnavailable):
                http.json("https://example.com", {}, body={"prompt": "x"}, retry_statuses=(503,))
        self.assertEqual(opened.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_midnight_stops_before_submission(self):
        q = problem()
        with patch("bot.today", return_value="2099-01-01"):
            with self.assertRaisesRegex(bot.BotError, "date changed"):
                bot.run_day(CFG, FakeLC([]), FakeSolver(), self.path, q)

    def test_different_account_state_rejected(self):
        bot.run_day(CFG, FakeLC([GOOD, GOOD]), FakeSolver(), self.path)
        with self.assertRaisesRegex(bot.BotError, "different problem/account"):
            bot.run_day({**CFG, "username": "another-user"}, FakeLC([]), FakeSolver(), self.path)

    def test_os_lock_prevents_overlap(self):
        with bot.exclusive_lock(self.path / "lock"):
            with self.assertRaises(bot.BotError):
                with bot.exclusive_lock(self.path / "lock"):
                    pass
        with bot.exclusive_lock(self.path / "lock"):
            pass

    def test_hosted_fresh_runner_restores_accepted(self):
        checkpoint, solver = FakeCheckpoint(), FakeSolver()
        bot.run_day(CFG, FakeLC([GOOD, GOOD]), solver, self.path, checkpoint=checkpoint)
        with tempfile.TemporaryDirectory() as fresh:
            lc = FakeLC([])
            self.assertEqual(bot.run_day(CFG, lc, solver, Path(fresh), checkpoint=checkpoint), 0)
            self.assertEqual(lc.starts, [])
            self.assertEqual(len(solver.calls), 1)

    def test_hosted_checkpoint_failure_prevents_submit(self):
        class FailingCheckpoint(FakeCheckpoint):
            def save(self, state):
                if state["phase"] == "sending_submit":
                    raise bot.BotError("GitHub unavailable")
                super().save(state)
        lc = FakeLC([GOOD])
        with self.assertRaises(bot.BotError):
            bot.run_day(CFG, lc, FakeSolver(), self.path, checkpoint=FailingCheckpoint())
        self.assertEqual(lc.starts, ["test"])

    def test_hosted_empty_checkpoint_fails_closed(self):
        checkpoint = FakeCheckpoint()
        checkpoint.state = {}
        with self.assertRaisesRegex(bot.BotError, "Invalid remote"):
            bot.run_day(CFG, FakeLC([]), FakeSolver(), self.path, checkpoint=checkpoint)

    def test_hosted_fresh_runner_preserves_budget(self):
        checkpoint, solver = FakeCheckpoint(), FakeSolver()
        bot.run_day(CFG, FakeLC([BAD, BAD, BAD]), solver, self.path, checkpoint=checkpoint)
        with tempfile.TemporaryDirectory() as fresh:
            self.assertEqual(bot.run_day(CFG, FakeLC([]), solver, Path(fresh), checkpoint=checkpoint), 1)
        self.assertEqual(len(solver.calls), 3)


class ContractTests(unittest.TestCase):
    def test_missing_id_reports_error_without_credentials(self):
        from unittest.mock import Mock
        http = Mock()
        http.json.return_value = {"error": "rejected secret-cookie secret-csrf"}
        lc = bot.LeetCode({"leetcode_session": "secret-cookie", "csrf_token": "secret-csrf",
                          "user_agent": "test"}, http)
        with self.assertRaises(bot.BotError) as error:
            lc.start({**problem(), "sampleTestCase": "[1]"}, "code", "test")
        self.assertIn("rejected", str(error.exception))
        self.assertNotIn("secret-cookie", str(error.exception))
        self.assertNotIn("secret-csrf", str(error.exception))

    def test_model_fallback_on_503(self):
        from unittest.mock import Mock
        cfg = {"model": "gemini-3.8-flash", "fallback_models": ["gemini-3.5-flash-lite"],
               "thinking_level": "medium", "max_output_tokens": 16000, "gemini_api_key": "test"}
        http = Mock()
        http.json.side_effect = [bot.ModelUnavailable("503"), {"candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": "class Solution {};"}]}}]}]
        code, _ = bot.Solver(cfg, http).solve(problem(), "", {})
        self.assertIn("class Solution", code)
        self.assertEqual(http.json.call_count, 2)
        self.assertIn("gemini-3.5-flash-lite:generateContent", http.json.call_args.args[0])

    def test_all_fallbacks_unavailable_preserve_error(self):
        from unittest.mock import Mock
        cfg = {"model": "primary", "fallback_models": ["fallback"],
               "thinking_level": "medium", "max_output_tokens": 16000, "gemini_api_key": "test"}
        http = Mock()
        http.json.side_effect = bot.ModelUnavailable("503")
        with self.assertRaises(bot.ModelUnavailable):
            bot.Solver(cfg, http).solve(problem(), "", {})
        self.assertEqual(http.json.call_count, 2)

    def test_code_extraction(self):
        self.assertEqual(bot.extract_code("```cpp\nclass Solution {};\n```"), "class Solution {};\n")
        with self.assertRaises(bot.BotError):
            bot.extract_code("")

    def test_sample_failure_detected_despite_successful_execution(self):
        self.assertFalse(bot.passed_test({**GOOD, "correct_answer": False}))
        self.assertFalse(bot.passed_test({**GOOD, "total_correct": 1, "total_testcases": 2}))

    def test_model_request_excludes_cookie(self):
        class FakeHTTP:
            def json(self, url, headers, body, **kwargs):
                self.request = (url, headers, body)
                return {"candidates": [{"finishReason": "STOP", "content": {"parts": [
                    {"text": "class Solution {};"}]}}]}
        cfg = {"model": "gemini-3.8-flash", "thinking_level": "medium", "max_output_tokens": 16000,
               "gemini_api_key": "test-key", "leetcode_session": "PRIVATE_COOKIE"}
        http = FakeHTTP()
        bot.Solver(cfg, http).solve(problem(), "", {})
        self.assertNotIn("PRIVATE_COOKIE", json.dumps(http.request))
        self.assertEqual(http.request[1]["x-goog-api-key"], "test-key")
        self.assertEqual(http.request[2]["generationConfig"]["thinkingConfig"]["thinkingLevel"], "medium")

    def test_submit_payload_and_csrf(self):
        class FakeHTTP:
            def json(self, url, headers, body, **kwargs):
                self.request = (url, headers, body, kwargs)
                return {"submission_id": 123}
        http = FakeHTTP()
        cfg = {"leetcode_session": "session", "csrf_token": "csrf", "user_agent": "test"}
        lc = bot.LeetCode(cfg, http)
        self.assertEqual(lc.start(problem(), "code", "submit"), "123")
        url, headers, body, kwargs = http.request
        self.assertEqual(url, "https://leetcode.com/problems/test-problem/submit/")
        self.assertEqual(body, {"lang": "cpp", "question_id": "1", "typed_code": "code"})
        self.assertEqual(headers["X-CSRFToken"], "csrf")
        self.assertFalse(kwargs.get("retry", False))

    def test_feedback_limits_and_allowlist(self):
        result = bot.feedback({"last_testcase": "x" * 10000, "cookie": "secret"})
        self.assertEqual(len(result["last_testcase"]), 6000)
        self.assertNotIn("cookie", result)


if __name__ == "__main__":
    unittest.main()
