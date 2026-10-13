import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
import test_locale_package as fixtures
import locale_package as package
import update_locale_candidate as upgrade


class UpgradeTests(unittest.TestCase):
    setUp=fixtures.PackageTests.setUp
    build=fixtures.PackageTests.build
    def prepare(self):
        self.build();target=self.root/'copy';package.apply(self.package,self.source,target)
        (self.source/'added.bin').write_bytes(b'original addition')
        (target/'added.bin').write_bytes(b'original addition')
        (target/'MC00.sav').write_bytes(b'untouched saved name')
        second=self.root/'second';second.mkdir()
        (second/'field.bin').write_bytes(b'new localization');(second/'added.bin').write_bytes(b'new addition')
        (second/'build.json').write_text(json.dumps(dict(source_unchanged=True,game_started=False,resources=[dict(resource=n,modified_sha256=package.sha((second/n).read_bytes())) for n in ['field.bin','added.bin']])),encoding='utf8')
        native=self.root/'native';shutil.copytree(self.runtime,native);(native/'workspace_profile.dll').write_bytes(b'new owned profile')
        new=self.root/'new-package';package.build(self.source,[second],native,self.scope,new)
        return target,new,self.root/'backup'

    def test_upgrade_addition_and_exact_rollback_preserve_save(self):
        target,new,backup=self.prepare();(target/'added.bin').chmod(0o444)
        original_mode=(target/'added.bin').stat().st_mode
        result=upgrade.apply(target,self.source,self.package,new,backup)
        self.assertEqual((target/'field.bin').read_bytes(),b'new localization');self.assertEqual((target/'added.bin').read_bytes(),b'new addition')
        self.assertEqual((target/'MC00.sav').read_bytes(),b'untouched saved name')
        upgrade.rollback(target,backup)
        self.assertEqual((target/'field.bin').read_bytes(),self.after);self.assertEqual((target/'added.bin').read_bytes(),b'original addition')
        self.assertEqual((target/'added.bin').stat().st_mode,original_mode)

    def test_upgrade_rejects_drift_before_writes(self):
        target,new,backup=self.prepare();(target/'added.bin').write_bytes(b'user edit')
        with self.assertRaises(ValueError):upgrade.apply(target,self.source,self.package,new,backup)
        self.assertEqual((target/'field.bin').read_bytes(),self.after);self.assertFalse(backup.exists())

    def test_injected_write_failure_restores_attempted_files(self):
        target,new,backup=self.prepare();original=Path.write_bytes
        def write(path,data):
            if path==target/'added.bin' and data==b'new addition':raise OSError('fixture write fault')
            return original(path,data)
        with patch.object(Path,'write_bytes',write):
            with self.assertRaises(OSError):upgrade.apply(target,self.source,self.package,new,backup)
        self.assertEqual((target/'field.bin').read_bytes(),self.after);self.assertEqual((target/'added.bin').read_bytes(),b'original addition')
