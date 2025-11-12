"""
Utility functions for the inventory app
"""
import unicodedata


def normalize_city_name(name):
    """
    Normalize city name by removing diacritics and converting to title case.

    Examples:
        Timișoara -> Timisoara
        Iași -> Iasi
        bucurești -> Bucuresti
    """
    if not name:
        return name

    # Remove leading/trailing spaces
    name = name.strip()

    # Convert to NFD (decomposed) form, then remove combining characters
    normalized = unicodedata.normalize('NFD', name)
    without_diacritics = ''.join(
        char for char in normalized
        if unicodedata.category(char) != 'Mn'  # Mn = Mark, Nonspacing
    )

    # Convert to title case for consistency
    return without_diacritics.title()

