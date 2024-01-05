from dis import Bytecode, opmap
from types import FunctionType


class Instructions(list):
    # instructions injection util, which is essentially a list (i.e. printable/iterable to see instructions)
    # basic usage:
    # Instructions(<function>).seek(<pos>).LOAD_GLOBAL(print).LOAD_CONST('hello world').CALL_FUNCTION(1).POP_TOP.build()
    #
    # all instruction arguments are optional, and default to 0
    # positional instructions like JUMP/SETUP/FOR_ITER are properly handled
    # has field `globals`, `name`, `freevar`, `const`, `closure` in case you want to load some objects
    # also note that simply getting attr (like `..POP_TOP` above) WILL HAVE SIDE EFFECT of registering such command
    #
    # syntactic sugars:
    # LOAD_GLOBAL:
    # accepts str (as name) or object (will be written to `globals[its.__name__]`). Will patch `globals` and `name`
    #
    # LOAD_DEFER (i.e. closure):
    # accepts str (as name) or object. Note if name given, it must already exist in `freevar`. Will also patch `closure`
    #
    # LOAD_CONST:
    # accepts object. Will patch `const`
    def __init__(self, f):
        # construct from callable
        super().__init__([i[0], i[2] or 0] for i in Bytecode(f))
        self.f = f
        self.n = 0
        self.globals = f.__globals__
        self.name = list(f.__code__.co_names)
        self.freevar = list(f.__code__.co_freevars)
        self.const = list(f.__code__.co_consts)
        self.closure = list(f.__closure__) or []

    def seek(self, n) -> "Instructions":
        # seek cursor
        self.n = n
        return self

    def __getattr__(self, f, jump=(
            "JUMP_IF_FALSE_OR_POP", "JUMP_IF_TRUE_OR_POP", "JUMP_ABSOLUTE", "POP_JUMP_IF_FALSE", "POP_JUMP_IF_TRUE",
            "JUMP_IF_NOT_EXC_MATCH"), setup=(
            "SETUP_ANNOTATIONS", "SETUP_FINALLY", "SETUP_WITH", "SETUP_ASYNC_WITH", "FOR_ITER")) -> "Instructions":
        # insert instruction
        for j, i in enumerate(self):
            if (i[1] if i[0] in jump else j + i[1] + 1 if i[0] in setup and j < self.n else -1) >= self.n:
                i[1] += 1
        self.insert(self.n, [f, 0])
        self.n += 1
        return self

    def __call__(self, _, ) -> "Instructions":
        # provide instruction arg
        if self[self.n - 1][0] == "LOAD_GLOBAL":
            if not isinstance(_, str):
                i = getattr(_, '__name__', str(_))
                self.globals[i] = _
                _ = i
            i = 'name'
        elif self[self.n - 1][0] == "LOAD_DEFER":
            if not isinstance(_, str):
                if _ not in self.closure:
                    self.closure.append(_)
                    _ = getattr(_, '__name__', str(_))
                else:
                    _ = self.freevar[self.closure.index(_)]
            i = "freevar"
        elif self[self.n - 1][0] == "LOAD_CONST":
            i = "const"
        else:
            i = None
        if i:
            j = getattr(self, i)
            if _ not in j:
                j.append(_)
                setattr(self, i, j)
            _ = j.index(_)
        self[self.n - 1][1] = _
        return self

    def build(self) -> FunctionType:
        # rebuild function. All misc info (such as name and signature) are inherited 
        return FunctionType(
            self.f.__code__.replace(co_code=bytes(sum(((opmap[i], j) for i, j in self), ())), co_names=tuple(self.name),
                                    co_consts=tuple(self.const), co_freevars=tuple(self.freevar)), self.globals,
            self.f.__name__,
            self.f.__defaults__,
            tuple(self.closure))


# noinspection PyStatementEffect
def inject(f, g, per=10) -> FunctionType:
    # rewrite `f`'self code such that it calls `g()` per `per` instructions
    f = Instructions(f)
    for per in range(per, len(f), per)[::-1]:
        f.seek(per).LOAD_GLOBAL(g).CALL_FUNCTION.POP_TOP
    return f.build()
