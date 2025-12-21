import cloudscraper
import pandas as pd
from config import HEADERS
from tqdm import tqdm
from paper import Paper
import time
from random import randint

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
    
def run_pipeline(readfile: str, writefile: str) -> None:
    """
    Executing the full pipeline that loads publication URLs, extracts their metadata, and writes it to a new file.

    Args:
        readfile (str): File path of the excel file of publication URLs
        writefile (str): File path of the excel file where metadata will be written to.

    Returns:
        None
    """

    # Reading URLs
    urls = get_urls_from_file(readfile)

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
        metadata += paper.get_metadata()
        time.sleep(randint(2,5))

    # Saving all metadata in an excel file using Pandas
    metadata_df = pd.DataFrame(metadata)
    metadata_df.to_excel(writefile, index=False, header=True)

if __name__ == "__main__":
    readfile = 'data/paper_links.xlsx'
    writefile = 'data/metadata.xlsx'
    run_pipeline(readfile=readfile, writefile=writefile)