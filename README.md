# greenlet_fiber: fiber with greenlet

### Basic usage

```python
from greenlet_fiber import fiber, schedule

# register fibers. They won't be actually ran unless scheduled
fiber(print, 'hello world')
fiber(print, 'hello', 'world', 'again', sep='! ', end='!\n')

# schedule fibers
# will run all schedulable fibers until none left, then return back to main
schedule()
```

### Cooperative scheduling

* do note that `schedule` will refuse to switch if current time slice (default 0.1s) didn't run out.
  Use `setslice(seconds)` or `schedule(force=True)` if not desired

```python
from greenlet_fiber import fiber, schedule
from time import sleep


def nice_function(name):
    for i in range(10):
        print(name, i)
        sleep(.1)
        # give other fibers chance to run
        # without this, fiber can't be rescheduled before finish
        schedule()


fiber(nice_function, 'a')
fiber(nice_function, 'b')

schedule()
```

### Preemptive scheduling by signal

* only works on main thread due to python signal handling
* occupies SIGALARM (fine for most cases)
* can't interrupt during C function (I believe)

```python
from greenlet_fiber import fiber, schedule, setpreemptive
from time import sleep


def bad_function(name):
    for i in range(10):
        print(name, i)
        sleep(.1)
        # schedule()


fiber(bad_function, 'a')
fiber(bad_function, 'b')

# will force switching every 0.1 seconds
# to disable, setpreemptive(0)
setpreemptive(0.1)
schedule()
```

### Preemptive scheduling by "wrap"

* this is aggressive. Since it wraps every callable (including class), so doing e.g. MyClass.MY_CONST will probably
  error

```python
from greenlet_fiber import schedule, wrap
from time import sleep


def bad_function(name):
    for i in range(10):
        print(name, i)
        sleep(.1)
        # schedule()


# will wrap function and traverse EVERY callable inside (infectious upon depth), to call `schedule` ahead
nice_function = wrap(bad_function, schedule, depth=1)
```

which is essentially

```python
from greenlet_fiber import schedule
from time import sleep


def _wrap_range(*_, **__):
    schedule()
    return range(*_, **__)


def _wrap_print(*_, **__):
    schedule()
    return print(*_, **__)


def _wrap_sleep(*_, **__):
    schedule()
    return sleep(*_, **__)


def nice_function(name):
    schedule()
    for i in _wrap_range(10):
        _wrap_print(name, i)
        _wrap_sleep(.1)
```

### Preemptive scheduling by "inject"

* this is even more aggressive. It creates a new function by rewriting target's python bytecode, to inject new
  instructions of calling `schedule` from time to time
* somewhat tested, will probably crash the whole interpreter if bug hidden somewhere

```python
from greenlet_fiber import schedule, inject
from time import sleep


def bad_function(name):
    for i in range(10):
        print(name, i)
        sleep(.1)
        # schedule()


# will inject calling `schedule` every 10 instructions
#
# note that python bytecode doesn't fully correspond to code, so it can inject
# to a lot of places where no code can be possibly written in real python
# this is somewhat tested to be fine, but need more rigorous testing
nice_function = inject(bad_function, schedule, per=10)
```

old byte code

```
  2           0 LOAD_GLOBAL              0 (range)
              2 LOAD_CONST               1 (10)
              4 CALL_FUNCTION            1
              6 GET_ITER
        >>    8 FOR_ITER                11 (to 32)
             10 STORE_FAST               1 (i)

  3          12 LOAD_GLOBAL              1 (print)
             14 LOAD_FAST                0 (name)
             16 LOAD_FAST                1 (i)
             18 CALL_FUNCTION            2
             20 POP_TOP

  4          22 LOAD_GLOBAL              2 (sleep)
             24 LOAD_CONST               2 (0.1)
             26 CALL_FUNCTION            1
             28 POP_TOP
             30 JUMP_ABSOLUTE            4 (to 8)

  2     >>   32 LOAD_CONST               0 (None)
             34 RETURN_VALUE

```

new byte code

```
  2           0 LOAD_GLOBAL              0 (range)
              2 LOAD_CONST               1 (10)
              4 CALL_FUNCTION            1
              6 GET_ITER
        >>    8 FOR_ITER                14 (to 38)     # fixed
             10 STORE_FAST               1 (i)

  3          12 LOAD_GLOBAL              1 (print)
             14 LOAD_FAST                0 (name)
             16 LOAD_FAST                1 (i)
             18 CALL_FUNCTION            2
             20 LOAD_GLOBAL              3 (schedule)  # new

  4          22 CALL_FUNCTION            0             # new
             24 POP_TOP                                # new
             26 POP_TOP
             28 LOAD_GLOBAL              2 (sleep)
             30 LOAD_CONST               2 (0.1)

  2          32 CALL_FUNCTION            1
             34 POP_TOP
             36 JUMP_ABSOLUTE            4 (to 8)
        >>   38 LOAD_CONST               0 (None)
             40 RETURN_VALUE
```

as can be seen, calling `schedule()` (20 to 24) is injected before the cleanup step (26) of calling `print(name, i)` (12
to 26), which is not possible in real python, but it does work fine. for loop (8) is automatically fixed since it has
jump-like argument