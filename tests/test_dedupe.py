"""Tests for utils.dedupe — hashing and normalisation helpers."""

from __future__ import annotations

import pytest

from utils import compute_hash, normalize


class TestNormalize:
    def test_lowercases(self) -> None:
        assert normalize("HELLO") == "hello"

    def test_strips_whitespace(self) -> None:
        assert normalize("  hello  ") == "hello"

    def test_removes_accents(self) -> None:
        assert normalize("développeur") == "developpeur"
        assert normalize("Île-de-France") == "ile-de-france"

    def test_combined(self) -> None:
        assert normalize("  Développeur BACKEND  ") == "developpeur backend"


class TestComputeHash:
    def test_same_inputs_same_hash(self) -> None:
        h1 = compute_hash("Dev Backend", "Acme", "Paris")
        h2 = compute_hash("Dev Backend", "Acme", "Paris")
        assert h1 == h2

    def test_different_inputs_different_hash(self) -> None:
        h1 = compute_hash("Dev Backend", "Acme", "Paris")
        h2 = compute_hash("Dev Frontend", "Acme", "Paris")
        assert h1 != h2

    def test_case_insensitive(self) -> None:
        h1 = compute_hash("Dev Backend", "ACME", "PARIS")
        h2 = compute_hash("dev backend", "acme", "paris")
        assert h1 == h2

    def test_accent_insensitive(self) -> None:
        h1 = compute_hash("Développeur", "Société", "Marseille")
        h2 = compute_hash("developpeur", "societe", "marseille")
        assert h1 == h2

    def test_returns_hex_string(self) -> None:
        h = compute_hash("title", "company", "location")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest
