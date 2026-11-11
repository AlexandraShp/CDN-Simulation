
from dataclasses import dataclass


@dataclass
class ServerWorkload:
    server_id: int
    capacity: float
    remaining_work: float = 0.0

    def estimated_waiting_time(self):
        if self.capacity <= 0:
            raise ValueError("Capacity must be positive")

        return self.remaining_work / self.capacity

    def add_request(self, work_units=1.0):
        if work_units <= 0:
            raise ValueError("Work units must be positive")

        self.remaining_work += work_units

    def complete_work(self, work_units=1.0):
        if work_units <= 0:
            raise ValueError("Work units must be positive")

        self.remaining_work = max(
            0.0,
            self.remaining_work - work_units
        )
