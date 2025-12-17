import requests
from bs4 import BeautifulSoup
import re
from habanero import Crossref, RequestError
import pandas as pd
from config import HEADERS, TIMEOUT, EMAIL
from tqdm import tqdm
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
    urls = urls_df['url'].to_list()

    return urls
    
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
    
    # Extracting metadata for each url
    papers = []
    metadata = []
    
    for url in tqdm(urls, desc='Publications'):
        paper = Paper(url)
        if paper.success:
            papers.append(paper)
            metadata.append(paper.metadata_dict())

    # Saving all metadata in an excel file using Pandas
    metadata_df = pd.DataFrame(metadata)
    metadata_df.to_excel(writefile, index=False, header=True)

if __name__ == "__main__":
    readfile = 'data/paper_links.xlsx'
    writefile = 'data/metadata.xlsx'
    run_pipeline(readfile=readfile, writefile=writefile)