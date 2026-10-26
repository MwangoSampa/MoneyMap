"""
Offline-first storage (Unit 4 - Files) with security built in.

data/
  settings.json      PIN hash, lockout counter, wrapped encryption key (no money data)
  transactions.json  all transactions   - AES-256-GCM encrypted
  goals.json         survival plan + weekly goals - AES-256-GCM encrypted

Security design
- The PIN is never stored. We keep a salted scrypt hash to check it.
- A random 256-bit data key encrypts the money files. That key is itself encrypted ("wrapped")
  with a key derived from the PIN, so without the PIN the files cannot be read - even if the
  phone or laptop is stolen.
- AES-GCM also detects tampering: an edited file refuses to decrypt.
- Every save is atomic (write temp file -> replace), and the previous version is kept as .bak,
  so a crash or power cut mid-save can't destroy the data.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from models import SurvivalPlan, Transaction, WeeklyGoal

log = logging.getLogger("moneymap.storage")

SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 5 * 60
WEAK_PINS = {"12345", "54321", "11111", "00000", "12121", "13579", "24680", "01234", "98765", "56789"}


class StorageError(Exception):
    """A user-safe message about a storage problem."""


class WrongPin(StorageError):
    pass


class LockedOut(StorageError):
    pass


def pin_problem(pin):
    if not (isinstance(pin, str) and pin.isdigit() and len(pin) == 5):
        return "PIN must be exactly 5 numbers"
    if pin in WEAK_PINS or len(set(pin)) == 1:
        return "That PIN is too easy to guess - choose another"
    return None


def _b64(b):
    return base64.b64encode(b).decode()


def _unb64(s):
    return base64.b64decode(s.encode())


def _derive(pin, salt):
    return hashlib.scrypt(pin.encode(), salt=salt, dklen=32, **SCRYPT)


class Vault:
    """Reads and writes the data folder. Locked until unlock() or create() is called."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._dek = None   # data-encryption key, only in memory while unlocked

    # ------------------------------------------------------------- file helpers
    def path(self, name):
        return os.path.join(self.data_dir, name)

    def _atomic_write(self, name, obj):
        final = self.path(name)
        tmp = final + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(final):
            os.replace(final, final + ".bak")
        os.replace(tmp, final)

    def _read_json(self, name):
        """Read a JSON file; if it is damaged, fall back to the .bak copy."""
        for candidate in (self.path(name), self.path(name) + ".bak"):
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError):
                log.error("Damaged file %s - trying backup", os.path.basename(candidate))
        return None

    # ------------------------------------------------------------- settings / PIN
    @property
    def settings(self):
        return self._read_json("settings.json") or {}

    def is_set_up(self):
        return "pin_hash" in self.settings

    @property
    def unlocked(self):
        return self._dek is not None

    def create(self, pin, plan: SurvivalPlan):
        problem = pin_problem(pin)
        if problem:
            raise StorageError(problem)
        if self.is_set_up():
            raise StorageError("MoneyMap is already set up on this device")
        self._dek = os.urandom(32)
        self._write_settings_for_pin(pin, {"failed": 0, "locked_until": 0, "version": 1})
        self.save(transactions=[], plan=plan, goals={})
        log.debug("Created new vault in %s", self.data_dir)

    def _write_settings_for_pin(self, pin, base):
        pin_salt, kek_salt = os.urandom(16), os.urandom(16)
        kek = _derive(pin, kek_salt)
        nonce = os.urandom(12)
        wrapped = AESGCM(kek).encrypt(nonce, self._dek, b"dek")
        base.update({
            "pin_salt": _b64(pin_salt), "pin_hash": _b64(_derive(pin, pin_salt)),
            "kek_salt": _b64(kek_salt), "wrapped_key": _b64(nonce + wrapped), "kdf": dict(SCRYPT),
        })
        self._atomic_write("settings.json", base)

    def lock_remaining(self):
        return max(0, int(self.settings.get("locked_until", 0) - time.time()))

    def unlock(self, pin):
        s = self.settings
        remaining = self.lock_remaining()
        if remaining:
            raise LockedOut(f"Too many wrong PINs. Try again in {remaining // 60 + 1} min")
        candidate = _derive(str(pin), _unb64(s["pin_salt"]))
        if not hmac.compare_digest(candidate, _unb64(s["pin_hash"])):
            s["failed"] = s.get("failed", 0) + 1
            if s["failed"] >= MAX_ATTEMPTS:
                s["failed"], s["locked_until"] = 0, time.time() + LOCKOUT_SECONDS
                self._atomic_write("settings.json", s)
                raise LockedOut("Too many wrong PINs. MoneyMap is locked for 5 minutes")
            self._atomic_write("settings.json", s)
            raise WrongPin(f"Wrong PIN - {MAX_ATTEMPTS - s['failed']} tries left")
        raw = _unb64(s["wrapped_key"])
        self._dek = AESGCM(_derive(str(pin), _unb64(s["kek_salt"]))).decrypt(raw[:12], raw[12:], b"dek")
        if s.get("failed"):
            s["failed"] = 0
            self._atomic_write("settings.json", s)
        log.debug("Vault unlocked")

    def lock(self):
        self._dek = None
        log.debug("Vault locked")

    def change_pin(self, old_pin, new_pin):
        problem = pin_problem(new_pin)
        if problem:
            raise StorageError(problem)
        self.unlock(old_pin)   # proves the old PIN and loads the key
        s = self.settings
        self._write_settings_for_pin(new_pin, {"failed": 0, "locked_until": 0, "version": s.get("version", 1)})
        # the data key did not change, so the money files don't need re-encrypting

    # ------------------------------------------------------------- encrypted money files
    def _encrypt_file(self, name, payload):
        nonce = os.urandom(12)
        ct = AESGCM(self._dek).encrypt(nonce, json.dumps(payload).encode(), name.encode())
        self._atomic_write(name, {"format": "moneymap-encrypted-v1", "cipher": "AES-256-GCM",
                                  "data": _b64(nonce + ct)})

    def _decrypt_file(self, name, default):
        obj = self._read_json(name)
        if obj is None:
            return default
        raw = _unb64(obj["data"])
        try:
            return json.loads(AESGCM(self._dek).decrypt(raw[:12], raw[12:], name.encode()))
        except Exception:
            raise StorageError(f"{name} could not be read - it may have been changed outside MoneyMap")

    def _require_unlocked(self):
        if not self.unlocked:
            raise StorageError("MoneyMap is locked")

    def load(self):
        """Return (transactions, plan, goals)."""
        self._require_unlocked()
        tx_rows = self._decrypt_file("transactions.json", [])
        goals_obj = self._decrypt_file("goals.json", {})
        transactions = []
        for row in tx_rows:
            try:
                transactions.append(Transaction.from_dict(row))
            except (KeyError, ValueError) as e:   # skip one bad row instead of losing everything
                log.error("Skipped a bad transaction row: %s", e)
        plan = SurvivalPlan.from_dict(goals_obj.get("plan", {}))
        goals = {k: WeeklyGoal.from_dict(v) for k, v in goals_obj.get("weeks", {}).items()}
        log.debug("Loaded %d transactions, %d weekly goals", len(transactions), len(goals))
        return transactions, plan, goals

    def save(self, transactions, plan, goals):
        self._require_unlocked()
        self._encrypt_file("transactions.json", [t.to_dict() for t in transactions])
        self._encrypt_file("goals.json", {"plan": plan.to_dict(),
                                          "weeks": {k: g.to_dict() for k, g in goals.items()}})
        log.debug("Saved %d transactions, %d weekly goals", len(transactions), len(goals))

    # ------------------------------------------------------------- privacy (POPIA)
    def export_plain(self, filename="moneymap-export.json"):
        """User-requested readable copy of their own data."""
        transactions, plan, goals = self.load()
        out = {"plan": plan.to_dict(), "weekly_goals": {k: g.to_dict() for k, g in goals.items()},
               "transactions": [t.to_dict() for t in transactions]}
        path = self.path(filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        return path

    def erase_all(self, pin):
        self.unlock(pin)
        for name in os.listdir(self.data_dir):
            if name.endswith((".json", ".bak", ".tmp")):
                os.remove(os.path.join(self.data_dir, name))
        self._dek = None
