#!/usr/bin/env python3

"""
Return a modified version of the specified SQL text that has had
unnecessary whitespace and comments removed.
"""

import sys
import re

# Adapted from:
# https://github.com/dgoffredo/okra/blob/3a9484baaef9882883e50f24707ba3599e70f0d0/sql-dialects/mysql5.6/types2crud.js#L21

_sql_tokens_re = re.compile(
    "|".join("({})".format(x) for x in [
        r'\s+', # 1. whitespace
        r"'[^']*'", # 2. 'single-quoted string'
        r'`[^`]*`', # 3. `backtick-quoted string`
        r'"[^"]*"', # 4. "double-quoted string"
        r'--.*$', # 5. -- line comment
        r'\/\*(\*[^/]|[^*])*\*\/', # 6. /* block comment */
        # There are several tokens this does _not_ match, such as "SELECT" or "+",
        # but everything missed by this regex can't contain newlines.
    ]),
    re.MULTILINE
)
def _format_sql_replacer(match):
    if match.group(1) or match.group(5) or match.group(6):
        return " "
    return match.group()

def format_sql(sqlText):
    return _sql_tokens_re.sub(_format_sql_replacer, sqlText.strip());

def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-e", metavar="SCRIPT", dest="script", help=
        "this argument is the SQL text to format. "
        "if this argument is not specified, the SQL text is read from stdin.")
    parser.add_argument("-o", "--output", metavar="FILE", help=
        "write output to file instead of stdout, "
        "and omit the newline at the end.")
    parser.add_argument("-n", "--no-newline", action="store_true", help=
        "omit the newline at the end, even when outputting to stdout.")
    args = parser.parse_args()

    input_text = args.script or sys.stdin.read()
    output_text = format_sql(input_text)
    if args.output == None:
        if args.no_newline:
            sys.stdout.write(output_text); sys.stdout.flush()
        else:
            print(output_text)
    else:
        with open(args.output, "w") as f:
            f.write(output_text)

if __name__ == "__main__":
    main()
