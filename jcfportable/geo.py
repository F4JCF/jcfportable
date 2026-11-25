"""Locators Maidenhead, distances et caps."""
import math


def grid_to_latlon(grid):
    """Retourne le centre du carré (lat, lon) ou None."""
    if not grid:
        return None
    g = grid.strip()
    if len(g) < 4:
        return None
    try:
        g = g[:2].upper() + g[2:4] + g[4:6].lower() + g[6:8]
        lon = (ord(g[0]) - 65) * 20 - 180
        lat = (ord(g[1]) - 65) * 10 - 90
        lon += int(g[2]) * 2
        lat += int(g[3])
        if len(g) >= 6:
            lon += (ord(g[4]) - 97) * (2 / 24)
            lat += (ord(g[5]) - 97) * (1 / 24)
            if len(g) >= 8:
                lon += int(g[6]) * (2 / 240)
                lat += int(g[7]) * (1 / 240)
                lon += 1 / 240
                lat += 0.5 / 240
            else:
                lon += 1 / 24
                lat += 0.5 / 24
        else:
            lon += 1
            lat += 0.5
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return lat, lon
    except (ValueError, IndexError):
        return None


def latlon_to_grid(lat, lon, precision=6):
    lon += 180
    lat += 90
    a = chr(65 + int(lon // 20)) + chr(65 + int(lat // 10))
    lon %= 20
    lat %= 10
    a += str(int(lon // 2)) + str(int(lat // 1))
    if precision >= 6:
        lon %= 2
        lat %= 1
        a += chr(97 + int(lon * 12)) + chr(97 + int(lat * 24))
    return a


def distance_bearing(lat1, lon1, lat2, lon2):
    """Distance en km et cap en degrés (orthodromie)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    dp = p2 - p1
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * r * math.asin(min(1, math.sqrt(a)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    brg = (math.degrees(math.atan2(y, x)) + 360) % 360
    return d, brg


def grid_distance(g1, g2):
    a, b = grid_to_latlon(g1), grid_to_latlon(g2)
    if not a or not b:
        return None
    return distance_bearing(a[0], a[1], b[0], b[1])
