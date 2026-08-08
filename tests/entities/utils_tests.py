# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev.entities.utils import snake_case_name
from punit import fact, inlinedata, theory


@theory
@inlinedata('FooBar', 'foo_bar')
@inlinedata('fooBar', 'foo_bar')
@inlinedata('FooBarBaz', 'foo_bar_baz')
@inlinedata('HTMLParser', 'html_parser')
@inlinedata('getHTTPSResponse', 'get_https_response')
@inlinedata('XMLParser', 'xml_parser')
@inlinedata('parseHTML', 'parse_html')
@inlinedata('someHTMLValue', 'some_html_value')
@inlinedata('JSON', 'json')
@inlinedata('id', 'id')
@inlinedata('getHTTP', 'get_http')
@inlinedata('already_snake', 'already_snake')
@inlinedata('_leading', 'leading')
@inlinedata('_Camel', 'camel')
@inlinedata('trailing_', 'trailing')
@inlinedata('IOError', 'io_error')
@inlinedata('URLPath', 'url_path')
@inlinedata('parseHTMLContent', 'parse_html_content')
@inlinedata('HTTPSConnection', 'https_connection')
@inlinedata('simpleTest', 'simple_test')
@inlinedata('', '')
def snake_case_name_roundtrip(value: str, expected: str) -> None:
    actual = snake_case_name(value)
    assert actual == expected, f'expected "{expected}", got "{actual}"'
