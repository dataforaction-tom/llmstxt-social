"""Tests for 360Giving enricher."""

import pytest
import pandas as pd
from llmstxt_social.enrichers.threesixty_giving import (
    _similar_names,
    _extract_themes,
    _assess_data_quality,
    _analyze_grants_dataframe,
)


def test_similar_names():
    """Test fuzzy name matching for funders."""
    assert _similar_names("the smith foundation", "smith foundation trust")
    assert _similar_names("community fund", "the community fund")
    assert not _similar_names("smith foundation", "jones trust")
    assert _similar_names("abc charity", "abc charitable trust")


def test_extract_themes():
    """Test theme extraction from grant descriptions."""
    df = pd.DataFrame({
        'description': [
            'Support for youth mental health services',
            'Community arts and cultural projects',
            'Environmental conservation work',
            'Education and training for young people',
            'Health and wellbeing programs',
        ],
        'programme': [
            'Youth Programme',
            'Arts Grant',
            'Environment Fund',
            'Education Support',
            'Health Initiative',
        ]
    })

    themes = _extract_themes(df)

    assert isinstance(themes, list)
    assert len(themes) > 0
    # Check that common themes are identified
    assert any(theme in ['youth', 'health', 'arts', 'environment', 'education'] for theme in themes)


def test_assess_data_quality_excellent():
    """Test data quality assessment - excellent quality."""
    df = pd.DataFrame({
        'amount': [1000, 2000, 3000],
        'award_date': pd.to_datetime(['2025-01-01', '2025-02-01', '2025-03-01']),
        'recipient': ['Org A', 'Org B', 'Org C'],
        'description': ['Project 1', 'Project 2', 'Project 3']
    })

    quality = _assess_data_quality(df)
    assert quality in ["Good", "Excellent"]


def test_assess_data_quality_basic():
    """Test data quality assessment - basic quality."""
    df = pd.DataFrame({
        'amount': [1000, 2000],
    })

    quality = _assess_data_quality(df)
    assert quality == "Basic"


def test_analyze_grants_dataframe():
    """Test analyzing a 360Giving grants dataframe."""
    df = pd.DataFrame({
        'Amount Awarded': [1000, 2000, 3000, 4000, 5000],
        'Award Date': pd.to_datetime(['2024-01-01', '2024-03-01', '2024-06-01', '2024-09-01', '2024-12-01']),
        'Recipient Org:Name': ['Org A', 'Org B', 'Org C', 'Org D', 'Org E'],
        'Beneficiary Location:Name': ['London', 'Manchester', 'London', 'Birmingham', 'London'],
        'Description': [
            'Youth project',
            'Health initiative',
            'Education program',
            'Community development',
            'Arts project'
        ]
    })

    result = _analyze_grants_dataframe(df, "Test Foundation")

    assert result is not None
    assert result.funder_name == "Test Foundation"
    assert result.total_grants == 5
    assert result.total_amount == 15000.0
    assert result.average_grant == 3000.0
    assert result.grant_range['min'] == 1000
    assert result.grant_range['max'] == 5000
    assert len(result.top_themes) > 0
    assert 'London' in result.geographic_distribution
    assert len(result.sample_recipients) > 0
    assert len(result.grants_over_time) > 0
    assert result.data_quality_score in ["Basic", "Good", "Excellent"]


def test_analyze_grants_dataframe_minimal():
    """Test analyzing a minimal dataframe."""
    df = pd.DataFrame({
        'Amount Awarded': [1000, 2000],
        'Recipient Org:Name': ['Org A', 'Org B'],
    })

    result = _analyze_grants_dataframe(df, "Minimal Foundation")

    assert result is not None
    assert result.total_grants == 2
    assert result.total_amount == 3000.0


def test_grants_over_time():
    """Test grants over time analysis."""
    df = pd.DataFrame({
        'Amount Awarded': [1000, 2000, 3000, 4000],
        'Award Date': pd.to_datetime(['2023-01-01', '2023-06-01', '2024-01-01', '2024-06-01']),
        'Recipient Org:Name': ['Org A', 'Org B', 'Org C', 'Org D'],
    })

    result = _analyze_grants_dataframe(df, "Test Foundation")

    assert result is not None
    assert len(result.grants_over_time) == 2
    assert 2023 in result.grants_over_time
    assert 2024 in result.grants_over_time
    assert result.grants_over_time[2023]['count'] == 2
    assert result.grants_over_time[2024]['count'] == 2
    assert result.grants_over_time[2023]['total'] == 3000.0
    assert result.grants_over_time[2024]['total'] == 7000.0
