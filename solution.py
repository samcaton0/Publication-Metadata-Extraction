import cloudscraper
import pandas as pd
from config import HEADERS
from tqdm import tqdm
from paper import Paper
import time
from random import randint
import argparse

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
    
def run_pipeline(urls: list, writefile: str, full: bool = False) -> None:
    """
    Executing the full pipeline that loads publication URLs, extracts their metadata, and writes it to a new file.

    Args:
        urls (list): List of publication URLs
        writefile (str): File path of the excel file where metadata will be written to
        full (bool): If True, save all authors. If False, only save authors with emails.

    Returns:
        None
    """

    # Creating a persistent scraper used for all requests
    scraper = cloudscraper.create_scraper()

    # Extracting metadata for each url
    papers = []
    metadata = []

    for i, url in enumerate(tqdm(urls, desc='Publications')):
        # Rotating user agents to avoid being blocked
        header_idx = i % len(HEADERS)
        scraper.headers.update(HEADERS[header_idx])

        paper = Paper(url, scraper=scraper)
        papers.append(paper)

        # Get metadata and filter if needed
        paper_metadata = paper.get_metadata()
        if not full:
            # Only include authors with emails
            paper_metadata = [author for author in paper_metadata if author['author_email']]

        metadata += paper_metadata
        time.sleep(randint(2,5))

    # Saving all metadata in an excel file using Pandas
    metadata_df = pd.DataFrame(metadata)
    metadata_df.to_excel(writefile, index=False, header=True)

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

    args = parser.parse_args()

    # Validate that either readfile or urls is provided
    if not args.readfile and not args.urls:
        parser.error('Either --readfile or --urls must be specified')

    # Get URLs from file or command line
    if args.urls:
        urls = args.urls
    else:
        urls = get_urls_from_file(args.readfile)

    run_pipeline(urls=urls, writefile=args.writefile, full=args.full)