"""Core account ledger, escrow holds, and shadow honeypot ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any
import uuid


@dataclass
class BankAccount:
    account_id: str
    holder_name: str
    iban: str
    balance_aed: float
    daily_limit_aed: float
    daily_spent_aed: float = 0.0
    p95_transfer_aed: float = 12_000.0
    trusted_device_fp: str = "fp_iphone16_dubai_home"
    trusted_country: str = "AE"
    sleep_window_utc4: tuple[int, int] = (0, 5)  # 00:00 - 05:00 Dubai (UTC+4)
    frozen: bool = False


@dataclass
class EscrowHold:
    hold_id: str
    account_id: str
    amount_aed: float
    beneficiary_iban: str
    incident_id: str
    status: str = "HELD"  # HELD | CONFIRMED_FRAUD | RELEASED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TransferRecord:
    tx_id: str
    account_id: str
    beneficiary_iban: str
    amount_aed: float
    status: str
    is_shadow_decoy: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class BankLedger:
    """In-memory bank ledger for DubaiTrust Core."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.accounts: dict[str, BankAccount] = {}
        self.transfers: list[TransferRecord] = []
        self.shadow_transfers: list[TransferRecord] = []
        self.escrow_holds: dict[str, EscrowHold] = {}
        self.blocked_ibans: set[str] = {
            "CY17002001280000001200527600",  # known offshore mule cluster
            "GE29NB0000000101904917",
        }
        self.reset()

    def reset(self) -> None:
        self.accounts = {
            "acc_tariq_001": BankAccount(
                account_id="acc_tariq_001",
                holder_name="Tariq Al-Mansoori",
                iban="AE070331234567890123456",
                balance_aed=250_000.00,
                daily_limit_aed=50_000.00,
                p95_transfer_aed=14_500.00,
                trusted_device_fp="fp_iphone16_tariq_dubai",
            ),
            "acc_nadia_002": BankAccount(
                account_id="acc_nadia_002",
                holder_name="Nadia Al-Hashimi",
                iban="AE460090000000123456789",
                balance_aed=180_000.00,
                daily_limit_aed=50_000.00,
                p95_transfer_aed=9_200.00,
                trusted_device_fp="fp_macbook_nadia_difc",
            ),
            "acc_dmitry_003": BankAccount(
                account_id="acc_dmitry_003",
                holder_name="Dmitry Volkov",
                iban="AE210260001015523412301",
                balance_aed=115_000.00,
                daily_limit_aed=40_000.00,
                p95_transfer_aed=7_800.00,
                trusted_device_fp="fp_pixel9_dmitry_marina",
            ),
        }
        self.transfers = []
        self.shadow_transfers = []
        self.escrow_holds = {}

    def get_account(self, account_id: str) -> BankAccount:
        if account_id not in self.accounts:
            raise KeyError(f"Unknown account: {account_id}")
        return self.accounts[account_id]

    def debit(
        self,
        account_id: str,
        beneficiary_iban: str,
        amount_aed: float,
        metadata: dict[str, Any] | None = None,
    ) -> TransferRecord:
        account = self.get_account(account_id)
        if account.frozen:
            raise PermissionError("Account is frozen")
        if amount_aed <= 0:
            raise ValueError("Transfer amount must be positive")
        if account.balance_aed < amount_aed:
            raise ValueError("Insufficient funds")

        account.balance_aed = round(account.balance_aed - amount_aed, 2)
        account.daily_spent_aed = round(account.daily_spent_aed + amount_aed, 2)
        record = TransferRecord(
            tx_id=f"TX-{uuid.uuid4().hex[:10].upper()}",
            account_id=account_id,
            beneficiary_iban=beneficiary_iban,
            amount_aed=amount_aed,
            status="COMPLETED",
            is_shadow_decoy=False,
            metadata=metadata or {},
        )
        self.transfers.append(record)
        return record

    def create_escrow_hold(
        self,
        account_id: str,
        amount_aed: float,
        beneficiary_iban: str,
        incident_id: str,
    ) -> EscrowHold:
        hold = EscrowHold(
            hold_id=f"ESC-{uuid.uuid4().hex[:8].upper()}",
            account_id=account_id,
            amount_aed=amount_aed,
            beneficiary_iban=beneficiary_iban,
            incident_id=incident_id,
            status="HELD",
        )
        self.escrow_holds[hold.hold_id] = hold
        return hold

    def record_shadow_decoy(
        self,
        account_id: str,
        beneficiary_iban: str,
        amount_aed: float,
        metadata: dict[str, Any] | None = None,
    ) -> TransferRecord:
        """Records a synthetic decoy transaction for the attacker without touching real balance."""
        record = TransferRecord(
            tx_id=f"SHADOW-TX-{uuid.uuid4().hex[:8].upper()}",
            account_id=account_id,
            beneficiary_iban=beneficiary_iban,
            amount_aed=amount_aed,
            status="PROCESSING_SHADOW_DECOY",
            is_shadow_decoy=True,
            metadata=metadata or {},
        )
        self.shadow_transfers.append(record)
        return record

    def snapshot(self) -> dict[str, Any]:
        return {
            "accounts": [
                {
                    "account_id": a.account_id,
                    "holder_name": a.holder_name,
                    "iban": a.iban,
                    "balance_aed": a.balance_aed,
                    "daily_limit_aed": a.daily_limit_aed,
                    "daily_spent_aed": a.daily_spent_aed,
                    "frozen": a.frozen,
                    "trusted_device_fp": a.trusted_device_fp,
                }
                for a in self.accounts.values()
            ],
            "escrow_holds": [vars(h) for h in self.escrow_holds.values()],
            "transfers": [vars(t) for t in self.transfers[-20:]],
            "shadow_transfers": [vars(t) for t in self.shadow_transfers[-20:]],
            "blocked_ibans": sorted(self.blocked_ibans),
        }
