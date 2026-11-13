import random
import math

def lognormal_seconds(median_sec, sigma=0.8):
    return random.lognormvariate(math.log(median_sec), sigma)

def poisson_events(rate_per_min, duration_min):
    n = max(1, int(rate_per_min * duration_min * 1.5))
    events = []
    t = 0.0
    for _ in range(n):
        t += random.expovariate(rate_per_min / 60.0)
        if t > duration_min * 60:
            break
        events.append(t)
    return events
