import unittest
from progress import ReadingProgress, TOTAL_AYAHS

class ReadingProgressTests(unittest.TestCase):
    def test_old_random_visits_do_not_count_as_reading(self):
        progress = ReadingProgress.from_record({"number": 2534, "seed": 123, "cursor": 3})
        self.assertEqual((progress.number, progress.read_count, progress.tafsir_count), (1, 0, 0))

    def test_unread_verse_cannot_advance(self):
        for ayah, tafsir in [(False, False), (False, True)]:
            progress = ReadingProgress(1, ayah, tafsir)
            self.assertFalse(progress.advance())
            self.assertEqual(progress.on_reminder(visible=False), 1)

    def test_reading_confirmation_alone_allows_exactly_one_step(self):
        progress = ReadingProgress(7, True, False)
        self.assertTrue(progress.advance())
        self.assertEqual(progress.number, 8)
        self.assertEqual((progress.ayah_read, progress.tafsir_read), (False, False))
        self.assertFalse(progress.advance())

    def test_visible_completed_verse_stays_on_screen(self):
        progress = ReadingProgress(1, True, False)
        self.assertEqual(progress.on_reminder(visible=True), 1)
        self.assertEqual(progress.on_reminder(visible=True), 1)

    def test_hiding_unread_verse_preserves_place(self):
        progress = ReadingProgress(1, False, False)
        progress.on_reminder(visible=False)
        self.assertEqual((progress.number, progress.ayah_read, progress.tafsir_read), (1, False, False))

    def test_hidden_completed_verse_advances_on_next_reminder(self):
        progress = ReadingProgress(1, True, False)
        self.assertEqual(progress.on_reminder(visible=False), 2)

    def test_progress_survives_restart_with_partial_confirmation(self):
        progress = ReadingProgress.from_record(ReadingProgress(100, True, False, 6).to_record())
        self.assertEqual((progress.read_count, progress.tafsir_count, progress.complete_count), (100, 6, 100))
        self.assertAlmostEqual(progress.percent_read, 100 / TOTAL_AYAHS * 100)

    def test_finishing_quran_never_wraps_or_discards_progress(self):
        progress = ReadingProgress(TOTAL_AYAHS, True, False)
        self.assertTrue(progress.finished)
        self.assertFalse(progress.advance())
        self.assertEqual(progress.on_reminder(visible=False), TOTAL_AYAHS)
        self.assertEqual(progress.percent_read, 100)

    def test_existing_progress_migrates_without_inventing_tafsir_reading(self):
        for tafsir_read in (False, True):
            progress = ReadingProgress.from_record({"schema_version": 2, "number": 7, "ayah_read": True, "tafsir_read": tafsir_read})
            self.assertEqual(progress.read_count, 7)
            self.assertEqual(progress.tafsir_count, 6 + int(tafsir_read))
            progress.advance()
            progress.ayah_read = True
            progress.advance()
            restored = ReadingProgress.from_record(progress.to_record())
            self.assertEqual(restored.read_count, 8)
            self.assertEqual(restored.tafsir_count, 6 + int(tafsir_read))

    def test_corrupt_current_schema_does_not_silently_reset_progress(self):
        for record in [
            {"schema_version": 2, "number": 0, "ayah_read": True, "tafsir_read": True},
            {"schema_version": 2, "number": 1, "ayah_read": "false", "tafsir_read": False},
        ]:
            with self.assertRaises(ValueError):
                ReadingProgress.from_record(record)

if __name__ == "__main__":
    unittest.main()
