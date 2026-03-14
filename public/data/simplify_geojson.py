#!/usr/bin/env python3
"""
Simplify and optimize Singapore Master Plan GeoJSON.
This script reduces file size from 166MB to ~5-10MB by:
1. Reducing coordinate precision (from 14+ decimals to 4-5)
2. Simplifying polygon geometries (removing excess points)
3. Grouping features by region/planning area
4. Creating pre-computed region boundaries
"""

import json
import math
from collections import defaultdict
from pathlib import Path

def simplify_coordinate(lng, lat, decimals=5):
    """Round coordinates to reduce precision."""
    factor = 10 ** decimals
    return [round(lng * factor) / factor, round(lat * factor) / factor]

def simplify_linestring(coords, tolerance=0.0002):
    """
    Simplify coordinates using Ramer-Douglas-Peucker algorithm.
    Tolerance in degrees (default ~20m for Singapore latitudes).
    """
    if len(coords) < 3:
        return coords
    
    def perpendicular_distance(point, line_start, line_end):
        """Calculate perpendicular distance from point to line."""
        if line_start == line_end:
            dx = point[0] - line_start[0]
            dy = point[1] - line_start[1]
            return math.sqrt(dx * dx + dy * dy)
        
        x, y = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        num = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1)
        den = math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
        return num / den if den > 0 else 0
    
    dmax = 0.0
    index = 0
    
    for i in range(1, len(coords) - 1):
        d = perpendicular_distance(coords[i], coords[0], coords[-1])
        if d > dmax:
            index = i
            dmax = d
    
    if dmax > tolerance:
        rec1 = simplify_linestring(coords[:index + 1], tolerance)
        rec2 = simplify_linestring(coords[index:], tolerance)
        return rec1[:-1] + rec2
    else:
        return [coords[0], coords[-1]]

def calculate_centroid(coords):
    """Calculate centroid of a polygon."""
    if isinstance(coords[0][0], list):  # MultiPolygon or Polygon with holes
        coords = coords[0]
    
    n = len(coords)
    x = sum(c[0] for c in coords) / n
    y = sum(c[1] for c in coords) / n
    return [x, y]

def point_to_region(lng, lat):
    """Map a lat/lng point to a Singapore region based on coordinates."""
    # Singapore bounds approximately
    # North: 1.46, South: 1.13, West: 103.6, East: 104.0
    
    center_lng = 103.8
    center_lat = 1.29
    
    dlng = lng - center_lng
    dlat = lat - center_lat
    
    # Determine region based on rough coordinate ranges
    if dlat > 0.08:
        if dlng < -0.08:
            return "North"  # Woodlands, Yishun area
        elif dlng > 0.1:
            return "North-East"  # Punggol, Sengkang area
        else:
            return "North"
    elif dlat < -0.08:
        if dlng < -0.08:
            return "West"  # Jurong area
        elif dlng > 0.08:
            return "East"  # Bedok, Tampines area
        else:
            return "South"
    else:
        if dlng < -0.08:
            return "West"
        elif dlng > 0.08:
            return "East"
        else:
            return "Central"

