"""Domaenentypen, die in allen Schichten verwendet werden."""

from __future__ import annotations

from enum import StrEnum


class Frequency(StrEnum):
    """Beobachtungsfrequenz einer Preiszeitreihe."""

    DAILY = "daily"
    SNAPSHOT_AM = "snapshot_am"
    SNAPSHOT_PM = "snapshot_pm"


class PriceField(StrEnum):
    """Welches Preisfeld eine Berechnung oder Grafik verwendet."""

    CLOSE = "close"
    ADJ_CLOSE = "adj_close"


class YScale(StrEnum):
    """Skalierung der Y-Achse eines Kurscharts."""

    LINEAR = "linear"
    LOG = "log"


class TrendType(StrEnum):
    """Unterstuetzte Trendregressionen (siehe analytics.regression)."""

    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    LOG2 = "log2"


class QualityStatus(StrEnum):
    """Datenqualitaetsstatus einer einzelnen Beobachtung."""

    OK = "ok"
    FLAGGED = "flagged"
    MISSING = "missing"


class JobStatus(StrEnum):
    """Status eines Batch-Laufs oder Laufschritts in ops.job_runs."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
