"""
Crawler implementation.
"""
# pylint: disable=too-many-arguments, too-many-instance-attributes, unused-import, undefined-variable
import datetime
import json
import pathlib
import os
import random
import re
import requests
from bs4 import BeautifulSoup
from time import sleep
from typing import Pattern, Union
from core_utils import constants
from core_utils.article.io import to_raw
from core_utils.article.article import Article
from core_utils.config_dto import ConfigDTO


class IncorrectSeedURLError(Exception):
    pass


class IncorrectNumberOfArticlesError(Exception):
    pass


class NumberOfArticlesOutOfRangeError(Exception):
    pass


class IncorrectHeadersError(Exception):
    pass


class IncorrectEncodingError(Exception):
    pass


class IncorrectVerifyError(Exception):
    pass


class IncorrectTimeoutError(Exception):
    pass


class Config:
    """
    Class for unpacking and validating configurations.
    """

    def __init__(self, path_to_config: pathlib.Path) -> None:
        """
        Initialize an instance of the Config class.

        Args:
            path_to_config (pathlib.Path): Path to configuration.
        """
        self.path_to_config = path_to_config
        self._validate_config_content()
        self.config = self._extract_config_content()
        self._seed_urls = self.config.seed_urls
        self._num_articles = self.config.total_articles
        self._headers = self.config.headers
        self._encoding = self.config.encoding
        self._timeout = self.config.timeout
        self._should_verify_certificate = self.config.should_verify_certificate
        self._headless_mode = self.config.headless_mode

    def _extract_config_content(self) -> ConfigDTO:
        """
        Get config values.

        Returns:
            ConfigDTO: Config values
        """
        with open(self.path_to_config, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return ConfigDTO(seed_urls=config['seed_urls'],
                         total_articles_to_find_and_parse=config['total_articles_to_find_and_parse'],
                         headers=config['headers'],
                         encoding=config['encoding'],
                         timeout=config['timeout'],
                         should_verify_certificate=config['should_verify_certificate'],
                         headless_mode=config['headless_mode'])

    def _validate_config_content(self) -> None:
        """
        Ensure configuration parameters are not corrupt.
        """
        config = self._extract_config_content()
        if not (isinstance(config.seed_urls, list)
                and all(re.match(r'https?://(www)?\.21mm.ru+', seed_url)
                        for seed_url in config.seed_urls
                        )
                ):
            raise IncorrectSeedURLError
        num = config.total_articles
        if not isinstance(num, int) or num <= 0:
            raise IncorrectNumberOfArticlesError
        if not 0 < num <= 150:
            raise NumberOfArticlesOutOfRangeError
        if not isinstance(config.headers, dict):
            raise IncorrectHeadersError
        if not isinstance(config.encoding, str):
            raise IncorrectEncodingError
        if not isinstance(config.timeout, int) or not (0 <= config.timeout <= 60):
            raise IncorrectTimeoutError
        if not isinstance(config.should_verify_certificate, bool) or not isinstance(config.headless_mode, bool):
            raise IncorrectVerifyError

    def get_seed_urls(self) -> list[str]:
        """
        Retrieve seed urls.

        Returns:
            list[str]: Seed urls
        """
        return self._seed_urls

    def get_num_articles(self) -> int:
        """
        Retrieve total number of articles to scrape.

        Returns:
            int: Total number of articles to scrape
        """
        return self._num_articles

    def get_headers(self) -> dict[str, str]:
        """
        Retrieve headers to use during requesting.

        Returns:
            dict[str, str]: Headers
        """
        return self._headers

    def get_encoding(self) -> str:
        """
        Retrieve encoding to use during parsing.

        Returns:
            str: Encoding
        """
        return self._encoding

    def get_timeout(self) -> int:
        """
        Retrieve number of seconds to wait for response.

        Returns:
            int: Number of seconds to wait for response
        """
        return self._timeout

    def get_verify_certificate(self) -> bool:
        """
        Retrieve whether to verify certificate.

        Returns:
            bool: Whether to verify certificate or not
        """
        return self._should_verify_certificate

    def get_headless_mode(self) -> bool:
        """
        Retrieve whether to use headless mode.

        Returns:
            bool: Whether to use headless mode or not
        """
        return self._headless_mode


def make_request(url: str, config: Config) -> requests.models.Response:
    """
    Deliver a response from a request with given configuration.

    Args:
        url (str): Site url
        config (Config): Configuration

    Returns:
        requests.models.Response: A response from a request
    """
    sleep(random.randrange(3))
    return requests.get(url=url,
                        timeout=config.get_timeout(),
                        headers=config.get_headers(),
                        verify=config.get_verify_certificate())


class Crawler:
    """
    Crawler implementation.
    """

    url_pattern: Union[Pattern, str]

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the Crawler class.

        Args:
            config (Config): Configuration
        """
        self.config = config
        self.urls = []
        self.url_pattern = 'https://www.21mm.ru'

    def _extract_url(self, article_bs: BeautifulSoup) -> str:
        """
        Find and retrieve url from HTML.

        Args:
            article_bs (bs4.BeautifulSoup): BeautifulSoup instance

        Returns:
            str: Url from HTML
        """
        links = article_bs.find_all('div', {'class': 'figcaption promo-link'})
        url = ''
        for each in links:
            for link in each.select('a'):
                url = link['href']
        return self.url_pattern + url

    def find_articles(self) -> None:
        """
        Find articles.
        """
        urls = []
        for url in self.get_search_urls():
            response = make_request(url, self.config)
            if not response.ok:
                continue
            article_bs = BeautifulSoup(response.text, 'lxml')
            urls.append(self._extract_url(article_bs))
        self.urls.extend(urls)

    def get_search_urls(self) -> list:
        """
        Get seed_urls param.

        Returns:
            list: seed_urls param
        """
        return self.config.get_seed_urls()

# 10
# 4, 6, 8, 10


class HTMLParser:
    """
    HTMLParser implementation.
    """

    def __init__(self, full_url: str, article_id: int, config: Config) -> None:
        """
        Initialize an instance of the HTMLParser class.

        Args:
            full_url (str): Site url
            article_id (int): Article id
            config (Config): Configuration
        """
        self.full_url = full_url
        self.article_id = article_id
        self.config = config
        self.article = Article(full_url, article_id)

    def _fill_article_with_text(self, article_soup: BeautifulSoup) -> None:
        """
        Find text of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        text_elements = article_soup.find_all('div')
        if text_elements:
            all_divs = text_elements[0].find_all('div', {'class': 'categories-block__figure border-radius4px'})
            extracted_text = []
            for div in all_divs:
                extracted_text.append(div.text)
            self.article.text = ''.join(extracted_text)

    def _fill_article_with_meta_information(self, article_soup: BeautifulSoup) -> None:
        """
        Find meta information of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """

    def unify_date_format(self, date_str: str) -> datetime.datetime:
        """
        Unify date format.

        Args:
            date_str (str): Date in text format

        Returns:
            datetime.datetime: Datetime object
        """

    def parse(self) -> Union[Article, bool, list]:
        """
        Parse each article.

        Returns:
            Union[Article, bool, list]: Article instance
        """
        response = make_request(self.full_url, self.config)
        if response.ok:
            article_bs = BeautifulSoup(response.text, 'lxml')
            self._fill_article_with_text(article_bs)

        return self.article


def prepare_environment(base_path: Union[pathlib.Path, str]) -> None:
    """
    Create ASSETS_PATH folder if no created and remove existing folder.

    Args:
        base_path (Union[pathlib.Path, str]): Path where articles stores
    """
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    else:
        files = os.listdir(base_path)
        for file in files:
            if os.path.exists(file):
                os.remove(file)


def main() -> None:
    """
    Entrypoint for scrapper module.
    """


if __name__ == "__main__":
    main()
