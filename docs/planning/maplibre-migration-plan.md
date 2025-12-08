# Migration Plan: Leaflet to MapLibre GL JS (Cartes.app-style)

## Executive Summary

This document outlines the migration strategy for moving BahnVision from the current Leaflet-based mapping system to a modern MapLibre GL JS stack inspired by cartes.app. This migration will enable advanced features like 3D buildings, seamless vector rendering, and improved performance.

## Current State Analysis

### Current Stack
- **Frontend**: React 19 + Vite + TypeScript
- **Mapping**: Leaflet 1.9.4 + React-Leaflet 5.0.0
- **Heat Visualization**: leaflet.heat plugin
- **Base Maps**: Raster tiles (CartoDB, OSM, ÖPNVKarte)
- **Overlays**: OpenRailwayMap raster tiles
- **Markers**: Standard Leaflet markers with custom icons

### Current Limitations
- Raster tiles only (no vector rendering)
- Limited 3D capabilities
- Slower zoom/pan performance
- No indoor mapping support
- Limited styling flexibility
- No seamless transitions between zoom levels

## Target Stack (Cartes.app-inspired)

### Core Technologies
- **MapLibre GL JS 5.6.0** - Primary mapping engine
- **MapLibre GL IndoorEqual 1.3.0** - Indoor mapping
- **@watergis/maplibre-gl-terradraw 1.3.11** - Drawing/annotation
- **PMTiles** - Vector tile format
- **MapTiler** - Vector tile provider
- **Turf.js** - Geospatial analysis

### Advanced Features
- Vector tiles with smooth rendering
- 3D building extrusions
- Custom styling and themes
- Indoor mapping capabilities
- Drawing and annotation tools
- Performance optimizations

## Migration Strategy

### Phase 1: Foundation & Setup (Week 1-2)

#### 1.1 Dependency Installation
```bash
# Remove Leaflet dependencies
npm uninstall leaflet react-leaflet leaflet.heat leaflet.markercluster @types/leaflet @types/leaflet.markercluster

# Install MapLibre dependencies
npm install maplibre-gl@5.6.0 maplibre-gl-indoorequal@1.3.0 @watergis/maplibre-gl-terradraw@1.3.11
npm install @turf/bbox @turf/bbox-polygon @turf/bearing @turf/bezier-spline @turf/boolean-contains @turf/distance @turf/length @turf/turf
npm install pmtiles

# Install types
npm install --save-dev @types/maplibre-gl
```

#### 1.2 CSS Integration
- Replace Leaflet CSS with MapLibre GL CSS
- Update Tailwind configuration for MapLibre containers
- Add MapLibre-specific styling

#### 1.3 Basic Map Component
Create new `MapLibreMap` component to replace `CancellationHeatmap`:
```typescript
// src/components/map/MapLibreMap.tsx
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
```

### Phase 2: Core Functionality Migration (Week 3-4)

#### 2.1 Base Map Implementation
- Replace raster tile layers with MapTiler vector tiles
- Implement multiple base map styles (light, dark, satellite)
- Add layer control for style switching

#### 2.2 Markers & Interactions
- Convert Leaflet markers to MapLibre markers
- Implement popup functionality
- Add station selection interactions
- Maintain existing zoom tracking

#### 2.3 Heatmap Visualization
- Replace leaflet.heat with MapLibre's native heatmap support
- Implement dynamic intensity based on zoom level
- Maintain existing color gradients and styling

### Phase 3: Advanced Features (Week 5-6)

#### 3.1 3D Buildings
- Add 3D building extrusions for Munich area
- Implement building height data integration
- Add lighting and shadows

#### 3.2 Railway Infrastructure
- Convert OpenRailwayMap raster overlay to vector data
- Implement custom styling for railway lines
- Add animated train movements (future enhancement)

#### 3.3 Performance Optimizations
- Implement PMTiles for efficient tile loading
- Add data caching strategies
- Optimize rendering for large datasets

### Phase 4: Enhanced Features (Week 7-8)

#### 4.1 Indoor Mapping
- Integrate IndoorEqual for station interiors
- Add floor selection controls
- Implement indoor navigation

#### 4.2 Drawing & Annotation
- Add drawing tools for custom regions
- Implement measurement tools
- Add export functionality

#### 4.3 Advanced Styling
- Implement custom map styles
- Add theme switching (light/dark)
- Create transport-specific styling

## Implementation Details

### Component Migration Path

#### Current: CancellationHeatmap.tsx (426 lines)
→ New: MapLibreHeatmap.tsx

#### Key Changes:
1. **Map Initialization**
```typescript
// Old (Leaflet)
<MapContainer center={MUNICH_CENTER} zoom={DEFAULT_ZOOM}>

// New (MapLibre)
const map = new maplibregl.Map({
  container: mapContainer.current,
  style: 'https://api.maptiler.com/maps/streets-v2/style.json?key=YOUR_KEY',
  center: MUNICH_CENTER,
  zoom: DEFAULT_ZOOM,
})
```

2. **Heat Layer Implementation**
```typescript
// Old (leaflet.heat)
L.heatLayer(processedData, options).addTo(map)

// New (MapLibre)
map.addLayer({
  id: 'heatmap',
  type: 'heatmap',
  source: 'heatmap-data',
  paint: {
    'heatmap-weight': ['get', 'intensity'],
    'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
    'heatmap-color': [
      'interpolate',
      ['linear'],
      ['heatmap-density'],
      0, 'rgba(0, 255, 0, 0)',
      0.2, 'rgba(0, 255, 0, 0.5)',
      0.4, 'yellow',
      0.6, 'orange',
      0.8, 'red',
      1, 'darkred'
    ]
  }
})
```

