import requests
from bs4 import BeautifulSoup
from habanero import Crossref
from config import HEADERS, EMAIL, TIMEOUT

class Paper:
    def __init__(self, url: str):
        # Metadata
        self.url = url
        self.html = None
        self.journal = None
        self.title = None
        self.doi = None
        self.authors = None
        self.success = None

        # Extracting metadata
        self._extract_metadata()

    def _get_html(self) -> bool:
        response = requests.get(self.url, timeout=TIMEOUT, headers=HEADERS)

        # Validating that the request was received correctly
        status = response.status_code
        if status != 200:
            print(f'\nError {status} fetching {self.url}')
            return False
        
        self.html = response.text
        return True

    def _extract_doi(self) -> bool:
        soup = BeautifulSoup(self.html, 'lxml')
        doi = soup.find('meta', attrs={'name': 'citation_doi'})

        # Validating that the DOI was extracted correctly
        if not doi:
            print(f'\nError extracting DOI for {self.url}')
            return False
        
        self.doi = doi.get('content')
        return True

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