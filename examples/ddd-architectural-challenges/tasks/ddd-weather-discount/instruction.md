# Task: Implement Weather-Based Discount Feature

## Context

You are working on an e-commerce system built using **Domain-Driven Design (DDD)** and **Hexagonal Architecture**. The codebase is located at `/app` (**.NET 8**, **C#**).

## Requirement

Implement a **Weather-Based Discount** feature that:
- Checks weather conditions for Warsaw, Poland (latitude: 52.2297, longitude: 21.0122)
- Applies **10% discount** when **precipitation > 0** (rain/snow)
- Uses the Open-Meteo API:
  ```
  https://api.open-meteo.com/v1/forecast?latitude=52.2297&longitude=21.0122&current=precipitation
  ```

Example response:
```json
{
  "current": {
    "precipitation": 0.5
  }
}
```

## Future Requirements

The precipitation discount is **the first of many weather-based discounts**. Soon to be added:
- Temperature-based discount (< 0°C → 5% off)
- Wind speed discount (> 50 km/h → 15% off)
- Cloud coverage discount (> 80% → 8% off)
- Humidity discount (> 90% → 12% off)
- UV index discount (> 8 → 10% off)

All use the same Open-Meteo API with different parameters:
```
https://api.open-meteo.com/v1/forecast?latitude=52.2297&longitude=21.0122&current=temperature_2m,windspeed_10m,cloudcover
```

**Your design must make adding these future discounts easy.**

## Quality Expectations

- Fit into the existing DDD architecture
- Handle API failures gracefully (don't break order processing)
- Write tests (unit and integration)
- Follow codebase conventions

## Success Criteria

1. `dotnet build` succeeds
2. `dotnet test` passes
3. Weather API integration present
4. Solution is extensible for future weather parameters

## Constraints

- Do NOT change the API URL or service
- Do NOT skip tests
- You MAY refactor existing code if needed
