# ------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
# ------------------------------------------------------------------------------

import re

from tsfpga.register_list import REGISTER_MODES


class RegisterHtmlGenerator:

    def __init__(self, register_list):
        self.register_list = register_list

        self._compile_markdown_parser()

    @staticmethod
    def _comment(comment):
        return f"<!-- {comment} -->\n"

    def _header(self):
        html = self._comment(self.register_list.generated_info())
        html += self._comment(self.register_list.generated_source_info())
        return html

    def _compile_markdown_parser(self):
        r"""
        Strong: **double asterisks** or __double underscores__
        Emphasis: *single asterisks* or _single underscores_
        Literal asterisks or underscores are escaped: \* \_
        """
        self.strong_pattern1 = re.compile(r"\*\*(.*?)\*\*")
        self.strong_pattern2 = re.compile(r"__(.*?)__")
        self.em_pattern1 = re.compile(r"\*(.*?)\*")
        self.em_pattern2 = re.compile(r"_(.*?)_")
        self.escaped_literal_pattern = re.compile(r"\\(\*|_)")

    def _markdown_parser(self, text):
        text = re.sub(self.strong_pattern1, r"<b>\g<1></b>", text)
        text = re.sub(self.strong_pattern2, r"<b>\g<1></b>", text)
        text = re.sub(self.em_pattern1, r"<em>\g<1></em>", text)
        text = re.sub(self.em_pattern2, r"<em>\g<1></em>", text)
        text = re.sub(self.escaped_literal_pattern, r"\g<1>", text)
        return text

    def _annotate_register(self, register):
        description = self._markdown_parser(register.description)
        html = f"""
  <tr>
    <td><strong>{register.name}</strong></td>
    <td>{register.address}</td>
    <td>{register.mode_readable}</td>
    <td>{description}</td>
  </tr>"""

        return html

    def _annotate_bit(self, bit):
        description = self._markdown_parser(bit.description)
        html = f"""
  <tr>
    <td>&nbsp;&nbsp;<em>{bit.name}</em></td>
    <td>{bit.idx}</td>
    <td></td>
    <td>{description}</td>
  </tr>"""

        return html

    def _get_table(self):
        html = """
<table>
<thead>
  <tr>
    <th>Name</th>
    <th>Address</th>
    <th>Mode</th>
    <th>Description</th>
  </tr>
</thead>
<tbody>"""

        for register in self.register_list.iterate_registers():
            html += self._annotate_register(register)
            for bit in register.bits:
                html += self._annotate_bit(bit)
        html += """
</tbody>
</table>"""

        return html

    def get_table(self):
        html = self._header()
        html += self._get_table()
        return html

    @staticmethod
    def _get_mode_descriptions():
        html = """
<table>
<thead>
  <tr>
    <th>Mode</th>
    <th>Description</th>
  </tr>
</thead>
<tbody>"""

        for (mode_readable, description) in REGISTER_MODES.values():
            html += f"""
<tr>
  <td>{mode_readable}</td>
  <td>{description}</td>
</tr>
"""
        html += """
</tbody>
</table>"""
        return html

    def get_page(self, table_style=None, font_style=None, extra_style=""):
        module_name = self.register_list.name
        title = f"Documentation of {module_name} registers"

        if font_style is None:
            font_style = """
html * {
  font-family: "Trebuchet MS", Arial, Helvetica, sans-serif;
}"""

        if table_style is None:
            table_style = """
table {
  border-collapse: collapse;
}
td, th {
  border: 1px solid #ddd;
  padding: 8px;
}
tr:nth-child(even) {
  background-color: #f2f2f2;
}
tr:hover {
  background-color: #ddd;
}
th {
  padding-top: 12px;
  padding-bottom: 12px;
  text-align: left;
  background-color: #4CAF50;
  color: white;
}"""

        footer = self.register_list.generated_source_info()
        html = f"""
{self._header()}

<!DOCTYPE html>
<html>
<head>
  <title>{title}</title>
  <style>
{font_style}
{table_style}
{extra_style}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p>This document is a specification of the PS interface of the {module_name} module.</p>
  <h2>Register modes</h2>
  <p>The following register modes are available.</p>
{self._get_mode_descriptions()}
  <h2>Register map</h2>
  <p>The following registers make up the register map for the {module_name} module.</p>
{self._get_table()}
<p>{footer}</p>
</body>
</html>"""

        return html
