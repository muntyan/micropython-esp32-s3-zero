"""
Process raw qstr file and output qstr data with length, hash and data bytes.

This script works with Python 2.6, 2.7, 3.3 and 3.4.
"""

from __future__ import print_function

import re
import sys

# codepoint2name is different in Python 2 to Python 3
import platform
if platform.python_version_tuple()[0] == '2':
    from htmlentitydefs import codepoint2name
elif platform.python_version_tuple()[0] == '3':
    from html.entities import codepoint2name
codepoint2name[ord('-')] = 'hyphen';

# add some custom names to map characters that aren't in HTML
codepoint2name[ord(' ')] = 'space'
codepoint2name[ord('\'')] = 'squot'
codepoint2name[ord(',')] = 'comma'
codepoint2name[ord('.')] = 'dot'
codepoint2name[ord(':')] = 'colon'
codepoint2name[ord(';')] = 'semicolon'
codepoint2name[ord('/')] = 'slash'
codepoint2name[ord('%')] = 'percent'
codepoint2name[ord('#')] = 'hash'
codepoint2name[ord('(')] = 'paren_open'
codepoint2name[ord(')')] = 'paren_close'
codepoint2name[ord('[')] = 'bracket_open'
codepoint2name[ord(']')] = 'bracket_close'
codepoint2name[ord('{')] = 'brace_open'
codepoint2name[ord('}')] = 'brace_close'
codepoint2name[ord('*')] = 'star'
codepoint2name[ord('!')] = 'bang'
codepoint2name[ord('\\')] = 'backslash'
codepoint2name[ord('+')] = 'plus'
codepoint2name[ord('$')] = 'dollar'
codepoint2name[ord('=')] = 'equals'
codepoint2name[ord('?')] = 'question'
codepoint2name[ord('@')] = 'at_sign'
codepoint2name[ord('^')] = 'caret'
codepoint2name[ord('|')] = 'pipe'
codepoint2name[ord('~')] = 'tilde'

# this must match the equivalent function in qstr.c
def compute_hash(qstr, bytes_hash):
    hash = 5381
    for char in qstr:
        hash = (hash * 33) ^ ord(char)
    # Make sure that valid hash is never zero, zero means "hash not computed"
    return (hash & ((1 << (8 * bytes_hash)) - 1)) or 1

def qstr_escape(qst):
    def esc_char(m):
        c = ord(m.group(0))
        try:
            name = codepoint2name[c]
        except KeyError:
            name = '0x%02x' % c
        return "_" + name + '_'
    return re.sub(r'[^A-Za-z0-9_]', esc_char, qst)

def parse_input_headers(infiles):
    # read the qstrs in from the input files
    qcfgs = {}
    qstrs = {}
    for infile in infiles:
        with open(infile, 'rt') as f:
            for line in f:
                line = line.strip()

                # is this a config line?
                match = re.match(r'^QCFG\((.+), (.+)\)', line)
                if match:
                    value = match.group(2)
                    if value[0] == '(' and value[-1] == ')':
                        # strip parenthesis from config value
                        value = value[1:-1]
                    qcfgs[match.group(1)] = value
                    continue

                # is this a QSTR line?
                match = re.match(r'^Q\((.*)\)$', line)
                if not match:
                    continue

                # get the qstr value
                qstr = match.group(1)
                ident = qstr_escape(qstr)

                # don't add duplicates
                if ident in qstrs:
                    continue

                # add the qstr to the list, with order number to retain original order in file
                qstrs[ident] = (len(qstrs), ident, qstr)

    if not qcfgs:
        sys.stderr.write("ERROR: Empty preprocessor output - check for errors above\n")
        sys.exit(1)

    return qcfgs, qstrs

def make_bytes(cfg_bytes_len, cfg_bytes_hash, qstr):
    qhash = compute_hash(qstr, cfg_bytes_hash)
    if all(32 <= ord(c) <= 126 and c != '\\' for c in qstr):
        # qstr is all printable ASCII so render it as-is (for easier debugging)
        qlen = len(qstr)
        qdata = qstr
    else:
        # qstr contains non-printable codes so render entire thing as hex pairs
        qbytes = qstr.encode('utf8')
        qlen = len(qbytes)
        qdata = ''.join(('\\x%02x' % b) for b in qbytes)
    if qlen >= (1 << (8 * cfg_bytes_len)):
        print('qstr is too long:', qstr)
        assert False
    qlen_str = ('\\x%02x' * cfg_bytes_len) % tuple(((qlen >> (8 * i)) & 0xff) for i in range(cfg_bytes_len))
    qhash_str = ('\\x%02x' * cfg_bytes_hash) % tuple(((qhash >> (8 * i)) & 0xff) for i in range(cfg_bytes_hash))
    return '(const byte*)"%s%s" "%s"' % (qhash_str, qlen_str, qdata)

def print_qstr_data(qcfgs, qstrs):
    # get config variables
    cfg_bytes_len = int(qcfgs['BYTES_IN_LEN'])
    cfg_bytes_hash = int(qcfgs['BYTES_IN_HASH'])

    # print out the starter of the generated C header file
    print('// This file was automatically generated by makeqstrdata.py')
    print('')

    # add NULL qstr with no hash or data
    print('QDEF(MP_QSTR_NULL, (const byte*)"%s%s" "")' % ('\\x00' * cfg_bytes_hash, '\\x00' * cfg_bytes_len))

    # go through each qstr and print it out
    for order, ident, qstr in sorted(qstrs.values(), key=lambda x: x[0]):
        qbytes = make_bytes(cfg_bytes_len, cfg_bytes_hash, qstr)
        print('QDEF(MP_QSTR_%s, %s)' % (ident, qbytes))

def do_work(infiles):
    qcfgs, qstrs = parse_input_headers(infiles)
    print_qstr_data(qcfgs, qstrs)

if __name__ == "__main__":
    do_work(sys.argv[1:])
