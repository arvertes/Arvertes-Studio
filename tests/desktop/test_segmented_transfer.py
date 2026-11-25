from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from arvertes_desktop.segmented_transfer import MIB, Segments, describe


class TransferTests(TestCase):
    def test_restart_resume_and_reject_altered_segment(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            a, b = b"a"*MIB, b"b"*MIB
            source.write_bytes(a+b+b"end")
            storage = root / "store"
            begin = Segments(storage,8*MIB)
            identifier = begin.begin(describe(source,MIB))
            self.assertEqual(begin.copy_missing(identifier,source,max_parts=1)["missing"],[1,2])
            resumed = Segments(storage,8*MIB)
            with self.assertRaises(ValueError):
                resumed.finalize(identifier)
            source.write_bytes(a+b"a"*MIB+b"end")
            with self.assertRaises(ValueError):
                resumed.copy_missing(identifier,source)
            self.assertEqual(resumed.status(identifier)["missing"],[1,2])
            source.write_bytes(a+b+b"end")
            self.assertEqual(resumed.copy_missing(identifier,source)["missing"],[])
            self.assertEqual(sha256(resumed.finalize(identifier).read_bytes()).hexdigest(),
                             sha256(source.read_bytes()).hexdigest())
            self.assertEqual(resumed.status(identifier)["state"],"complete")

    def test_reservation_atomic_across_concurrent_clients(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root/"a",root/"b"]
            for index,path in enumerate(paths):
                path.write_bytes(bytes([index])*(MIB+32))
            storage = root/"store"
            Segments(storage,3*MIB)
            with ThreadPoolExecutor(max_workers=2) as pool:
                def reserve(path):
                    try:
                        return Segments(storage,3*MIB).begin(describe(path,MIB))
                    except ValueError:
                        return None
                self.assertEqual(sum(value is not None for value in pool.map(reserve,paths)),1)
