from random import choice
from signal import ITIMER_REAL, SIGALRM, setitimer, signal
from threading import current_thread
from time import time

from greenlet import greenlet

FIBERS = {}
SLICE = 0.1
LOG = True


def gets():
    # get (all schedulable fibers, last schedule time)
    return FIBERS.setdefault(current_thread(), ([], 0))


def fiber(f, *_, **__):
    # create schedulable fiber `f(*_, **__)`
    @greenlet
    def fiber():
        try:
            f(*_, **__)
        finally:
            schedule(finish=greenlet.getcurrent())

    gets()[0].append(fiber)
    return fiber


def schedule(*_, force=False, finish=None):
    # schedule a random fiber (switch out from current).
    # finish `finish` (if given) (wake up dependencies if any)
    # otherwise won't actually switch if not `force` and time slice didn't run out
    fibers, last = gets()
    if finish:
        fibers.remove(finish)
        for i in getattr(finish, "rdep", ()):
            i.dep -= 1
            if not i.dep:
                fibers.append(i)
    elif not force and time() - last < SLICE:
        return
    if fibers:
        cur = choice(fibers)
        if cur != greenlet.getcurrent():
            if LOG:
                print(end=f"[schedule {current_thread().name}] {id(greenlet.getcurrent()):x} -> {id(cur):x}\n")
            FIBERS[current_thread()] = fibers, time()
            cur.switch()


def wait(*fibers, waiter=None):
    # make `waiter` (default current) wait for all `fibers` to finish
    waiter = waiter or greenlet.getcurrent()
    waiter.dep = getattr(waiter, "dep", 0) + len(fibers)
    for i in fibers:
        i.rdep = getattr(i, "rdep", [])
        i.rdep.append(waiter)
    try:
        gets()[0].remove(waiter)
    except ValueError:
        pass
    if waiter == greenlet.getcurrent():
        schedule()


def waitmap(f, *_, **__):
    # make `waiter` (default current) wait for all `_ => fiber(f(*_))`
    wait(*(fiber(f, *_) for _ in _), **__)


def setpreemptive(t=1):
    # enable preemptive (non-cooperative) scheduling with time slice `t`
    # this occupies `SIGALRM` and only works on MainThread because signal will always be handled by MainThread in python
    # it can't interrupt during C function (I believe)
    # set to `0` to disable (time slice unchanged)
    if t:
        setslice(t)
    signal(SIGALRM, schedule)
    setitimer(ITIMER_REAL, t, t)


def setslice(t=1):
    # set time slice `t`
    global SLICE
    SLICE = t


def setlog(b=True):
    # set log stataus
    global LOG
    LOG = b
