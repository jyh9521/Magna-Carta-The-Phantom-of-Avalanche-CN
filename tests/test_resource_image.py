import sys
from dataclasses import replace
from pathlib import Path
import struct
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import resource_image as m


def tga(offset=24, width=2, height=2):
    header = bytearray(18)
    header[2] = 2
    struct.pack_into('<HHHH', header, 8, 7, 11, width, height)
    header[16:18] = b'\x20\x08'
    bitmap = bytes([1, 2, 3, 4]) * (width * height)
    return b'W' * offset + bytes(header) + bitmap + m.TGA_FOOTER


def bmp(width=3, height=2):
    stride = ((width * 3 + 3) // 4) * 4
    header = bytearray(54)
    header[:2] = b'BM'
    struct.pack_into('<I', header, 2, 54 + stride * height + 2)
    header[6:10] = b'abcd'
    struct.pack_into('<IIiiHHII', header, 10, 54, 40, width, height, 1, 24, 0, 0)
    header[38:54] = bytes(range(16))
    bitmap = (bytes([1, 2, 3]) * width + b'P' * (stride - width * 3)) * height
    return b'X' * 24 + bytes(header) + bitmap + b'\0\0'


class ImageTests(unittest.TestCase):
    def test_all_observed_tga_wrapper_sizes(self):
        for offset in (12, 24, 40, 56):
            data = tga(offset)
            image = m.parse(data)
            self.assertEqual(len(image.wrapper), offset)
            self.assertEqual(image.to_bytes(), data)
            self.assertEqual(image.replace_rgba(image.rgba()).to_bytes(), data)

    def test_tga_bottom_origin_bgra(self):
        image = m.parse(tga(width=1, height=2))
        image = replace(image, bitmap=bytes([1, 2, 3, 4, 5, 6, 7, 8]))
        self.assertEqual(image.rgba(), bytes([7, 6, 5, 8, 3, 2, 1, 4]))

    def test_tga_replace_changes_only_pixels(self):
        original = m.parse(tga(56))
        replacement = bytes(range(16))
        modified = original.replace_rgba(replacement)
        self.assertEqual(modified.rgba(), replacement)
        self.assertEqual(modified.wrapper, original.wrapper)
        self.assertEqual(modified.header, original.header)
        self.assertEqual(modified.suffix, original.suffix)
        self.assertNotEqual(modified.bitmap, original.bitmap)

    def test_bmp_unknown_bytes_and_padding_preserved(self):
        for width in (1, 2, 3, 4):
            data = bmp(width)
            image = m.parse(data)
            self.assertEqual(image.to_bytes(), data)
            modified = image.replace_rgba(b'\x12\x34\x56\xff' * width * 2)
            self.assertEqual(modified.wrapper, image.wrapper)
            self.assertEqual(modified.header, image.header)
            for y in range(2):
                start = y * image.stride + width * 3
                end = (y + 1) * image.stride
                self.assertEqual(modified.bitmap[start:end], image.bitmap[start:end])

    def test_bmp_bottom_origin_bgr_opaque(self):
        image = m.parse(bmp(1, 2))
        image = replace(image, bitmap=bytes([1, 2, 3, 80, 5, 6, 7, 81]))
        self.assertEqual(image.rgba(), bytes([7, 6, 5, 255, 3, 2, 1, 255]))

    def test_bmp_alpha_rejected_instead_of_silently_discarded(self):
        with self.assertRaises(ValueError):
            m.parse(bmp()).replace_rgba(b'\0' * 24)

    def test_bmp_observed_two_byte_suffix_required_and_preserved(self):
        image = m.parse(bmp())
        self.assertEqual(image.suffix, b'\0\0')
        self.assertEqual(image.replace_rgba(image.rgba()).suffix, image.suffix)
        for data in (bmp()[:-2], bmp()[:-1] + b'X'):
            with self.assertRaises(ValueError):
                m.parse(data)

    def test_tga_transparent_rgb_preserved(self):
        image = m.parse(tga())
        pixels = b'\x90\x80\x70\0' * 4
        modified = image.replace_rgba(pixels)
        self.assertEqual(modified.rgba(), pixels)
        self.assertEqual(modified.replace_rgba(modified.rgba()).to_bytes(), modified.to_bytes())

    def test_replacement_length_and_type_rejected(self):
        image = m.parse(tga())
        for pixels in (b'', b'\0' * 17, 'pixels', 16):
            with self.assertRaises(ValueError):
                image.replace_rgba(pixels)

    def test_truncation_and_trailing_data_rejected(self):
        for data in (tga()[:20], tga()[:-1], tga() + b'\0', bmp()[:-1], bmp() + b'\0'):
            with self.assertRaises(ValueError):
                m.parse(data)

    def test_tga_variant_rejections(self):
        for offset, value in ((0, 1), (1, 1), (2, 10), (3, 1), (16, 24), (17, 40)):
            data = bytearray(tga())
            data[24 + offset] = value
            with self.assertRaises(ValueError):
                m.parse(data)

    def test_tga_footer_and_extension_rejected(self):
        data = bytearray(tga())
        data[-26] = 1
        with self.assertRaises(ValueError):
            m.parse(data)

    def test_invalid_tga_dimensions_rejected(self):
        for width in (0, 4097):
            data = bytearray(tga())
            struct.pack_into('<H', data, 24 + 12, width)
            with self.assertRaises(ValueError):
                m.parse(data)

    def test_bmp_variant_rejections(self):
        for offset, fmt, value in ((10, '<I', 55), (14, '<I', 108), (26, '<H', 2),
                                   (28, '<H', 32), (30, '<I', 1), (34, '<I', 24),
                                   (2, '<I', 0), (18, '<i', 0), (22, '<i', -2)):
            data = bytearray(bmp())
            struct.pack_into(fmt, data, 24 + offset, value)
            with self.assertRaises(ValueError):
                m.parse(data)

    def test_bare_images_and_txrs_wrapper_not_supported(self):
        for data in (tga()[24:], bmp()[24:], b'Z' * 32 + tga()[24:]):
            with self.assertRaises(ValueError):
                m.parse(data)

    def test_metadata_inconsistency_rejected(self):
        with self.assertRaises(ValueError):
            replace(m.parse(tga()), width=99).to_bytes()

    def test_buffer_inputs_and_invalid_input(self):
        self.assertEqual(m.parse(memoryview(tga())), m.parse(bytearray(tga())))
        for data in (None, '', 20):
            with self.assertRaises(ValueError):
                m.parse(data)

    def test_inspect_static_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            (source / '0001.BGR').write_bytes(tga())
            (source / '0002.BGR').write_bytes(bmp())
            result = m.inspect(source)
            self.assertEqual(len(result['files']), 2)
            self.assertFalse(result['game_started'])
            self.assertTrue(all(row['roundtrip_exact'] for row in result['files']))
            self.assertEqual((source / '0001.BGR').read_bytes(), tga())

    def test_empty_inspect_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                m.inspect(temp)


if __name__ == '__main__':
    unittest.main()
