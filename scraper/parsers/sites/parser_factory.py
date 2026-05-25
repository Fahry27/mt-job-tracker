from scraper.parsers.sites.curated_board_parser import CuratedBoardParser
from scraper.parsers.sites.prosple_parser import ProspleParser
from scraper.parsers.sites.jobstreet_parser import JobStreetParser
from scraper.parsers.sites.indeed_parser import IndeedParser
from scraper.parsers.sites.loker_id_parser import LokerIdParser
from scraper.parsers.sites.jooble_parser import JoobleParser
from scraper.parsers.sites.glints_parser import GlintsParser
from scraper.parsers.sites.kalibrr_parser import KalibrrParser

class ParserFactory:
    @staticmethod
    def get_parser(source_type, url):
        """
        Returns the appropriate parser instance based on source_type and url.
        """
        if source_type == "curated_job_board":
            return CuratedBoardParser()
        elif source_type == "graduate_job_board":
            return ProspleParser()
        elif source_type == "large_job_board":
            if "jobstreet" in url:
                return JobStreetParser()
            elif "indeed" in url:
                return IndeedParser()
            elif "glints" in url:
                return GlintsParser()
            elif "kalibrr" in url:
                return KalibrrParser()
        elif source_type == "job_board":
            return LokerIdParser()
        elif source_type == "aggregator":
            return JoobleParser()
        elif source_type == "glints":
            return GlintsParser()
        elif source_type == "kalibrr":
            return KalibrrParser()
        
        return None
