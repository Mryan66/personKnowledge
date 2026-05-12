import unittest

from app.tools.openai_client import extract_output_text, extract_stream_text_delta, iter_sse_text_deltas


class OpenAIClientTests(unittest.TestCase):
    def test_extract_output_text_from_convenience_field(self):
        text = extract_output_text({"output_text": " hello "})

        self.assertEqual(text, "hello")

    def test_extract_output_text_from_output_items(self):
        text = extract_output_text(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "第一段"},
                            {"type": "text", "text": "第二段"},
                        ]
                    }
                ]
            }
        )

        self.assertEqual(text, "第一段\n第二段")

    def test_extract_stream_text_delta(self):
        delta = extract_stream_text_delta({"type": "response.output_text.delta", "delta": "你好"})

        self.assertEqual(delta, "你好")

    def test_iter_sse_text_deltas(self):
        response = [
            b"event: response.output_text.delta\n",
            '{"type":"response.output_text.delta","delta":"你"}\n'.encode("utf-8").join([b"data: ", b""]),
            b"\n",
            '{"type":"response.output_text.delta","delta":"好"}\n'.encode("utf-8").join([b"data: ", b""]),
            b"\n",
            b"data: [DONE]\n",
            b"\n",
        ]

        deltas = list(iter_sse_text_deltas(response))

        self.assertEqual(deltas, ["你", "好"])
