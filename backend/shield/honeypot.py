"""Track 1: Autonomous Shadow Honeypot & Protected Escrow Controller.

Instead of alerting the attacker with a hard HTTP 403, Aegis 2AM:
1. Locks the real customer funds in Protected Escrow (0 AED lost while customer sleeps).
2. Serves the attacker a convincing synthetic decoy transaction from a shadow ledger.
3. Harvests attacker telemetry (IP, device fingerprint, replay token, mule IBAN, TTPs)
   to feed directly into Track 2 (Bank Immune System).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.bank.ledger import BankLedger, EscrowHold, TransferRecord


@dataclass
class HoneypotCapture:
    decoy_tx_id: str
    attacker_ip: str
    attacker_country: str
    device_fp: str
    mule_iban: str
    replayed_token: str | None
    ttp_tags: list[str]
    attacker_response_seen: dict[str, Any]
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ClientShieldController:
    """Coordinates Escrow Holds and Shadow Honeypot deception for customer accounts."""

    def divert_to_honeypot(
        self,
        *,
        ledger: BankLedger,
        incident_id: str,
        account_id: str,
        amount_aed: float,
        beneficiary_iban: str,
        attacker_ip: str,
        attacker_country: str,
        device_fp: str,
        kyc_token: str | None,
        ttp_tags: list[str],
    ) -> tuple[EscrowHold, HoneypotCapture, TransferRecord]:
        # 1. Protect customer's real balance in escrow (balance untouched)
        hold = ledger.create_escrow_hold(
            account_id=account_id,
            amount_aed=amount_aed,
            beneficiary_iban=beneficiary_iban,
            incident_id=incident_id,
        )

        # 2. Record decoy transaction in shadow ledger so attacker stays engaged
        decoy_tx = ledger.record_shadow_decoy(
            account_id=account_id,
            beneficiary_iban=beneficiary_iban,
            amount_aed=amount_aed,
            metadata={
                "incident_id": incident_id,
                "attacker_ip": attacker_ip,
                "device_fp": device_fp,
            },
        )

        # 3. Synthesize realistic fake confirmation sent back to attacker
        attacker_response = {
            "status": "QUEUED_FOR_SETTLEMENT",
            "reference": decoy_tx.tx_id,
            "amount_aed": amount_aed,
            "beneficiary_iban": beneficiary_iban,
            "estimated_clearing": "02:15 GMT+4",
            "_internal_note": "SHADOW_HONEYPOT_ACTIVE — real customer balance untouched",
        }

        capture = HoneypotCapture(
            decoy_tx_id=decoy_tx.tx_id,
            attacker_ip=attacker_ip,
            attacker_country=attacker_country,
            device_fp=device_fp,
            mule_iban=beneficiary_iban,
            replayed_token=kyc_token,
            ttp_tags=ttp_tags,
            attacker_response_seen=attacker_response,
        )
        return hold, capture, decoy_tx

    def resolve_morning_decision(
        self,
        *,
        ledger: BankLedger,
        hold_id: str,
        action: str,
    ) -> dict[str, Any]:
        hold = ledger.escrow_holds.get(hold_id)
        if not hold:
            raise KeyError(f"Escrow hold {hold_id} not found")

        account = ledger.get_account(hold.account_id)
        if action == "confirm_fraud":
            hold.status = "CONFIRMED_FRAUD"
            ledger.blocked_ibans.add(hold.beneficiary_iban)
            return {
                "hold_id": hold.hold_id,
                "status": hold.status,
                "message": (
                    f"Fraud confirmed by {account.holder_name}. AED {hold.amount_aed:,.2f} remains safely in account; "
                    f"mule IBAN {hold.beneficiary_iban} permanently blacklisted across network."
                ),
                "account_balance_aed": account.balance_aed,
            }
        elif action == "approve_transfer":
            hold.status = "RELEASED"
            tx = ledger.debit(
                account_id=hold.account_id,
                beneficiary_iban=hold.beneficiary_iban,
                amount_aed=hold.amount_aed,
                metadata={"approved_by_customer_morning_override": True},
            )
            return {
                "hold_id": hold.hold_id,
                "status": hold.status,
                "tx_id": tx.tx_id,
                "message": f"Transfer released by {account.holder_name}. TX {tx.tx_id} settled.",
                "account_balance_aed": account.balance_aed,
            }
        else:
            raise ValueError("action must be 'confirm_fraud' or 'approve_transfer'")
