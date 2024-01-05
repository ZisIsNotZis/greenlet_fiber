import builtins
from types import FunctionType
from typing import Callable


def wrap(f, g, depth=0) -> Callable:
    # wrap `f` to call `g(f,*_,**__)` ahead, return modified function
    # propagate to all global/captured callables used inside unless running out of depth, set -1 for infinite
    # wrapped global will be written to '_wrap' + name
    if hasattr(f, "__call__"):
        if hasattr(f, "__code__") and depth != 0:
            f = FunctionType(
                f.__code__.replace(
                    co_consts=tuple(wrap(i, g, depth - 1) or i for i in f.__code__.co_consts),
                    co_names=tuple(
                        [_ := "_wrap_" + i, f.__globals__.__setitem__(_, o)][0] if o else i for i in f.__code__.co_names
                        for o in [wrap(f.__globals__.get(i, getattr(builtins, i, None)), g, depth - 1)]),
                ),
                f.__globals__,
                f.__name__,
                f.__defaults__,
                tuple(wrap(i, g, depth - 1) or i for i in f.__closure__ or ()),
            )
        return lambda *_, **__: g(f, *_, **__) or f(*_, **__)
