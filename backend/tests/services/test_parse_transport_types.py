"""Unit tests for parse_transport_types function."""

from app.services.mvg_client import parse_transport_types, TransportType


def test_parse_transport_types_deduplication_and_order_preservation() -> None:
    """Test that parse_transport_types deduplicates while preserving order."""
    # Input with duplicates and synonym collisions
    input_values = ["UBAHN", "TRAM", "UBAHN", "S-Bahn", "SBAHN"]

    result = parse_transport_types(input_values)

    # Expected: [UBAHN, TRAM, SBAHN]
    # - First UBAHN is kept, second UBAHN is duplicate and removed
    # - TRAM is kept
    # - S-Bahn and SBAHN are synonyms, S-Bahn appears first but maps to SBAHN enum
    # - Second SBAHN is a duplicate and removed
    expected = [TransportType.UBAHN, TransportType.TRAM, TransportType.SBAHN]

    assert result == expected


def test_parse_transport_types_no_duplicates() -> None:
    """Test parse_transport_types with unique inputs."""
    input_values = ["UBAHN", "BUS", "TRAM"]

    result = parse_transport_types(input_values)

    expected = [TransportType.UBAHN, TransportType.BUS, TransportType.TRAM]
    assert result == expected


def test_parse_transport_types_all_duplicates() -> None:
    """Test parse_transport_types when all inputs are duplicates."""
    input_values = ["UBAHN", "UBAHN", "ubahn", "U-BAHN"]

    result = parse_transport_types(input_values)

    # Should return only one UBAHN
    expected = [TransportType.UBAHN]
    assert result == expected


def test_parse_transport_types_synonym_variations() -> None:
    """Test parse_transport_types with various synonym inputs."""
    # Test different S-Bahn variations
    input_values = ["S-BAHN", "SBAHN", "SBAHN"]  # S-BAHN and SBAHN are synonyms

    result = parse_transport_types(input_values)

    # Should return only one SBAHN (the enum value)
    expected = [TransportType.SBAHN]
    assert result == expected


def test_parse_transport_types_empty_list() -> None:
    """Test parse_transport_types with empty input."""
    result = parse_transport_types([])
    assert result == []


def test_parse_transport_types_empty_strings() -> None:
    """Test parse_transport_types with empty and whitespace strings."""
    input_values = ["", "  ", "UBAHN", "", "BUS"]

    result = parse_transport_types(input_values)

    expected = [TransportType.UBAHN, TransportType.BUS]
    assert result == expected


def test_parse_transport_types_case_variations() -> None:
    """Test parse_transport_types with different case variations."""
    input_values = ["ubahn", "BUS", "Tram"]

    result = parse_transport_types(input_values)

    expected = [TransportType.UBAHN, TransportType.BUS, TransportType.TRAM]
    assert result == expected