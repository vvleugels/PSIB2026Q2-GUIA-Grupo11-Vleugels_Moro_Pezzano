"""Inventory accepts video names independently of their experimental type."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from psib.video_io import list_videos, record_type


class VideoInventoryTests(unittest.TestCase):
    def test_arbitrary_names_formats_case_and_nonfiles(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            names=['grabacion.mp4','ojo con luz.MOV','ensayo.avi','otra.mkv','A_1.mp4']
            for name in names+['notes.txt','video.mp4.bak']:
                (root/name).touch()
            (root/'folder.mp4').mkdir()
            self.assertEqual([p.name for p in list_videos(root)],sorted(names,key=str.lower))

    def test_record_type_is_optional_filename_convention(self):
        for name in ['A_1.mp4','a_otra.MOV']:
            self.assertEqual(record_type(name),'A')
        self.assertEqual(record_type('B_2.avi'),'B')
        for name in ['grabacion.mp4','birthday.mov','archivo.avi']:
            self.assertEqual(record_type(name),'?')


if __name__=='__main__':unittest.main()
