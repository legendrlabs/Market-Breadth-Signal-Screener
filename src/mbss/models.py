from dataclasses import dataclass, field
import pandas as pd


@dataclass(frozen=True)
class Event:
    signal: str
    date: pd.Timestamp
    components: tuple[str, ...] = field(default_factory=tuple)
    definition: str = 'primary'

    def record(self):
        return {'signal': self.signal, 'signal_date': self.date.date().isoformat(),
                'components': list(self.components), 'definition': self.definition}
