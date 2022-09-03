from functools import reduce, partial
from itertools import islice
import re

identifier_initial = re.compile(r"\w|_")
identifier_rest = re.compile(r"\w|\d|_")
whitespace = [" ", "\t"]
quotes = ["'", '"']

class XMLError(Exception):
    def __str__(self):
        return "Pooh, that's not JSON! That's XML!"

class StringGenerator(object):
    def __init__(self, s):
        self.pos = 0
        self.string = s
        self.size = len(s)
    def __iter__(self):
        return self
    def __next__(self):
        if self.exhausted():
            raise StopIteration()
        retval = self.string[self.pos]
        self.pos += 1
        return retval
    def lookahead(self, n):
        if self.pos + n >= self.size:
            return "R TO THE A TO THE C-H-I-E"

        return self.string[self.pos + n]
    def exhausted(self):
        return self.pos >= self.size
    def cw(self):
        while self.lookahead(0) in whitespace:
            next(self)
    def expect_next_opt(self, c):
        self.cw()
        if self.lookahead(0) in c:
            return next(self)
    def remaining(self):
        return self.string[self.pos:]

def byte(num):
    return bytes([num]).decode("utf-8")

def iterate_while_true(f, gen):
    try:
        while f(): yield next(gen)
    except StopIteration:
        pass

class compose:
    def __init__(self, *fs): self.fs = fs

    def __call__(self, *a, **kw):
        firstfunc, *funcs = list(reversed(self.fs))
        arg = firstfunc(*a, **kw)
        for func in funcs: arg = func(arg)
        return arg

def parse_escape(gen):
    normal_chars = {
        "a": "\a",
        "b": "\b",
        "e": "\x1B",
        "f": "\f",
        "v": "\v"
    }
    octal_digits = list(map(str, range(8)))
    decimal_digits = list(map(str, range(10)))
    hex_digits = [*decimal_digits, *"abcdefABCDEF"]
    try:
        char = next(gen)
    except StopIteration:
        return "\\"

    next_char_in = lambda s: lambda: gen.lookahead(0) in s
    iter_while_cin = compose(partial(iterate_while_true, gen=gen), next_char_in)
    
    if char in normal_chars:
        return normal_chars[char]
    if char in octal_digits:
        return byte(int("".join(islice(iter_while_cin(digits), 3)), 8))
    if char == "x":
        return byte(int("".join(iter_while_cin(hex_digits)), 16))
    if char == "u":
        return chr(int("".join(islice(iter_while_cin(hex_digits), 4)), 16))
    if char == "U":
        return chr(int("".join(islice(iter_while_cin(hex_digit), 8)), 16))
    return char

parse_identifier = lambda gen: "".join(iterate_while_true(lambda: identifier_rest.fullmatch(gen.lookahead(0)), gen))

def parse_string(gen):
    retval = ""
    starting_quote = gen.expect_next_opt(quotes)
    while not gen.exhausted():
        try:
            c = next(gen)
        except StopIteration:
            break
        if c == "\\":
            retval += parse_escape(gen)
            continue
        if c == starting_quote:
            break
        retval += c
    return retval

def parse_num(gen):
    retval = 0
    sign = 1
    base = 10
    decimal_multiplier = 1
    prefixes = {
        "x": 16,
        "o": 8,
        "b": 2
    }
    digits = dict(zip("0123456789abcdef", range(16)))
    symbols = "".join(digits.keys()) + "xob-+."
    symbols += symbols.upper()
    if gen.lookahead(0) == "0":
        next(gen)
        if gen.lookahead(0) in prefixes:
            base = prefixes[next(gen).lower()]
        else:
            base = 8
    while gen.lookahead(0) in symbols:
        c = next(gen).lower()
        if c in digits:
            if decimal_multiplier == 1:
                retval *= base
            retval += digits[c] * decimal_multiplier
            if decimal_multiplier != 1:
                decimal_multiplier /= base
        elif c in "+":
            pass
        elif c == "-":
            sign = -sign
        elif c == ".":
            decimal_multiplier = 1/base
    return retval * sign


upcoming = lambda s, gen: "".join(map(gen.lookahead, range(len(s)))).lower() == s
consume = lambda s, gen: "".join(next(gen) for _ in s)

def parse_bool(gen):
    if upcoming("true", gen):
        consume("true", gen)
        return True
    if upcoming("false", gen):
        consume("false", gen)
        return False
    
    
        
def parse_list(gen):
    retval = []
    gen.expect_next_opt("([")
    while not gen.exhausted():
        if gen.lookahead(0) in ")]":
            next(gen)
            break
        retval.append(parse_any(gen))
        gen.cw()
        gen.expect_next_opt(",")
    return retval
            
        

def parse_object(gen):
    retval = {}
    gen.cw()
    gen.expect_next_opt("{")
    while not gen.exhausted():
        if gen.lookahead(0) == "}":
            next(gen)
            break 
        key = parse_any(gen)
        gen.expect_next_opt(":")
        value = parse_any(gen)
        retval[key] = value
        gen.cw()
        gen.expect_next_opt(",")
    return retval

def parse_any(gen):
    gen.cw()
    c = gen.lookahead(0).lower()
    if c == "{":
        return parse_object(gen)
    elif c in "([":
        return parse_list(gen)
    elif c in quotes:
        return parse_string(gen)
    elif c in [*map(str, range(10)), "-", "."]:
        return parse_num(gen)
    elif upcoming("true", gen) or upcoming("false", gen):
        return parse_bool(gen)
    elif upcoming("null", gen):
        consume("null", gen)
        return None
    elif c == "<":
        raise XMLError()
    elif identifier_initial.fullmatch(c):
        return parse_identifier(gen)
    else:
        next(gen)
    
parse = compose(parse_any, StringGenerator)
