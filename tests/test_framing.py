"""Unit tests for the length-prefix FrameDecoder (no sockets involved)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from protocol import (  # noqa: E402
    FrameDecoder, FrameTooLarge, ProtocolError, encode_frame, parse_payload, HEADER_STRUCT,
)


class TestFrameDecoder(unittest.TestCase):
    def test_single_frame(self):
        d = FrameDecoder()
        frames = d.feed(encode_frame({"type": "PING"}))
        self.assertEqual([parse_payload(f) for f in frames], [{"type": "PING"}])
        self.assertEqual(d.buffered, 0)

    def test_combined_frames_in_one_read(self):
        msgs = [{"type": "BROADCAST", "content": f"m{i}"} for i in range(5)]
        d = FrameDecoder()
        frames = d.feed(b"".join(encode_frame(m) for m in msgs))
        self.assertEqual([parse_payload(f) for f in frames], msgs)

    def test_every_split_point_including_inside_utf8(self):
        # 'é' and the emoji are multi-byte in UTF-8, so some cuts fall inside a character
        msgs = [{"type": "BROADCAST", "content": "café ☕ héllo"}, {"type": "PING"}]
        stream = b"".join(encode_frame(m) for m in msgs)
        for cut in range(len(stream) + 1):
            d = FrameDecoder()
            frames = d.feed(stream[:cut]) + d.feed(stream[cut:])
            self.assertEqual([parse_payload(f) for f in frames], msgs, f"cut at {cut}")
            self.assertEqual(d.buffered, 0)

    def test_byte_by_byte(self):
        msg = {"type": "DIRECT", "target": "bob", "content": "one byte at a time"}
        d = FrameDecoder()
        out = []
        for b in encode_frame(msg):
            out += d.feed(bytes([b]))
        self.assertEqual([parse_payload(f) for f in out], [msg])

    def test_partial_frame_stays_buffered(self):
        frame = encode_frame({"type": "PING"})
        d = FrameDecoder()
        self.assertEqual(d.feed(frame[:-1]), [])
        self.assertEqual(d.buffered, len(frame) - 1)
        self.assertEqual(len(d.feed(frame[-1:])), 1)

    def test_oversized_frame_rejected(self):
        d = FrameDecoder(max_frame=100)
        with self.assertRaises(FrameTooLarge):
            d.feed(HEADER_STRUCT.pack(101))

    def test_parse_payload_errors(self):
        for raw in [b"\xff\xfe", b"not json", b"[1, 2]", b'{"no_type": 1}', b'{"type": 5}']:
            with self.assertRaises(ProtocolError, msg=raw):
                parse_payload(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
