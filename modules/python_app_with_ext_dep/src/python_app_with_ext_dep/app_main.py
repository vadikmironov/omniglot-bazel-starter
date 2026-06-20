from abc import ABC
from html.parser import HTMLParser

import requests


class HTMLFilter(HTMLParser, ABC):
    """
    A simple no dependency HTML -> TEXT converter.
    Usage:
          str_output = HTMLFilter.convert_html_to_text(html_input)
    """

    def __init__(self, *args, **kwargs):
        self.text = ""
        self.in_body = False
        super().__init__(*args, **kwargs)

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() == "body":
            self.in_body = True

    def handle_endtag(self, tag):
        if tag.lower() == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body:
            self.text += data

    @classmethod
    def convert_html_to_text(cls, html: str) -> str:
        f = cls()
        f.feed(html)
        return f.text.strip()


def main() -> None:
    response = requests.get("http://info.cern.ch/", timeout=5, allow_redirects=False)
    print(f"HTTP status code = {response.status_code}")

    if response.status_code == requests.codes.ok:
        print("\n+++++ HTML content +++++\n")
        print(HTMLFilter.convert_html_to_text(response.text))
