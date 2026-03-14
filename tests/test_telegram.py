import unittest

from topic_pitcher.telegram import TELEGRAM_TEXT_LIMIT, _chunk_message


class TelegramTests(unittest.TestCase):
    def test_short_message_is_not_split(self):
        message = "짧은 메시지"
        self.assertEqual(_chunk_message(message), [message])

    def test_long_message_is_split_with_part_labels(self):
        block = "1. 제목\n" + ("가" * 1200)
        message = "\n\n".join([block, block, block, block])
        chunks = _chunk_message(message)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].startswith("(1/"))
        self.assertTrue(chunks[-1].startswith("({}/{})".format(len(chunks), len(chunks))))
        self.assertTrue(all(len(chunk) < TELEGRAM_TEXT_LIMIT + 32 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
