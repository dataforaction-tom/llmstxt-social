"""Fetch grant data from 360Giving."""

import re
from dataclasses import dataclass
import httpx
import pandas as pd
from io import StringIO

from ..extractor import ExtractedPage


@dataclass
class GrantData:
    """360Giving grant data for a funder."""
    funder_name: str
    total_grants: int
    total_amount: float
    average_grant: float
    grant_range: dict  # {min, max}
    top_themes: list[str]
    geographic_distribution: dict
    sample_recipients: list[dict]  # Sample of funded organisations
    grants_over_time: dict  # Year -> count/amount
    data_quality_score: str  # "Basic", "Good", "Excellent"


async def fetch_360giving_data(
    funder_name: str,
    charity_number: str | None = None
) -> GrantData | None:
    """
    Fetch grant data from the 360Giving Datastore.

    360Giving is an open data standard for grant funding. Many UK funders
    publish their grants data in this format.

    API Documentation: https://standard.threesixtygiving.org/
    Datastore: https://grantnav.threesixtygiving.org/

    Args:
        funder_name: Name of the funder
        charity_number: Optional charity number to help identify the funder

    Returns:
        GrantData if found, None otherwise
    """
    # Try to find the funder's 360Giving data
    registry_data = await _find_funder_in_registry(funder_name, charity_number)

    if not registry_data:
        return None

    # Fetch and analyze the grants data
    return await _fetch_and_analyze_grants(registry_data)


