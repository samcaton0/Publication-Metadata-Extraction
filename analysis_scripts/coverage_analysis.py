import pandas as pd
import cloudscraper
import time
import sys
from pathlib import Path
from random import randint
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from solution import get_urls_from_file
from paper import Paper
from config import HEADERS

def get_role_subsets(df: pd.DataFrame) -> dict:
    """Returns a dictionary of dataframes that are filtered by author role"""
    return {
        'first': df[df['author_role'].apply(lambda x: 'first_author' in x)],
        'last': df[df['author_role'].apply(lambda x: 'last_author' in x)],
        'corresponding': df[df['author_role'].apply(lambda x: 'corresponding_author' in x)]
    }

def compute_stats(df: pd.DataFrame, papers: int, roles_dict: dict) -> dict:
    """Compute statistics about the % of successful email/role extraction for each author role"""
    return {
        'First Author Email %': roles_dict['first']['author_email'].notna().sum() / len(roles_dict['first']) * 100 if len(roles_dict['first']) > 0 else 0,
        'Last Author Email %': roles_dict['last']['author_email'].notna().sum() / len(roles_dict['last']) * 100 if len(roles_dict['last']) > 0 else 0,
        'All Authors Email %': df['author_email'].notna().sum() / len(df) * 100 if len(df) > 0 else 0,
        'Corresponding Identified %': roles_dict['corresponding']['link'].nunique() / papers * 100 if papers > 0 else 0
    }

def compute_journal_breakdown(success_df: pd.DataFrame, total_by_journal: dict) -> pd.DataFrame:
    """Compute all statistics grouped by journal"""
    journal_stats = []

    for journal in success_df['journal'].unique():
        journal_df = success_df[success_df['journal'] == journal]
        papers = journal_df['link'].nunique()
        total_papers_journal = total_by_journal.get(journal, papers)

        roles = get_role_subsets(journal_df)
        stats = compute_stats(journal_df, papers, roles)

        journal_stats.append({
            'Journal': journal,
            'Papers Success %': papers / total_papers_journal * 100,
            **stats
        })

    return pd.DataFrame(journal_stats).sort_values('Papers Success %', ascending=False)

def run_coverage_analysis() -> None:
    """Main analysis function"""
    # Load URLs and deduplicate
    urls = get_urls_from_file('../example_data/paper_links.xlsx')
    unique_urls = list(set(urls))
    total_papers = len(unique_urls)

    scraper = cloudscraper.create_scraper()
    successful_metadata = []
    failed_urls = []

    for i, url in enumerate(tqdm(unique_urls, desc='Publications')):
        header_idx = i % len(HEADERS)
        scraper.headers.update(HEADERS[header_idx])

        paper = Paper(url, scraper=scraper, verbose=False)
        paper_data = paper.get_metadata()

        if paper.success:
            successful_metadata += paper_data
        else:
            failed_urls.append(url)
            print(f"\nError extracting {url[:60]}... - {paper.error_type}")

        time.sleep(randint(2, 5))

    # Convert to DataFrame
    success_df = pd.DataFrame(successful_metadata)
    papers_extracted = success_df['link'].nunique() if not success_df.empty else 0

    # Compute overall statistics
    roles = get_role_subsets(success_df)
    stats = compute_stats(success_df, papers_extracted, roles)

    overall_row = {
        'Journal': 'OVERALL',
        'Papers Success %': papers_extracted / total_papers * 100,
        **stats
    }

    # Track total papers by journal (need to count from both success and failures)
    # For now use successful papers only as denominator per journal
    total_by_journal = success_df.groupby('journal')['link'].nunique().to_dict()

    # Compute journal breakdown and add overall row
    journal_breakdown = compute_journal_breakdown(success_df, total_by_journal)
    stats_df = pd.concat([pd.DataFrame([overall_row]), journal_breakdown], ignore_index=True)

    # Save to Excel
    stats_df.to_excel('../example_data/coverage_stats.xlsx', index=False)
    print(f"\n\nTotal papers processed: {total_papers}")
    print(f"Successful: {papers_extracted} ({papers_extracted/total_papers*100:.1f}%)")
    print(f"Failed: {len(failed_urls)} ({len(failed_urls)/total_papers*100:.1f}%)")
    print("\nCoverage statistics saved to: example_data/coverage_stats.xlsx")
    print(stats_df.to_string(index=False))

if __name__ == "__main__":
    run_coverage_analysis()
