import numpy as np
from gplearn.functions import make_function


# Create a safe exp function which does not cause problems
def exp(x):
    with np.errstate(all="ignore"):
        max_value = np.full(shape=x.shape, fill_value=100000)
        return np.minimum(np.exp(x), max_value)


def get_function_set():
    exp_func = make_function(function=exp, arity=1, name="exp")

    function_set = [
        "add",
        "sub",
        "mul",
        "div",
        "sqrt",
        "log",
        "sin",
        "cos",
        "abs",
        exp_func
    ]

    return function_set
