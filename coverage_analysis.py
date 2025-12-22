import pandas as pd
import cloudscraper
import time
from random import randint
from tqdm import tqdm
from solution import get_urls_from_file
from paper import Paper
from config import HEADERS

def compute_journal_breakdown(success_df, total_by_journal):
    """Compute all statistics grouped by journal"""
    journal_stats = []

    for journal in success_df['journal'].unique():
        journal_df = success_df[success_df['journal'] == journal]
        papers = journal_df['link'].nunique()
        total_papers_journal = total_by_journal.get(journal, papers)

        first_authors = journal_df[journal_df['author_role'].apply(lambda x: 'first_author' in x)]
        last_authors = journal_df[journal_df['author_role'].apply(lambda x: 'last_author' in x)]
        corresponding = journal_df[journal_df['author_role'].apply(lambda x: 'corresponding_author' in x)]

        journal_stats.append({
            'Journal': journal,
            'Papers Success %': papers / total_papers_journal * 100,
            'First Author Email %': first_authors['author_email'].notna().sum() / len(first_authors) * 100 if len(first_authors) > 0 else 0,
            'Last Author Email %': last_authors['author_email'].notna().sum() / len(last_authors) * 100 if len(last_authors) > 0 else 0,
            'All Authors Email %': journal_df['author_email'].notna().sum() / len(journal_df) * 100,
            'Corresponding Identified %': corresponding['link'].nunique() / papers * 100
        })

    return pd.DataFrame(journal_stats).sort_values('Papers Success %', ascending=False)

def run_coverage_analysis():
    """Main analysis function"""
    # Load URLs and deduplicate
    urls = get_urls_from_file('example_data/paper_links.xlsx')
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
    first_authors = success_df[success_df['author_role'].apply(lambda x: 'first_author' in x)]
    last_authors = success_df[success_df['author_role'].apply(lambda x: 'last_author' in x)]
    corresponding = success_df[success_df['author_role'].apply(lambda x: 'corresponding_author' in x)]

    overall_row = {
        'Journal': 'OVERALL',
        'Papers Success %': papers_extracted / total_papers * 100,
        'First Author Email %': first_authors['author_email'].notna().sum() / len(first_authors) * 100 if len(first_authors) > 0 else 0,
        'Last Author Email %': last_authors['author_email'].notna().sum() / len(last_authors) * 100 if len(last_authors) > 0 else 0,
        'All Authors Email %': success_df['author_email'].notna().sum() / len(success_df) * 100 if len(success_df) > 0 else 0,
        'Corresponding Identified %': corresponding['link'].nunique() / papers_extracted * 100 if papers_extracted > 0 else 0
    }

    # Track total papers by journal (need to count from both success and failures)
    # For now use successful papers only as denominator per journal
    total_by_journal = success_df.groupby('journal')['link'].nunique().to_dict()

    # Compute journal breakdown and add overall row
    journal_breakdown = compute_journal_breakdown(success_df, total_by_journal)
    stats_df = pd.concat([pd.DataFrame([overall_row]), journal_breakdown], ignore_index=True)

    # Save to Excel
    stats_df.to_excel('example_data/coverage_stats.xlsx', index=False)
    print(f"\n\nTotal papers processed: {total_papers}")
    print(f"Successful: {papers_extracted} ({papers_extracted/total_papers*100:.1f}%)")
    print(f"Failed: {len(failed_urls)} ({len(failed_urls)/total_papers*100:.1f}%)")
    print("\nCoverage statistics saved to: example_data/coverage_stats.xlsx")
    print(stats_df.to_string(index=False))

if __name__ == "__main__":
    run_coverage_analysis()