async def _find_funder_in_registry(
    funder_name: str,
    charity_number: str | None
) -> dict | None:
    """
    Find a funder in the 360Giving publisher registry.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # The 360Giving registry API
            registry_url = "https://data.threesixtygiving.org/data.json"

            response = await client.get(registry_url)

            if response.status_code != 200:
                return None

            registry = response.json()

            # Search for the funder by name or charity number
            funder_name_lower = funder_name.lower()

            for publisher in registry.get("publishers", []):
                pub_name = publisher.get("name", "").lower()

                # Check if names match (fuzzy matching)
                if (funder_name_lower in pub_name or
                    pub_name in funder_name_lower or
                    _similar_names(funder_name_lower, pub_name)):

                    # If we have charity number, verify it matches
                    if charity_number:
                        pub_charity_num = publisher.get("charity_number", "")
                        if pub_charity_num and pub_charity_num != charity_number:
                            continue

                    return publisher

    except Exception:
        pass

    return None


def _similar_names(name1: str, name2: str) -> bool:
    """Check if two funder names are similar (basic fuzzy matching)."""
    # Remove common words
    stopwords = ["foundation", "trust", "charity", "fund", "the", "limited", "ltd"]

    words1 = set(name1.split())
    words2 = set(name2.split())

    # Remove stopwords
    words1 = {w for w in words1 if w not in stopwords}
    words2 = {w for w in words2 if w not in stopwords}

    # Check if significant overlap
    if not words1 or not words2:
        return False

    overlap = len(words1 & words2)
    min_len = min(len(words1), len(words2))

    return overlap / min_len >= 0.6


async def _fetch_and_analyze_grants(publisher: dict) -> GrantData | None:
    """
    Fetch and analyze grant data from a 360Giving dataset.
    """
    try:
        # Get the dataset URL
        datasets = publisher.get("datasets", [])
        if not datasets:
            return None

        # Use the most recent dataset
        dataset = datasets[0]
        download_url = dataset.get("distribution", [{}])[0].get("downloadURL")

        if not download_url:
            return None

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(download_url)

            if response.status_code != 200:
                return None

            # Parse the data (usually CSV or JSON)
            if download_url.endswith('.csv'):
                df = pd.read_csv(StringIO(response.text))
            elif download_url.endswith('.json'):
                df = pd.read_json(StringIO(response.text))
            else:
                return None

            return _analyze_grants_dataframe(df, publisher.get("name", "Unknown"))

    except Exception:
        return None


def _analyze_grants_dataframe(df: pd.DataFrame, funder_name: str) -> GrantData | None:
    """Analyze a 360Giving grants dataframe."""
    try:
        # Standardize column names (360Giving uses specific field names)
        # Map common 360Giving field names
        column_map = {
            'Amount Awarded': 'amount',
            'Award Date': 'award_date',
            'Recipient Org:Name': 'recipient',
            'Beneficiary Location:Name': 'location',
            'Grant Programme:Title': 'programme',
            'Description': 'description'
        }

        # Rename columns if they exist
        for old_col, new_col in column_map.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})

        # Calculate statistics
        total_grants = len(df)

        # Amount analysis
        if 'amount' in df.columns:
            amounts = pd.to_numeric(df['amount'], errors='coerce').dropna()

            total_amount = amounts.sum()
            average_grant = amounts.mean()
            grant_range = {
                'min': int(amounts.min()),
                'max': int(amounts.max())
            }
        else:
            total_amount = 0
            average_grant = 0
            grant_range = {'min': 0, 'max': 0}

        # Theme analysis (from descriptions or programme titles)
        top_themes = _extract_themes(df)

        # Geographic distribution
        geographic_distribution = {}
        if 'location' in df.columns:
            location_counts = df['location'].value_counts().head(10)
            geographic_distribution = location_counts.to_dict()

        # Sample recipients
        sample_recipients = []
        if 'recipient' in df.columns:
            recipient_cols = ['recipient']
            if 'amount' in df.columns:
                recipient_cols.append('amount')
            if 'award_date' in df.columns:
                recipient_cols.append('award_date')

            sample_df = df[recipient_cols].head(10)

            for _, row in sample_df.iterrows():
                recipient = {'name': row.get('recipient', 'Unknown')}
                if 'amount' in row:
                    recipient['amount'] = float(row['amount'])
                if 'award_date' in row:
                    recipient['date'] = str(row['award_date'])
                sample_recipients.append(recipient)

        # Grants over time
        grants_over_time = {}
        if 'award_date' in df.columns:
            df['year'] = pd.to_datetime(df['award_date'], errors='coerce').dt.year
            year_stats = df.groupby('year').agg({
                'amount': ['count', 'sum']
            }).dropna()

            for year, row in year_stats.iterrows():
                if pd.notna(year):
                    grants_over_time[int(year)] = {
                        'count': int(row[('amount', 'count')]),
                        'total': float(row[('amount', 'sum')])
                    }

        # Data quality assessment
        data_quality_score = _assess_data_quality(df)

        return GrantData(
            funder_name=funder_name,
            total_grants=total_grants,
            total_amount=float(total_amount),
            average_grant=float(average_grant),
            grant_range=grant_range,
            top_themes=top_themes,
            geographic_distribution=geographic_distribution,
            sample_recipients=sample_recipients,
            grants_over_time=grants_over_time,
            data_quality_score=data_quality_score
        )

    except Exception:
        return None


def _extract_themes(df: pd.DataFrame) -> list[str]:
    """Extract common themes from grant descriptions and programmes."""
    themes = []

    # Combine description and programme columns
    text_columns = []
    if 'description' in df.columns:
        text_columns.append('description')
    if 'programme' in df.columns:
        text_columns.append('programme')

    if not text_columns:
        return themes

    # Combine all text
    all_text = ' '.join(
        df[text_columns].fillna('').astype(str).values.flatten()
    ).lower()

    # Common charity/funding themes to look for
    theme_keywords = {
        'youth': ['youth', 'young people', 'children', 'schools'],
        'health': ['health', 'wellbeing', 'mental health', 'medical'],
        'education': ['education', 'learning', 'training', 'skills'],
        'environment': ['environment', 'climate', 'nature', 'conservation'],
        'community': ['community', 'neighbourhood', 'local'],
        'arts': ['arts', 'culture', 'music', 'theatre'],
        'poverty': ['poverty', 'deprivation', 'disadvantaged'],
        'disability': ['disability', 'disabled', 'accessibility'],
        'elderly': ['elderly', 'older people', 'seniors'],
        'homelessness': ['homeless', 'housing', 'shelter'],
    }

    theme_counts = {}
    for theme, keywords in theme_keywords.items():
        count = sum(all_text.count(keyword) for keyword in keywords)
        if count > 0:
            theme_counts[theme] = count

    # Return top 5 themes
    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
    return [theme for theme, _ in sorted_themes[:5]]


def _assess_data_quality(df: pd.DataFrame) -> str:
    """Assess the quality of the 360Giving data."""
    # Check completeness of key fields
    key_fields = ['amount', 'award_date', 'recipient', 'description']

    present_fields = sum(1 for field in key_fields if field in df.columns)
    completeness = present_fields / len(key_fields)

    # Check data freshness (most recent grant)
    is_recent = False
    if 'award_date' in df.columns:
        latest_date = pd.to_datetime(df['award_date'], errors='coerce').max()
        if pd.notna(latest_date):
            years_ago = (pd.Timestamp.now() - latest_date).days / 365
            is_recent = years_ago < 2

    # Score
    if completeness >= 0.75 and is_recent:
        return "Excellent"
    elif completeness >= 0.5:
        return "Good"
    else:
        return "Basic"


def find_funder_identifier(pages: list[ExtractedPage]) -> tuple[str | None, str | None]:
    """
    Try to find funder identifier information from pages.

    Returns:
        Tuple of (funder_name, charity_number)
    """
    # Look for 360Giving badge or mention
    for page in pages:
        if '360' in page.body_text and 'giving' in page.body_text.lower():
            # This funder likely publishes 360Giving data
            pass

        # Try to extract formal name
        # Usually in <title>, <h1>, or "about" sections
        if page.page_type.value == 'about':
            # The charity number may have been extracted
            charity_num = page.charity_number
            if charity_num:
                return (page.title, charity_num)

    return (None, None)
