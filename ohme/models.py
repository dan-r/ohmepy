"""Data models for Ohme API."""

from enum import Enum

from typing import TypedDict, Optional, List

from dataclasses import dataclass


class ChargerStatus(Enum):
    """Charger state enum."""

    UNPLUGGED = "unplugged"
    PENDING_APPROVAL = "pending_approval"
    CHARGING = "charging"
    PLUGGED_IN = "plugged_in"
    PAUSED = "paused"
    FINISHED = "finished"


class ChargerMode(Enum):
    """Charger mode enum."""

    SMART_CHARGE = "smart_charge"
    MAX_CHARGE = "max_charge"
    PAUSED = "paused"


class SummaryGranularity(Enum):
    """Granularity for charge summary data."""

    DAY = "DAY"
    HOUR = "HOUR"
    WEEK = "WEEK"
    MONTH = "MONTH"


class Money(TypedDict):
    currencyCode: str
    amount: str


class CarbonStats(TypedDict, total=False):
    carbonReleasedGreenScore: float
    carbonReleasedPerKmGrams: int
    carbonReleasedGrams: int
    carbonReleasedRegularCableGrams: int
    carbonSavedVsRegularCableGrams: int
    carbonReleasedGasCarGrams: int
    carbonSavedVsGasCarGrams: int
    comparedGasCarLabel: Optional[str]


class CostStats(TypedDict):
    moneyCostTotal: Money
    moneyCostStandardTariff: Money
    moneySavedVsStandardTariff: Money
    moneyCostPerKm: Money
    averageKwhPrice: Money


class BatteryStats(TypedDict):
    batteryScore: float
    batteryCycleUsePercent: int
    rangeAddedKm: float


class ChargeStat(TypedDict):
    ownerUserId: str
    deviceId: Optional[str]
    energyChargedTotalWh: int
    solarEnergyChargedWh: int
    startTime: int
    endTime: int
    activeChargeMs: int
    location: Optional[str]
    locationType: Optional[str]
    carbonStats: CarbonStats
    costStats: CostStats
    batteryStats: BatteryStats


class ChargeSummary(TypedDict):
    totalStats: ChargeStat
    stats: List[ChargeStat]
    granularity: SummaryGranularity


@dataclass
class ChargerPower:
    """Dataclass for reporting power status of charger."""

    watts: float
    amps: float
    volts: int | None
