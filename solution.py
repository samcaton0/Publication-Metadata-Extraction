import cloudscraper
import pandas as pd
from tqdm import tqdm
import time
from random import randint
import argparse
from config import HEADERS
from paper import Paper

def get_urls_from_file(filepath: str) -> list:
    """
    Create a list of publication URLs read from an excel file.

    Args:
        filepath (str): Path to the excel file of publication URLs

    Returns:
        list: List of the URLs from the excel file.
    """

    urls_df = pd.read_excel(filepath)
    urls = urls_df.iloc[:, 0].to_list()

    # Removing any duplicate URLs
    return set(urls)
    
def _print_summary(total: int, successful: int, failed: int, error_file: str = None):
    print("\n" + "="*60)
    print("Pipeline Complete!")
    print("="*60)
    print(f"Total papers: {total}")
    print(f"Successful: {successful} ({successful/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    if failed > 0 and error_file:
        print(f"\nError details saved to: {error_file}")
    print("="*60)

def run_pipeline(urls: list, writefile: str, full: bool = False, verbose: bool = False) -> None:
    """
    Executing the full pipeline that loads publication URLs, extracts their metadata, and writes it to a new file.

    Args:
        urls (list): List of publication URLs
        writefile (str): File path of the excel file where metadata will be written to
        full (bool): If True, save all authors. If False, only save authors with emails.
        verbose (bool): If True, print extraction progress for each paper

    Returns:
        None
    """

    # Creating a persistent scraper used for all requests
    scraper = cloudscraper.create_scraper()

    # Extracting metadata for each url
    successful_metadata = []
    failed_papers = []

    for i, url in enumerate(tqdm(urls, desc='Publications')):
        # Rotating user agents to avoid being blocked
        header_idx = i % len(HEADERS)
        scraper.headers.update(HEADERS[header_idx])

        paper = Paper(url, scraper=scraper, verbose=verbose)
        paper_data = paper.get_metadata()

        if paper.success:
            if not full:
                # Only include authors with emails
                paper_data = [author for author in paper_data if author.get('author_email')]
            successful_metadata += paper_data
        else:
            failed_papers += paper_data

        time.sleep(randint(2,5))

    # Save successful extractions
    if successful_metadata:
        metadata_df = pd.DataFrame(successful_metadata)
        metadata_df.to_excel(writefile, index=False, header=True)

    # Save failed papers to error file
    error_file = None
    if failed_papers:
        error_file = writefile.replace('.xlsx', '_errors.xlsx')
        error_df = pd.DataFrame(failed_papers)
        error_df.to_excel(error_file, index=False, header=True)

    # Print summary
    _print_summary(len(urls), len(set(d['link'] for d in successful_metadata)) if successful_metadata else 0,
                   len(failed_papers), error_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract metadata from academic papers')

    parser.add_argument('--full', action='store_true',
                        help='Save all authors (default: only save authors with emails)')
    parser.add_argument('--urls', nargs='+',
                        help='Specify individual URLs instead of reading from file')
    parser.add_argument('--writefile', default='data/metadata.xlsx',
                        help='Output file path (default: data/metadata.xlsx)')
    parser.add_argument('--readfile',
                        help='Input file path with URLs (required unless --urls is specified)')
    parser.add_argument('--verbose', action='store_true',
                        help='Print detailed extraction progress for each paper')

    args = parser.parse_args()

    # Validate that either readfile or urls is provided
    if not args.readfile and not args.urls:
        parser.error('Either --readfile or --urls must be specified')

    # Get URLs from file or command line
    if args.urls:
        urls = args.urls
    else:
        urls = get_urls_from_file(args.readfile)

    run_pipeline(urls=urls, writefile=args.writefile, full=args.full, verbose=args.verbose)