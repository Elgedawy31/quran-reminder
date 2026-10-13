"""Persistent sequential reading with preserved historical tafsir confirmations."""
from dataclasses import dataclass

TOTAL_AYAHS = 6236

@dataclass
class ReadingProgress:
    number: int = 1
    ayah_read: bool = False
    tafsir_read: bool = False
    tafsir_completed: int = 0

    @classmethod
    def from_record(cls, record):
        # The old shuffled app did not collect reading confirmations.
        if record.get("schema_version") not in (2, 3):
            return cls()
        number = record["number"]
        ayah_read = record["ayah_read"]
        tafsir_read = record["tafsir_read"]
        if type(number) is not int or not 1 <= number <= TOTAL_AYAHS:
            raise ValueError("Invalid ayah number in reading progress")
        if type(ayah_read) is not bool or type(tafsir_read) is not bool:
            raise ValueError("Reading confirmations must be boolean")
        tafsir_completed = number - 1 if record["schema_version"] == 2 else record["tafsir_completed"]
        if type(tafsir_completed) is not int or not 0 <= tafsir_completed <= number - 1:
            raise ValueError("Invalid historical tafsir count")
        return cls(number, ayah_read, tafsir_read, tafsir_completed)

    def to_record(self):
        return {"schema_version": 3, "number": self.number, "ayah_read": self.ayah_read, "tafsir_read": self.tafsir_read, "tafsir_completed": self.tafsir_completed}

    @property
    def ready(self):
        return self.ayah_read

    @property
    def read_count(self):
        return self.number - 1 + int(self.ayah_read)

    @property
    def tafsir_count(self):
        return self.tafsir_completed + int(self.tafsir_read)

    @property
    def complete_count(self):
        return self.number - 1 + int(self.ready)

    @property
    def percent_read(self):
        return self.read_count / TOTAL_AYAHS * 100

    @property
    def finished(self):
        return self.number == TOTAL_AYAHS and self.ready

    def advance(self):
        if not self.ready or self.number == TOTAL_AYAHS:
            return False
        self.number += 1
        self.tafsir_completed += int(self.tafsir_read)
        self.ayah_read = False
        self.tafsir_read = False
        return True

    def on_reminder(self, visible):
        # A visible verse never changes or closes on a timer.
        if not visible:
            self.advance()
        return self.number
