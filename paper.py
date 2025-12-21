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
        self.authors = {author_name: {'email': None, 'role': []} for author_name in author_names}

        # Identifying the first and last authors
        self.authors[author_names[0]]['role'].append('first_author')
        self.authors[author_names[-1]]['role'].append('last_author')

        return True
    
    def _find_emails_in_html(self, html: str) -> list:
        emails = []

        # Standard email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+(?:@|\{at\})[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
        raw_emails = re.findall(email_pattern, html)

        # Clean query parameters from emails
        for email in raw_emails:
            clean_email = email.split('?')[0].split('&')[0]
            emails.append(clean_email)

        # Cloudflare protected emails
        cf_pattern = r'/cdn-cgi/l/email-protection#([0-9a-f]+)'
        cf_matches = re.findall(cf_pattern, html)
        for encoded in cf_matches:
            try:
                # Decode Cloudflare XOR cipher
                key = int(encoded[:2], 16)
                decoded = ''.join(chr(int(encoded[i:i+2], 16) ^ key) for i in range(2, len(encoded), 2))
                emails.append(decoded)
            except:
                continue

        return emails

    def _filter_junk_emails(self, emails: list) -> list:
        # Removing non-author emails (examples, permissions, campaigns, etc.)
        junk_keywords = ['example', 'permission', 'campaign', 'placeholder', 'noreply',
                         'donotreply', 'support', 'info', 'admin', 'help']
        junk_prefixes = ['name@', 'email@', 'user@', 'author@', 'your@']

        filtered = []
        for email in emails:
            email_lower = email.lower()

            # Skip if contains junk keywords
            if any(keyword in email_lower for keyword in junk_keywords):
                continue

            # Skip if starts with junk prefixes
            if any(email_lower.startswith(prefix) for prefix in junk_prefixes):
                continue
            
            filtered.append(email)

        # Removing repeat emails
        return set(filtered)

    def _identify_corresponding_authors(self) -> None:
        # Finding correspondence markers in HTML
        corresp_pattern = r'correspon[ds](?:ence|ing)?.*?(?:to|:)'
        matches = re.finditer(corresp_pattern, self.html, re.IGNORECASE)

        for match in matches:
            start = match.start()
            chunk = self.html[start:start+500]

            # Check if any author name appears near correspondence marker
            for author_name in self.authors.keys():
                if author_name.lower() in chunk.lower():
                    if 'corresponding_author' not in self.authors[author_name]['role']:
                        self.authors[author_name]['role'].append('corresponding_author')

            # Check if any known email appears near correspondence marker
            for author_name, data in self.authors.items():
                if data['email'] and data['email'] in chunk.lower():
                    if 'corresponding_author' not in data['role']:
                        data['role'].append('corresponding_author')

    def _extract_emails(self) -> bool:
        # Finding all emails and their positions in HTML
        all_emails = self._find_emails_in_html(self.html)
        all_emails = self._filter_junk_emails(all_emails)

        if not all_emails:
            print(f'\nNo emails found for {self.url}')
            return False

        email_positions = {}
        for email in all_emails:
            matches = list(re.finditer(re.escape(email), self.html, re.IGNORECASE))
            if matches:
                email_positions[email] = matches[0].start()

        # For each author, find closest email by proximity
        any_matches = False
        for author_name in self.authors.keys():
            author_matches = list(re.finditer(re.escape(author_name), self.html, re.IGNORECASE))

            if not author_matches:
                continue

            closest_email = None
            min_distance = float('inf')

            for author_match in author_matches:
                author_pos = author_match.start()

                for email, email_pos in email_positions.items():
                    distance = abs(author_pos - email_pos)
                    if distance < min_distance:
                        min_distance = distance
                        closest_email = email

            if closest_email:
                self.authors[author_name]['email'] = closest_email.replace('{at}', '@')
                any_matches = True

        if not any_matches:
            print(f'\nCould not match any emails to author names for {self.url}')
            return False

        # Identify corresponding authors
        self._identify_corresponding_authors()

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

    def get_metadata(self) -> dict:
        paper_metadata = []
        for author_name, author_metadata in self.authors.items():
            author_dict = {'link': self.url,
                           'journal': self.journal,
                           'title': self.title,
                           'doi': self.doi,
                           'author_name': author_name,
                           'author_role': author_metadata['role'],
                           'author_email': author_metadata['email']}
            paper_metadata.append(author_dict)

        return paper_metadata