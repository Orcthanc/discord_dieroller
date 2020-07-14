#!/bin/env python3
import ply.lex as lex
from random import randrange
from json import load
import shutil
import urllib.request as url
from subprocess import run

message = ""
characters = {}

def loadFromJSON(name):
    with open("files/{}.json".format(name), 'rb') as jfile:
        json = load(jfile)
        if not name in characters:
            characters[name] = {}

        characters[name]["name"] = json["basic_info"]["Character_Name"]

        characters[name]["fortitude"] = json["classes"]["Fort_Total"]
        characters[name]["reflex"] = json["classes"]["Ref_Total"]
        characters[name]["will"] = json["classes"]["Will_Total"]

        characters[name]["initiative"] = json["stats"]["init"]["total"]

        for key, value in json["skill"].items():
            if "Total" in value:
                characters[name][key.lower()] = value["Total"]
                print(key, characters[name][key.lower()])

        print( characters[name] )

        return characters[name]["name"]

class SyntaxError(Exception):
    def __init__(self, message):
        super().__init__()
        self.message = message

class RollResult:
    def __init__(self, res, roll):
        self.res = res
        self.roll = roll

    def __add__(self, other):
        if isinstance(other, RollResult):
            return RollResult(self.res + other.res, self.roll + ", " + other.roll)
        return RollResult(self.res + other, self.roll)

    def __gt__(self, other):
        if isinstance(other, RollResult):
            return self.res > other.res
        return self.res > other
 
    def __lt__(self, other):
        if isinstance(other, RollResult):
            return self.res < other.res
        return self.res < other

    def __ge__(self, other):
        if isinstance(other, RollResult):
            return self.res >= other.res
        return self.res >= other

    def __le__(self, other):
        if isinstance(other, RollResult):
            return self.res <= other.res
        return self.res <= other

    def __mul__(self, other):
        if isinstance(other, RollResult):
            return RollResult(self.res * other.res, self.roll + other.roll)
        return RollResult(self.res * other, self.roll)

    def __div__(self, other):
        if isinstance(other, RollResult):
            return RollResult(self.res / other.res, self.roll + other.roll)
        return RollResult(self.res / other, self.roll)

    def __str__(self):
        return "{}: {{{}}}".format(self.res, self.roll)

reserved = (
    'READ', 'REREAD', 'HELP', 'LOADCON', 'ROLL', 'DMINIT',
)

tokens = reserved + (
    # Integer, Float, dynamic command
    'INTL', 'FLOATL', 'COMMAND',

    # Operator
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE',

    'COMMA', 'LBRACK', 'RBRACK', 'SEMICOLON',

    #DieRoll
    'DIE', 'KEEPH', 'KEEPL'
)

t_ignore = ' \t\x0c'

def t_NEWLINE(t):
    r'\n'
    t.lexer.lineno += t.value.count("\n")

t_PLUS = r'\+'
t_MINUS = r'-'
t_TIMES = r'\*'
t_DIVIDE = r'/'
t_COMMA = r','
t_LBRACK = r'\('
t_RBRACK = r'\)'
t_SEMICOLON = r';'

t_DIE = r'd'
t_KEEPH = r'h'
t_KEEPL = r'l'

reserved_map = {}
for r in reserved:
    reserved_map[r.lower()] = r


def t_ID(t):
    r'[A-Za-z_][A-Za-z_][\w_]*'
    t.type = reserved_map.get(t.value, "COMMAND")
    return t

t_FLOATL = r'\d*\.\d+'
t_INTL = r'\d+'


def t_error(t):
    print("Illegal character %s" % repr(t.value[0]))
    t.lexer.skip(1)

lexer = lex.lex()

import ply.yacc as yacc

precedence = (
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('nonassoc', 'DIE', 'KEEPL', 'KEEPH'),
    ('right', 'UMINUS', 'UPLUS')
)

def p_line1(p):
    'line : expression SEMICOLON line'
    p[0] = "{}\n{}".format(p[1], p[3])

def p_line2(p):
    '''line : expression
            | expression SEMICOLON'''
    p[0] = "{}".format(p[1])


def p_read_expression(p):
    'expression : READ'
    p[0] = "Called read"
    if len(message.attachments) == 1:
        with open("files/{}.pdf".format(message.author), 'wb') as pfile:
            print(message.attachments[0].url)
            req = url.Request(
                message.attachments[0].url,
                data = None,
                headers = {
                    'User-Agent': 'DieRollBot'
                }
            )
            with url.urlopen(req) as pdf:
                shutil.copyfileobj(pdf, pfile)

        run(["./PDFtoJSON", "files/{}.pdf".format(message.author), "files/{}.json".format(message.author)])

        p[0] = loadFromJSON("{}".format(message.author))
    else:
        p[0] = "Could not find attachment"

def p_reread_expression(p):
    'expression : REREAD'
    p[0] = loadFromJSON("{}".format(message.author))

def p_help_expression(p):
    'expression : HELP'
    p[0] = """help: Displays this message
read: Reads the attached pdf
reread: Loads the last pdf you send with read
roll: Evaluates a roll expression.
loadcon: loads a configuration

Dicerolling: examples:
    1d20 rolls 1 20-sided die.
    3d20h2 rolls 3 20-sided dice and keeps the highest 2
    5d10l1 rolls 5 10-sided dice and keeps the lowest 1
    Rolls may be combined with the mathmatical operators +, -, * and /
    if a fraction is tried to be rolled, it will be rounded down (3.8d6 is equal to 3d6)"""