3. **Marker Implementation**
```typescript
// Old (Leaflet)
<Marker position={[lat, lng]} icon={customIcon}>

// New (MapLibre)
new maplibregl.Marker({color: markerColor})
  .setLngLat([lng, lat])
  .addTo(map)
```

### Data Structure Changes

#### Current: HeatmapDataPoint
```typescript
interface HeatmapDataPoint {
  station_id: string
  station_name: string
  latitude: number
  longitude: number
  cancellation_rate: number
  total_departures: number
  cancelled_count: number
  by_transport: Record<string, TransportStats>
}
```

#### Enhanced: GeoJSON-based Structure
```typescript
interface HeatmapFeature {
  type: 'Feature'
  geometry: {
    type: 'Point'
    coordinates: [number, number] // [lng, lat]
  }
  properties: HeatmapDataPoint
}

interface HeatmapSource {
  type: 'geojson'
  data: {
    type: 'FeatureCollection'
    features: HeatmapFeature[]
  }
}
```

## Configuration & Setup

### Environment Variables
```bash
# .env.local
NEXT_PUBLIC_MAPTILER_API_KEY=your_maptiler_key
NEXT_PUBLIC_INDOOREQUAL_API_KEY=your_indoorequal_key
NEXT_PUBLIC_MAPTILER_STYLE_URL=https://api.maptiler.com/maps/streets-v2/style.json
```

### MapTiler Setup
1. Sign up for free MapTiler account
2. Generate API key
3. Configure vector tile styles
4. Set up usage monitoring

### PMTiles Integration (Optional)
```typescript
import { PMTiles } from 'pmtiles'

const pmtiles = new PMTiles('https://example.com/munich.pmtiles')
map.addSource('munich-data', {
  type: 'vector',
  url: 'pmtiles://' + pmtiles.source.getKey()
})
```

## Testing Strategy

### Unit Tests
- MapLibre component rendering
- Layer management
- Marker interactions
- Heatmap data processing

### Integration Tests
- Map loading and initialization
- API integration with MapTiler
- Performance benchmarks
- Memory usage monitoring

### E2E Tests
- User interaction flows
- Zoom/pan performance
- Heatmap visualization accuracy
- Cross-browser compatibility

## Performance Considerations

### Expected Improvements
- **Rendering Speed**: 3-5x faster zoom/pan operations
- **Memory Usage**: 40-60% reduction with vector tiles
- **Data Transfer**: 50-70% reduction with PMTiles
- **Mobile Performance**: Significantly improved touch interactions

### Monitoring Metrics
- Map initialization time
- Tile loading speed
- Frame rate during interactions
- Memory consumption patterns

## Risk Assessment & Mitigation

### Technical Risks
1. **API Key Management**
   - Risk: Exposed API keys in client code
   - Mitigation: Environment variables + rate limiting

2. **Browser Compatibility**
   - Risk: WebGL requirements
   - Mitigation: Fallback to raster tiles for older browsers

3. **Performance Regression**
   - Risk: Complex 3D rendering impacting performance
   - Mitigation: Progressive enhancement + performance budgets

### Business Risks
1. **Development Timeline**
   - Risk: Underestimated complexity
   - Mitigation: Phased rollout + parallel development

2. **User Experience**
   - Risk: Breaking existing functionality
   - Mitigation: Comprehensive testing + feature flags

## Rollout Plan

### Phase 1: Internal Testing (Week 1-2)
- Development environment setup
- Basic functionality verification
- Performance benchmarking

### Phase 2: Beta Release (Week 3-4)
- Feature flag for new map
- Limited user testing
- Feedback collection

### Phase 3: Full Migration (Week 5-6)
- Gradual rollout to all users
- Performance monitoring
- Issue resolution

### Phase 4: Advanced Features (Week 7-8)
- 3D buildings release
- Indoor mapping rollout
- Drawing tools launch

## Success Metrics

### Technical Metrics
- Map load time < 2 seconds
- Zoom/pan operations at 60fps
- Memory usage < 100MB
- Zero critical bugs in production

### User Metrics
- User engagement with new features
- Performance satisfaction scores
- Support ticket reduction
- Feature adoption rates

## Future Enhancements

### Short-term (3-6 months)
- Real-time train positioning
- Advanced routing capabilities
- Offline map support
- Custom map styles

### Long-term (6-12 months)
- AR integration
- Machine learning predictions
- Multi-city expansion
- API monetization

## Resources & References

### Documentation
- [MapLibre GL JS Documentation](https://maplibre.org/maplibre-gl-js/docs/)
- [MapTiler API Documentation](https://www.maptiler.com/documentation/)
- [PMTiles Specification](https://protomaps.com/docs/pmtiles)
- [Cartes.app Source Code](https://github.com/cartesapp/cartes)

### Community
- MapLibre Discord Community
- OpenStreetMap Forum
- Cartes.app Matrix Channel

### Tools & Utilities
- MapLibre GL Inspector (browser extension)
- TileServer GL (for self-hosting)
- QGIS (for data preparation)
- Tippecanoe (for tile generation)

---

**Migration Owner**: Lead Frontend Developer  
**Review Date**: Monthly during migration period  
**Last Updated**: 2025-12-04  
**Version**: 1.0