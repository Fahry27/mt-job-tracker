import re

class BaseParser:
    def discover_links(self, soup, base_url):
        """
        Extract links from the page soup.
        Returns a list of dictionaries: [{"job_title": "...", "job_url": "...", "source_url": "..."}]
        """
        raise NotImplementedError("discover_links must be implemented by subclasses")
