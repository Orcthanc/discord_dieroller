#!/bin/env python3
import ply.lex as lex
from random import randrange
from json import load
import shutil
import urllib.request as url
from subprocess import run
import os

message = ""
characters = {}
charDefs = {}

def loadFromJSON(name):
    with open("files/{}.json".format(name), 'rb') as jfile:
        json = load(jfile)
        if not name in characters:
            characters[name] = {}

        characters[name]["name"] = json["basic_info"]["Character_Name"]

        characters[name]["fortitude"] = json["savingthrows"]["Fort"]["Total"]
        characters[name]["reflex"] = json["savingthrows"]["Ref"]["Total"]
        characters[name]["will"] = json["savingthrows"]["Will"]["Total"]

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

    def addStrs(self, other):
        if not self.roll:
            return other.roll
        elif not other.roll:
            return self.roll
        else:
            return self.roll + ", " + other.roll

    def __add__(self, other):
        if isinstance(other, RollResult):
            return RollResult(self.res + other.res, self.addStrs(other))
        return RollResult(self.res + other, self.roll)

    def __sub__(self, other):
        if isinstance(other, RollResult):
            return RollResult(self.res - other.res, self.addStrs(other))
        return RollResult(self.res - other, self.roll)

    def __mul__(self, other):
        if isinstance(other, RollResult):
            return RollResult(self.res * other.res, self.addStrs(other))
        return RollResult(self.res * other, self.roll)

    def __truediv__(self, other):
        if isinstance(other, RollResult):
            return RollResult(self.res / other.res, self.addStrs(other))
        return RollResult(self.res / other, self.roll)

    def __neg__(self):
        return RollResult(-self.res, self.roll)

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

    def __str__(self):
        return "{{{}}}: **{}**".format(self.roll, self.res)

class Math_Element:
    def execute(self):
        raise Exception

class Math_Element_Comp:
    def __init__(self):
        self.exprs = []

    def add(self, other):
        self.exprs.append(other)

    def execute(self):
        return "\n".join(map(lambda x: "{}".format(x.execute()), self.exprs))

class Constant(Math_Element):
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value

class Roll(Math_Element):
    def __init__(self, amount, size):
        self.amount = amount
        self.size = size

    def execute(self):
        tmpamt = self.amount.execute()
        tmpsz = self.size.execute()
        amount = int(tmpamt.res)
        size = int(tmpsz.res)

        if size == 0 or amount == 0:
            return RollResult(0, tmpamt.roll + tmpsz.roll)

        negative = amount < 0
        amount = abs(amount)

        print("{} {}".format(amount, size))
        if amount > 1000000:
            raise SyntaxError("Will not roll more than 1,000,000 dice in one roll")
        res = []
        for i in range(0, amount):
            res.append(randrange(1, size + 1, 1))
        if(amount < 200):
            res.sort()
            rolls = "{" + ", ".join(map(str, res)) + "}"
        else:
            rolls = "{ Omitted because more than 200 die were rolled }"
        return RollResult(-sum(res) if negative else sum(res), tmpamt.roll + tmpsz.roll + rolls)

class ComplicatedRoll(Math_Element):
    def __init__(self, amount, size, keep, high):
        self.amount = amount
        self.size = size
        self.keep = keep
        self.high = high

    def execute(self):
        tmpamt = self.amount.execute()
        tmpsz = self.size.execute()
        tmpkp = self.keep.execute()
        amount = int(tmpamt.res)
        size = int(tmpsz.res)
        keep = int(tmpkp.res)

        if size == 0 or amount == 0 or keep == 0:
            return RollResult(0, tmpamt.roll + tmpsz.roll + tmpkp.roll)

        negative = amount < 0
        amount = abs(amount)

        print("{} {}".format(amount, size))
        if amount > 1000000:
            raise SyntaxError("Will not roll more than 1,000,000 dice in one roll")
        res = []
        for i in range(0, amount):
            res.append(randrange(1, size + 1, 1))
        res.sort()
        if self.high:
            if(amount < 200):
                rolls = "{~~" + ", ".join(map(str, res[:-keep]))+ "~~, " + ", ".join(map(str, res[-keep:])) + "}"
            else:
                rolls = "{ Omitted because more than 200 die were rolled }"
            return RollResult(-sum(res[-keep:]) if negative else sum(res[-keep:]), tmpamt.roll + tmpsz.roll + tmpkp.roll + rolls)

        else:
            if(amount < 200):
                rolls = "{" + ", ".join(map(str, res[:keep]))+ ", ~~" + ", ".join(map(str, res[keep:])) + "~~}"
            else:
                rolls = "{ Omitted because more than 200 die were rolled }"
            return RollResult(-sum(res[:keep]) if negative else sum(res[:keep]), tmpamt.roll + tmpsz.roll + tmpkp.roll + rolls)

class Binop(Math_Element):
    def __init__(self, left, right):
        self.left = left
        self.right = right

class Add(Binop):
    def execute(self):
        return self.left.execute() + self.right.execute()

class Sub(Binop):
    def execute(self):
        return self.left.execute() - self.right.execute()

class Mul(Binop):
    def execute(self):
        return self.left.execute() * self.right.execute()

