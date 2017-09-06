import os, sys, math

EPSILON = 1e-12

def scale_var(var, min_range, max_range):
    return (var - min_range) / max((max_range - min_range), EPSILON)

def unscale_var(var, min_range, max_range):
    return (var * (max_range - min_range)) + min_range