def p_loadcon_expression(p):
    'expression : LOADCON LBRACK COMMAND RBRACK'
    try:
        with open("cfgs/{}.com".format(p[3].replace("/", "#")), 'r') as pfile:
            global attributes
            attributes = dict([(x.split()[0], x.split()[1]) for x in pfile if " " in x])
        p[0] = "Succesfully read config {}".format(p[3])
        print(attributes)
    except IOError:
        p[0] = "Could not find config {}".format(p[3])


def p_roll_expression(p):
    'expression : ROLL m_expression'
    p[0] = p[2]

def p_dminit_expression1(p):
    'expression : DMINIT'
    results = [(x["name"], randrange(1, 21, 1) + int(x["initiative"])) for x in characters.values()]
    results.sort(key = lambda x: x[1], reverse = True)
    p[0] = "```\n"
    for x in results:
        p[0] += "{}: {}\n".format(x[1], x[0])
    p[0] += "```"

def p_dminit_expression2(p):
    'expression : DMINIT LBRACK arglist RBRACK'
    results = [(x["name"], randrange(1, 21, 1) + int(x["initiative"])) for x in characters.values()]
    for x in range(1, len(p[3]) + 1):
        results.append(("Enemy {}".format(x), randrange(1, 21, 1) + p[3][x-1]))
    results.sort(key = lambda x: x[1], reverse = True)
    p[0] = "```\n"
    for x in results:
        p[0] += "{:>3}: {}\n".format(x[1], x[0])
    p[0] += "```"

def p_arg_list1(p):
    'arglist : m_expression'
    p[0] = []
    p[0].append(p[1])

def p_arg_list2(p):
    'arglist : arglist COMMA m_expression'
    p[0] = p[1]
    p[0].append(p[3])

def p_command_expression1(p):
    'expression : COMMAND'
    if not p[1] in attributes:
        raise SyntaxError("Unknown attribute {}".format(p[1]))
    if not "{}".format(message.author) in characters:
        raise SyntaxError("Could not find char of {}".format(message.author))
    p[0] = randrange(1, 21, 1) + int(characters["{}".format(message.author)].get(attributes[p[1]], "-20"))

def p_command_expression2(p):
    'expression : COMMAND m_expression'
    if not p[1] in attributes:
        raise SyntaxError("Unknown attribute {}".format(p[1]))
    if not "{}".format(message.author) in characters:
        raise SyntaxError("Could not find char of {}".format(message.author))
    p[0] = randrange(1, 21, 1) + int(characters["{}".format(message.author)].get(attributes[p[1]], "-20")) + p[2]

def p_m_expression_expression(p):
    'expression : m_expression'
    p[0] = p[1]

def p_m_expression1(p):
    '''m_expression : m_expression PLUS m_expression
                  | m_expression MINUS m_expression
                  | m_expression TIMES m_expression
                  | m_expression DIVIDE m_expression'''
    if p[2] == '+':
        p[0] = p[1] + p[3]
    elif p[2] == '-':
        p[0] = p[1] - p[3]
    elif p[2] == '*':
        p[0] = p[1] * p[3]
    elif p[2] == '/':
        p[0] = p[1] / p[3]

def p_m_expression2(p):
    'number : LBRACK m_expression RBRACK'
    p[0] = p[2]

def p_m_expression3(p):
    'm_expression : dieroll'
    p[0] = p[1]

def p_m_expression4(p):
    'm_expression : MINUS m_expression %prec UMINUS'
    p[0] = -p[2]

def p_m_expression5(p):
    'm_expression : PLUS m_expression %prec UPLUS'
    p[0] = p[2]

def p_m_expression6(p):
    'm_expression : number'
    p[0] = p[1]

def p_m_dieroll1(p):
    'dieroll : number DIE number'
    if p[1] > 1000000:
        raise SyntaxError("Will not roll more than 1,000,000 dice in one roll")
    res = []
    for i in range(0, p[1]):
        res.append(randrange(1, p[3] + 1, 1))
    if(p[1] < 200):
        res.sort()
        rolls = "{" + ", ".join(map(str, res)) + "}"
    else:
        rolls = "{ Omitted because more than 200 die were rolled }"
    p[0] = RollResult(sum(res), rolls)

def p_m_dieroll2(p):
    '''dieroll : number DIE number KEEPH number
               | number DIE number KEEPL number'''
    if p[1] > 1000000:
        raise SyntaxError("Will not roll more than 1,000,000 dice in one roll")
    res = []
    for i in range(0, p[1]):
        res.append(randrange(1, p[3] + 1, 1))
    res.sort()
    if p[4] == 'h':
        if(p[1] < 200):
            rolls = "{~~" + ", ".join(map(str, res[:-p[5]]))+ "~~, " + ", ".join(map(str, res[-p[5]:])) + "}"
        else:
            rolls = "{ Omitted because more than 200 die were rolled }"
        p[0] = RollResult(sum(res[-p[5]:]), rolls)
    elif p[4] == 'l':
        if(p[1] < 200):
            rolls = "{" + ", ".join(map(str, res[:p[5]]))+ ", ~~" + ", ".join(map(str, res[p[5]:])) + "~~}"
        else:
            rolls = "{ Omitted because more than 200 die were rolled }"
        p[0] = RollResult(sum(res[:p[5]]), rolls)



def p_m_number1(p):
    'number : FLOATL'
    p[0] = float(p[1])

def p_m_number2(p):
    'number : INTL'
    p[0] = int(p[1])

def p_error(p):
    print("Syntax error {}".format(p))
    raise SyntaxError("Syntax error near {}".format(p))

parser = yacc.yacc(debug=True)

if __name__ == "__main__":
    while True:
        try:
            s = input('> ')
        except EOFError:
            break
        if not s: continue
        result = parser.parse(s)
        print(result)