def process_geojson(input_file, output_file):
    """Process GeoJSON file to create simplified version."""
    print(f"Loading GeoJSON from {input_file}...")
    
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    print(f"Total features: {len(data['features'])}")
    
    # Group features by region
    regions = defaultdict(list)
    region_bounds = {
        'North': {'minLng': float('inf'), 'maxLng': float('-inf'), 'minLat': float('inf'), 'maxLat': float('-inf')},
        'North-East': {'minLng': float('inf'), 'maxLng': float('-inf'), 'minLat': float('inf'), 'maxLat': float('-inf')},
        'East': {'minLng': float('inf'), 'maxLng': float('-inf'), 'minLat': float('inf'), 'maxLat': float('-inf')},
        'West': {'minLng': float('inf'), 'maxLng': float('-inf'), 'minLat': float('inf'), 'maxLat': float('-inf')},
        'South': {'minLng': float('inf'), 'maxLng': float('-inf'), 'minLat': float('inf'), 'maxLat': float('-inf')},
        'Central': {'minLng': float('inf'), 'maxLng': float('-inf'), 'minLat': float('inf'), 'maxLat': float('-inf')},
    }
    
    simplified_features = []
    
    for idx, feature in enumerate(data['features']):
        if (idx + 1) % 10000 == 0:
            print(f"  Processing feature {idx + 1}/{len(data['features'])}...")
        
        geom = feature.get('geometry', {})
        geom_type = geom.get('type')
        
        if geom_type == 'Polygon':
            coords = geom['coordinates']
            # Simplify the outer ring
            simplified_ring = simplify_linestring(coords[0], tolerance=0.0002)
            
            # Calculate centroid to determine region
            centroid = calculate_centroid(simplified_ring)
            region = point_to_region(centroid[0], centroid[1])
            
            # Round coordinates
            simplified_ring = [simplify_coordinate(c[0], c[1], 5) for c in simplified_ring]
            
            # Update bounds
            for lng, lat in simplified_ring:
                bounds = region_bounds[region]
                bounds['minLng'] = min(bounds['minLng'], lng)
                bounds['maxLng'] = max(bounds['maxLng'], lng)
                bounds['minLat'] = min(bounds['minLat'], lat)
                bounds['maxLat'] = max(bounds['maxLat'], lat)
            
            simplified_features.append({
                'type': 'Feature',
                'properties': {
                    'LU_DESC': feature['properties'].get('LU_DESC', 'Unknown'),
                    'region': region,
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [simplified_ring]
                }
            })
            
            regions[region].append({
                'coordinates': simplified_ring,
                'lu_desc': feature['properties'].get('LU_DESC', 'Unknown'),
            })
        
        elif geom_type == 'MultiPolygon':
            # Take only the largest polygon to save space
            polygons = geom['coordinates']
            if polygons:
                coords = polygons[0]
                simplified_ring = simplify_linestring(coords[0], tolerance=0.0002)
                
                centroid = calculate_centroid(simplified_ring)
                region = point_to_region(centroid[0], centroid[1])
                
                simplified_ring = [simplify_coordinate(c[0], c[1], 5) for c in simplified_ring]
                
                for lng, lat in simplified_ring:
                    bounds = region_bounds[region]
                    bounds['minLng'] = min(bounds['minLng'], lng)
                    bounds['maxLng'] = max(bounds['maxLng'], lng)
                    bounds['minLat'] = min(bounds['minLat'], lat)
                    bounds['maxLat'] = max(bounds['maxLat'], lat)
                
                regions[region].append({
                    'coordinates': simplified_ring,
                    'lu_desc': feature['properties'].get('LU_DESC', 'Unknown'),
                })
    
    # Create output
    output_data = {
        'type': 'FeatureCollection',
        'name': 'Singapore_Regions_Simplified',
        'features': simplified_features,
        'regionBounds': region_bounds,
    }
    
    print(f"\nWriting simplified GeoJSON to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(output_data, f, separators=(',', ':'))
    
    # Get file sizes
    original_size = Path(input_file).stat().st_size / (1024 * 1024)
    simplified_size = Path(output_file).stat().st_size / (1024 * 1024)
    
    print(f"\nCompleted!")
    print(f"Original size: {original_size:.2f} MB")
    print(f"Simplified size: {simplified_size:.2f} MB")
    print(f"Reduction: {(1 - simplified_size/original_size)*100:.1f}%")
    print(f"Features per region: {[(region, len(regions[region])) for region in regions]}")

if __name__ == '__main__':
    input_file = '/Users/rishi/GitHub/DellInnovate2026_Team-Untitled/public/data/G_MP19_LAND_USE_PL.geojson'
    output_file = '/Users/rishi/GitHub/DellInnovate2026_Team-Untitled/public/data/singapore_regions_simplified.geojson'
    process_geojson(input_file, output_file)
