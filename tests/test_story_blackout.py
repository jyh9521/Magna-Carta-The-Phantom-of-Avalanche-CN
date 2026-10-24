import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from audit_story_blackout import opening_matches


class StoryBlackoutTests(unittest.TestCase):
    def fixture(self):
        rows = [dict(opcode=1, parameters=[0]*14) for _ in range(30)]
        for index, opcode, params in [(1,503,[8,1,0,0,100]), (6,603,[470,1]),
                (8,603,[471,1]), (10,507,[30,0]), (11,603,[472,1]),
                (29,700,[10002,101,0,100,0,3,5,1342,80])]:
            rows[index] = dict(opcode=opcode, parameters=params+[0]*(14-len(params)))
        return rows

    def test_intended_opening(self):
        self.assertTrue(opening_matches(self.fixture()))

    def test_not_a_black_target(self):
        rows = copy.deepcopy(self.fixture()); rows[1]['parameters'][4] = 0
        self.assertFalse(opening_matches(rows))

    def test_no_release_instruction(self):
        rows = copy.deepcopy(self.fixture()); rows[10]['opcode'] = 2
        self.assertFalse(opening_matches(rows))

    def test_earlier_regular_dialogue_not_sound_only(self):
        rows = copy.deepcopy(self.fixture()); rows[7]['opcode'] = 700
        self.assertFalse(opening_matches(rows))

    def test_truncated(self):
        self.assertFalse(opening_matches(self.fixture()[:12]))


if __name__ == '__main__':
    unittest.main()