class Div(Binop):
    def execute(self):
        right = self.right.execute()
        if right.res == 0:
            raise SyntaxError("Cannot divide by zero")
        return self.left.execute() / right

class UnMinus(Math_Element):
    def __init__(self, value):
        self.value = value

    def execute(self):
        return -self.value.execute()




reserved = (
    'READ', 'REREAD', 'HELP', 'LOADCON', 'ROLL', 'DMINIT',
)

tokens = reserved + (
    # Integer, Float, dynamic command
    'INTL', 'FLOATL', 'COMMAND',

    # Operator
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'EQUALS',

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
t_EQUALS = r'='

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
    raise SyntaxError("Illegal character {}".format(t.value[0]))

lexer = lex.lex()

import ply.yacc as yacc

precedence = (
    ('right', 'EQUALS'),
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

def p_line3(p):
    'line : COMMAND EQUALS m_expression_list'
    try:
        if p[1] in attributes:
            p[0] = "Error: Could not overwrite predefined command {}".format(p[1])
            return
    except NameError:
        pass
    name = "{}".format(message.author)
    if not name in charDefs:
        charDefs[name] = {}
    retmsg = ""
    if p[1] in charDefs[name]:
        retmsg = "Warning: redecleration of identifier {}".format(p[1])
    else:
        retmsg = "Declared identifier {} for {}".format(p[1], message.author)
    charDefs[name][p[1]] = p[3]
    p[0] = retmsg

def p_m_expression_list(p):
    'm_expression_list : m_expression SEMICOLON m_expression_list'
    p[0] = p[3]
    p[0].add(p[1])

def p_m_expression_list2(p):
    '''m_expression_list : m_expression
                         | m_expression SEMICOLON'''
    p[0] = Math_Element_Comp()
    p[0].add(p[1])

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

        os.remove("files/{}.pdf".format(message.author))

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
    p[0] = p[2].execute()

def p_dminit_expression1(p):
    'expression : DMINIT'
    results = [(x["name"], randrange(1, 21, 1) + int(x["initiative"])) for x in characters.values()]
    results.sort(key = lambda x: x[1], reverse = True)
    p[0] = "```\n"
    for x in results:
        p[0] += "{:>3}: {}\n".format(x[1], x[0])
    p[0] += "```"

def p_dminit_expression2(p):
    'expression : DMINIT LBRACK arglist RBRACK'
    results = [(x["name"], randrange(1, 21, 1) + int(x["initiative"])) for x in characters.values()]
    for x in range(1, len(p[3]) + 1):
        results.append(("Enemy {}".format(x), randrange(1, 21, 1) + p[3][x-1].execute().res))
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
    'm_expression : COMMAND'
    name = "{}".format(message.author)

    try:
        if not p[1] in attributes:
            if name in charDefs:
                if p[1] in charDefs[name]:
                    p[0] = charDefs[name][p[1]]
                    return
            raise SyntaxError("Unknown identifier {}".format(p[1]))
    except NameError:
        if name in charDefs:
            if p[1] in charDefs[name]:
                p[0] = charDefs[name][p[1]]
                return
        raise SyntaxError("Unknown identifier {}".format(p[1]))

    if not "{}".format(message.author) in characters:
        raise SyntaxError("Could not find char of {}".format(message.author))
    #p[0] = randrange(1, 21, 1) + int(characters["{}".format(message.author)].get(attributes[p[1]], "-20"))
    p[0] = Add(Roll(Constant(RollResult(1, "")), Constant(RollResult(20, ""))), Constant(RollResult(int(characters["{}".format(message.author)].get(attributes[p[1]], "-20")), "")))

def p_m_expression_expression(p):
    'expression : m_expression'
    p[0] = p[1].execute()

def p_m_expression1(p):
    '''m_expression : m_expression PLUS m_expression
                  | m_expression MINUS m_expression
                  | m_expression TIMES m_expression
                  | m_expression DIVIDE m_expression'''
    if p[2] == '+':
        p[0] = Add(p[1], p[3])
    elif p[2] == '-':
        p[0] = Sub(p[1], p[3])
    elif p[2] == '*':
        p[0] = Mul(p[1], p[3])
    elif p[2] == '/':
        p[0] = Div(p[1], p[3])


def p_m_expression2(p):
    'number : LBRACK m_expression RBRACK'
    p[0] = p[2]

def p_m_expression3(p):
    'm_expression : dieroll'
    p[0] = p[1]

def p_m_expression4(p):
    'm_expression : MINUS m_expression %prec UMINUS'
    p[0] = UnMinus(p[2])

def p_m_expression5(p):
    'm_expression : PLUS m_expression %prec UPLUS'
    p[0] = p[2]

def p_m_expression6(p):
    'm_expression : number'
    p[0] = p[1]

def p_m_dieroll1(p):
    'dieroll : number DIE number'
    p[0] = Roll(p[1], p[3])

def p_m_dieroll2(p):
    '''dieroll : number DIE number KEEPH number
               | number DIE number KEEPL number'''
    p[0] = ComplicatedRoll(p[1], p[3], p[5], p[4] == 'h')


def p_m_number1(p):
    'number : FLOATL'
    p[0] = Constant(RollResult(float(p[1]), ""))

def p_m_number2(p):
    'number : INTL'
    p[0] = Constant(RollResult(int(p[1]), ""))

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
