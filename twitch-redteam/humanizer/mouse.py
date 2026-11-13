import asyncio
import random
import math

def _cubic_bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )

def _lognormal_delay(median_ms=10.0, sigma=0.4):
    return random.lognormvariate(math.log(median_ms), sigma) / 1000.0

async def human_move(page, target_x, target_y, steps=None, jitter=1.5):
    current = await page.evaluate("() => ({x: window.__mouseX || 0, y: window.__mouseY || 0})")
    p0 = (current["x"], current["y"])
    p3 = (target_x, target_y)
    dist = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
    p1 = (p0[0] + (p3[0] - p0[0]) * 0.3 + random.uniform(-dist * 0.2, dist * 0.2),
          p0[1] + (p3[1] - p0[1]) * 0.3 + random.uniform(-dist * 0.2, dist * 0.2))
    p2 = (p0[0] + (p3[0] - p0[0]) * 0.7 + random.uniform(-dist * 0.2, dist * 0.2),
          p0[1] + (p3[1] - p0[1]) * 0.7 + random.uniform(-dist * 0.2, dist * 0.2))
    if steps is None:
        steps = max(8, int(dist / 30) + random.randint(-3, 3))
    for i in range(steps + 1):
        t = i / steps
        x, y = _cubic_bezier(p0, p1, p2, p3, t)
        x += random.gauss(0, jitter)
        y += random.gauss(0, jitter)
        await page.mouse.move(x, y)
        await page.evaluate(f"window.__mouseX = {x}; window.__mouseY = {y};")
        await asyncio.sleep(_lognormal_delay(median_ms=8, sigma=0.5))
    await asyncio.sleep(_lognormal_delay(median_ms=40, sigma=0.3))
    await page.mouse.move(target_x, target_y)

async def human_click(page, x, y):
    await human_move(page, x, y)
    await asyncio.sleep(_lognormal_delay(median_ms=60, sigma=0.3))
    await page.mouse.down()
    await asyncio.sleep(_lognormal_delay(median_ms=80, sigma=0.4))
    await page.mouse.up()
