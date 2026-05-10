import unittest

from app.tools.openai_client import extract_output_text


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
