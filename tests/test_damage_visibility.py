"""Production numeric popup visibility pointer hook and exact rollback ABI."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
BRIDGE=ROOT/'build/native/Release/damage-render-fixture/damage_projection_bridge.exe'


@unittest.skipUnless(BRIDGE.is_file(),'Build the owned damage projection bridge')
class NumericVisibility(unittest.TestCase):
    def run_visibility(self,options=()):
        result=subprocess.run([str(BRIDGE),str(BRIDGE.parent/'AsrD3DDrv.dll'),*options],
                              input='visibility -1 0 0 3 0 0 0\nvisibility 0 -1 -1 3 -1 -1 -1\n',
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        rows=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertTrue(all(r['abi_error_bits']==0 and not r['game_started'] for r in rows))
        return rows

    def test_digit_children_follow_hide_and_show(self):
        hidden,shown=self.run_visibility()
        self.assertEqual([hidden['popup'],hidden['number'],*hidden['digits']],[-1]*5)
        self.assertEqual([shown['popup'],shown['number'],*shown['digits']],[0]*5)

    def test_native_and_rollback_restore_unsynchronised_digits(self):
        for option in ('--native','--rollback'):
            with self.subTest(option=option):
                hidden,shown=self.run_visibility((option,))
                self.assertEqual([hidden['popup'],hidden['number'],*hidden['digits']],[-1,0,0,0,0])
                self.assertEqual([shown['popup'],shown['number'],*shown['digits']],[0,-1,-1,-1,-1])
                self.assertEqual(hidden['rollback_exact'],option=='--rollback')


if __name__=='__main__':unittest.main()
