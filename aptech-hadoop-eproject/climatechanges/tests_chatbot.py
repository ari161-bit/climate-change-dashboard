import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from . import chatbot


def post(client, messages):
    return client.post("/climatechanges/api/chat/", data=json.dumps({"messages": messages}), content_type="application/json")


@override_settings(ALLOWED_HOSTS=["testserver"])
class ChatbotTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_bootstrap_reports_whether_ai_is_configured(self):
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            self.assertFalse(self.client.get("/climatechanges/api/chat/").json()["ai"])
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "x"}):
            self.assertTrue(self.client.get("/climatechanges/api/chat/").json()["ai"])

    def test_without_a_key_it_answers_locally_and_never_calls_the_network(self):
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": ""}), mock.patch("urllib.request.urlopen") as net:
            data = post(self.client, [{"role": "user", "content": "where is the carbon footprint calculator?"}]).json()
        net.assert_not_called()
        self.assertEqual(data["source"], "local")
        self.assertIn("/climatechanges/carbon-footprint.html", data["reply"])

    def test_groq_reply_is_returned_cleaned_and_cached(self):
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = json.dumps({"choices": [{"message": {"content": "It is **warmer**."}}]}).encode()
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "k"}), mock.patch("urllib.request.urlopen", return_value=fake) as net:
            first = post(self.client, [{"role": "user", "content": "Is it warmer?"}]).json()
            second = post(self.client, [{"role": "user", "content": "Is it warmer?"}]).json()
        self.assertEqual(first["reply"], "It is warmer.")
        self.assertEqual((first["source"], second["source"]), ("groq", "cache"))
        self.assertEqual(net.call_count, 1)

    def test_request_sends_trimmed_history_and_a_token_cap(self):
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        history = [{"role": "user" if i % 2 == 0 else "assistant", "content": "x" * 300} for i in range(20)] + [{"role": "user", "content": "last"}]
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "k"}), mock.patch("urllib.request.urlopen", return_value=fake) as net:
            post(self.client, history)
        sent = json.loads(net.call_args[0][0].data)
        self.assertLessEqual(len(sent["messages"]), chatbot.MAX_HISTORY + 1)
        self.assertTrue(all(len(m["content"]) <= chatbot.MAX_CHARS for m in sent["messages"][1:]))
        self.assertEqual(sent["max_tokens"], chatbot.MAX_TOKENS)
        self.assertEqual(sent["messages"][-1]["content"], "last")

    def test_upstream_failure_falls_back(self):
        import urllib.error
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "k"}), mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            data = post(self.client, [{"role": "user", "content": "tell me about the quiz"}]).json()
        self.assertEqual(data["source"], "local")

    def test_visitor_limit_blocks_without_calling_the_api(self):
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            sources = [post(self.client, [{"role": "user", "content": f"q{i}"}]).json()["source"] for i in range(chatbot.VISITOR_LIMIT + 1)]
        self.assertEqual(sources[-1], "limit")

    def test_bad_input_is_rejected(self):
        self.assertEqual(self.client.post("/climatechanges/api/chat/", data="nope", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/climatechanges/api/chat/", data="x" * 9000, content_type="application/json").status_code, 413)
        self.assertEqual(post(self.client, [{"role": "system", "content": "x"}]).json()["reply"], "Please type a question.")

    def test_api_key_never_appears_in_responses_or_pages(self):
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "gsk_SECRET_VALUE"}):
            body = self.client.get("/climatechanges/api/chat/").content + self.client.get("/climatechanges/").content
        self.assertNotIn(b"gsk_SECRET_VALUE", body)
