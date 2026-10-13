import copy
import struct
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import resource_bink as m


def fixture(tracks=1,frames=3):
    header=b'BIKi'+struct.pack('<10I',0,frames,0,frames,64,48,24,1,0,tracks)+bytes(12*tracks)
    table=dict(header=header,frames=[dict(audio=[struct.pack('<I',4)+struct.pack('<I',i*2)]*tracks,
                                         video=bytes([32+i])*12,key=1 if i==0 else 0) for i in range(frames)])
    return m.rebuild(table)


class BinkContainerTests(unittest.TestCase):
    def test_original_container_byte_roundtrip(self):
        for tracks in (0,1,2):
            raw=fixture(tracks);self.assertEqual(m.rebuild(m.parse(raw)),raw)

    def test_replacement_keeps_audio_packets_and_metadata_exact(self):
        original=fixture();video=fixture(0);table=m.parse(video);table['frames'][1]['video']=b'X'*12;video=m.rebuild(table)
        changed=m.replace_video(original,video)
        self.assertEqual(m.audio_digest(original),m.audio_digest(changed))
        self.assertEqual(m.parse(changed)['frames'][1]['video'],b'X'*12)
        self.assertEqual(m.parse(original)['header'][40:],m.parse(changed)['header'][40:])

    def test_fixed_member_allocation_is_exact_and_distributed(self):
        original=fixture();video=fixture(0)
        changed=m.replace_video(original,video,len(original)+24)
        self.assertEqual(len(changed),len(original)+24)
        self.assertEqual(m.audio_digest(original),m.audio_digest(changed))
        lengths=[len(f['video']) for f in m.parse(changed)['frames']]
        self.assertEqual(lengths,[20,20,20])

    def test_revision_count_offsets_and_audio_overflow_rejected(self):
        raw=fixture()
        for offset,value in [(0,0),(8,0),(16,4),(20,0),(28,0),(40,300),(56,2)]:
            bad=bytearray(raw);struct.pack_into('<I',bad,offset,value)
            with self.assertRaises(ValueError):m.parse(bytes(bad))
        bad=bytearray(raw);start=m.parse(raw)['header'];first=struct.unpack_from('<I',raw,len(start))[0]&~1
        struct.pack_into('<I',bad,first,0xffffffff)
        with self.assertRaises(ValueError):m.parse(bytes(bad))

    def test_truncated_streams_and_unexpected_padding_are_rejected(self):
        raw=fixture()
        for length in (0,4,43,len(raw)-1):
            with self.assertRaises(ValueError):m.parse(raw[:length])
        with self.assertRaises(ValueError):m.parse(raw+b'\0\0')

    def test_video_replacement_cannot_change_rate_geometry_or_audio(self):
        original=fixture()
        with self.assertRaises(ValueError):m.replace_video(original,original)
        for offset,value in [(20,65),(24,49),(28,25),(36,1)]:
            video=bytearray(fixture(0));struct.pack_into('<I',video,offset,value)
            with self.assertRaises(ValueError):m.replace_video(original,bytes(video))

    def test_unknown_or_insufficient_member_capacity_rejected(self):
        for size in (1,True,len(fixture())+1):
            with self.assertRaises(ValueError):m.replace_video(fixture(),fixture(0),size)

    def test_concatenated_members_keep_independent_offsets(self):
        a,b=fixture(0),fixture(1)
        rows=m.members(a+b);self.assertEqual(rows,[(0,a),(len(a),b)])
        with self.assertRaises(ValueError):m.members(a+b[:-1])


if __name__=='__main__':unittest.main()
