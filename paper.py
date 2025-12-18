import cloudscraper
from requests.exceptions import Timeout
from requests import Response
from bs4 import BeautifulSoup
from habanero import Crossref
from config import HEADERS, EMAIL, TIMEOUT
from numpy.random import choice
import re

class Paper:
    def __init__(self, url: str, scraper: cloudscraper.CloudScraper=None):
        # Metadata
        self.url = url
        self.html = None
        self.journal = None
        self.title = None
        self.doi = None
        self.authors = None
        self.status = None
        self.success = None
        self.scraper = scraper

        # Extracting metadata
        self._extract_metadata()

    def _safe_get(self) -> cloudscraper.requests.Response:
        # Creating the scraper if not passed as argument
        if not self.scraper:
            self.scraper = cloudscraper.create_scraper()
        
        # Handling timeout exceptions to avoid crashing the pipeline
        try:
            response = self.scraper.get(self.url, timeout=TIMEOUT, headers=choice(HEADERS))
            return response
        
        except Timeout:
            print(f'Timed out requesting: {self.url} after {TIMEOUT}s')

            # Creating a dummy response to keep clean logic in _get_html
            response = Response()
            response.status_code = 408
            response._content = b''
            
            return response

    def _get_html(self) -> bool:
        response = self._safe_get()

        # Validating that the request was received correctly
        status = response.status_code
        if status != 200:
            print(f'\nError {status} fetching {self.url}')
            return False
        
        self.html = response.text
        return True

    def _extract_doi(self) -> bool:
        # Extracting DOI from meta tags
        soup = BeautifulSoup(self.html, 'lxml')

        # Potential names for the meta tags associated with DOI
        citation_meta_names = [
          'citation_doi',
          'dc.Identifier',
      ]
        
        # DOI format Regex
        doi_pattern = r'^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$'

        for name in citation_meta_names:
            doi_metas = soup.find_all('meta', attrs={'name': name})
            for doi_meta in doi_metas:
                if re.match(doi_pattern, doi_meta.get('content')):
                    self.doi = doi_meta.get('content')
                    return True
            
        print(f'\nError extracting DOI for {self.url}')
        print(self.html)
        return False
                
    def _get_crossref_metadata(self) -> bool:
        # Querying Crossref
        cr = Crossref(mailto=EMAIL)
        response = cr.works(ids=self.doi)

        # Validating that Crossref was queried successfully
        status = response['status']
        if status != 'ok':
            print(f'\nError querying Crossref for {self.url}')
            return False
        cr_metadata = response['message']

        # Formatting author names
        author_names = [f'{author.get('given', '')} {author.get('family', '')}' for author in cr_metadata['author']]

        # Updating metadata
        self.journal = cr_metadata['container-title'][0]
        self.title = cr_metadata['title'][0]
        self.authors = author_names

        return True

    def _extract_emails(self) -> bool:
        return True

    def _extract_metadata(self):            
        if not self._get_html():
            self.success = False
            return False
        
        if not self._extract_doi():
            self.success = False
            return False

        if not self._get_crossref_metadata():
            self.success = False
            return False 

        if not self._extract_emails():
            self.success = False
            return False

        self.success = True
        return True

    def metadata_dict(self) -> dict:
        return {'link': self.url,
                'journal': self.journal,
                'title': self.title,
                'doi': self.doi,
                'authors': self.authors}